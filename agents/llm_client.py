"""OpenRouter chat client built on plain `requests` (no LLM framework, PROJECT_PLAN.md §4).

Features: response cache, retries with backoff, model fallback, and one JSON log line per call.
The API key is read from the environment and is never printed, logged or cached.

Command line:
    python -m agents.llm_client --ping     one tiny request (served from the cache after the first time)
    python -m agents.llm_client --quota    free-model requests used / remaining today (no model call)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import config
from agents.models import LLMResponse

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
FATAL_STATUS = {401, 402}  # rejected key / payment required: no other model will do better


class LLMError(RuntimeError):
    """A call failed: no model produced a usable reply. The run can continue with the next problem."""

    def __init__(self, message: str, attempts: list[dict] | None = None):
        super().__init__(message)
        self.attempts = attempts or []


class FatalLLMError(LLMError):
    """Continuing the run is pointless (missing or rejected key, payment required)."""


class QuotaExhaustedError(FatalLLMError):
    """The daily free-model quota is used up."""


class LLMClient:
    """Sends chat requests to OpenRouter. One instance is shared by all agents in a run.

    Arguments left as None are read from config.py when the client is created.
    """

    def __init__(
        self,
        model: str | None = None,
        fallback_models: list[str] | None = None,
        cache_dir: Path | str | None = None,
        min_interval_s: float | None = None,
        retry_waits_s: list[float] | None = None,
        max_retries: int | None = None,
    ):
        self.model = model or config.PRIMARY_MODEL
        self.fallback_models = list(config.FALLBACK_MODELS if fallback_models is None else fallback_models)
        self.cache_dir = Path(config.CACHE_DIR if cache_dir is None else cache_dir)
        self.min_interval_s = config.MIN_SECONDS_BETWEEN_CALLS if min_interval_s is None else min_interval_s
        self.retry_waits_s = list(config.RETRY_WAITS_S if retry_waits_s is None else retry_waits_s)
        self.max_retries = config.MAX_RETRIES if max_retries is None else max_retries
        self.network_calls = 0          # HTTP requests actually sent by this client
        self._last_call: float | None = None

    def chat(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
        agent: str,
        log_path: Path | str,
        top_p: float = 1.0,
        seed: int | None = None,
    ) -> LLMResponse:
        """Return the model's reply, from the cache if this exact request was made before."""
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "reasoning": config.REASONING,
        }
        if seed is not None:
            body["seed"] = seed
        key = cache_key(body)
        entry = {"time": _now(), "agent": agent, "cache_key": key, "request": body}

        hit = self._read_cache(key)
        if hit is not None:
            response = LLMResponse(hit["content"], hit["model"], hit.get("usage") or {}, cached=True, latency_s=0.0)
            _append_jsonl(log_path, {**entry, **_response_fields(response), "attempts": []})
            return response

        try:
            response, attempts = self._call_with_fallback(body)
        except LLMError as exc:
            _append_jsonl(log_path, {**entry, "cached": False, "error": str(exc), "attempts": exc.attempts})
            raise
        self._write_cache(key, body, response)
        _append_jsonl(log_path, {**entry, **_response_fields(response), "attempts": attempts})
        return response

    # --- network -------------------------------------------------------------------------

    def _call_with_fallback(self, body: dict) -> tuple[LLMResponse, list[dict]]:
        attempts: list[dict] = []
        try:
            api_key = config.get_api_key()
        except RuntimeError as exc:
            raise FatalLLMError(str(exc), attempts) from None

        for model in [self.model, *self.fallback_models]:
            retry_after = None
            for attempt in range(self.max_retries + 1):
                if attempt:
                    self._wait_before_retry(model, attempt, retry_after, attempts[-1]["error"])
                result = self._post({**body, "model": model}, api_key)
                attempts.append({k: result[k] for k in ("model", "status", "error", "latency_s")})
                kind = result["kind"]
                if kind == "ok":
                    response = LLMResponse(result["content"], result["model"], result["usage"],
                                           cached=False, latency_s=result["latency_s"])
                    return response, attempts
                if kind == "quota":
                    raise QuotaExhaustedError(
                        "Daily free-model quota is used up (check: python -m agents.llm_client --quota). "
                        + result["error"], attempts)
                if kind == "fatal":
                    raise FatalLLMError(result["error"], attempts)
                if kind == "next_model":
                    break
                retry_after = result["retry_after"]
        raise LLMError(f"all models failed; last error: {attempts[-1]['error']}", attempts)

    def _post(self, request: dict, api_key: str) -> dict:
        """Send one request and classify the outcome as ok / retry / next_model / quota / fatal."""
        self._respect_min_interval()
        result = {"kind": "retry", "model": request["model"], "status": None, "error": None,
                  "latency_s": 0.0, "retry_after": None, "content": None, "usage": {}}
        start = time.monotonic()
        try:
            reply = requests.post(
                config.OPENROUTER_URL,
                json=request,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=config.REQUEST_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            result["error"] = f"network error: {type(exc).__name__}"
            return result
        finally:
            self._last_call = time.monotonic()
            self.network_calls += 1
            result["latency_s"] = round(self._last_call - start, 2)

        try:
            data = reply.json()
        except ValueError:
            data = None
        data = data if isinstance(data, dict) else {}
        error = data.get("error")
        result["status"] = reply.status_code

        if reply.status_code == 200 and not error:
            choices = data.get("choices") or [{}]
            content = ((choices[0] or {}).get("message") or {}).get("content") or ""
            if isinstance(content, list):  # some providers return a list of content parts
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            if content.strip():
                result.update(kind="ok", content=content, model=data.get("model") or request["model"],
                              usage=data.get("usage") or {})
            else:
                result["error"] = "empty reply"
            return result

        code = reply.status_code
        message = (reply.text or "")[:300]
        if isinstance(error, dict):
            if isinstance(error.get("code"), int):
                code = error["code"]
            raw = (error.get("metadata") or {}).get("raw")
            message = " ".join(str(part) for part in (error.get("message"), raw) if part)
        result["status"] = code
        result["error"] = f"HTTP {code}: {message}"[:500]
        retry_after = (reply.headers or {}).get("Retry-After")
        try:
            result["retry_after"] = float(retry_after) if retry_after else None
        except ValueError:
            pass

        lowered = message.lower()
        if code == 429 and ("per-day" in lowered or "per day" in lowered):
            result["kind"] = "quota"
        elif code in FATAL_STATUS:
            result["kind"] = "fatal"
        elif code in RETRYABLE_STATUS:
            result["kind"] = "retry"
        else:  # other 4xx (bad request, model not found, ...): this model will not work, try the next one
            result["kind"] = "next_model"
        return result

    def _respect_min_interval(self) -> None:
        if self._last_call is None or self.min_interval_s <= 0:
            return
        remaining = self.min_interval_s - (time.monotonic() - self._last_call)
        if remaining > 0:
            time.sleep(remaining)

    def _wait_before_retry(self, model: str, attempt: int, retry_after: float | None, last_error: str) -> None:
        planned = self.retry_waits_s[min(attempt - 1, len(self.retry_waits_s) - 1)] if self.retry_waits_s else 0
        wait = max(planned, min(retry_after or 0, 120))
        print(f"    [llm] {model}: {last_error[:90]} -> retry {attempt}/{self.max_retries} in {wait:.0f}s",
              file=sys.stderr, flush=True)
        if wait > 0:
            time.sleep(wait)

    # --- cache ---------------------------------------------------------------------------

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> dict | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            response = json.loads(path.read_text(encoding="utf-8"))["response"]
        except (ValueError, KeyError, OSError):
            return None  # a damaged cache file is ignored and later overwritten
        if not isinstance(response, dict) or "content" not in response or "model" not in response:
            return None
        return response

    def _write_cache(self, key: str, body: dict, response: LLMResponse) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "created_at": _now(),
            "request": body,
            "response": {"content": response.content, "model": response.model, "usage": response.usage},
            "latency_s": response.latency_s,
        }
        path = self._cache_path(key)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)  # atomic: an interrupted run never leaves a half-written cache file


def cache_key(body: dict) -> str:
    """SHA-256 of the request body: the same prompt, model and settings give the same key on any machine."""
    text = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _response_fields(response: LLMResponse) -> dict:
    return {"cached": response.cached, "model_used": response.model, "response": response.content,
            "usage": response.usage, "latency_s": response.latency_s}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append_jsonl(path: Path | str, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# --- command line ------------------------------------------------------------------------

def _ping() -> int:
    client = LLMClient()
    messages = [{"role": "system", "content": "Reply with the single word: pong"},
                {"role": "user", "content": "ping"}]
    response = client.chat(messages, temperature=0.0, max_tokens=20, seed=42, agent="ping",
                           log_path=config.ROOT / "runs" / "ping" / "llm_calls.jsonl")
    details = response.usage.get("completion_tokens_details") or {}
    print(f"model={response.model} cached={response.cached} "
          f"reasoning_tokens={details.get('reasoning_tokens')} reply={response.content.strip()!r}")
    return 0


def _quota() -> int:
    reply = requests.get(config.OPENROUTER_KEY_URL, timeout=30,
                         headers={"Authorization": f"Bearer {config.get_api_key()}"})
    if reply.status_code != 200:
        print(f"Could not read the quota: HTTP {reply.status_code}")
        return 1
    data = reply.json().get("data") or {}
    quota = data.get("free_model_daily_requests") or {}
    print(f"free-model requests today: used {quota.get('used')} of {quota.get('limit')} "
          f"(remaining {quota.get('remaining')}); free tier: {data.get('is_free_tier')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenRouter client helpers.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ping", action="store_true", help="send one tiny request (cached after the first time)")
    group.add_argument("--quota", action="store_true", help="show today's free-model quota (no model call)")
    args = parser.parse_args(argv)
    try:
        return _ping() if args.ping else _quota()
    except (LLMError, RuntimeError, requests.RequestException) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
