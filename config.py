"""Central configuration for the pipeline (PROJECT_PLAN.md §3.3).

Every run copies these values into its config.json, so the report can quote the exact settings.
The API key is only ever read from the environment; it is never stored in this file.
"""
from __future__ import annotations

import os
from pathlib import Path

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
TESTGEN_SETTINGS: dict = {}  # Phase 2 fills this in (PROJECT_PLAN.md §3.3)

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


def get_api_key() -> str:
    """Return the OpenRouter key from the environment, or fail with a message that shows no secret."""
    key = os.environ.get(API_KEY_ENV_VAR, "").strip()
    if not key:
        raise RuntimeError(
            f"{API_KEY_ENV_VAR} is not set. Set it as a Windows user environment variable "
            "(see README.md) and restart VS Code."
        )
    return key
