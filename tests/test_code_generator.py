"""Offline tests for agents/code_generator.py, using a fake LLM client."""
import pytest

import config
from agents.code_generator import CodeGeneratorAgent
from agents.llm_client import FatalLLMError, LLMError
from agents.models import LLMResponse, load_problems

GOOD_REPLY = "```python\ndef remove_Occ(s, ch):\n    return s\n\n\nprint(remove_Occ('a', 'a'))\n```"


class FakeLLM:
    def __init__(self, reply="", error=None):
        self.reply, self.error, self.calls = reply, error, []

    def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        if self.error:
            raise self.error
        return LLMResponse(self.reply, "fake/model", {}, cached=False, latency_s=0.0)


@pytest.fixture
def problem():
    return next(p for p in load_problems(config.DATA_FILE) if p.task_id == 11)


def test_prompt_has_signature_and_one_example_but_never_the_reference(problem, tmp_path):
    llm = FakeLLM(GOOD_REPLY)
    CodeGeneratorAgent(llm).run(problem, tmp_path / "llm_calls.jsonl")
    system, user = llm.calls[0]["messages"]
    assert (system["role"], user["role"]) == ("system", "user")
    for expected in (problem.prompt, problem.signature, problem.reference_tests[0]):
        assert expected in user["content"]
    for hidden in (problem.reference_tests[1], problem.reference_tests[2], problem.reference_code.strip()):
        assert hidden not in user["content"]


def test_settings_come_from_config(problem, tmp_path):
    llm = FakeLLM(GOOD_REPLY)
    CodeGeneratorAgent(llm).run(problem, tmp_path / "llm_calls.jsonl")
    call = llm.calls[0]
    assert {key: call[key] for key in config.CODEGEN_SETTINGS} == config.CODEGEN_SETTINGS
    assert call["agent"] == "code_generator"


def test_good_reply_gives_clean_code(problem, tmp_path):
    result = CodeGeneratorAgent(FakeLLM(GOOD_REPLY)).run(problem, tmp_path / "llm_calls.jsonl")
    assert (result.ok, result.error) == (True, None)
    assert result.code == "def remove_Occ(s, ch):\n    return s\n"


def test_wrong_function_name_is_rejected(problem, tmp_path):
    reply = "```python\ndef remove(s, ch):\n    return s\n```"
    result = CodeGeneratorAgent(FakeLLM(reply)).run(problem, tmp_path / "llm_calls.jsonl")
    assert not result.ok and "remove_Occ" in result.error


def test_reply_without_code_is_rejected(problem, tmp_path):
    result = CodeGeneratorAgent(FakeLLM("Sorry, I can't do that.")).run(problem, tmp_path / "llm_calls.jsonl")
    assert not result.ok and result.raw_response == "Sorry, I can't do that."


def test_failed_call_is_reported_not_raised(problem, tmp_path):
    result = CodeGeneratorAgent(FakeLLM(error=LLMError("all models failed"))).run(problem, tmp_path / "x.jsonl")
    assert not result.ok and "all models failed" in result.error


def test_fatal_error_stops_the_run(problem, tmp_path):
    with pytest.raises(FatalLLMError):
        CodeGeneratorAgent(FakeLLM(error=FatalLLMError("no key"))).run(problem, tmp_path / "x.jsonl")
