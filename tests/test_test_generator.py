"""Offline tests for agents/test_generator.py, using a fake LLM client."""
import pytest

import config
from agents.llm_client import FatalLLMError, LLMError
from agents.models import ExecutionResult, LLMResponse, load_problems
from agents.test_generator import TestGeneratorAgent

SOLUTION = "def remove_Occ(s, ch):\n    if ch not in s:\n        return s\n    return s.replace(ch, '', 1)\n"
GOOD_REPLY = ("Here are the tests:\n```python\nfrom solution import remove_Occ\n\n\n"
              "def test_removes_the_character():\n    assert remove_Occ('hello', 'l') == 'heo'\n```")


class FakeLLM:
    def __init__(self, reply="", error=None):
        self.reply, self.error, self.calls = reply, error, []

    def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        if self.error:
            raise self.error
        return LLMResponse(self.reply, "fake/model", {}, cached=False, latency_s=0.0)


def feedback_result(**changes) -> ExecutionResult:
    fields = dict(status="RAN", tests_total=1, tests_passed=1, tests_failed=0,
                  test_outcomes={"test_removes_the_character": "passed"}, statement_coverage=75.0,
                  branch_coverage=50.0, missing_lines=[3], missing_branches=[[2, 3]], target_met=False,
                  verdict="COVERAGE_NOT_MET", output_tail="")
    return ExecutionResult(**{**fields, **changes})


@pytest.fixture
def problem():
    return next(p for p in load_problems(config.DATA_FILE) if p.task_id == 11)


def run(llm, problem, tmp_path, **kwargs):
    return llm, TestGeneratorAgent(llm).run(problem, SOLUTION, "branch", 100.0,
                                            tmp_path / "llm_calls.jsonl", **kwargs)


def test_prompt_is_white_box_but_never_shows_the_mbpp_reference(problem, tmp_path):
    llm, _ = run(FakeLLM(GOOD_REPLY), problem, tmp_path)
    system, user = llm.calls[0]["messages"]
    assert (system["role"], user["role"]) == ("system", "user")
    assert problem.entry_point in system["content"]
    assert "  1 | def remove_Occ(s, ch):" in user["content"]       # the numbered solution under test
    assert problem.prompt in user["content"]
    assert problem.reference_tests[0] in user["content"]           # the one example that fixes the format
    assert config.criterion_goal("branch", 100.0) in user["content"]
    for hidden in (problem.reference_code.strip(), problem.reference_tests[1], problem.reference_tests[2]):
        assert hidden not in user["content"]


def test_expected_values_are_asked_for_from_the_description_not_the_code(problem, tmp_path):
    llm, _ = run(FakeLLM(GOOD_REPLY), problem, tmp_path)
    system = llm.calls[0]["messages"][0]["content"]
    assert "from the problem description, not from the code under test" in system


def test_settings_come_from_config(problem, tmp_path):
    llm, _ = run(FakeLLM(GOOD_REPLY), problem, tmp_path)
    call = llm.calls[0]
    assert {key: call[key] for key in config.TESTGEN_SETTINGS} == config.TESTGEN_SETTINGS
    assert call["agent"] == "test_generator"


def test_goal_text_follows_the_chosen_criterion_and_target(problem, tmp_path):
    llm = FakeLLM(GOOD_REPLY)
    TestGeneratorAgent(llm).run(problem, SOLUTION, "statement", 90.0, tmp_path / "llm_calls.jsonl")
    assert "Reach 90% statement coverage" in llm.calls[0]["messages"][1]["content"]


def test_feedback_prompt_reports_what_is_still_uncovered(problem, tmp_path):
    existing = "from solution import remove_Occ\n\n\ndef test_removes_the_character():\n    assert True\n"
    llm, _ = run(FakeLLM(GOOD_REPLY), problem, tmp_path, feedback=feedback_result(), existing_tests=existing)
    user = llm.calls[0]["messages"][1]["content"]
    assert "statements 75%, branches 50%" in user
    assert "- line 3 `return s` was never run" in user
    assert "- line 2 `if ch not in s:` never went to line 3 `return s`" in user
    assert existing.strip() in user
    assert "only NEW test functions" in user
    assert problem.reference_tests[0] not in user  # the feedback round shows the tests instead


def test_reply_without_code_is_rejected(problem, tmp_path):
    _, result = run(FakeLLM("I cannot write tests for this."), problem, tmp_path)
    assert not result.ok and result.code is None
    assert result.raw_response == "I cannot write tests for this."


def test_file_that_defines_the_function_under_test_is_rejected(problem, tmp_path):
    reply = ("```python\nfrom solution import remove_Occ\n\n\ndef remove_Occ(s, ch):\n    return s\n\n\n"
             "def test_x():\n    assert remove_Occ('a', 'a') == 'a'\n```")
    _, result = run(FakeLLM(reply), problem, tmp_path)
    assert not result.ok and "defines remove_Occ" in result.error


def test_file_without_a_test_function_is_rejected(problem, tmp_path):
    _, result = run(FakeLLM("```python\nfrom solution import remove_Occ\n```"), problem, tmp_path)
    assert not result.ok and "test_" in result.error


def test_good_reply_gives_a_usable_pytest_file(problem, tmp_path):
    _, result = run(FakeLLM(GOOD_REPLY), problem, tmp_path)
    assert (result.ok, result.error) == (True, None)
    assert result.code.startswith("from solution import remove_Occ")
    compile(result.code, "test_solution.py", "exec")


def test_failed_call_is_reported_not_raised(problem, tmp_path):
    _, result = run(FakeLLM(error=LLMError("all models failed")), problem, tmp_path)
    assert not result.ok and "all models failed" in result.error


def test_fatal_error_stops_the_run(problem, tmp_path):
    with pytest.raises(FatalLLMError):
        run(FakeLLM(error=FatalLLMError("no key")), problem, tmp_path)
