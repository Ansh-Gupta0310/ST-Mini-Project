"""Pipeline orchestrator: plain Python that calls the agents in a fixed order (no agent framework).

--mode baseline (Phase 1), for each problem:
    [1] Code Generator agent -> solution.py
    [2] Test Executor agent  -> runs MBPP's 3 reference asserts against solution.py, giving
                                code_correct and the coverage that the dataset's own tests reach
--mode full (Phase 2), for each problem, adds:
    [3] Test Generator agent -> a pytest file aimed at the user-specified coverage criterion
    [4] Test Executor agent  -> runs it; if the goal is not met, the missing lines and branches go back
                                to [3] and the new tests are added to the existing ones (up to --max-rounds)
    [5] Test validation      -> re-runs the final suite against MBPP's reference solution and labels
                                every test VALID / BUG_FOUND / INVALID_TEST / MISLEADING

Usage:
    python pipeline.py --mode baseline --out results/phase1_baseline
    python pipeline.py --mode full --criterion branch --target 100 --max-rounds 3 --out results/phase2_branch100
    python pipeline.py --mode full --task-ids 11 --max-rounds 1 --out runs/smoke

Output (PROJECT_PLAN.md §3.10): <out>/config.json, summary.json, summary.md and one Mbpp_<id>/ folder
per problem with problem.json, llm_calls.jsonl, solution.py, reference/ and verdict.json; in full mode
also round_1/ … round_k/, test_solution.py, validation/ and validation.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import config
from agents.code_generator import CodeGeneratorAgent
from agents.code_utils import merge_test_files
from agents.llm_client import FatalLLMError, LLMClient
from agents.models import ExecutionResult, Problem, load_problems
from agents.test_executor import (TEST_LABELS, TestExecutorAgent, count_labels, reference_tests_to_pytest,
                                 remove_path)
from agents.test_generator import TestGeneratorAgent


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-assisted unit testing pipeline (see PROJECT_PLAN.md).")
    parser.add_argument("--mode", choices=["baseline", "full"], required=True,
                        help="baseline: code generation + MBPP's reference tests (Phase 1); full: Phase 2")
    parser.add_argument("--out", type=Path, required=True, help="output folder, e.g. results/phase1_baseline")
    parser.add_argument("--task-ids", type=int, nargs="+", help="only these MBPP task ids")
    parser.add_argument("--limit", type=int, help="only the first N problems")
    parser.add_argument("--criterion", choices=config.CRITERIA, default=config.DEFAULT_CRITERION,
                        help="coverage criterion (default: %(default)s)")
    parser.add_argument("--target", type=float, default=config.DEFAULT_TARGET,
                        help="coverage target in percent (default: %(default)s)")
    parser.add_argument("--max-rounds", type=int, default=config.DEFAULT_MAX_ROUNDS,
                        help="test-generation rounds, --mode full only (default: %(default)s)")
    args = parser.parse_args(argv)
    if not 0 < args.target <= 100:
        parser.error("--target must be greater than 0 and at most 100")
    if args.max_rounds < 1:
        parser.error("--max-rounds must be at least 1")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    return args


def select_problems(problems: list[Problem], task_ids: list[int] | None, limit: int | None) -> list[Problem]:
    if task_ids:
        by_id = {p.task_id: p for p in problems}
        unknown = [t for t in task_ids if t not in by_id]
        if unknown:
            raise SystemExit(f"Unknown task ids {unknown}; the subset has {sorted(by_id)}")
        problems = [by_id[t] for t in task_ids]
    return problems[:limit] if limit else problems


# --- one problem -------------------------------------------------------------------------

def generate_and_check(problem: Problem, problem_dir: Path, codegen: CodeGeneratorAgent,
                       executor: TestExecutorAgent, args: argparse.Namespace) -> tuple[dict, str | None]:
    """Steps [1] and [2]: write solution.py, then run MBPP's own 3 asserts against it.

    Both modes start here, so the baseline numbers always describe exactly the code that Phase 2 tests.
    Returns the verdict fields filled in so far and the generated source (None if generation failed).
    """
    remove_path(problem_dir)  # never mix files from an earlier run into this one
    problem_dir.mkdir(parents=True)
    write_json(problem_dir / "problem.json", asdict(problem))
    verdict = {"task_id": problem.task_id, "entry_point": problem.entry_point}

    generated = codegen.run(problem, problem_dir / "llm_calls.jsonl")             # [1]
    verdict["codegen_ok"] = generated.ok
    if not generated.ok:
        (problem_dir / "codegen_reply.txt").write_text(generated.raw_response, encoding="utf-8")
        verdict.update(status="CODEGEN_FAILED", error=generated.error, code_correct=False, baseline=None)
        return verdict, None

    (problem_dir / "solution.py").write_text(generated.code, encoding="utf-8")
    reference = executor.run(generated.code, reference_tests_to_pytest(problem),  # [2]
                             problem_dir / "reference", args.criterion, args.target)
    verdict.update(status="COMPLETED", code_correct=passes_all(reference, problem),
                   baseline=execution_summary(reference))
    return verdict, generated.code


def run_baseline_problem(problem: Problem, problem_dir: Path, codegen: CodeGeneratorAgent,
                         executor: TestExecutorAgent, args: argparse.Namespace) -> dict:
    verdict, _ = generate_and_check(problem, problem_dir, codegen, executor, args)
    verdict.update(llm_usage(problem_dir / "llm_calls.jsonl"))
    write_json(problem_dir / "verdict.json", verdict)
    return verdict


def run_full_problem(problem: Problem, problem_dir: Path, codegen: CodeGeneratorAgent,
                     testgen: TestGeneratorAgent, executor: TestExecutorAgent,
                     args: argparse.Namespace) -> dict:
    """Steps [1]–[5]: baseline, then the coverage feedback loop and validation (PROJECT_PLAN.md §3.1)."""
    verdict, solution_code = generate_and_check(problem, problem_dir, codegen, executor, args)
    verdict.update(criterion=args.criterion, target=args.target, max_rounds=args.max_rounds,
                   rounds_used=0, final_round=None, round_1=None, final=None, test_labels=None,
                   testgen_errors=[])
    if solution_code is not None:
        verdict.update(generate_tests(problem, problem_dir, solution_code, testgen, executor, args))
    verdict.update(llm_usage(problem_dir / "llm_calls.jsonl"))
    write_json(problem_dir / "verdict.json", verdict)
    return verdict


def generate_tests(problem: Problem, problem_dir: Path, solution_code: str, testgen: TestGeneratorAgent,
                   executor: TestExecutorAgent, args: argparse.Namespace) -> dict:
    """Steps [3]–[5]: the coverage feedback loop (§3.8), then validation against MBPP's reference (§3.7).

    `tests` and `measured` always hold the best suite so far: a round that produces nothing usable (no
    code block, a rejected file, or a file pytest cannot even collect) is thrown away, and the next round
    still gets the feedback from the last suite that did run.
    """
    log_path = problem_dir / "llm_calls.jsonl"
    tests: str | None = None
    measured: ExecutionResult | None = None
    fields: dict = {"rounds_used": 0, "final_round": None, "round_1": None, "testgen_errors": []}

    for round_no in range(1, args.max_rounds + 1):
        feedback = measured if tests is not None else None                       # [3]
        generated = testgen.run(problem, solution_code, args.criterion, args.target, log_path,
                                feedback=feedback, existing_tests=tests if feedback else None,
                                retry_note=retry_note(fields["testgen_errors"], round_no))
        fields["rounds_used"] = round_no
        if not generated.ok:
            (problem_dir / f"testgen_reply_round_{round_no}.txt").write_text(generated.raw_response,
                                                                            encoding="utf-8")
            fields["testgen_errors"].append({"round": round_no, "error": generated.error})
            print(f"    round {round_no}: no usable test file ({generated.error})", flush=True)
            continue

        candidate = merge_test_files(tests, generated.code, round_no) if tests else generated.code
        result = executor.run(solution_code, candidate, problem_dir / f"round_{round_no}",  # [4]
                              args.criterion, args.target)
        if round_no == 1:
            fields["round_1"] = execution_summary(result)  # the single-shot result, kept for §3.11
        print(f"    round {round_no}: {round_line(result)}", flush=True)
        if result.status != "RAN":  # the new tests broke the file: keep the last suite that worked
            fields["testgen_errors"].append({"round": round_no, "error": f"execution {result.status}"})
            continue
        tests, measured = candidate, result
        fields["final_round"] = round_no
        if result.target_met:
            break

    if tests is None or measured is None:
        last = fields["testgen_errors"][-1]["error"] if fields["testgen_errors"] else "no test file"
        return {**fields, "status": "TESTGEN_FAILED", "error": f"no usable test suite: {last}", "final": None,
                "test_labels": None}

    (problem_dir / "test_solution.py").write_text(tests, encoding="utf-8")
    labels = executor.validate(tests, problem, problem_dir / "validation", measured.test_outcomes)  # [5]
    counts = count_labels(labels)
    write_json(problem_dir / "validation.json", {
        "labels": labels,
        "counts": counts,
        "on_generated": measured.test_outcomes,
        "on_reference": read_json(problem_dir / "validation" / "execution.json").get("test_outcomes", {}),
    })
    return {**fields, "final": execution_summary(measured), "test_labels": counts}


def passes_all(result: ExecutionResult, problem: Problem) -> bool:
    return (result.status == "RAN" and result.tests_total == len(problem.reference_tests)
            and result.tests_passed == result.tests_total)


def execution_summary(r: ExecutionResult) -> dict:
    return {"verdict": r.verdict, "status": r.status, "tests_total": r.tests_total, "tests_passed": r.tests_passed,
            "statement_coverage": r.statement_coverage, "branch_coverage": r.branch_coverage,
            "target_met": r.target_met, "num_statements": r.num_statements, "num_branches": r.num_branches,
            "missing_lines": r.missing_lines, "missing_branches": r.missing_branches}


def retry_note(errors: list[dict], round_no: int) -> str | None:
    """What to tell the Test Generator when the round before this one produced nothing usable.

    Only sent after a failed round, and only then: it also makes the request different from the one that
    failed, which matters because identical requests are answered from the response cache.
    """
    if not errors or errors[-1]["round"] != round_no - 1:
        return None
    return (f"Attempt {round_no - 1} could not be used: {errors[-1]['error']}. "
            "Reply with exactly one Python code block containing a complete pytest file and nothing else.")


def round_line(r: ExecutionResult) -> str:
    return (f"{r.tests_passed}/{r.tests_total} tests passed | statements {r.statement_coverage:.1f}% "
            f"branches {r.branch_coverage:.1f}% | {r.verdict}")


def llm_usage(log_path: Path) -> dict:
    lines = []
    if log_path.exists():
        lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    answered = [line for line in lines if "error" not in line]

    def tokens(line: dict, name: str) -> int:
        usage = line.get("usage") or {}
        if name == "reasoning_tokens":
            return (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        return usage.get(name) or 0

    return {
        "llm_calls": len(lines),
        "llm_cached_calls": sum(1 for line in lines if line.get("cached")),
        "llm_requests_sent": sum(len(line.get("attempts", [])) for line in lines),
        "models_used": sorted({line["model_used"] for line in answered}),
        **{name: sum(tokens(line, name) for line in answered)
           for name in ("prompt_tokens", "completion_tokens", "reasoning_tokens")},
    }


def pipeline_error(problem: Problem, problem_dir: Path, exc: Exception) -> dict:
    problem_dir.mkdir(parents=True, exist_ok=True)
    (problem_dir / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
    verdict = {"task_id": problem.task_id, "entry_point": problem.entry_point, "codegen_ok": None,
               "status": "PIPELINE_ERROR", "error": f"{type(exc).__name__}: {exc}", "code_correct": False,
               "baseline": None, **llm_usage(problem_dir / "llm_calls.jsonl")}
    write_json(problem_dir / "verdict.json", verdict)
    return verdict


# --- run-level files ---------------------------------------------------------------------

def run_config(args: argparse.Namespace, problems: list[Problem]) -> dict:
    return {
        "mode": args.mode,
        "criterion": args.criterion,
        "target": args.target,
        "max_rounds": args.max_rounds if args.mode == "full" else None,
        "task_ids": [p.task_id for p in problems],
        "started_at": now(),
        "models": {"primary": config.PRIMARY_MODEL, "fallbacks": config.FALLBACK_MODELS},
        "code_generator": {**config.CODEGEN_SETTINGS, "reasoning": config.REASONING},
        "test_generator": {**config.TESTGEN_SETTINGS, "reasoning": config.REASONING,
                           "criterion_goal": config.criterion_goal(args.criterion, args.target)},
        "executor": {"timeout_s": config.EXECUTOR_TIMEOUT_S},
        "llm_client": {"min_seconds_between_calls": config.MIN_SECONDS_BETWEEN_CALLS,
                       "max_retries": config.MAX_RETRIES, "retry_waits_s": config.RETRY_WAITS_S,
                       "request_timeout_s": config.REQUEST_TIMEOUT_S},
        "dataset": {"file": "data/mbpp_subset.json", "sha256": text_sha256(config.DATA_FILE)},
        "prompts": {p.name: text_sha256(p) for p in sorted(config.PROMPTS_DIR.glob("*.txt"))},
        "environment": {"python": platform.python_version(),
                        **{pkg: version(pkg) for pkg in ("pytest", "coverage", "requests")}},
    }


def summarize(verdicts: list[dict], cfg: dict, stopped: str | None) -> dict:
    run = len(verdicts)
    measured = [v for v in verdicts if v.get("baseline")]  # code was generated and the baseline ran
    correct = sum(1 for v in verdicts if v.get("code_correct"))

    def total(key: str) -> int:
        return sum(v.get(key) or 0 for v in verdicts)

    aggregate = {
        "problems_planned": len(cfg["task_ids"]),
        "problems_run": run,
        "code_generated": sum(1 for v in verdicts if v.get("codegen_ok")),
        "code_correct": correct,
        "code_correct_rate": rate(correct, run),
        "baseline_problems_measured": len(measured),
        "baseline_mean_statement_coverage": mean([v["baseline"]["statement_coverage"] for v in measured]),
        "baseline_mean_branch_coverage": mean([v["baseline"]["branch_coverage"] for v in measured]),
        "baseline_target_met": sum(1 for v in measured if v["baseline"]["target_met"]),
        "baseline_pass": sum(1 for v in measured if v["baseline"]["verdict"] == "PASS"),
        **(generated_aggregate(verdicts, measured) if cfg["mode"] == "full" else {}),
        **{key: total(key) for key in ("llm_calls", "llm_cached_calls", "llm_requests_sent",
                                       "prompt_tokens", "completion_tokens", "reasoning_tokens")},
        "models_used": sorted({m for v in verdicts for m in v.get("models_used", [])}),
    }
    return {"config": cfg, "finished_at": now(), "stopped_early": stopped, "aggregate": aggregate,
            "problems": verdicts}


def generated_aggregate(verdicts: list[dict], measured: list[dict]) -> dict:
    """The Phase 2 metrics of PROJECT_PLAN.md §3.11, over the problems that reached test generation.

    `measured` are the problems with a generated solution, so every rate has the same denominator as the
    baseline it is compared with. Test counts are taken from the final suite of each problem.
    """
    finals = [v for v in verdicts if v.get("final")]
    single_shot = [v for v in verdicts if v.get("round_1")]
    buggy = [v for v in measured if not v.get("code_correct")]
    labels = {label: sum((v.get("test_labels") or {}).get(label, 0) for v in verdicts) for label in TEST_LABELS}
    tests_total = sum(v["final"]["tests_total"] for v in finals)
    tests_passed = sum(v["final"]["tests_passed"] for v in finals)
    labelled = sum(labels.values())
    met_round_1 = sum(1 for v in single_shot if v["round_1"]["target_met"])
    met_final = sum(1 for v in finals if v["final"]["target_met"])
    bug_found = sum(1 for v in buggy if (v.get("test_labels") or {}).get("BUG_FOUND"))
    return {
        "testgen_problems": len(measured),
        "testgen_failed": sum(1 for v in verdicts if v.get("status") == "TESTGEN_FAILED"),
        "suites_produced": len(finals),
        "generated_mean_statement_coverage": mean([v["final"]["statement_coverage"] for v in finals]),
        "generated_mean_branch_coverage": mean([v["final"]["branch_coverage"] for v in finals]),
        "generated_target_met_round_1": met_round_1,
        "generated_target_met_round_1_rate": rate(met_round_1, len(measured)),
        "generated_target_met_final": met_final,
        "generated_target_met_final_rate": rate(met_final, len(measured)),
        "generated_pass": sum(1 for v in finals if v["final"]["verdict"] == "PASS"),
        "mean_rounds_used": mean([v.get("rounds_used", 0) for v in measured]),
        "tests_generated": tests_total,
        "tests_passing": tests_passed,
        "test_pass_rate": rate(tests_passed, tests_total),
        "test_labels": labels,
        "test_validity_rate": rate(labels["VALID"], labelled),
        "problems_with_incorrect_code": len(buggy),
        "problems_with_bug_found": bug_found,
        "fault_detection_rate": rate(bug_found, len(buggy)),
    }


def summary_markdown(summary: dict) -> str:
    cfg, agg = summary["config"], summary["aggregate"]
    full = cfg["mode"] == "full"
    goal = f"{cfg['criterion']} coverage >= {cfg['target']:g}%"
    settings, testgen = cfg["code_generator"], cfg.get("test_generator", {})
    mode_text = ("full (Code Generator + Test Generator + coverage feedback loop + validation)" if full
                 else "baseline (Code Generator + MBPP's 3 reference asserts)")
    lines = [
        f"# Run summary: {cfg['mode']}",
        "",
        "| Setting | Value |",
        "|---|---|",
        f"| Mode | {mode_text} |",
        f"| Coverage goal used for the verdict | {goal} |",
        f"| Model | `{cfg['models']['primary']}` (fallbacks: {', '.join(f'`{m}`' for m in cfg['models']['fallbacks'])}) |",
        f"| Code Generator settings | temperature {settings['temperature']}, top_p {settings['top_p']}, "
        f"max_tokens {settings['max_tokens']}, seed {settings.get('seed')}, reasoning disabled |",
    ]
    if full:
        lines += [
            f"| Test Generator settings | temperature {testgen.get('temperature')}, top_p {testgen.get('top_p')}, "
            f"max_tokens {testgen.get('max_tokens')}, seed {testgen.get('seed')}, reasoning disabled |",
            f"| Max test-generation rounds | {cfg['max_rounds']} |",
        ]
    lines += [f"| Started / finished (UTC) | {cfg['started_at']} / {summary['finished_at']} |", ""]
    if summary["stopped_early"]:
        lines += [f"**Stopped early:** {summary['stopped_early']}", ""]

    lines += ["## Results per problem", ""]
    lines += full_problem_table(summary) if full else baseline_problem_table(summary)
    tested = "the generated tests" if full else "MBPP's own 3 asserts"
    item = "test" if full else "assert"
    lines += [
        "",
        f"Verdict = the Test Executor's verdict for {tested} with the goal \"{goal}\": "
        f"PASS (all passed, goal met), COVERAGE_NOT_MET (all passed, goal not met), "
        f"TESTS_FAILED (at least one {item} failed), ERROR (could not run).",
        "",
        "## Aggregate",
        "",
    ]
    run = agg["problems_run"]
    lines += [
        f"- Problems run: {run} of {agg['problems_planned']} planned",
        f"- Code generated: {agg['code_generated']}/{run}; code correct (passes all 3 MBPP asserts): "
        f"{agg['code_correct']}/{run} ({agg['code_correct_rate']}%)",
        f"- Mean coverage of the generated code by MBPP's own tests: statements "
        f"{fmt_pct(agg['baseline_mean_statement_coverage'])}, branches {fmt_pct(agg['baseline_mean_branch_coverage'])} "
        f"(over the {agg['baseline_problems_measured']} problem(s) with generated code)",
        f"- Coverage goal ({goal}) reached by MBPP's own tests: "
        f"{agg['baseline_target_met']}/{agg['baseline_problems_measured']}; with all 3 asserts also passing "
        f"(verdict PASS): {agg['baseline_pass']}/{agg['baseline_problems_measured']}",
    ]
    if full:
        lines += generated_aggregate_lines(agg, goal, cfg['max_rounds'])
    lines += [
        f"- LLM calls: {agg['llm_calls']} ({agg['llm_cached_calls']} from the cache); HTTP requests sent: "
        f"{agg['llm_requests_sent']}; tokens: {agg['prompt_tokens']} prompt, {agg['completion_tokens']} completion, "
        f"{agg['reasoning_tokens']} reasoning",
        f"- Models that answered: {', '.join(f'`{m}`' for m in agg['models_used']) or '-'}",
        "",
    ]
    return "\n".join(lines)


def baseline_problem_table(summary: dict) -> list[str]:
    lines = [
        "| Task | Function | Status | Code correct | MBPP asserts passed | Statement coverage | Branch coverage "
        "| Verdict | LLM calls (cached) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for v in summary["problems"]:
        b = v.get("baseline")
        if b:
            cells = [yes_no(v["code_correct"]), f"{b['tests_passed']}/{b['tests_total']}",
                     f"{b['statement_coverage']:.1f}% of {b['num_statements']}", fmt_branches(b), b["verdict"]]
        else:
            cells = [yes_no(v.get("code_correct")), "-", "-", "-", v.get("error", "")]
        lines.append(f"| {v['task_id']} | `{v['entry_point']}` | {v['status']} | " + " | ".join(cells)
                     + f" | {v.get('llm_calls', 0)} ({v.get('llm_cached_calls', 0)}) |")
    return lines


def full_problem_table(summary: dict) -> list[str]:
    """One row per problem: MBPP's own tests on the left, the generated suite on the right."""
    lines = [
        "| Task | Function | Status | Code correct | Baseline stmt % | Baseline branch % | Rounds | Tests passed "
        "| Final stmt % | Final branch % | Goal met | Verdict | Test labels V/B/I/M | LLM calls (cached) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for v in summary["problems"]:
        b, f = v.get("baseline"), v.get("final")
        cells = [yes_no(v.get("code_correct"))]
        cells += [f"{b['statement_coverage']:.1f}%", fmt_branches(b)] if b else ["-", "-"]
        cells.append(str(v.get("rounds_used", "-") or "-"))
        if f:
            labels = v.get("test_labels") or {}
            cells += [f"{f['tests_passed']}/{f['tests_total']}", f"{f['statement_coverage']:.1f}%",
                      fmt_branches(f), yes_no(f["target_met"]), f["verdict"],
                      "/".join(str(labels.get(label, 0)) for label in
                               ("VALID", "BUG_FOUND", "INVALID_TEST", "MISLEADING"))]
        else:
            cells += ["-", "-", "-", "-", v.get("error", "-"), "-"]
        lines.append(f"| {v['task_id']} | `{v['entry_point']}` | {v['status']} | " + " | ".join(cells)
                     + f" | {v.get('llm_calls', 0)} ({v.get('llm_cached_calls', 0)}) |")
    return lines


def generated_aggregate_lines(agg: dict, goal: str, max_rounds: int) -> list[str]:
    """The §3.11 Phase 2 metrics, written so the baseline vs generated comparison is the headline."""
    problems, labels = agg["testgen_problems"], agg["test_labels"]
    labelled = sum(labels.values())
    return [
        f"- **Mean coverage of the generated code by the LLM's own tests: statements "
        f"{fmt_pct(agg['generated_mean_statement_coverage'])}, branches "
        f"{fmt_pct(agg['generated_mean_branch_coverage'])}** (over {agg['suites_produced']} suite(s); "
        f"baseline was {fmt_pct(agg['baseline_mean_statement_coverage'])} / "
        f"{fmt_pct(agg['baseline_mean_branch_coverage'])})",
        f"- **Coverage goal ({goal}) reached: {agg['generated_target_met_final']}/{problems} "
        f"({fmt_pct(agg['generated_target_met_final_rate'])}) with feedback, "
        f"{agg['generated_target_met_round_1']}/{problems} "
        f"({fmt_pct(agg['generated_target_met_round_1_rate'])}) single-shot (round 1 only)**; "
        f"baseline reached it {agg['baseline_target_met']}/{agg['baseline_problems_measured']}",
        f"- Verdict PASS (all generated tests passed and the goal was met): {agg['generated_pass']}/{problems}; "
        f"no usable test suite (TESTGEN_FAILED): {agg['testgen_failed']}/{problems}",
        f"- Mean test-generation rounds used: {agg['mean_rounds_used']} of at most {max_rounds}",
        f"- Generated tests: {agg['tests_generated']}; passing on the generated code: {agg['tests_passing']} "
        f"({fmt_pct(agg['test_pass_rate'])})",
        f"- Validation against MBPP's reference solution ({labelled} test(s)): "
        + ", ".join(f"{label} {labels[label]}" for label in TEST_LABELS if labels[label] or label != "NOT_RUN")
        + f"; test validity rate {fmt_pct(agg['test_validity_rate'])}",
        f"- Fault detection: {agg['problems_with_bug_found']}/{agg['problems_with_incorrect_code']} "
        f"({fmt_pct(agg['fault_detection_rate'])}) of the problems with incorrect generated code have at "
        f"least one BUG_FOUND test",
    ]


def fmt_branches(execution: dict) -> str:
    if not execution.get("num_branches"):
        return "no branches"
    return f"{execution['branch_coverage']:.1f}% of {execution['num_branches']}"


def one_line(v: dict) -> str:
    b, f = v.get("baseline"), v.get("final")
    if not b:
        return f"{v['status']}: {v.get('error')}"
    line = (f"code correct: {yes_no(v['code_correct'])} | MBPP asserts {b['tests_passed']}/{b['tests_total']} | "
            f"statements {b['statement_coverage']:.1f}% branches {b['branch_coverage']:.1f}% | {b['verdict']} | "
            f"LLM calls {v['llm_calls']} ({v['llm_cached_calls']} cached)")
    if f:
        labels = v.get("test_labels") or {}
        line += (f"\n  final (round {v['final_round']} of {v['rounds_used']} used): {round_line_dict(f)} | "
                 + ", ".join(f"{label} {labels[label]}" for label in TEST_LABELS if labels.get(label)))
    elif v.get("status") == "TESTGEN_FAILED":
        line += f"\n  final: TESTGEN_FAILED ({v.get('error')})"
    return line


def round_line_dict(f: dict) -> str:
    return (f"{f['tests_passed']}/{f['tests_total']} tests passed | statements {f['statement_coverage']:.1f}% "
            f"branches {f['branch_coverage']:.1f}% | {f['verdict']}")


def yes_no(value: bool | None) -> str:
    return {True: "yes", False: "no"}.get(value, "-")


def fmt_pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}%"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text_sha256(path: Path) -> str:
    """Hash of the text with normalised line endings, so it is the same on Windows and Linux checkouts."""
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    """Read a JSON file written earlier in this run; an unreadable file gives {} instead of stopping."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def rate(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


# --- main --------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    problems = select_problems(load_problems(config.DATA_FILE), args.task_ids, args.limit)
    args.out.mkdir(parents=True, exist_ok=True)
    cfg = run_config(args, problems)
    write_json(args.out / "config.json", cfg)

    llm = LLMClient()
    codegen = CodeGeneratorAgent(llm)
    testgen = TestGeneratorAgent(llm) if args.mode == "full" else None
    executor = TestExecutorAgent()
    rounds = f" | up to {args.max_rounds} test-generation round(s)" if args.mode == "full" else ""
    print(f"Mode {args.mode} | {len(problems)} problems | goal: {args.criterion} coverage >= {args.target:g}%"
          f"{rounds} | output: {args.out}")
    verdicts, stopped = [], None
    for number, problem in enumerate(problems, start=1):
        print(f"[{number}/{len(problems)}] Mbpp_{problem.task_id} {problem.entry_point}", flush=True)
        problem_dir = args.out / f"Mbpp_{problem.task_id}"
        try:
            if args.mode == "full":
                verdict = run_full_problem(problem, problem_dir, codegen, testgen, executor, args)
            else:
                verdict = run_baseline_problem(problem, problem_dir, codegen, executor, args)
        except FatalLLMError as exc:  # no key / quota used up: later problems would fail too
            stopped = f"{exc} (finished problems are saved; re-running repeats no finished LLM call)"
            print(f"  STOPPED: {exc}", flush=True)
            break
        except Exception as exc:  # one broken problem must never stop the whole run
            verdict = pipeline_error(problem, problem_dir, exc)
        verdicts.append(verdict)
        print("  " + one_line(verdict), flush=True)

    summary = summarize(verdicts, cfg, stopped)
    write_json(args.out / "summary.json", summary)
    (args.out / "summary.md").write_text(summary_markdown(summary), encoding="utf-8")
    agg = summary["aggregate"]
    print(f"\nCode correct: {agg['code_correct']}/{agg['problems_run']} | mean coverage by MBPP's tests: "
          f"statements {fmt_pct(agg['baseline_mean_statement_coverage'])}, "
          f"branches {fmt_pct(agg['baseline_mean_branch_coverage'])} | LLM calls {agg['llm_calls']} "
          f"({agg['llm_cached_calls']} cached)")
    if args.mode == "full":
        print(f"Generated tests: mean coverage statements {fmt_pct(agg['generated_mean_statement_coverage'])}, "
              f"branches {fmt_pct(agg['generated_mean_branch_coverage'])} | goal met "
              f"{agg['generated_target_met_final']}/{agg['testgen_problems']} (single-shot "
              f"{agg['generated_target_met_round_1']}/{agg['testgen_problems']}) | tests "
              f"{agg['tests_generated']}, valid {agg['test_labels']['VALID']}")
    print(f"Wrote {args.out / 'summary.md'}")
    return 1 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
