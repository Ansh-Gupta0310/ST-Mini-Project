"""Offline tests for agents/llm_client.py: the network is replaced by scripted fake replies."""
import json

import pytest

import agents.llm_client as llm_client
from agents.llm_client import FatalLLMError, LLMClient, LLMError, QuotaExhaustedError

FAKE_KEY = "sk-or-v1-FAKE-KEY-FOR-TESTS"
MESSAGES = [{"role": "user", "content": "write f"}]


class FakeReply:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = json.dumps(payload) if payload is not None else ""

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


def ok(content="def f():\n    return 1", model="main/model"):
    usage = {"prompt_tokens": 5, "completion_tokens": 7, "completion_tokens_details": {"reasoning_tokens": 0}}
    return FakeReply(200, {"model": model, "choices": [{"message": {"content": content}}], "usage": usage})


def error(code, message="something went wrong"):
    return FakeReply(code, {"error": {"code": code, "message": message}})


@pytest.fixture
def network(monkeypatch):
    """Scripted replacement for requests.post. Append replies (or exceptions) to `script`."""
    script, sent = [], []

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.append({"url": url, "body": json, "headers": headers})
        if not script:
            raise AssertionError("unexpected network call")
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(llm_client.requests, "post", fake_post)
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    return script, sent


def make_client(tmp_path, max_retries=2):
    return LLMClient(model="main/model", fallback_models=["backup/model"], cache_dir=tmp_path / "cache",
                     min_interval_s=0, retry_waits_s=[0], max_retries=max_retries)


def ask(client, tmp_path, messages=MESSAGES):
    return client.chat(messages, temperature=0.2, max_tokens=50, seed=42, agent="test",
                       log_path=tmp_path / "llm_calls.jsonl")


def log_lines(tmp_path):
    return [json.loads(line) for line in (tmp_path / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()]


def test_request_has_settings_and_reasoning_disabled(network, tmp_path):
    script, sent = network
    script.append(ok())
    ask(make_client(tmp_path), tmp_path)
    body = sent[0]["body"]
    assert body["model"] == "main/model"
    assert (body["temperature"], body["top_p"], body["max_tokens"], body["seed"]) == (0.2, 1.0, 50, 42)
    assert body["reasoning"] == {"enabled": False}
    assert body["messages"] == MESSAGES


def test_second_identical_request_comes_from_cache(network, tmp_path):
    script, sent = network
    script.append(ok())
    client = make_client(tmp_path)
    first = ask(client, tmp_path)
    second = ask(client, tmp_path)
    assert len(sent) == 1
    assert (first.cached, second.cached) == (False, True)
    assert second.content == first.content and second.model == "main/model"
    assert [line["cached"] for line in log_lines(tmp_path)] == [False, True]


def test_different_request_is_not_served_from_cache(network, tmp_path):
    script, sent = network
    script.extend([ok(), ok()])
    client = make_client(tmp_path)
    ask(client, tmp_path)
    ask(client, tmp_path, messages=[{"role": "user", "content": "write g"}])
    assert len(sent) == 2


def test_rate_limit_is_retried_then_succeeds(network, tmp_path):
    script, sent = network
    script.extend([error(429, "temporarily rate-limited upstream"), ok()])
    response = ask(make_client(tmp_path), tmp_path)
    assert response.content.startswith("def f")
    assert [s["body"]["model"] for s in sent] == ["main/model", "main/model"]


def test_network_exception_is_retried(network, tmp_path):
    script, sent = network
    script.extend([llm_client.requests.ConnectionError("boom"), ok()])
    ask(make_client(tmp_path), tmp_path)
    assert len(sent) == 2


def test_empty_reply_is_retried(network, tmp_path):
    script, sent = network
    script.extend([ok(content="  "), ok()])
    assert ask(make_client(tmp_path), tmp_path).content.startswith("def f")
    assert len(sent) == 2


def test_falls_back_to_next_model_after_retries(network, tmp_path):
    script, sent = network
    script.extend([error(503), error(503), ok(model="backup/model")])
    response = ask(make_client(tmp_path, max_retries=1), tmp_path)
    assert response.model == "backup/model"
    assert [s["body"]["model"] for s in sent] == ["main/model", "main/model", "backup/model"]
    assert log_lines(tmp_path)[0]["model_used"] == "backup/model"


def test_other_client_error_skips_straight_to_next_model(network, tmp_path):
    script, sent = network
    script.extend([error(404, "model not found"), ok(model="backup/model")])
    assert ask(make_client(tmp_path), tmp_path).model == "backup/model"
    assert len(sent) == 2


def test_daily_quota_stops_immediately(network, tmp_path):
    script, sent = network
    script.append(error(429, "Rate limit exceeded: free-models-per-day"))
    with pytest.raises(QuotaExhaustedError):
        ask(make_client(tmp_path), tmp_path)
    assert len(sent) == 1


def test_rejected_key_is_fatal(network, tmp_path):
    script, sent = network
    script.append(error(401, "User not found"))
    with pytest.raises(FatalLLMError):
        ask(make_client(tmp_path), tmp_path)
    assert len(sent) == 1


def test_all_models_failing_raises_and_is_logged(network, tmp_path):
    script, _ = network
    script.extend([error(500), error(500)])
    with pytest.raises(LLMError) as info:
        ask(make_client(tmp_path, max_retries=0), tmp_path)
    assert not isinstance(info.value, FatalLLMError)
    line = log_lines(tmp_path)[0]
    assert "error" in line and len(line["attempts"]) == 2


def test_missing_key_only_matters_when_the_network_is_needed(network, tmp_path, monkeypatch):
    script, _ = network
    script.append(ok())
    client = make_client(tmp_path)
    ask(client, tmp_path)                                  # cached with the key present
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert ask(client, tmp_path).cached is True            # cache still works without a key
    with pytest.raises(FatalLLMError):
        ask(client, tmp_path, messages=[{"role": "user", "content": "new"}])


def test_key_is_never_written_to_log_or_cache(network, tmp_path):
    script, _ = network
    script.append(ok())
    ask(make_client(tmp_path), tmp_path)
    written = (tmp_path / "llm_calls.jsonl").read_text(encoding="utf-8")
    written += "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "cache").glob("*.json"))
    assert FAKE_KEY not in written
    assert "Authorization" not in written
