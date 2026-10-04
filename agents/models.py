"""Data classes shared by all agents (PROJECT_PLAN.md §3.5). Phase 2 is written against these."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Problem:
    task_id: int
    prompt: str                   # problem text from MBPP
    entry_point: str              # e.g. "remove_Occ"
    signature: str                # e.g. "def remove_Occ(s, ch):"
    reference_code: str           # MBPP reference solution (never shown to an LLM)
    reference_tests: list[str]    # MBPP's 3 assert statements
    test_imports: list[str]


@dataclass
class LLMResponse:
    content: str
    model: str                    # the model that actually answered
    usage: dict                   # token counts, including completion_tokens_details.reasoning_tokens
    cached: bool
    latency_s: float


@dataclass
class AgentResult:
    """Returned by both LLM agents."""
    ok: bool
    code: str | None              # extracted Python source (solution or test file)
    raw_response: str
    error: str | None


@dataclass
class ExecutionResult:
    status: str                            # "RAN" | "ERROR" | "TIMEOUT"
    tests_total: int
    tests_passed: int
    tests_failed: int                      # failures + errors (+ skips: a skipped test verified nothing)
    test_outcomes: dict[str, str]          # test name -> "passed" | "failed"
    statement_coverage: float              # 0-100, coverage.py percent_statements_covered
    branch_coverage: float                 # 0-100, coverage.py percent_branches_covered (100 if no branches)
    missing_lines: list[int]
    missing_branches: list[list[int]]      # [from_line, to_line]; a negative to_line means "exit the function"
    target_met: bool
    verdict: str                           # PASS | TESTS_FAILED | COVERAGE_NOT_MET | ERROR (§3.7)
    output_tail: str                       # last ~40 lines of pytest output, for debugging
    criterion: str = "branch"
    target: float = 100.0
    num_statements: int = 0
    num_branches: int = 0
    exit_code: int | None = None
    duration_s: float = 0.0
    # Edge-pair ("loops") coverage. Measured only for criterion="loops", which needs a second, untraced
    # pytest pass (agents/path_coverage.py); the defaults keep every other run exactly as it was.
    edge_pair_coverage: float = 0.0        # 0-100 (100 if the code has no decisions at all)
    num_edge_pairs: int = 0
    missing_edge_pairs: list[list[int]] = field(default_factory=list)   # [line_a, line_b, line_c]


def load_problems(path: Path | str) -> list[Problem]:
    """Load the problem subset written by data/prepare_dataset.py."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Problem(**item) for item in data]
