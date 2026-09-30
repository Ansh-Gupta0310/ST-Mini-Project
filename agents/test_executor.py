"""Test Executor agent: runs a pytest file against solution.py under coverage.py and gives a verdict.

No LLM is involved: the verdict is computed from what pytest and coverage.py measured
(PROJECT_PLAN.md §3.2, §3.7). Every execution happens in its own folder, which keeps everything
needed to re-run it by hand:   cd <folder>;  python -m pytest test_solution.py

Command line:
    python -m agents.test_executor --self-check    run each reference solution against its reference tests
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import textwrap
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path

import config
from agents.models import ExecutionResult, Problem, load_problems

SOLUTION_FILE = "solution.py"
TEST_FILE = "test_solution.py"
# Results of an earlier execution in the same folder are deleted first, so they can never be mixed up.
OLD_ARTIFACTS = ("junit.xml", "coverage.json", ".coverage", "output.txt", "execution.json", "coverage_html")
PYTEST_INI = "[pytest]\n# Keeps pytest from picking up the repository's own pytest.ini.\n"
TOOL_TIMEOUT_S = 60  # for `coverage json` / `coverage html`


def reference_tests_to_pytest(problem: Problem) -> str:
    """Wrap MBPP's reference asserts as pytest functions test_reference_1, _2, _3."""
    lines = [*problem.test_imports, "from solution import *", ""]
    for number, test in enumerate(problem.reference_tests, start=1):
        lines += ["", f"def test_reference_{number}():", textwrap.indent(test.strip(), "    ")]
    return "\n".join(lines) + "\n"


def coverage_target_met(criterion: str, target: float, statement: float, branch: float) -> bool:
    """Branch coverage subsumes statement coverage, so the branch criterion needs both.

    (coverage.py reports 100% branch coverage for a function without decisions even if no test calls it.)
    """
    if criterion == "statement":
        return statement >= target
    return branch >= target and statement >= target


def decide_verdict(status: str, tests_total: int, tests_failed: int, target_met: bool) -> str:
    """PROJECT_PLAN.md §3.7, checked in this order."""
    if status != "RAN" or tests_total == 0:
        return "ERROR"
    if tests_failed:
        return "TESTS_FAILED"
    if not target_met:
        return "COVERAGE_NOT_MET"
    return "PASS"


class TestExecutorAgent:
    __test__ = False  # not a pytest test class, despite its name

    def __init__(self, timeout_s: float = config.EXECUTOR_TIMEOUT_S, html: bool = True):
        self.timeout_s = timeout_s
        self.html = html

    def run(self, solution_code: str, test_code: str, work_dir: Path | str,
            criterion: str = config.DEFAULT_CRITERION, target: float = config.DEFAULT_TARGET) -> ExecutionResult:
        """Run test_code against solution_code in work_dir and return the measured result."""
        if criterion not in config.CRITERIA:
            raise ValueError(f"criterion must be one of {config.CRITERIA}, not {criterion!r}")
        work_dir = Path(work_dir)
        _prepare_folder(work_dir, solution_code, test_code)

        start = time.monotonic()
        pytest_cmd = [sys.executable, "-m", "coverage", "run", "--branch", f"--include={SOLUTION_FILE}",
                      "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=junit.xml", TEST_FILE]
        exit_code, output, timed_out = _run(pytest_cmd, work_dir, self.timeout_s)
        duration = round(time.monotonic() - start, 2)
        (work_dir / "output.txt").write_text(output, encoding="utf-8")

        outcomes = _read_junit(work_dir / "junit.xml")
        if timed_out:
            status = "TIMEOUT"
        elif exit_code in (0, 1) and outcomes is not None:
            status = "RAN"
        else:  # collection error (2), internal/usage error (3, 4), no tests collected (5), or no junit.xml
            status = "ERROR"
        if status != "RAN":
            outcomes = {}  # no test ran to completion

        if not timed_out:
            _run([sys.executable, "-m", "coverage", "json", "-q", "-o", "coverage.json"], work_dir, TOOL_TIMEOUT_S)
            if self.html and (work_dir / "coverage.json").exists():
                _run([sys.executable, "-m", "coverage", "html", "-q", "-d", "coverage_html"], work_dir, TOOL_TIMEOUT_S)
        cov = _read_coverage(work_dir / "coverage.json")

        tests_passed = sum(1 for outcome in outcomes.values() if outcome == "passed")
        tests_failed = len(outcomes) - tests_passed
        target_met = coverage_target_met(criterion, target, cov["statement_coverage"], cov["branch_coverage"])
        result = ExecutionResult(
            status=status,
            tests_total=len(outcomes),
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            test_outcomes=outcomes,
            statement_coverage=cov["statement_coverage"],
            branch_coverage=cov["branch_coverage"],
            missing_lines=cov["missing_lines"],
            missing_branches=cov["missing_branches"],
            target_met=target_met,
            verdict=decide_verdict(status, len(outcomes), tests_failed, target_met),
            output_tail="\n".join(output.strip().splitlines()[-40:]),
            criterion=criterion,
            target=target,
            num_statements=cov["num_statements"],
            num_branches=cov["num_branches"],
            exit_code=exit_code,
            duration_s=duration,
        )
        (work_dir / "execution.json").write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False),
                                                 encoding="utf-8")
        return result


def remove_path(path: Path) -> None:
    """Delete a file or folder tree, also inside OneDrive.

    OneDrive marks synced folders read-only, which makes a plain shutil.rmtree fail on Windows, and it can
    briefly lock files while syncing. So: clear the read-only flag and retry, and retry a few times.
    """
    def clear_read_only_and_retry(func, target, _exc):
        os.chmod(target, stat.S_IRWXU)  # on Windows this clears the read-only flag
        func(target)

    handler = {"onexc" if sys.version_info >= (3, 12) else "onerror": clear_read_only_and_retry}
    for attempt in range(5):
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path, **handler)
            elif path.exists():
                if not os.access(path, os.W_OK):
                    os.chmod(path, stat.S_IRWXU)
                path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.5 * (attempt + 1))


def _prepare_folder(work_dir: Path, solution_code: str, test_code: str) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    for name in OLD_ARTIFACTS:
        remove_path(work_dir / name)
    (work_dir / SOLUTION_FILE).write_text(solution_code, encoding="utf-8")
    (work_dir / TEST_FILE).write_text(test_code, encoding="utf-8")
    (work_dir / "pytest.ini").write_text(PYTEST_INI, encoding="utf-8")


def _child_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "COVERAGE_"))}
    env.pop(config.API_KEY_ENV_VAR, None)  # generated code must never be able to read the API key
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    return env


def _run(args: list[str], cwd: Path, timeout: float) -> tuple[int | None, str, bool]:
    """Run a command (arguments as a list: the project path contains spaces). Returns (exit code, output, timed out)."""
    try:
        proc = subprocess.run(args, cwd=cwd, env=_child_env(), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), False
    except subprocess.TimeoutExpired as exc:
        partial = _decode(exc.stdout) + _decode(exc.stderr)
        return None, partial + f"\n[executor] stopped after the {timeout:g} s timeout\n", True


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    return data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data


def _read_junit(path: Path) -> dict[str, str] | None:
    """test name -> "passed" | "failed". Failures, errors and skips all count as "failed"."""
    if not path.exists():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    outcomes: dict[str, str] = {}
    for case in root.iter("testcase"):
        name = case.get("name", "?")
        owner = (case.get("classname") or "").rsplit(".", 1)[-1]
        if owner and owner != Path(TEST_FILE).stem:  # a test inside a class
            name = f"{owner}::{name}"
        failed = any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
        outcomes[name] = "failed" if failed else "passed"
    return outcomes


def _read_coverage(path: Path) -> dict:
    result = {"statement_coverage": 0.0, "branch_coverage": 0.0, "missing_lines": [], "missing_branches": [],
              "num_statements": 0, "num_branches": 0}
    if not path.exists():  # e.g. solution.py was never imported
        return result
    try:
        files = json.loads(path.read_text(encoding="utf-8")).get("files", {})
    except ValueError:
        return result
    entry = files.get(SOLUTION_FILE) or next(
        (value for key, value in files.items() if Path(key).name == SOLUTION_FILE), None)
    if entry is None:
        return result
    summary = entry.get("summary", {})
    statements, branches = summary.get("num_statements", 0), summary.get("num_branches", 0)
    statement_pct = summary.get("percent_statements_covered")
    if statement_pct is None:
        statement_pct = 100.0 * summary.get("covered_lines", 0) / statements if statements else 100.0
    branch_pct = summary.get("percent_branches_covered")
    if branch_pct is None:
        branch_pct = 100.0 * summary.get("covered_branches", 0) / branches if branches else 100.0
    result.update(
        statement_coverage=round(statement_pct, 2),
        branch_coverage=round(branch_pct, 2),
        missing_lines=entry.get("missing_lines", []),
        missing_branches=entry.get("missing_branches", []),
        num_statements=statements,
        num_branches=branches,
    )
    return result


# --- command line ------------------------------------------------------------------------

def _self_check() -> int:
    problems = load_problems(config.DATA_FILE)
    executor = TestExecutorAgent()
    out_dir = config.ROOT / "runs" / "self_check"
    print(f"{'task':>5}  {'function':<20} {'tests':>5}  {'stmt %':>6}  {'branch %':>8}  verdict (branch, 100%)")
    passed = 0
    for problem in problems:
        r = executor.run(problem.reference_code, reference_tests_to_pytest(problem), out_dir / f"Mbpp_{problem.task_id}")
        ok = r.status == "RAN" and r.tests_total == len(problem.reference_tests) and r.tests_passed == r.tests_total
        passed += ok
        print(f"{problem.task_id:>5}  {problem.entry_point:<20} {r.tests_passed:>2}/{r.tests_total:<2}  "
              f"{r.statement_coverage:>6.1f}  {r.branch_coverage:>8.1f}  {r.verdict}")
    print(f"{passed}/{len(problems)} reference solutions pass all their reference tests")
    return 0 if passed == len(problems) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test Executor helpers.")
    parser.add_argument("--self-check", action="store_true", required=True,
                        help="run every reference solution against its MBPP reference tests")
    parser.parse_args(argv)
    return _self_check()


if __name__ == "__main__":
    sys.exit(main())
