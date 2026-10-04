"""Offline tests for agents/test_executor.py: real pytest + coverage.py runs in temporary folders."""
import json
import os
import stat
import sys

import pytest

import config
from agents.models import Problem, load_problems
from agents.test_executor import (TestExecutorAgent, classify_tests, count_labels,
                                 coverage_target_met, reference_tests_to_pytest, remove_path)

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


# --- the `loops` criterion: edge-pair coverage (PROJECT_PLAN.md §2.3) ---------------------

CLASSIFY = """def classify(nums):
    total = 0
    for n in nums:
        if n > 0:
            total += n
    return total
"""
CLASSIFY_ONE = "from solution import classify\n\n\ndef test_pos():\n    assert classify([1, 2]) == 3\n"
CLASSIFY_MORE = CLASSIFY_ONE + (
    "\n\ndef test_empty():\n    assert classify([]) == 0\n"
    "\n\ndef test_negative_in_the_middle():\n    assert classify([1, -5, 2]) == 3\n"
)


def test_loops_criterion_measures_edge_pairs(executor, tmp_path):
    r = executor.run(CLASSIFY, CLASSIFY_ONE, tmp_path, criterion="loops", target=100.0)
    assert (r.num_edge_pairs, r.edge_pair_coverage) == (9, 55.56)
    assert [2, 3, 6] in r.missing_edge_pairs          # the loop body is never skipped
    assert (r.target_met, r.verdict) == (False, "COVERAGE_NOT_MET")


def test_loops_criterion_is_stricter_than_branch(executor, tmp_path):
    """The point of the third criterion: 100% branch coverage can still leave an ordering untested."""
    r = executor.run(CLASSIFY, CLASSIFY_MORE, tmp_path, criterion="loops", target=100.0)
    assert (r.statement_coverage, r.branch_coverage) == (100.0, 100.0)   # branch is satisfied
    assert r.edge_pair_coverage == 88.89                                  # but one ordering is missing
    assert r.missing_edge_pairs == [[4, 3, 6]]       # condition False, then the loop ends
    assert (r.target_met, r.verdict) == (False, "COVERAGE_NOT_MET")


def test_loops_criterion_passes_when_every_ordering_is_covered(executor, tmp_path):
    tests = CLASSIFY_MORE + "\n\ndef test_negative_last():\n    assert classify([1, -5]) == 1\n"
    r = executor.run(CLASSIFY, tests, tmp_path, criterion="loops", target=100.0)
    assert (r.edge_pair_coverage, r.missing_edge_pairs) == (100.0, [])
    assert (r.target_met, r.verdict) == (True, "PASS")


def test_other_criteria_do_not_run_the_traced_pass(executor, tmp_path):
    """Nothing about the existing two criteria changes: no tracer, no conftest, fields left at defaults."""
    r = executor.run(CLASSIFY, CLASSIFY_MORE, tmp_path, criterion="branch", target=100.0)
    assert (r.target_met, r.verdict) == (True, "PASS")
    assert (r.edge_pair_coverage, r.num_edge_pairs, r.missing_edge_pairs) == (0.0, 0, [])
    assert not (tmp_path / "conftest.py").exists()
    assert not (tmp_path / "traces.json").exists()


def test_a_stale_tracer_from_an_earlier_loops_run_is_removed(executor, tmp_path):
    """A conftest.py left behind would hijack the coverage pass, so a re-run must delete it."""
    executor.run(CLASSIFY, CLASSIFY_ONE, tmp_path, criterion="loops", target=100.0)
    assert (tmp_path / "conftest.py").exists()
    r = executor.run(CLASSIFY, CLASSIFY_MORE, tmp_path, criterion="branch", target=100.0)
    assert not (tmp_path / "conftest.py").exists()
    assert (r.statement_coverage, r.branch_coverage) == (100.0, 100.0)   # coverage.py still measured


def test_loops_target_also_requires_branch_and_statement_coverage():
    # Code without decisions has no edge pairs and no branches: 0 of 0 reads as 100% for both.
    assert not coverage_target_met("loops", 100.0, statement=50.0, branch=100.0, edge_pair=100.0)
    assert coverage_target_met("loops", 100.0, statement=100.0, branch=100.0, edge_pair=100.0)
    assert not coverage_target_met("loops", 100.0, statement=100.0, branch=100.0, edge_pair=90.0)
    # and the older criteria are unaffected by the new argument
    assert coverage_target_met("branch", 100.0, statement=100.0, branch=100.0)
    assert coverage_target_met("statement", 100.0, statement=100.0, branch=0.0)


RECURSIVE = """def total(items):
    out = 0
    for item in items:
        if isinstance(item, list):
            out += total(item)
        else:
            out += item
    return out
"""
RECURSIVE_TESTS = (
    "from solution import total\n\n\n"
    "def test_flat():\n    assert total([1, 2]) == 3\n\n\n"
    "def test_empty():\n    assert total([]) == 0\n\n\n"
    "def test_nested_then_more():\n    assert total([[1], 2]) == 3\n\n\n"
    "def test_two_nested():\n    assert total([[1], [2]]) == 3\n\n\n"
    "def test_only_nested():\n    assert total([[1]]) == 1\n\n\n"
    "def test_plain_last_is_not_a_list():\n    assert total([[1], 2, 3]) == 6\n"
)


def test_edge_pairs_of_a_recursive_function_are_measured_per_call_frame(executor, tmp_path):
    """Regression: a flat trace splices the inner call's lines in, so `4 -> 5 -> 3` looks untested.

    Found by the first official loops run, which reported 70% for MBPP problem 65 (a recursive sum)
    although its tests did cover every pair.
    """
    r = executor.run(RECURSIVE, RECURSIVE_TESTS, tmp_path, criterion="loops", target=100.0)
    assert r.tests_passed == r.tests_total == 6
    assert [4, 5, 3] not in r.missing_edge_pairs      # recursive call, then back to the loop header
    assert (r.edge_pair_coverage, r.missing_edge_pairs) == (100.0, [])
    assert (r.target_met, r.verdict) == (True, "PASS")
