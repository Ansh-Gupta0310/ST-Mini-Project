"""Central configuration for the pipeline (PROJECT_PLAN.md §3.3).

Every run copies these values into its config.json, so the report can quote the exact settings.
The API key is only ever read from the environment; it is never stored in this file.
"""
from __future__ import annotations

import os
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "mbpp_subset.json"
CACHE_DIR = ROOT / "llm_cache"
PROMPTS_DIR = ROOT / "prompts"

# --- LLM access (OpenRouter) -------------------------------------------------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
API_KEY_ENV_VAR = "OPENROUTER_API_KEY"

PRIMARY_MODEL = "cohere/north-mini-code:free"
FALLBACK_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
]

# Sent with every request: no hidden chain of thought (PROJECT_PLAN.md §4).
REASONING = {"enabled": False}

CODEGEN_SETTINGS = {"temperature": 0.2, "top_p": 1.0, "max_tokens": 1024, "seed": 42}
# Tests get a slightly higher temperature (more varied inputs) and more room: a test file is longer
# than a solution. Changing these values changes the cache key, so every call becomes a new API call.
TESTGEN_SETTINGS = {"temperature": 0.4, "top_p": 1.0, "max_tokens": 2048, "seed": 42}

REQUEST_TIMEOUT_S = 120            # one HTTP request
MIN_SECONDS_BETWEEN_CALLS = 3      # spacing between network calls
MAX_RETRIES = 4                    # retries per model, after the first attempt
RETRY_WAITS_S = [5, 15, 30, 60]    # wait before retry 1, 2, 3, 4

# --- Test execution ----------------------------------------------------------------------
EXECUTOR_TIMEOUT_S = 30
CRITERIA = ("statement", "branch")
DEFAULT_CRITERION = "branch"
DEFAULT_TARGET = 100.0
DEFAULT_MAX_ROUNDS = 3             # used by --mode full (Phase 2)

# What the Test Generator is told to aim for. $target is filled in from --target (PROJECT_PLAN.md App. B).
CRITERION_GOALS = {
    "statement": "Reach $target% statement coverage: every executable line of solution.py must be run "
                 "by at least one test.",
    "branch": "Reach $target% branch coverage: every if/elif/while condition must be True in some test "
              "and False in some test, and every loop must run its body at least once and also finish "
              "at least once.",
}


def criterion_goal(criterion: str, target: float) -> str:
    """The goal sentence for this criterion, with the target percentage filled in."""
    if criterion not in CRITERION_GOALS:
        raise ValueError(f"criterion must be one of {tuple(CRITERION_GOALS)}, not {criterion!r}")
    return Template(CRITERION_GOALS[criterion]).substitute(target=f"{target:g}")


def get_api_key() -> str:
    """Return the OpenRouter key from the environment, or fail with a message that shows no secret."""
    key = os.environ.get(API_KEY_ENV_VAR, "").strip()
    if not key:
        raise RuntimeError(
            f"{API_KEY_ENV_VAR} is not set. Set it as a user environment variable or put it in a local "
            ".env file (see README.md), then restart VS Code."
        )
    return key


def load_env_file(path: Path | None = None) -> None:
    """Copy KEY=VALUE lines from a local .env into the environment, without overwriting real variables.

    A convenience for running from a plain terminal. .env is git-ignored, so the key still never reaches
    the repository, and a variable that is already set always wins.
    """
    path = ROOT / ".env" if path is None else Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if name and value and not os.environ.get(name):
            os.environ[name] = value


load_env_file()
