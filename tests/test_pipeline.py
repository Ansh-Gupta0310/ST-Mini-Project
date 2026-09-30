"""Offline tests for pipeline.py --mode baseline: real agents and executor, only the network is faked."""
import json

import pytest

import config
import pipeline
from agents import llm_client
from agents.models import load_problems

PROBLEMS = {p.task_id: p for p in load_problems(config.DATA_FILE)}


class FakeReply:
    def __init__(self, status_code, payload):
        self.status_code, self._payload, self.headers = status_code, payload, {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def reply_with(content):
    return FakeReply(200, {"model": "fake/model", "choices": [{"message": {"content": content}}],
                           "usage": {"prompt_tokens": 10, "completion_tokens": 20}})


def code_reply(code):
    return reply_with(f"```python\n{code}```")


@pytest.fixture
def network(monkeypatch, tmp_path):
    """Replies are chosen by the function name in the prompt. Nothing touches the real llm_cache/."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "MIN_SECONDS_BETWEEN_CALLS", 0)
    monkeypatch.setattr(config, "RETRY_WAITS_S", [0])
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-FAKE-KEY-FOR-TESTS")
    replies, sent = {}, []

    def fake_post(url, json=None, headers=None, timeout=None):
        prompt = json["messages"][-1]["content"]
        sent.append(prompt)
        for name, reply in replies.items():
            if f"def {name}(" in prompt:
                return reply
        raise AssertionError("no scripted reply for this prompt")

    monkeypatch.setattr(llm_client.requests, "post", fake_post)
    return replies, sent


def run(tmp_path, *task_ids):
    out = tmp_path / "out"
    exit_code = pipeline.main(["--mode", "baseline", "--out", str(out), "--task-ids", *map(str, task_ids)])
    return exit_code, out, json.loads((out / "summary.json").read_text(encoding="utf-8"))


def test_baseline_run_end_to_end(network, tmp_path):
    replies, _ = network
    replies["remove_Occ"] = code_reply(PROBLEMS[11].reference_code)
    replies["is_woodall"] = reply_with("I don't know.")
    exit_code, out, summary = run(tmp_path, 11, 20)

    assert exit_code == 0
    v11, v20 = summary["problems"]
    assert (v11["status"], v11["code_correct"]) == ("COMPLETED", True)
    assert (v11["baseline"]["tests_passed"], v11["baseline"]["tests_total"]) == (3, 3)
    assert (v20["status"], v20["code_correct"], v20["baseline"]) == ("CODEGEN_FAILED", False, None)
    assert (out / "Mbpp_20" / "codegen_reply.txt").read_text(encoding="utf-8") == "I don't know."
    for name in ("problem.json", "llm_calls.jsonl", "solution.py", "verdict.json", "reference/execution.json"):
        assert (out / "Mbpp_11" / name).exists(), name

    agg = summary["aggregate"]
    assert (agg["problems_run"], agg["code_generated"], agg["code_correct"]) == (2, 1, 1)
    assert (agg["llm_calls"], agg["llm_requests_sent"], agg["models_used"]) == (2, 2, ["fake/model"])
    assert json.loads((out / "config.json").read_text(encoding="utf-8"))["task_ids"] == [11, 20]
    assert "| 11 | `remove_Occ` | COMPLETED | yes | 3/3 |" in (out / "summary.md").read_text(encoding="utf-8")


def test_rerun_is_served_from_the_cache(network, tmp_path):
    replies, sent = network
    replies["remove_Occ"] = code_reply(PROBLEMS[11].reference_code)
    run(tmp_path, 11)
    _, _, summary = run(tmp_path, 11)
    assert len(sent) == 1
    assert (summary["aggregate"]["llm_cached_calls"], summary["aggregate"]["llm_requests_sent"]) == (1, 0)


def test_used_up_quota_stops_the_run(network, tmp_path):
    replies, sent = network
    replies["remove_Occ"] = FakeReply(429, {"error": {"code": 429,
                                                      "message": "Rate limit exceeded: free-models-per-day"}})
    exit_code, _, summary = run(tmp_path, 11, 20)
    assert exit_code == 1 and len(sent) == 1
    assert "quota" in summary["stopped_early"].lower()
    assert summary["aggregate"]["problems_run"] == 0


def test_one_broken_problem_does_not_stop_the_run(network, tmp_path, monkeypatch):
    replies, _ = network
    replies["remove_Occ"] = code_reply(PROBLEMS[11].reference_code)
    replies["is_woodall"] = code_reply(PROBLEMS[20].reference_code)
    original = pipeline.reference_tests_to_pytest

    def crash_on_11(problem):
        if problem.task_id == 11:
            raise RuntimeError("simulated crash")
        return original(problem)

    monkeypatch.setattr(pipeline, "reference_tests_to_pytest", crash_on_11)
    exit_code, out, summary = run(tmp_path, 11, 20)
    assert exit_code == 0
    assert [v["status"] for v in summary["problems"]] == ["PIPELINE_ERROR", "COMPLETED"]
    assert "simulated crash" in (out / "Mbpp_11" / "error.txt").read_text(encoding="utf-8")


def test_unknown_task_id_is_rejected(tmp_path):
    with pytest.raises(SystemExit):
        pipeline.main(["--mode", "baseline", "--out", str(tmp_path / "out"), "--task-ids", "9999"])
