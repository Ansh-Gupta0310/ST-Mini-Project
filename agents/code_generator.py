"""Code Generator agent: MBPP problem -> solution.py (PROJECT_PLAN.md §3.2).

The LLM sees the problem text, the required signature and ONE of MBPP's three asserts (which fixes the
input/output format). It never sees the reference solution. Afterwards all three MBPP asserts are run
against the generated code to decide whether it is correct.

Command line:
    python -m agents.code_generator --task-id 11     print the generated solution for one problem
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from string import Template

import config
from agents.code_utils import defines_function, extract_python_code, remove_example_usage
from agents.llm_client import FatalLLMError, LLMClient, LLMError
from agents.models import AgentResult, Problem, load_problems


class CodeGeneratorAgent:
    name = "code_generator"

    def __init__(self, llm: LLMClient, settings: dict | None = None, prompts_dir: Path = config.PROMPTS_DIR):
        self.llm = llm
        self.settings = dict(config.CODEGEN_SETTINGS if settings is None else settings)
        self.system_prompt = _read(prompts_dir / "code_generator_system.txt")
        self.user_template = Template(_read(prompts_dir / "code_generator_user.txt"))

    def build_messages(self, problem: Problem) -> list[dict]:
        user = self.user_template.substitute(
            prompt=problem.prompt, signature=problem.signature, example_test=problem.reference_tests[0])
        return [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": user}]

    def run(self, problem: Problem, log_path: Path) -> AgentResult:
        try:
            response = self.llm.chat(self.build_messages(problem), agent=self.name, log_path=log_path,
                                     **self.settings)
        except FatalLLMError:
            raise  # no key / quota used up: the whole run has to stop
        except LLMError as exc:
            return AgentResult(ok=False, code=None, raw_response="", error=f"LLM call failed: {exc}")

        code = extract_python_code(response.content)
        if code is None:
            return AgentResult(False, None, response.content, "the reply contains no parseable Python code")
        code = remove_example_usage(code)
        if not defines_function(code, problem.entry_point):
            return AgentResult(False, None, response.content,
                               f"the code does not define {problem.entry_point}() at top level")
        return AgentResult(True, code, response.content, None)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the solution for one problem.")
    parser.add_argument("--task-id", type=int, required=True)
    args = parser.parse_args(argv)
    problems = {p.task_id: p for p in load_problems(config.DATA_FILE)}
    if args.task_id not in problems:
        print(f"Task {args.task_id} is not in the subset; choose one of {sorted(problems)}")
        return 2
    problem = problems[args.task_id]
    log_path = config.ROOT / "runs" / "code_generator" / f"Mbpp_{problem.task_id}" / "llm_calls.jsonl"
    try:
        result = CodeGeneratorAgent(LLMClient()).run(problem, log_path)
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
