"""Offline tests for agents/test_executor.py: real pytest + coverage.py runs in temporary folders."""
import json
import os
import stat
import sys

import pytest

import config
from agents.models import Problem, load_problems
from agents.test_executor import (TestExecutorAgent, classify_tests, count_labels,
                                 reference_tests_to_pytest, remove_path)

# The worked example from PROJECT_PLAN.md §2.3.
SIGN = """\
def sign(x):
    if x > 0:
        return 1
    elif x < 0:
        return -1
    return 0
"""
ONLY_POSITIVE = "from solution import sign\n\n\ndef test_positive():\n    assert sign(5) == 1\n"
ALL_THREE = ONLY_POSITIVE + (
    "\n\ndef test_negative():\n    assert sign(-5) == -1\n"
    "\n\ndef test_zero():\n    assert sign(0) == 0\n"
)
SYNTAX_ERROR = "from solution import sign\n\n\ndef test_broken(:\n    pass\n"


@pytest.fixture
def executor():
    return TestExecutorAgent(html=False)


def problem_11():
    return next(p for p in load_problems(config.DATA_FILE) if p.task_id == 11)


def test_partial_coverage_matches_the_plan_example(executor, tmp_path):
    r = executor.run(SIGN, ONLY_POSITIVE, tmp_path)
    assert (r.status, r.tests_total, r.tests_passed, r.tests_failed) == ("RAN", 1, 1, 0)
    assert (r.statement_coverage, r.branch_coverage) == (50.0, 25.0)
    assert (r.num_statements, r.num_branches) == (6, 4)
    assert r.missing_lines == [4, 5, 6]
    assert r.missing_branches == [[2, 4], [4, 5], [4, 6]]
    assert (r.target_met, r.verdict) == (False, "COVERAGE_NOT_MET")


def test_full_coverage_passes(executor, tmp_path):
    r = executor.run(SIGN, ALL_THREE, tmp_path)
    assert (r.statement_coverage, r.branch_coverage, r.target_met, r.verdict) == (100.0, 100.0, True, "PASS")
    assert r.test_outcomes == {"test_positive": "passed", "test_negative": "passed", "test_zero": "passed"}


def test_wrong_expected_value_fails(executor, tmp_path):
    wrong = ONLY_POSITIVE + "\n\ndef test_wrong():\n    assert sign(0) == 1\n"
    r = executor.run(SIGN, wrong, tmp_path)
    assert (r.tests_total, r.tests_passed, r.tests_failed) == (2, 1, 1)
    assert r.test_outcomes == {"test_positive": "passed", "test_wrong": "failed"}
    assert r.verdict == "TESTS_FAILED"


def test_statement_criterion_uses_statement_coverage(executor, tmp_path):
    r = executor.run(SIGN, ONLY_POSITIVE, tmp_path, criterion="statement", target=50.0)
    assert (r.target_met, r.verdict) == (True, "PASS")


def test_branch_criterion_also_requires_statement_coverage(executor, tmp_path):
    # No decisions -> coverage.py reports 100% branch coverage even though mul() is never called.
    solution = "def mul(a, b):\n    return a * b\n"
    tests = "import solution\n\n\ndef test_module_loads():\n    assert solution is not None\n"
    r = executor.run(solution, tests, tmp_path)
    assert (r.branch_coverage, r.statement_coverage) == (100.0, 50.0)
    assert (r.target_met, r.verdict) == (False, "COVERAGE_NOT_MET")


def test_unknown_criterion_is_rejected(executor, tmp_path):
    with pytest.raises(ValueError):
        executor.run(SIGN, ALL_THREE, tmp_path, criterion="loop")


def test_syntax_error_in_test_file_is_an_error(executor, tmp_path):
    r = executor.run(SIGN, SYNTAX_ERROR, tmp_path)
    assert (r.status, r.verdict, r.tests_total, r.exit_code) == ("ERROR", "ERROR", 0, 2)


def test_file_without_tests_is_an_error(executor, tmp_path):
    r = executor.run(SIGN, "from solution import sign\n", tmp_path)
    assert (r.status, r.verdict, r.exit_code) == ("ERROR", "ERROR", 5)


def test_infinite_loop_times_out(tmp_path):
    solution = "def spin():\n    while True:\n        pass\n"
    tests = "from solution import spin\n\n\ndef test_spin():\n    spin()\n"
    r = TestExecutorAgent(timeout_s=3, html=False).run(solution, tests, tmp_path)
    assert (r.status, r.verdict, r.exit_code) == ("TIMEOUT", "ERROR", None)


def test_generated_code_cannot_see_the_api_key(executor, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-FAKE-KEY-FOR-TESTS")
    solution = "import os\n\n\ndef key():\n    return os.environ.get('OPENROUTER_API_KEY')\n"
    tests = "from solution import key\n\n\ndef test_no_key():\n    assert key() is None\n"
    assert executor.run(solution, tests, tmp_path).verdict == "PASS"


def test_folder_keeps_everything_needed_to_rerun(tmp_path):
    TestExecutorAgent(html=True).run(SIGN, ALL_THREE, tmp_path)
    for name in ("solution.py", "test_solution.py", "pytest.ini", "junit.xml", "coverage.json", "output.txt",
                 "execution.json", "coverage_html/index.html"):
        assert (tmp_path / name).exists(), name
    saved = json.loads((tmp_path / "execution.json").read_text(encoding="utf-8"))
    assert (saved["verdict"], saved["criterion"], saved["target"]) == ("PASS", "branch", 100.0)


def test_rerun_in_the_same_folder_never_reuses_old_results(executor, tmp_path):
    executor.run(SIGN, ALL_THREE, tmp_path)
    r = executor.run(SIGN, SYNTAX_ERROR, tmp_path)
    assert (r.verdict, r.statement_coverage, r.branch_coverage) == ("ERROR", 0.0, 0.0)


@pytest.mark.skipif(sys.platform != "win32", reason="read-only folders are a Windows/OneDrive issue")
def test_remove_path_deletes_read_only_folders_like_onedrive_makes_them(tmp_path):
    folder = tmp_path / "coverage_html"
    (folder / "sub").mkdir(parents=True)
    (folder / "sub" / "index.html").write_text("x", encoding="utf-8")
    for path in (folder / "sub" / "index.html", folder / "sub", folder):
        os.chmod(path, stat.S_IREAD)  # what OneDrive does to synced folders
    remove_path(folder)
    assert not folder.exists()


def test_reference_tests_wrap_the_mbpp_asserts():
    code = reference_tests_to_pytest(problem_11())
    assert code.count("def test_reference_") == 3
    assert "from solution import *" in code
    compile(code, "test_solution.py", "exec")


def test_reference_solution_passes_its_reference_tests(executor, tmp_path):
    problem = problem_11()
    r = executor.run(problem.reference_code, reference_tests_to_pytest(problem), tmp_path)
    assert (r.status, r.tests_total, r.tests_passed) == ("RAN", 3, 3)


# --- validation against MBPP's reference solution (PROJECT_PLAN.md §3.7, step 2.4) ---------

# The generated version is buggy: it answers 1 for sign(0), where the reference answers 0.
BUGGY_SIGN = "def sign(x):\n    if x < 0:\n        return -1\n    return 1\n"
FOUR_LABELS = (
    "from solution import sign\n\n\ndef test_positive():\n    assert sign(5) == 1\n"
    "\n\ndef test_zero():\n    assert sign(0) == 0\n"          # right expectation, wrong code -> BUG_FOUND
    "\n\ndef test_negative_wrong():\n    assert sign(-5) == 1\n"  # wrong expectation -> INVALID_TEST
    "\n\ndef test_zero_wrong():\n    assert sign(0) == 1\n"       # agrees with the bug -> MISLEADING
)


def sign_problem():
    return Problem(task_id=0, prompt="Return the sign of x.", entry_point="sign", signature="def sign(x):",
                   reference_code=SIGN, reference_tests=[], test_imports=[])


def test_classify_tests_applies_the_label_table():
    labels = classify_tests({"a": "passed", "b": "failed", "c": "failed", "d": "passed"},
                            {"a": "passed", "b": "passed", "c": "failed", "d": "failed"})
    assert labels == {"a": "VALID", "b": "BUG_FOUND", "c": "INVALID_TEST", "d": "MISLEADING"}


def test_classify_tests_marks_a_test_the_reference_run_never_reported():
    assert classify_tests({"a": "passed"}, {}) == {"a": "NOT_RUN"}


def test_count_labels_always_reports_every_label():
    counts = count_labels({"a": "VALID", "b": "VALID", "c": "BUG_FOUND"})
    assert counts == {"VALID": 2, "BUG_FOUND": 1, "INVALID_TEST": 0, "MISLEADING": 0, "NOT_RUN": 0}


def test_validate_labels_each_test_against_the_reference(executor, tmp_path):
    on_generated = executor.run(BUGGY_SIGN, FOUR_LABELS, tmp_path / "round_1").test_outcomes
    labels = executor.validate(FOUR_LABELS, sign_problem(), tmp_path / "validation", on_generated)
    assert labels == {"test_positive": "VALID", "test_zero": "BUG_FOUND",
                      "test_negative_wrong": "INVALID_TEST", "test_zero_wrong": "MISLEADING"}
    assert (tmp_path / "validation" / "execution.json").exists()  # re-runnable evidence for the report


def test_validate_runs_the_tests_against_the_reference_not_the_generated_code(executor, tmp_path):
    """The validation folder must contain MBPP's reference solution, not the generated one."""
    executor.validate(FOUR_LABELS, sign_problem(), tmp_path / "validation", {})
    assert (tmp_path / "validation" / "solution.py").read_text(encoding="utf-8") == SIGN
