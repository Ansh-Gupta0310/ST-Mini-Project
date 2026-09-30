"""Pipeline orchestrator: plain Python that calls the agents in a fixed order (no agent framework).

--mode baseline (Phase 1), for each problem:
    [1] Code Generator agent -> solution.py
    [2] Test Executor agent  -> runs MBPP's 3 reference asserts against solution.py, giving
                                code_correct and the coverage that the dataset's own tests reach
--mode full (Phase 2, PROJECT_PLAN.md §7) adds the Test Generator, the coverage feedback loop and
test validation.

Usage:
    python pipeline.py --mode baseline --out results/phase1_baseline
    python pipeline.py --mode baseline --task-ids 11 20 --out runs/smoke

Output (PROJECT_PLAN.md §3.10): <out>/config.json, summary.json, summary.md and one Mbpp_<id>/ folder
per problem with problem.json, llm_calls.jsonl, solution.py, reference/ and verdict.json.
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
from agents.llm_client import FatalLLMError, LLMClient
from agents.models import ExecutionResult, Problem, load_problems
from agents.test_executor import TestExecutorAgent, reference_tests_to_pytest, remove_path


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

def run_baseline_problem(problem: Problem, problem_dir: Path, codegen: CodeGeneratorAgent,
                         executor: TestExecutorAgent, args: argparse.Namespace) -> dict:
    remove_path(problem_dir)  # never mix files from an earlier run into this one
    problem_dir.mkdir(parents=True)
    write_json(problem_dir / "problem.json", asdict(problem))
    log_path = problem_dir / "llm_calls.jsonl"
    verdict = {"task_id": problem.task_id, "entry_point": problem.entry_point}

    generated = codegen.run(problem, log_path)                                   # [1]
    verdict["codegen_ok"] = generated.ok
    if not generated.ok:
        (problem_dir / "codegen_reply.txt").write_text(generated.raw_response, encoding="utf-8")
        verdict.update(status="CODEGEN_FAILED", error=generated.error, code_correct=False, baseline=None)
    else:
        (problem_dir / "solution.py").write_text(generated.code, encoding="utf-8")
        reference = executor.run(generated.code, reference_tests_to_pytest(problem),  # [2]
                                 problem_dir / "reference", args.criterion, args.target)
        verdict.update(status="COMPLETED", code_correct=passes_all(reference, problem),
                       baseline=execution_summary(reference))
    verdict.update(llm_usage(log_path))
    write_json(problem_dir / "verdict.json", verdict)
    return verdict


def passes_all(result: ExecutionResult, problem: Problem) -> bool:
    return (result.status == "RAN" and result.tests_total == len(problem.reference_tests)
            and result.tests_passed == result.tests_total)


def execution_summary(r: ExecutionResult) -> dict:
    return {"verdict": r.verdict, "status": r.status, "tests_total": r.tests_total, "tests_passed": r.tests_passed,
            "statement_coverage": r.statement_coverage, "branch_coverage": r.branch_coverage,
            "target_met": r.target_met, "num_statements": r.num_statements, "num_branches": r.num_branches,
            "missing_lines": r.missing_lines, "missing_branches": r.missing_branches}


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
    completed = [v for v in verdicts if v["status"] == "COMPLETED"]
    correct = sum(1 for v in verdicts if v.get("code_correct"))

    def mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 2) if values else None

    def total(key: str) -> int:
        return sum(v.get(key) or 0 for v in verdicts)

    aggregate = {
        "problems_planned": len(cfg["task_ids"]),
        "problems_run": run,
        "code_generated": sum(1 for v in verdicts if v.get("codegen_ok")),
        "code_correct": correct,
        "code_correct_rate": round(100 * correct / run, 1) if run else None,
        "baseline_problems_measured": len(completed),
        "baseline_mean_statement_coverage": mean([v["baseline"]["statement_coverage"] for v in completed]),
        "baseline_mean_branch_coverage": mean([v["baseline"]["branch_coverage"] for v in completed]),
        "baseline_target_met": sum(1 for v in completed if v["baseline"]["target_met"]),
        "baseline_pass": sum(1 for v in completed if v["baseline"]["verdict"] == "PASS"),
        **{key: total(key) for key in ("llm_calls", "llm_cached_calls", "llm_requests_sent",
                                       "prompt_tokens", "completion_tokens", "reasoning_tokens")},
        "models_used": sorted({m for v in verdicts for m in v.get("models_used", [])}),
    }
    return {"config": cfg, "finished_at": now(), "stopped_early": stopped, "aggregate": aggregate,
            "problems": verdicts}


def summary_markdown(summary: dict) -> str:
    cfg, agg = summary["config"], summary["aggregate"]
    goal = f"{cfg['criterion']} coverage >= {cfg['target']:g}%"
    settings = cfg["code_generator"]
    lines = [
        f"# Run summary: {cfg['mode']}",
        "",
        "| Setting | Value |",
        "|---|---|",
        f"| Mode | {cfg['mode']} (Code Generator + MBPP's 3 reference asserts) |",
        f"| Coverage goal used for the verdict | {goal} |",
        f"| Model | `{cfg['models']['primary']}` (fallbacks: {', '.join(f'`{m}`' for m in cfg['models']['fallbacks'])}) |",
        f"| Code Generator settings | temperature {settings['temperature']}, top_p {settings['top_p']}, "
        f"max_tokens {settings['max_tokens']}, seed {settings.get('seed')}, reasoning disabled |",
        f"| Started / finished (UTC) | {cfg['started_at']} / {summary['finished_at']} |",
        "",
    ]
    if summary["stopped_early"]:
        lines += [f"**Stopped early:** {summary['stopped_early']}", ""]
    lines += [
        "## Results per problem",
        "",
        "| Task | Function | Status | Code correct | MBPP asserts passed | Statement coverage | Branch coverage "
        "| Verdict | LLM calls (cached) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for v in summary["problems"]:
        b = v.get("baseline")
        if b:
            branches = f"{b['branch_coverage']:.1f}% of {b['num_branches']}" if b["num_branches"] else "no branches"
            cells = [yes_no(v["code_correct"]), f"{b['tests_passed']}/{b['tests_total']}",
                     f"{b['statement_coverage']:.1f}% of {b['num_statements']}", branches, b["verdict"]]
        else:
            cells = [yes_no(v.get("code_correct")), "-", "-", "-", v.get("error", "")]
        lines.append(f"| {v['task_id']} | `{v['entry_point']}` | {v['status']} | " + " | ".join(cells)
                     + f" | {v.get('llm_calls', 0)} ({v.get('llm_cached_calls', 0)}) |")
    run = agg["problems_run"]
    lines += [
        "",
        f"Verdict = the Test Executor's verdict for MBPP's own 3 asserts with the goal \"{goal}\": "
        "PASS (all passed, goal met), COVERAGE_NOT_MET (all passed, goal not met), "
        "TESTS_FAILED (at least one assert failed), ERROR (could not run).",
        "",
        "## Aggregate",
        "",
        f"- Problems run: {run} of {agg['problems_planned']} planned",
        f"- Code generated: {agg['code_generated']}/{run}; code correct (passes all 3 MBPP asserts): "
        f"{agg['code_correct']}/{run} ({agg['code_correct_rate']}%)",
        f"- Mean coverage of the generated code by MBPP's own tests: statements "
        f"{fmt_pct(agg['baseline_mean_statement_coverage'])}, branches {fmt_pct(agg['baseline_mean_branch_coverage'])} "
        f"(over the {agg['baseline_problems_measured']} problem(s) with generated code)",
        f"- Coverage goal ({goal}) reached by MBPP's own tests: "
        f"{agg['baseline_target_met']}/{agg['baseline_problems_measured']}; with all 3 asserts also passing "
        f"(verdict PASS): {agg['baseline_pass']}/{agg['baseline_problems_measured']}",
        f"- LLM calls: {agg['llm_calls']} ({agg['llm_cached_calls']} from the cache); HTTP requests sent: "
        f"{agg['llm_requests_sent']}; tokens: {agg['prompt_tokens']} prompt, {agg['completion_tokens']} completion, "
        f"{agg['reasoning_tokens']} reasoning",
        f"- Models that answered: {', '.join(f'`{m}`' for m in agg['models_used']) or '-'}",
        "",
    ]
    return "\n".join(lines)


def one_line(v: dict) -> str:
    b = v.get("baseline")
    if not b:
        return f"{v['status']}: {v.get('error')}"
    return (f"code correct: {yes_no(v['code_correct'])} | MBPP asserts {b['tests_passed']}/{b['tests_total']} | "
            f"statements {b['statement_coverage']:.1f}% branches {b['branch_coverage']:.1f}% | {b['verdict']} | "
            f"LLM calls {v['llm_calls']} ({v['llm_cached_calls']} cached)")


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


# --- main --------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "full":
        print("--mode full is Phase 2 (PROJECT_PLAN.md §7, step 2.5) and is not implemented yet.")
        return 2
    problems = select_problems(load_problems(config.DATA_FILE), args.task_ids, args.limit)
    args.out.mkdir(parents=True, exist_ok=True)
    cfg = run_config(args, problems)
    write_json(args.out / "config.json", cfg)

    codegen = CodeGeneratorAgent(LLMClient())
    executor = TestExecutorAgent()
    print(f"Mode {args.mode} | {len(problems)} problems | goal: {args.criterion} coverage >= {args.target:g}% "
          f"| output: {args.out}")
    verdicts, stopped = [], None
    for number, problem in enumerate(problems, start=1):
        print(f"[{number}/{len(problems)}] Mbpp_{problem.task_id} {problem.entry_point}", flush=True)
        problem_dir = args.out / f"Mbpp_{problem.task_id}"
        try:
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
    print(f"Wrote {args.out / 'summary.md'}")
    return 1 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
