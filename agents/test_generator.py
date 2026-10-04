"""Test Generator agent: problem + generated solution -> a pytest file aimed at a coverage goal.

This is the agent that satisfies the assignment's "one requirement": the requirement is a
**user-specified coverage criterion** (statement or branch) with a target percentage, passed in from
`--criterion` and `--target` (PROJECT_PLAN.md §1.1, §3.2).

The prompt is white-box: the model sees the numbered source of solution.py, because it has to aim at
particular lines and branches. It never sees MBPP's reference solution, and it is told to take expected
values from the problem description, not from the code, so the reference stays an independent check on
the tests (§2.4). In a feedback round it also sees the tests written so far and a plain-language list of
what coverage.py reported as still uncovered.

Command line:
    python -m agents.test_generator --task-id 11 --solution results/phase1_baseline/Mbpp_11/solution.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from string import Template

import config
from agents.code_utils import check_test_file, describe_missing, extract_python_code, number_lines
from agents.llm_client import FatalLLMError, LLMClient, LLMError
from agents.models import AgentResult, ExecutionResult, Problem, load_problems


class TestGeneratorAgent:
    __test__ = False  # not a pytest test class, despite its name

    name = "test_generator"

    def __init__(self, llm: LLMClient, settings: dict | None = None, prompts_dir: Path = config.PROMPTS_DIR):
        self.llm = llm
        self.settings = dict(config.TESTGEN_SETTINGS if settings is None else settings)
        self.system_template = Template(_read(prompts_dir / "test_generator_system.txt"))
        self.user_template = Template(_read(prompts_dir / "test_generator_user.txt"))
        self.feedback_template = Template(_read(prompts_dir / "test_generator_feedback.txt"))

    def build_messages(self, problem: Problem, solution_code: str, criterion: str, target: float,
                       feedback: ExecutionResult | None = None, existing_tests: str | None = None,
                       retry_note: str | None = None) -> list[dict]:
        """The initial prompt, or the feedback prompt when a previous round's measurements are given.

        `retry_note` says what was wrong with the previous round's reply. It matters for more than
        politeness: responses are cached by the exact request, so re-sending an unchanged prompt would
        return the same unusable reply instead of a new attempt.
        """
        common = {
            "prompt": problem.prompt,
            "numbered_code": number_lines(solution_code),
            "criterion_goal": config.criterion_goal(criterion, target),
            "entry_point": problem.entry_point,
        }
        if feedback is None:
            user = self.user_template.substitute(common, example_test=problem.reference_tests[0])
        else:
            user = self.feedback_template.substitute(
                common,
                existing_tests=(existing_tests or "").rstrip(),
                statement_coverage=f"{feedback.statement_coverage:g}",
                branch_coverage=f"{feedback.branch_coverage:g}",
                missing_description=describe_missing(solution_code, feedback.missing_lines,
                                                    feedback.missing_branches,
                                                    feedback.missing_edge_pairs),
            )
        if retry_note:
            user = f"{user}\n\n{retry_note}"
        system = self.system_template.substitute(entry_point=problem.entry_point)
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def run(self, problem: Problem, solution_code: str, criterion: str, target: float, log_path: Path,
            feedback: ExecutionResult | None = None, existing_tests: str | None = None,
            retry_note: str | None = None) -> AgentResult:
        """Ask for a pytest file and return it only if it parses and follows the §3.6 rules."""
        messages = self.build_messages(problem, solution_code, criterion, target, feedback, existing_tests,
                                       retry_note)
        try:
            response = self.llm.chat(messages, agent=self.name, log_path=log_path, **self.settings)
        except FatalLLMError:
            raise  # no key / quota used up: the whole run has to stop
        except LLMError as exc:
            return AgentResult(ok=False, code=None, raw_response="", error=f"LLM call failed: {exc}")

        code = extract_python_code(response.content)
        if code is None:
            return AgentResult(False, None, response.content, "the reply contains no parseable Python code")
        rule_broken = check_test_file(code, problem.entry_point)
        if rule_broken is not None:
            return AgentResult(False, None, response.content, rule_broken)
        return AgentResult(True, code, response.content, None)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a pytest file for one problem (round 1 only).")
    parser.add_argument("--task-id", type=int, required=True)
    parser.add_argument("--solution", type=Path, required=True,
                        help="the generated solution, e.g. results/phase1_baseline/Mbpp_11/solution.py")
    parser.add_argument("--criterion", choices=config.CRITERIA, default=config.DEFAULT_CRITERION)
    parser.add_argument("--target", type=float, default=config.DEFAULT_TARGET)
    args = parser.parse_args(argv)

    problems = {p.task_id: p for p in load_problems(config.DATA_FILE)}
    if args.task_id not in problems:
        print(f"Task {args.task_id} is not in the subset; choose one of {sorted(problems)}")
        return 2
    if not args.solution.exists():
        print(f"No such file: {args.solution}. Run pipeline.py --mode baseline first.")
        return 2
    problem = problems[args.task_id]
    log_path = config.ROOT / "runs" / "test_generator" / f"Mbpp_{problem.task_id}" / "llm_calls.jsonl"
    try:
        result = TestGeneratorAgent(LLMClient()).run(
            problem, args.solution.read_text(encoding="utf-8"), args.criterion, args.target, log_path)
    except FatalLLMError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    sys.stdout.reconfigure(errors="replace")  # model output may contain characters the console can't show
    if not result.ok:
        print(f"FAILED: {result.error}\n--- raw reply ---\n{result.raw_response}")
        return 1
    print(result.code, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
