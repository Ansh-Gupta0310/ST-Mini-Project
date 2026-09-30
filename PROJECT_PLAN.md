# AI-Assisted Unit Testing Pipeline — Project Plan

**Course:** CSE731 Software Testing · IIIT Bangalore · Mid-term Project, Term I (2026-27)
**Team:** Member 1 — `<name>` (GitHub `@Ansh-Gupta0310`) · Member 2 — `<name>` (GitHub `@<username>`)
**Repository:** https://github.com/Ansh-Gupta0310/ST-Mini-Project
**Requirement chosen:** (1) a user-specified **coverage criterion** (statement or branch coverage)
**Dataset:** MBPP (sanitized), a fixed subset of 12 problems
**Plan written:** 30 Sep 2026 · **Submission closes:** 1 Oct 2026 (check the exact time on the LMS) · **Demos:** 1 / 6 / 8 Oct 2026, lecture slots

> This file is the single source of truth for the project. If the implementation has to differ from it,
> update this file in the same pull request.

**Status (1 Oct 2026):** Phase 1 is implemented and verified (branch `phase-1-foundation`, PR #1). Phase 2 is
implemented on branch `phase-2-test-generation`: Test Generator agent, coverage feedback loop, test validation
and `pipeline.py --mode full`, with the official run in `results/phase2_branch100/`. Where the implementation
extends this plan, the change is recorded in place and marked **[Phase 2 decision]**.

## Contents

1. [What we are building](#1-what-we-are-building)
2. [Key concepts](#2-key-concepts)
3. [System design](#3-system-design)
4. [How we follow the assignment's rules](#4-how-we-follow-the-assignments-rules)
5. [Work split](#5-work-split)
6. [Phase 1 — Member 1, step by step](#6-phase-1--member-1-step-by-step)
7. [Phase 2 — Member 2 via pull request, step by step](#7-phase-2--member-2-via-pull-request-step-by-step)
8. [Pull request workflow](#8-pull-request-workflow)
9. [API quota budget](#9-api-quota-budget)
10. [Timeline](#10-timeline)
11. [Report plan](#11-report-plan)
12. [Demo plan](#12-demo-plan)
13. [Risks and mitigations](#13-risks-and-mitigations)
- [Appendix A — Facts verified on 30 Sep 2026](#appendix-a--facts-verified-on-30-sep-2026)
- [Appendix B — Draft prompts](#appendix-b--draft-prompts)

---

## 1. What we are building

A Python program that, for each programming problem in our MBPP subset:

1. asks an LLM to **write the function** (Code Generator agent),
2. asks an LLM to **write pytest unit tests** for that function, aimed at a coverage goal the user chooses, for example
   "100% branch coverage" (Test Generator agent),
3. **runs the tests**, measures coverage and gives a verdict (Test Executor agent),
4. if the coverage goal is not met, sends the uncovered lines and branches back to the Test Generator for more tests
   (at most 3 rounds in total).

### 1.1 Assignment requirements and how we meet them

| Assignment requirement | How we meet it |
|---|---|
| Code generator agent | `CodeGeneratorAgent`: MBPP problem → `solution.py` |
| Test case generator agent that satisfies **one** requirement | `TestGeneratorAgent` targets a **user-specified coverage criterion**: `--criterion statement\|branch --target 100` |
| Test case executor agent that gives a verdict | `TestExecutorAgent`: runs pytest + coverage.py and returns `PASS` / `TESTS_FAILED` / `COVERAGE_NOT_MET` / `ERROR` |
| Dataset: MBPP or HumanEval | MBPP sanitized, 12 problems from its official test split (§3.4) |
| Free tokens | OpenRouter free model `cohere/north-mini-code:free` (§3.3) |
| No RAG, no chain of thought, no LangGraph | See §4 |
| Report items 1–5 | See §11 |

### 1.2 Decisions at a glance

| Decision | Choice | Reason |
|---|---|---|
| Testing goal | Coverage: statement or branch, with a target % | Objective and measurable with a standard tool (coverage.py); easy to demo |
| Default criterion / target | Branch coverage, 100% | Stronger than statement coverage; statement coverage is also supported |
| Dataset | MBPP sanitized, 12 problems | Plain-English problems, a reference solution and 3 reference asserts per problem; 12 fits the free quota |
| LLM access | Plain HTTP calls to OpenRouter using `requests` | "First principles": no agent framework |
| Model | `cohere/north-mini-code:free`, with two fallbacks | Code model; worked in testing with 0 reasoning tokens |
| What the Code Generator sees | Problem text + function signature + **1** of the 3 MBPP asserts | The one assert fixes the input/output format (for example, `True` vs `"Yes"`) |
| What the Test Generator sees | Problem text + the example assert + the **generated** code with line numbers | White-box: it needs the code to aim at specific branches |
| What the Test Generator never sees | The MBPP reference solution | Keeps the reference as an independent check on the tests |
| Executor | Deterministic (pytest + coverage.py), no LLM | A verdict must be a measured fact, not a model's opinion |
| Baseline | MBPP's own 3 asserts, run against the generated code | Lets us compare "dataset tests" vs "LLM tests targeted at coverage" |

---

## 2. Key concepts

Both members should be able to explain these in the demo.

### 2.1 Unit under test

One Python function: the function the Code Generator wrote, saved as `solution.py`. Coverage is measured on
`solution.py` only, never on the test file.

### 2.2 Statement coverage

The percentage of executable lines in `solution.py` that at least one test runs.

### 2.3 Branch (decision) coverage

The percentage of decision outcomes the tests exercise: every `if`/`elif`/`while` condition must be **both
True and False** in some test, and every loop must both run its body and finish. coverage.py measures this as
"arcs", meaning jumps from one line to another.

Worked example (verified with coverage.py 7.16.2):

```python
1  def sign(x):
2      if x > 0:
3          return 1
4      elif x < 0:
5          return -1
6      return 0
```

| Tests | Statement coverage | Branch coverage | What is missing |
|---|---|---|---|
| `sign(5)` only | 50% (3 of 6 lines; the `def` line counts) | 25% (1 of 4 branches) | lines 4, 5, 6; branches 2→4, 4→5, 4→6 |
| `sign(5)`, `sign(-5)`, `sign(0)` | 100% | 100% | nothing |

The 4 branches are 2→3 (x > 0 is True), 2→4 (x > 0 is False), 4→5 (x < 0 is True) and 4→6 (x < 0 is False).

### 2.4 The test oracle problem

A test is only useful if its **expected value** is right. If the LLM works out expected values by reading the
generated code, and that code has a bug, the test simply agrees with the bug. We handle this in two ways:

- the Test Generator prompt says to take expected values from the **problem description**, not from the code;
- Phase 2 re-runs every generated test against MBPP's **reference solution** and labels each test (§3.7).

### 2.5 What "agent" means in this project

An agent is a component with one role, fixed instructions, and defined inputs and outputs. The two LLM agents
call the model. The Executor agent uses tools (pytest, coverage.py) and decides the verdict with fixed rules.
The orchestrator (`pipeline.py`) is ordinary Python that calls the agents in a fixed order.

---

## 3. System design

### 3.1 Pipeline

```
MBPP problem (data/mbpp_subset.json)
   │
   ▼
[1] CODE GENERATOR AGENT  (LLM)                                    Phase 1
    in : problem text + function signature + 1 example assert
    out: solution.py
   │
   ▼
[2] TEST EXECUTOR AGENT — correctness check  (no LLM)              Phase 1
    runs MBPP's 3 reference asserts against solution.py
    out: code_correct (yes/no) + baseline coverage
   │
   ▼
[3] TEST GENERATOR AGENT  (LLM)                                    Phase 2
    in : problem text + example assert + numbered solution.py + coverage goal
    out: test_solution.py  (pytest)
   │
   ▼
[4] TEST EXECUTOR AGENT — coverage run  (no LLM)                   built in Phase 1,
    runs test_solution.py with pytest + coverage.py                used in Phase 2
    out: pass/fail per test, statement %, branch %,
         missing lines and branches, verdict
   │
   ├── goal not met and rounds < max?  ──► back to [3] with the missing lines/branches
   │                                         (new tests are added to the existing ones)
   ▼
[5] TEST VALIDATION  (no LLM)                                      Phase 2
    re-runs the final tests against MBPP's reference solution
    out: each test labelled VALID / BUG_FOUND / INVALID_TEST / MISLEADING
   │
   ▼
verdict.json for each problem + summary.md for the whole run
```

### 3.2 The agents

| Agent | File | Uses an LLM? | Input | Output |
|---|---|---|---|---|
| Code Generator | `agents/code_generator.py` | Yes (temperature 0.2) | `Problem` | `solution.py` source |
| Test Generator | `agents/test_generator.py` | Yes (temperature 0.4) | `Problem`, solution source, criterion, target, optional coverage feedback | pytest file source |
| Test Executor | `agents/test_executor.py` | No: runs pytest + coverage.py | solution source, test source, criterion, target | `ExecutionResult` with a verdict |

### 3.3 LLM settings

| Setting | Code Generator | Test Generator | Why |
|---|---|---|---|
| Model | `cohere/north-mini-code:free` | same | Code model; returned clean code with 0 reasoning tokens when tested on 30 Sep |
| Fallback models (in order) | `nvidia/nemotron-3-super-120b-a12b:free`, `google/gemma-4-31b-it:free` | same | Used only if the main model keeps failing; the model that actually answered is logged for every call |
| `temperature` | 0.2 | 0.4 | Code must be precise; tests benefit from slightly more varied inputs |
| `top_p` | 1.0 | 1.0 | Default |
| `max_tokens` | 1024 | 2048 | Test files are longer than solutions |
| `seed` | 42 | 42 | Repeatable output where the provider supports it (Cohere does) |
| `reasoning` | `{"enabled": false}` | same | No hidden chain of thought (§4) |

- **Endpoint:** `POST https://openrouter.ai/api/v1/chat/completions`, called with `requests`.
- **API key:** read only from the `OPENROUTER_API_KEY` environment variable. It is never printed, logged,
  cached or committed. **[Phase 2 decision]** `config.load_env_file()` copies `KEY=VALUE` lines from a local,
  git-ignored `.env` into the environment at start-up, without overwriting a variable that is already set. This
  only changes where the variable comes from; the key still never reaches the repository, the logs or the cache.
- **Executor settings:** 30 s timeout per run; default criterion `branch`; default target `100`; default
  max rounds `3`.
- All of these values live in `config.py`. Every run saves the values it used in `config.json`, which is
  where report item 2 gets its numbers. **[Phase 2 decision]** `config.TESTGEN_SETTINGS` was filled in with the
  planned values (`temperature` 0.4, `top_p` 1.0, `max_tokens` 2048, `seed` 42), and `config.criterion_goal
  (criterion, target)` fills `$target` into the `CRITERION_GOALS` text (Appendix B) for the prompt and for
  `config.json`.

### 3.4 Dataset and problem selection

- **Source:** `sanitized-mbpp.json` from
  `https://raw.githubusercontent.com/google-research/google-research/master/mbpp/sanitized-mbpp.json`.
  It has 427 problems with fields `task_id`, `prompt`, `code`, `test_imports`, `test_list` and `source_file`.
- **Official test split:** `task_id` 11–510, which is 257 problems in the sanitized version.
- **Selection rule (deterministic, so anyone gets the same 12):**
  1. the problem is in the test split (11–510);
  2. its reference solution has **at least 2 decision points** (`if`/`elif`, `for`, `while`, ternary,
     `try`, `if` inside a comprehension), counted with Python's `ast` module;
  3. its reference solution is at most 25 lines;
  4. from the 90 problems that pass rules 1–3, take the **first 12 by `task_id`**.
- **Why at least 2 decision points:** 113 of the 257 test-split problems have no decisions at all. They are
  one-line functions where a single test already gives 100% coverage, so there is nothing to measure.
- **Result (verified):**

  | task_id | function | task_id | function | task_id | function |
  |---|---|---|---|---|---|
  | 11 | `remove_Occ` | 67 | `bell_number` | 79 | `word_len` |
  | 20 | `is_woodall` | 69 | `is_sublist` | 83 | `get_Char` |
  | 65 | `recursive_list_sum` | 70 | `get_equal` | 90 | `len_log` |
  | 66 | `pos_count` | 71 | `comb_sort` | 92 | `is_undulating` |

  All 12 reference solutions pass their own 3 asserts, and none need extra `test_imports`.
- **Derived fields:** `entry_point` is the function called in the first reference assert (this works for all
  427 problems). `signature` is that function's `def` line in the reference code.
- **Why 12:** the free quota (§9).
- **Note:** coverage is measured on the **generated** solution, which can have more or fewer branches than
  the reference solution.

### 3.5 Data contracts

Phase 2 is written against these. **Do not change them without updating this section.**

`agents/models.py` (Phase 1):

```python
@dataclass
class Problem:
    task_id: int
    prompt: str                  # problem text from MBPP
    entry_point: str             # e.g. "remove_Occ"
    signature: str               # e.g. "def remove_Occ(s,ch):"
    reference_code: str          # MBPP reference solution (never shown to an LLM)
    reference_tests: list[str]   # MBPP's 3 assert statements
    test_imports: list[str]

@dataclass
class LLMResponse:
    content: str
    model: str                   # the model that actually answered
    usage: dict                  # tokens, including reasoning_tokens
    cached: bool
    latency_s: float

@dataclass
class AgentResult:               # returned by both LLM agents
    ok: bool
    code: str | None             # extracted Python source (solution or test file)
    raw_response: str
    error: str | None

@dataclass
class ExecutionResult:
    status: str                  # "RAN" | "ERROR" | "TIMEOUT"
    tests_total: int
    tests_passed: int
    tests_failed: int            # failures + errors (+ skips: a skipped test verified nothing)
    test_outcomes: dict[str, str]        # test name -> "passed" | "failed"
    statement_coverage: float            # 0-100, from percent_statements_covered
    branch_coverage: float               # 0-100, from percent_branches_covered (100 if no branches)
    missing_lines: list[int]
    missing_branches: list[list[int]]    # [from_line, to_line]; a negative to_line means "exit the function"
    target_met: bool
    verdict: str                         # see §3.7
    output_tail: str                     # last ~40 lines of pytest output, for debugging
    criterion: str = "branch"
    target: float = 100.0
    num_statements: int = 0
    num_branches: int = 0
    exit_code: int | None = None         # pytest's exit code; None after a timeout
    duration_s: float = 0.0

def load_problems(path) -> list[Problem]  # reads data/mbpp_subset.json
```

Public functions and classes:

```python
# agents/llm_client.py                                         (Phase 1)
class LLMError(RuntimeError)               # one call failed on every model: the run continues with the next problem
class FatalLLMError(LLMError)              # missing or rejected key: the run must stop
class QuotaExhaustedError(FatalLLMError)   # daily free quota used up: the run must stop
class LLMClient:                           # constructor arguments default to the values in config.py
    def chat(self, messages: list[dict], *, temperature: float, max_tokens: int,
             agent: str, log_path: Path, top_p: float = 1.0, seed: int | None = None) -> LLMResponse
    # usage: llm.chat(messages, agent="test_generator", log_path=..., **config.TESTGEN_SETTINGS)

# agents/code_utils.py                                         (Phase 1, Phase 2 adds the last three)
def extract_python_code(text: str) -> str | None     # first ```python block (or whole reply); None if it doesn't parse
def remove_example_usage(code: str) -> str           # drops top-level main blocks, bare calls, asserts
def defines_function(code: str, name: str) -> bool   # is there a top-level def with this name?
def number_lines(code: str) -> str                   # "  1 | def f(x):" ...
def describe_missing(code: str, missing_lines: list[int],
                     missing_branches: list[list[int]]) -> str                              # Phase 2
def merge_test_files(existing: str, new: str, round_no: int) -> str                         # Phase 2
def check_test_file(test_code: str, entry_point: str) -> str | None   # error message or None  # Phase 2

# agents/code_generator.py                                     (Phase 1)
class CodeGeneratorAgent:
    def __init__(self, llm: LLMClient, settings: dict | None = None, prompts_dir: Path = config.PROMPTS_DIR)
    def run(self, problem: Problem, log_path: Path) -> AgentResult   # re-raises FatalLLMError

# agents/test_executor.py                                      (Phase 1, Phase 2 adds the last two)
def reference_tests_to_pytest(problem: Problem) -> str
def coverage_target_met(criterion, target, statement, branch) -> bool     # §3.7
def decide_verdict(status, tests_total, tests_failed, target_met) -> str  # §3.7
def remove_path(path: Path) -> None          # deletes a file/folder, including OneDrive's read-only folders
class TestExecutorAgent:
    __test__ = False                         # stops pytest from collecting the class as a test class
    def __init__(self, timeout_s: float = 30, html: bool = True)
    def run(self, solution_code: str, test_code: str, work_dir: Path,
            criterion: str = "branch", target: float = 100.0) -> ExecutionResult
            # work_dir = one execution folder (§3.10); run() also writes work_dir/execution.json
    def validate(self, test_code: str, problem: Problem, work_dir: Path,
                 on_generated: dict[str, str]) -> dict[str, str]                             # Phase 2
def classify_tests(on_generated: dict[str, str], on_reference: dict[str, str]) -> dict[str, str]  # Phase 2

# agents/test_generator.py                                     (Phase 2)
class TestGeneratorAgent:
    __test__ = False                         # same reason as TestExecutorAgent
    def __init__(self, llm: LLMClient, settings: dict | None = None, prompts_dir: Path = config.PROMPTS_DIR)
    def build_messages(self, problem, solution_code, criterion, target,
                       feedback=None, existing_tests=None, retry_note=None) -> list[dict]
    def run(self, problem: Problem, solution_code: str, criterion: str, target: float,
            log_path: Path, feedback: ExecutionResult | None = None,
            existing_tests: str | None = None,
            retry_note: str | None = None) -> AgentResult    # re-raises FatalLLMError
```

**[Phase 2 decision] `retry_note`** is an extra optional argument, appended to the user prompt after a round
that produced nothing usable ("Attempt 1 could not be used: ..."). Without it, retrying is pointless: the cache
key is the request body, so re-sending an unchanged prompt returns the same unusable reply and spends the round
for nothing. `pipeline.retry_note(...)` builds it from the previous round's error.

**[Phase 2 decision]** `check_test_file` enforces two more of the §3.6 rules than the three listed above: the
file must import the module `solution` (otherwise it does not test the generated code at all), and it must not
import a module that breaks determinism or the "no files, no network" rule
(`agents.code_utils.FORBIDDEN_TEST_MODULES`: random, secrets, socket, subprocess, requests, urllib, http,
httpx, shutil, tempfile). `print` is not rejected: it is harmless in a test and rejecting a whole round for it
would waste a request.

**[Phase 2 decision]** `agents/test_executor.py` also exports `count_labels(labels) -> dict[str, int]`, which
counts each label with every label present even when it is 0, so the summary tables have stable columns.

### 3.6 File formats

**`solution.py`** (written by the Code Generator):
- contains the `entry_point` function with exactly the required signature; helper functions and
  standard-library imports are allowed;
- has no `print`, no `input()`, no example usage and no `if __name__ == "__main__":` block. If the model adds
  them anyway, `remove_example_usage` deletes top-level main blocks, bare calls such as `print(...)` and
  top-level asserts, because those lines could never be covered and would run on import.

**`test_solution.py`** (written by the Test Generator). This is the contract:

```python
from solution import remove_Occ

def test_removes_first_and_last_occurrence():
    assert remove_Occ("hello", "l") == "heo"

def test_character_not_present_returns_same_string():
    assert remove_Occ("abc", "z") == "abc"
```

Rules, enforced by `check_test_file`:
- import from `solution`;
- every test is a top-level function whose name starts with `test_`;
- use plain `assert` (`pytest.raises` only if the problem says an exception is raised);
- use only pytest and the standard library: no randomness, files, network or `print`;
- **must not define the function under test.** A file that does is rejected, because it would be testing its
  own copy.

**Reference test file** (built by `reference_tests_to_pytest` from MBPP's asserts):

```python
from solution import *

def test_reference_1():
    assert remove_Occ("hello","l") == "heo"

def test_reference_2():
    ...
```

Any `test_imports` from MBPP go at the top of this file.

**`verdict.json`** for each problem. This is the final Phase 2 shape; the numbers are only illustrative.
**[Phase 2 decision]** the implementation also writes `max_rounds`, `final_round` (which round produced the
final suite, which is not the same as `rounds_used` when a round was thrown away), `round_1` (the single-shot
result, in the same shape as `final`) and `testgen_errors` (one entry per unusable round). `rounds_used` counts
the test-generation rounds attempted, so it is also the number of LLM calls the loop spent.
Phase 1 writes the fields from `task_id` to `baseline`, plus the LLM usage fields (`llm_calls`,
`llm_cached_calls`, `llm_requests_sent`, `models_used`, token counts). The `baseline` block also has `verdict`,
`status`, `target_met`, `num_statements`, `num_branches`, `missing_lines` and `missing_branches`.

```json
{
  "task_id": 11,
  "entry_point": "remove_Occ",
  "codegen_ok": true,
  "status": "COMPLETED",
  "code_correct": true,
  "baseline": {"tests_total": 3, "tests_passed": 3, "statement_coverage": 83.33, "branch_coverage": 50.0,
               "verdict": "COVERAGE_NOT_MET"},
  "criterion": "branch",
  "target": 100.0,
  "rounds_used": 2,
  "final": {"tests_total": 7, "tests_passed": 7, "statement_coverage": 100.0, "branch_coverage": 100.0,
            "missing_lines": [], "missing_branches": [], "verdict": "PASS"},
  "test_labels": {"VALID": 7, "BUG_FOUND": 0, "INVALID_TEST": 0, "MISLEADING": 0},
  "llm_calls": 3,
  "models_used": ["cohere/north-mini-code:free"]
}
```

### 3.7 Verdicts and test labels

**Executor verdict** (one per execution). The rules are checked in this order:

| Verdict | Condition |
|---|---|
| `ERROR` | pytest could not run the file properly: syntax or import error, no tests collected, timeout, or a pytest exit code other than 0 or 1 |
| `TESTS_FAILED` | at least one test failed |
| `COVERAGE_NOT_MET` | all tests passed, but coverage for the chosen criterion is below the target |
| `PASS` | all tests passed and coverage is at or above the target |

- **What "coverage meets the target" means:** for `statement`, statement % ≥ target. For `branch`, branch % ≥
  target **and** statement % ≥ target. Branch coverage subsumes statement coverage, but coverage.py reports
  100% branch coverage for a function with no decisions even when no test calls it.
- **Pipeline-level statuses** (`status` in `verdict.json`):
  - `COMPLETED`: the problem was processed normally.
  - `CODEGEN_FAILED`: the LLM gave no usable solution; the raw reply is in `codegen_reply.txt`.
  - `PIPELINE_ERROR`: an unexpected exception; the traceback is in `error.txt` and the run continues.
  - Phase 2 adds `TESTGEN_FAILED`: no usable test file after all rounds.
- **Pass/fail and coverage are separate:** coverage counts lines run even by a test whose assert fails, so the
  two are always reported side by side. `target_met` depends only on coverage.

**Test labels** (Phase 2, step [5]): each final test is run against both the generated solution and MBPP's
reference solution.

| On generated solution | On MBPP reference | Label | Meaning |
|---|---|---|---|
| pass | pass | `VALID` | Correct test |
| fail | pass | `BUG_FOUND` | The test caught a real bug in the generated code |
| fail | fail | `INVALID_TEST` | The test's expected value is wrong |
| pass | fail | `MISLEADING` | The test and the generated code share the same wrong behaviour |

**[Phase 2 decision]** a fifth label, `NOT_RUN`, is used when the reference run reported no result for a test
at all (for example the whole file failed to import). It is never expected, and it keeps the label counts equal
to the number of tests instead of silently losing one.

Caveat for the report: a few MBPP descriptions are ambiguous. A test can be labelled `INVALID_TEST` or
`MISLEADING` because it follows a reasonable reading that differs from the reference.

### 3.8 Coverage feedback loop (Phase 2)

```
round 1:  tests = TestGenerator(initial prompt)
repeat:
    result = Executor.run(solution, tests)
    if result.target_met or round == max_rounds: stop
    round += 1
    new   = TestGenerator(feedback prompt: numbered code + existing tests + what is still uncovered)
    tests = merge_test_files(tests, new, round)   # add the new tests; rename duplicate names to <name>_r<round>
```

- **Unusable round:** if a round produces nothing usable (no code block, a syntax error, rejected by
  `check_test_file`, or an `ERROR` verdict from a collection failure), that round's new tests are thrown away
  and the next round is still a feedback round. If round 1 itself is unusable, the next round uses the initial
  prompt again. **[Phase 2 decision]** in both cases the retried prompt ends with one line saying what was
  wrong with the previous reply, because an unchanged prompt would be answered from the cache with the same
  unusable reply (§3.5).
- **Single-shot results:** `--max-rounds 1` switches the loop off. Round-1 results are saved separately
  (`round_1/execution.json`), so every run reports **single-shot vs with-feedback** numbers without a second
  run.
- **Plain-language feedback:** missing lines and branches are described to the model in plain words by
  `describe_missing`, for example ``line 4 `elif x < 0:` never went to line 6``.

### 3.9 Repository layout

```
ST-Mini-Project/
├── PROJECT_PLAN.md                    this file                                          P1
├── README.md                          setup + how to run                                 P1, P2 updates
├── Contributions.md                   what each member did (report item 5)               P1, P2 fills its part
├── AI-assisted-unit-testing-project.pdf   the assignment                                 P1
├── requirements.txt                   requests, pytest, coverage                         P1
├── pytest.ini                         testpaths = tests, pythonpath = .                  P1
├── .gitignore                                                                            P1
├── .github/pull_request_template.md                                                      P1
├── config.py                          models, temperatures, paths, defaults              P1 (P2 adds test-gen settings)
├── pipeline.py                        command-line orchestrator                          P1 baseline mode, P2 full mode
├── verify_run.py                      re-derives every verdict in a finished run          P2 [Phase 2 decision]
├── agents/
│   ├── __init__.py                                                                       P1
│   ├── models.py                      dataclasses (§3.5)                                  P1
│   ├── llm_client.py                  OpenRouter client: retry, fallback, cache, logging P1
│   ├── code_utils.py                  code extraction and helpers                        P1 (P2 adds 3 helpers)
│   ├── code_generator.py                                                                 P1
│   ├── test_executor.py               pytest + coverage runner, verdicts                 P1 (P2 adds validation)
│   └── test_generator.py                                                                 P2
├── prompts/
│   ├── code_generator_system.txt                                                         P1
│   ├── code_generator_user.txt                                                           P1
│   ├── test_generator_system.txt                                                         P2
│   ├── test_generator_user.txt                                                           P2
│   └── test_generator_feedback.txt                                                       P2
├── data/
│   ├── prepare_dataset.py                                                                P1
│   └── mbpp_subset.json               the 12 problems (committed)                        P1
├── tests/                             tests for OUR pipeline code; no API calls           P1, P2 adds
├── llm_cache/                         saved LLM responses (committed)                    P1 + P2 runs
├── results/                           official runs (committed)                          P1 baseline, P2 full
├── runs/                              scratch runs (git-ignored)
└── report/report.md                   the report, exported to PDF                        both
```

- **Why commit `llm_cache/`:** Member 2 reuses Phase 1's code-generation responses. That spends no quota, and
  Phase 2 tests exactly the same generated code as the baseline. The demo can also replay any run offline.
  The cache holds only prompts and responses, never the key.
- **Why `pytest.ini` with `testpaths = tests`:** a plain `pytest` then runs only our own tests, and does not
  pick up the generated `test_solution.py` files under `results/`. `pythonpath = .` lets the tests import
  `config` and `agents`.
- **`coverage_html/` folders are not committed:** coverage.py writes a `.gitignore` containing `*` into each
  one, and every run regenerates them.

`.gitignore`:

```
venv/
__pycache__/
*.pyc
.pytest_cache/
.coverage
.coverage.*
runs/
.env
```

### 3.10 Output of one run

```
results/phase2_branch100/
├── config.json              every setting used: models, temperatures, criterion, target, max rounds, seed,
│                            prompt and dataset hashes, package versions
├── summary.json             every problem's verdict + aggregate metrics
├── summary.md               the same as Markdown tables (goes into the report)
└── Mbpp_11/
    ├── problem.json
    ├── llm_calls.jsonl      one line per LLM call: agent, messages, settings, response, model, tokens, latency, cached
    ├── solution.py
    ├── codegen_reply.txt    only if code generation failed: the raw reply
    ├── error.txt            only after an unexpected exception (PIPELINE_ERROR): the traceback
    ├── reference/           execution of MBPP's 3 asserts against solution.py            (Phase 1)
    ├── round_1/ … round_k/  execution of each round's test suite                         (Phase 2)
    ├── test_solution.py     the final merged test suite                                  (Phase 2)
    ├── validation/          the final suite run against MBPP's reference solution        (Phase 2)
    ├── validation.json      the label of each test                                       (Phase 2)
    └── verdict.json
```

Every execution folder (`reference/`, `round_k/`, `validation/`) is written by `TestExecutorAgent.run`. It
holds `solution.py`, `test_solution.py`, `pytest.ini`, `junit.xml`, `coverage.json`, `output.txt`,
`execution.json` (the `ExecutionResult`) and `coverage_html/index.html` (open it in a browser; useful in the
demo). Any of them can be re-run by hand: `cd <folder>`, then `python -m pytest test_solution.py`.

### 3.11 Metrics (report item 4)

**For each problem:** `code_correct`, rounds used, number of tests, passed/failed, statement %, branch %,
target met, verdict, and the count of each test label.

**Across all 12 problems:**

| Metric | Definition |
|---|---|
| Code correctness rate | Problems whose solution passes all 3 MBPP asserts ÷ problems |
| Mean statement / branch coverage | Averaged over problems: **baseline (MBPP asserts) vs generated tests** |
| Target-met rate, round 1 | Problems that meet the target with the first test suite (single-shot) |
| Target-met rate, final | The same, after the feedback loop |
| Mean rounds used | |
| Test pass rate | Passed generated tests ÷ all generated tests |
| Test validity rate | `VALID` ÷ all generated tests |
| Fault detection | Of the problems with `code_correct = false`, how many have at least one `BUG_FOUND` test |
| LLM usage | Calls, tokens, cache hits, fallback uses |

The baseline comparison answers the main question: *do LLM tests aimed at a coverage goal reach higher coverage
than the dataset's own tests?*

---

## 4. How we follow the assignment's rules

| Rule | How we comply |
|---|---|
| No RAG | There is no vector store and no retrieval. Each prompt contains only the current problem (its text, its signature, one of its own asserts) and, in feedback rounds, our own tool output. |
| No chain of thought | Prompts never ask the model to reason or "think step by step"; they ask only for a code block. Every request sends `reasoning: {"enabled": false}`. Token usage, including `reasoning_tokens`, is logged for every call as evidence. |
| No LangGraph, LangChain or similar | The only libraries are `requests`, `pytest` and `coverage`. The orchestration is a plain Python loop in `pipeline.py`. |
| Feedback loop | This is ordinary control flow that passes tool output (coverage numbers) back to the generator, not a reasoning technique. It can be switched off with `--max-rounds 1`, and round-1 (single-shot) numbers are always reported as well. |

---

## 5. Work split

| | Phase 1 — Member 1 | Phase 2 — Member 2 |
|---|---|---|
| Theme | Foundation, Code Generator, Test Executor, baseline run | Test Generator, coverage feedback loop, test validation, experiments, report assembly |
| Git branch | `phase-1-foundation` | `phase-2-test-generation` |
| Pull request | PR #1 (merged by Member 1 after its checks pass) | PR #2 (reviewed and merged by Member 1) |
| Finished when | `pipeline.py --mode baseline` works on all 12 problems; `results/phase1_baseline/` committed | `pipeline.py --mode full` works; `results/phase2_branch100/` committed; report complete |
| Report sections | 1 (pipeline, dataset); 2 and 3 for the Code Generator and Executor; baseline results | 2 and 3 for the Test Generator; 4 (results); final assembly |
| Both | Section 5 (contributions: each member fills in their own part of `Contributions.md`), demo preparation | |

Phase 2 depends only on the contracts in §3.5. Member 2 changes Phase 1 files only where this plan says so
(`config.py`, `pipeline.py`, `code_utils.py`, `test_executor.py`, `README.md`).

---

## 6. Phase 1 — Member 1, step by step

Every step ends with a **check**. Don't start the next step until the check passes. Commit after each step.
All commands are for PowerShell in the VS Code terminal, run from the repository folder, with the venv active.

### Step 1.1 — Git repository and GitHub

The GitHub repository already exists (https://github.com/Ansh-Gupta0310/ST-Mini-Project), and Member 2 is
already a collaborator. Member 1 runs all git commands personally.

1. Create `.gitignore` (content in §3.9).
2. Connect the local folder to the repository, commit the plan on `main`, and create the Phase 1 branch:

```powershell
git init -b main
git remote add origin https://github.com/Ansh-Gupta0310/ST-Mini-Project.git
git add .gitignore PROJECT_PLAN.md AI-assisted-unit-testing-project.pdf
git commit -m "docs: add project plan and assignment"
git push -u origin main
git checkout -b phase-1-foundation
```

**Check:** the repo page on GitHub shows `PROJECT_PLAN.md`, and `git status` does not list `venv/`.

### Step 1.2 — Python environment

1. Create `requirements.txt`:

```
requests>=2.31
pytest==9.1.1
coverage==7.16.2
```

2. Create `pytest.ini`:

```
[pytest]
testpaths = tests
pythonpath = .
```

3. Install the dependencies:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Check:**

```powershell
python -c "import requests, pytest, coverage; print('ok')"
python -c "import os; print('set' if os.getenv('OPENROUTER_API_KEY') else 'missing')"
```

Both should print `ok` and `set`.

### Step 1.3 — `config.py`

Constants for everything in §3.3:
- `OPENROUTER_URL`, `PRIMARY_MODEL`, `FALLBACK_MODELS`;
- `CODEGEN_SETTINGS` (temperature, top_p, max_tokens, seed);
- `TESTGEN_SETTINGS`, which Phase 2 fills in;
- `EXECUTOR_TIMEOUT_S = 30`, `DEFAULT_CRITERION = "branch"`, `DEFAULT_TARGET = 100.0`, `DEFAULT_MAX_ROUNDS = 3`;
- `MIN_SECONDS_BETWEEN_CALLS = 3`, `MAX_RETRIES = 4`;
- paths: `DATA_FILE`, `CACHE_DIR`, `PROMPTS_DIR`.

The API key is read with `os.environ.get("OPENROUTER_API_KEY")`. If it is missing, stop with a clear message
that does not print anything secret.

**Check:** `python -c "import config"` runs without errors.

### Step 1.4 — LLM client (`agents/llm_client.py`)

Behaviour:
1. Build the request body: `model`, `messages`, `temperature`, `top_p`, `max_tokens`, `seed` and
   `reasoning: {"enabled": false}`.
2. **Cache:** the key is the SHA-256 of the request body (using the primary model name). If
   `llm_cache/<hash>.json` exists, return it with `cached=True` and make no network call.
3. Send the POST with headers `Authorization: Bearer <key>` and `Content-Type: application/json`. Wait at
   least `MIN_SECONDS_BETWEEN_CALLS` since the previous call.
4. **Retries:** on HTTP 429, HTTP 5xx or a network timeout, retry up to `MAX_RETRIES` times with waits of
   5, 15, 30 and 60 s (use the `Retry-After` header if the response has one). If it still fails, try the next
   fallback model.
5. **On success:** save the response to the cache, and append one JSON line to `log_path` with the agent,
   request body, response text, model actually used, `usage`, latency and `cached`. **Never log headers.**
6. If every model fails, raise a clear error.
7. Command-line helpers:
   - `python -m agents.llm_client --ping` sends one tiny request and prints the model, the reply and
     `reasoning_tokens`;
   - `python -m agents.llm_client --quota` calls `GET https://openrouter.ai/api/v1/key` and prints **only**
     `free_model_daily_requests` (used / limit / remaining).

**Check:**
- `--ping` prints a reply with `reasoning_tokens=0`;
- running `--ping` again prints `cached=True` (don't use `--quota` for this check: its counter can lag by
  several minutes);
- `git grep -nE "sk-or-v1-[0-9a-f]{20}"` finds nothing.

### Step 1.5 — Dataset (`data/prepare_dataset.py`)

A standalone script (no project imports) that:
1. downloads the URL in §3.4;
2. applies the selection rule;
3. derives `entry_point` and `signature` with `ast`;
4. runs each reference solution against its own 3 asserts as a sanity check;
5. writes `data/mbpp_subset.json` as a list of `Problem` dictionaries.

**Check:** `python data/prepare_dataset.py` prints exactly the task ids
`11, 20, 65, 66, 67, 69, 70, 71, 79, 83, 90, 92` and `12/12 reference solutions pass their own tests`.

### Step 1.6 — Test Executor agent (`agents/test_executor.py`) — no LLM, no API calls

`run()` works as follows:
1. Create `work_dir`, then write `solution.py` and `test_solution.py` into it.
2. Run a subprocess with `cwd=work_dir`, a timeout of `EXECUTOR_TIMEOUT_S` and the environment variable
   `PYTHONDONTWRITEBYTECODE=1`. Always pass the arguments as a **list** (the project path contains spaces):
   `[sys.executable, "-m", "coverage", "run", "--branch", "--include=solution.py", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=junit.xml", "test_solution.py"]`
3. Then run `coverage json -q -o coverage.json` and `coverage html -q -d coverage_html` the same way.
4. Parse the results:
   - `junit.xml`: a `<testcase>` with a `<failure>` or `<error>` counts as failed;
   - `coverage.json`: from `files["solution.py"]["summary"]` take `percent_statements_covered` and
     `percent_branches_covered`, and from `files["solution.py"]` take `missing_lines` and `missing_branches`.
     Do **not** use `percent_covered`, which mixes the two.
   - If there is no coverage data (for example, a collection error happened before the import), record 0%.
5. Apply the verdict rules in §3.7, using pytest exit codes 0 and 1 as "ran", anything else as `ERROR`, and a
   timeout as `TIMEOUT` → `ERROR`.
6. Also write `reference_tests_to_pytest(problem)` (format in §3.6).
7. Add a self-check command: `python -m agents.test_executor --self-check` runs every reference solution
   against its reference tests.

Write `tests/test_executor.py` (no API calls) covering these cases:

| Case | Expected result |
|---|---|
| `sign()` from §2.3 with only `sign(5)` | statement 50.0, branch 25.0, verdict `COVERAGE_NOT_MET` |
| `sign()` with all three tests | 100 / 100, `PASS` |
| A test with a wrong expected value | `TESTS_FAILED` |
| A test file with a syntax error | `ERROR` |
| A solution that loops forever (timeout lowered to 3 s for the test) | status `TIMEOUT`, verdict `ERROR` |
| `reference_tests_to_pytest` output for problem 11 | parses and contains 3 `test_reference_` functions |

**Check:** `pytest -q` is all green, and `python -m agents.test_executor --self-check` prints `12/12`, with
every problem at 3/3 passed.

### Step 1.7 — Code Generator agent (`agents/code_generator.py`)

1. Create `prompts/code_generator_system.txt` and `prompts/code_generator_user.txt` from Appendix B. Fill them
   with `string.Template` (`$name` placeholders), so that `{` and `}` in code don't break the formatting.
2. `run()` works as follows:
   1. build the messages;
   2. call `llm.chat` with `CODEGEN_SETTINGS`;
   3. extract the code with `extract_python_code`;
   4. check that `ast.parse` succeeds and that `entry_point` is defined at the top level;
   5. remove any `if __name__ == "__main__":` block;
   6. return an `AgentResult`.
3. In `agents/code_utils.py`, write `extract_python_code` (the first ```` ```python ```` block, otherwise the
   first ```` ``` ```` block, otherwise the whole reply; `None` if it does not parse) and `number_lines`.
4. Write `tests/test_code_utils.py` (no API calls), covering: a fenced block, an unfenced reply, text before
   and after the block, a reply that isn't code, and removal of the main block.
5. Add a command-line helper: `python -m agents.code_generator --task-id 11` prints the extracted code.

**Check:** `pytest -q` is green, and `python -m agents.code_generator --task-id 11` prints a function
`remove_Occ` (1 API call; a repeat comes from the cache).

### Step 1.8 — `pipeline.py`, baseline mode

```
python pipeline.py --mode baseline [--task-ids 11 20 ...] [--limit N] --out <folder>
```

For each problem:
1. Code Generator → save `solution.py`. If it fails, write `CODEGEN_FAILED` to `verdict.json` and continue.
2. Build the reference tests and run the Executor.
3. `code_correct` = all 3 reference tests passed.
4. Save the files in §3.10 and write `verdict.json`.

At the end, write:
- `config.json`;
- `summary.json`;
- `summary.md`: a table with task, function, code_correct, baseline statement %, baseline branch % and LLM
  calls, followed by the correctness rate and mean coverage.

One problem failing must never stop the whole run.

**Check:** `python pipeline.py --mode baseline --task-ids 11 --out runs/smoke` creates
`runs/smoke/Mbpp_11/` with `problem.json`, `llm_calls.jsonl`, `solution.py`, `verdict.json` and the execution
folder `reference/` (§3.10). It also creates `runs/smoke/summary.md`.

### Step 1.9 — Baseline run on all 12 problems

```powershell
python -m agents.llm_client --quota        # need at least 13 remaining
python pipeline.py --mode baseline --out results/phase1_baseline
```

**Check:**
- 12 `Mbpp_*` folders exist;
- `summary.md` has 12 rows;
- the quota went down by about 12.

A `CODEGEN_FAILED` or `code_correct = false` result is a **finding**, not a bug. Keep it and report it.
Commit `results/phase1_baseline/` and `llm_cache/`.

### Step 1.10 — README, PR template, report skeleton

1. **`README.md`:**
   - what the project is (2–3 lines, linking to this plan);
   - setup: venv, `pip install -r requirements.txt`;
   - setting `OPENROUTER_API_KEY` as a Windows **user** environment variable (Start → "Edit environment
     variables for your account" → New), then restarting VS Code;
   - the commands from steps 1.4–1.9.
2. **`.github/pull_request_template.md`:** the template in §8.
3. **`report/report.md`:** the section headings from §11, with Member 1's parts written: the dataset and
   selection, the pipeline overview, the Code Generator prompts and settings, how the Executor works, and the
   baseline results table.
4. **`Contributions.md`:** Member 1's section filled in; Member 2's section left open with placeholders.

**Check:** a person who has only the README can install the project and run the smoke test.

### Step 1.11 — Open PR #1, merge, hand over

```powershell
git push -u origin phase-1-foundation
gh pr create --base main --head phase-1-foundation --title "Phase 1: foundation, code generator, test executor, baseline" --body "See PROJECT_PLAN.md §6. Checks: pytest green, self-check 12/12, baseline run in results/phase1_baseline."
gh pr merge --merge
```

Then send Member 2 the repo link and tell them to start at step 2.0. **From this point Member 1 does not edit
code files until PR #2 is merged** (§8).

### Phase 1 — definition of done

- [ ] The repo is on GitHub (private) and Member 2 is invited
- [ ] `pytest -q` passes with no API calls
- [ ] `python -m agents.test_executor --self-check` → 12/12
- [ ] `results/phase1_baseline/` has 12 problem folders, `summary.md` and `config.json`
- [ ] `llm_cache/` is committed; `git grep -nE "sk-or-v1-[0-9a-f]{20}"` finds nothing
- [ ] The README explains setup and running
- [ ] Member 1's sections of `report/report.md` are written
- [ ] Member 1's section of `Contributions.md` is filled in
- [ ] PR #1 is merged into `main`

---

## 7. Phase 2 — Member 2 via pull request, step by step

Same rules: every step ends with a check, and you commit after each step.

### 7.0 Handover notes from Phase 1

Read these before starting. They are things Phase 1 found out that this plan could not know in advance.

- **Keep the cache valid.** Don't change `prompts/code_generator_*.txt`, `config.CODEGEN_SETTINGS`,
  `config.PRIMARY_MODEL` or `config.REASONING`. They are part of the cache key: any change makes every code
  generation a new API call and changes the generated code, which breaks the comparison with the baseline.
- **Calling the LLM:** `llm.chat(messages, agent="test_generator", log_path=problem_dir / "llm_calls.jsonl",
  **config.TESTGEN_SETTINGS)`, where `TESTGEN_SETTINGS` holds `temperature`, `top_p`, `max_tokens` and `seed`.
  Catch `LLMError` for each round, but let `FatalLLMError` propagate: `pipeline.main` stops the run on it and
  saves what finished.
- **Executing tests:** `TestExecutorAgent().run(solution, tests, problem_dir / f"round_{k}", criterion, target)`.
  Use a new folder for every execution; `run()` writes `execution.json` there itself.
- **Validation:** run the final suite with `problem.reference_code` as the solution in `problem_dir /
  "validation"`, then call `classify_tests(on_generated, on_reference)`.
- **Naming:** give `TestGeneratorAgent` the class attribute `__test__ = False`, like `TestExecutorAgent`.
  Otherwise pytest tries to collect it as a test class.
- **Where to plug in:** `pipeline.main` currently prints "not implemented" for `--mode full`. Add
  `run_full_problem(...)` next to `run_baseline_problem` (reuse it for steps [1]–[2]), and extend `summarize`
  and `summary_markdown` with the §3.11 metrics.
- **Deleting files:** use `agents.test_executor.remove_path`, not `shutil.rmtree`. OneDrive marks synced
  folders read-only, and a plain `rmtree` then fails on Windows.
- **Data issues you will meet in validation:**
  - **Problem 83:** MBPP's reference `get_Char` returns the integer `122` instead of `"z"` when the letter sum
    is a multiple of 26. A correct test for that case will be labelled `INVALID_TEST` or `MISLEADING`; explain
    it in the report instead of "fixing" the reference.
  - **Problem 11:** the generated `remove_Occ` passes MBPP's asserts, but returns `"abc"` for
    `remove_Occ("abc", "b")` where the reference returns `"ac"`. A branch-coverage test has to reach that
    branch, which makes it a good `BUG_FOUND` / `MISLEADING` example for the demo.
  - **Problems 71, 79 and 83:** the generated solutions fail MBPP's asserts (report §4.1). Generated tests that
    fail on them are expected, not a Phase 2 bug.
- **Baseline to compare against:** `results/phase1_baseline/summary.md`. MBPP's own tests covered 94.2% of
  statements and 89.6% of branches on average; the goal of 100% branch coverage was reached for 7 of 12
  problems.
- **Tests:** `pytest -q` runs 54 offline tests in about 30 s. Add yours to `tests/` in the same style. No test
  may call the real API; `tests/test_pipeline.py` shows how to fake the network.

### Step 2.0 — Setup

1. Accept the GitHub invitation if you haven't already (from the email, or github.com → notifications).
2. Clone the repo and install:

```powershell
git clone https://github.com/Ansh-Gupta0310/ST-Mini-Project.git
cd ST-Mini-Project
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Create your **own** OpenRouter account and key at openrouter.ai → Keys. Set it as the Windows user
   environment variable `OPENROUTER_API_KEY` (see the README), then restart VS Code. Don't put the key in any
   file in the repo.
4. Create your branch: `git checkout -b phase-2-test-generation`

**Check:**
- `pytest -q` is green;
- `python -m agents.llm_client --quota` shows 50 remaining;
- `python pipeline.py --mode baseline --task-ids 11 --out runs/check` finishes, and `llm_calls.jsonl` shows
  `"cached": true`, meaning no quota was used.

### Step 2.1 — Test Generator prompts

1. Create `prompts/test_generator_system.txt`, `test_generator_user.txt` and `test_generator_feedback.txt`
   from the drafts in Appendix B. You may improve the wording, but keep the rules.
2. Add `TESTGEN_SETTINGS` (§3.3) and `CRITERION_GOALS` (Appendix B) to `config.py`.

**Check:** `python -c "import config; print(config.TESTGEN_SETTINGS, list(config.CRITERION_GOALS))"`

### Step 2.2 — Helpers in `agents/code_utils.py`

- `describe_missing(code, missing_lines, missing_branches)` turns coverage output into plain lines, for example:

  ```
  - line 4 `elif x < 0:` was never run
  - line 2 `if x > 0:` never went to line 4
  ```

  A negative `to_line` means "never exited the function from here".
- `merge_test_files(existing, new, round_no)` uses `ast` to join the files: all imports from both, then the
  existing tests, then the new tests. A new test whose name already exists is renamed to `<name>_r<round_no>`.
- `check_test_file(test_code, entry_point)` returns an error message if the file does not parse, has no
  `test_` function, or defines `entry_point`; otherwise it returns `None`.

**Check:** add tests to `tests/test_code_utils.py`: `describe_missing` on the §2.3 example (only `sign(5)`)
mentions lines 4, 5 and 6; merging two files that both have `test_a` gives `test_a` and `test_a_r2`; a file
that defines the function is rejected. Then `pytest -q` is green.

### Step 2.3 — Test Generator agent (`agents/test_generator.py`)

`run()` works as follows:
1. With no `feedback`, use the system prompt + user prompt. With `feedback`, use the system prompt + feedback
   prompt, which is filled with the numbered code, the existing tests, the statement and branch %, and
   `describe_missing(...)`.
2. Call `llm.chat` with `TESTGEN_SETTINGS`.
3. Extract the code with `extract_python_code`, then run `check_test_file`.
4. Return an `AgentResult`.

Add a command-line helper: `python -m agents.test_generator --task-id 11 --solution results/phase1_baseline/Mbpp_11/solution.py`

**Check:** the helper prints a pytest file that follows the §3.6 rules (1 API call).

### Step 2.4 — Test validation (in `agents/test_executor.py`)

- `validate(...)` runs the final test file with the **reference** solution as `solution.py`, in the execution
  folder `validation/`, and then calls `classify_tests(...)`.
- `classify_tests(...)` applies the §3.7 table.

**Check:** add an offline test to `tests/test_executor.py`. The reference is the correct `sign()`; the
"generated" version is a buggy `sign()` that returns `1` for `0`:

| Test | Expected label |
|---|---|
| `sign(5) == 1` | `VALID` |
| `sign(0) == 0` | `BUG_FOUND` |
| `sign(-5) == 1` | `INVALID_TEST` |
| `sign(0) == 1` | `MISLEADING` |

Then `pytest -q` is green.

### Step 2.5 — `pipeline.py`, full mode with the feedback loop

```
python pipeline.py --mode full --criterion {statement,branch} --target 100 --max-rounds 3
                   [--task-ids ...] [--limit N] --out <folder>
```

For each problem:
1. Run steps [1]–[2] exactly as in baseline mode. They come from the cache, so they cost no quota.
2. Run the loop in §3.8, executing each round's suite in its own folder `round_<k>/` (the Executor writes
   `test_solution.py` and `execution.json` there). Save the final merged suite as `test_solution.py`.
3. Run validation and save `validation.json`.
4. Write `verdict.json` in the full shape (§3.6).

The summary adds the §3.11 metrics, including round-1 vs final target-met and the comparison with the baseline.

**Check:** `python pipeline.py --mode full --task-ids 11 --out runs/smoke2` produces the §3.10 files, and
`round_1/coverage_html/index.html` opens in a browser. `--max-rounds 1` also works.

### Step 2.6 — Official experiment

```powershell
python -m agents.llm_client --quota        # need at least 36 remaining
python pipeline.py --mode full --criterion branch --target 100 --max-rounds 3 --out results/phase2_branch100
```

- **Cost:** at most 36 API calls (12 problems × up to 3 rounds).
- **If the quota is short:** use `--max-rounds 2` (at most 24 calls) and say so in the report, or finish the
  run with Member 1's key. The cache means completed calls are never repeated.
- **Optional:** if quota is left over, also run `--criterion statement --out results/phase2_statement100`.

**Check:** `summary.md` has 12 rows and every problem has a verdict. Commit `results/phase2_branch100/` and
`llm_cache/`.

### Step 2.7 — Report

In `report/report.md`, add:
- the Test Generator prompts and settings;
- three complete examples: code, tests, execution and verdict. Choose one `PASS` at round 1, one that needed
  feedback rounds, and one with a `BUG_FOUND` or `INVALID_TEST` label (whichever occurred);
- the results tables from both `summary.md` files, with the baseline vs generated comparison;
- limitations.

Also fill in your section of `Contributions.md` (Member 1's section is already there). Then export the
report to PDF (§11).

### Step 2.8 — Open PR #2

```powershell
git push -u origin phase-2-test-generation
gh pr create --base main --head phase-2-test-generation --title "Phase 2: test generator, coverage feedback loop, validation, results"
```

(Or open the PR on GitHub.) Fill in the template. Member 1 reviews it using §8 and merges it.

### Phase 2 — definition of done

- [x] `pytest -q` passes with no API calls — 88 passed, 1 skipped (Windows-only)
- [x] `results/phase2_branch100/` has 12 problem folders, `summary.md` and `config.json`
- [x] Every final `test_solution.py` follows the §3.6 rules — checked by `python verify_run.py <run>`
- [x] `--max-rounds 1` works (single-shot) — and every round-1 result is recorded anyway (`round_1` in
      `verdict.json`), so single-shot numbers come out of the same run
- [x] Optional second criterion also run: `results/phase2_statement100/`
- [x] `git grep -nE "sk-or-v1-[0-9a-f]{20}"` finds nothing
- [x] `report/report.md` is complete — **the PDF still has to be exported** (§11: right-click the file in
      VS Code → *Markdown PDF: Export (pdf)*)
- [x] Member 2's section of `Contributions.md` is filled in, apart from the name and roll number
- [ ] PR #2 is approved and merged

---

## 8. Pull request workflow

**Rules**
- `main` must always work. After the first commit, nobody pushes to `main` directly; all work goes through a
  PR.
- **File freeze:** after PR #1 is merged, Member 1 does not edit `config.py`, `pipeline.py` or `agents/*`
  until PR #2 is merged. This prevents merge conflicts.
- Make small commits with clear messages, for example `phase2: add test generator agent`.

**`.github/pull_request_template.md`** (GitHub fills it into every new PR):

```markdown
## What this PR does

## Plan steps completed (PROJECT_PLAN.md)
- [ ] Step ...

## How I checked it
- [ ] `pytest -q` passes (no API calls)
- [ ] Smoke run: command + output folder

## Results
<!-- paste the key rows of summary.md -->

## API calls used

## Differences from the plan (was PROJECT_PLAN.md updated?)
```

**Review checklist** (Member 1 reviewing PR #2):
1. `gh pr checkout 2`
2. `pytest -q`: must be green.
3. `python pipeline.py --mode full --task-ids 11 --out runs/review`: must come from the committed cache
   (`"cached": true` in `llm_calls.jsonl`), so it uses 0 quota.
4. Open `results/phase2_branch100/summary.md` and two problem folders. Check that each verdict matches the
   numbers (for example, `PASS` only when all tests passed and coverage ≥ target).
5. `git grep -nE "sk-or-v1-[0-9a-f]{20}"` finds nothing.
6. Approve, then run `gh pr merge 2 --merge`.

---

## 9. API quota budget

**Verified on 30 Sep:**
- the key is on the free tier, with **50 free-model requests per day** per OpenRouter account;
- a request rejected with HTTP 429 (rate-limited) **did not** count against the quota;
- each member uses their own account, so there are 2 × 50 requests per day.

| Activity | Who | Calls (worst case) |
|---|---|---|
| Ping and smoke tests | Member 1 | about 5 |
| Baseline run (12 problems × 1 code generation) | Member 1 | 12 |
| Phase 2 development checks | Member 2 | about 5 |
| Code generation inside the full run | Member 2 | 0 (from the cache) |
| Full run (12 problems × up to 3 test-generation rounds) | Member 2 | at most 36 |
| **Total** | | **Member 1 ≈ 17 of 50 · Member 2 ≈ 41 of 50** |

**Actual Phase 1 usage:** 13 requests on Member 1's key (1 ping + 12 code generations). Every re-run after
that came from the cache.

Run `python -m agents.llm_client --quota` before any big run. If a key runs out, continue the run with the
other member's key (the cache skips finished calls), or lower `--max-rounds`.

---

## 10. Timeline

The plan was written late on 30 Sep, and submission closes on 1 Oct. **Check the exact closing time on the LMS
and work backwards from it.**

| When (1 Oct) | Who | Milestone |
|---|---|---|
| Early | Member 1 | Steps 1.1–1.2 (repo created, Member 2 invited) |
| Early, in parallel | Member 2 | OpenRouter account and key; accept the invite; clone (step 2.0 items 1–3) |
| Morning | Member 1 | Steps 1.3–1.11; PR #1 merged; hand-over message sent |
| Midday–afternoon | Member 2 | Steps 2.0 (check) – 2.6 |
| Afternoon | Member 2 → Member 1 | PR #2 opened, reviewed and merged |
| Before the portal closes | Both | Report PDF finished; one member uploads it (one report per team) |
| Your demo slot (1, 6 or 8 Oct) | Both | §12 |

---

## 11. Report plan

The report is written in `report/report.md` and exported to PDF, for example with the VS Code extension
"Markdown PDF" (right-click the file → *Markdown PDF: Export (pdf)*).

| Assignment item | Report section | Source | Written by |
|---|---|---|---|
| 1. Pipeline, dataset, test generator functionality | 1. Pipeline and dataset | §1, §3.1–3.4, §3.8 | Member 1 (pipeline, dataset), Member 2 (test generation) |
| 2. User prompts, system prompts, settings | 2. Prompts and settings | `prompts/*.txt` copied exactly + §3.3 table + `config.json` | Member 1 (code gen), Member 2 (test gen) |
| 3. Formats, plus the actual code, tests and verdicts | 3. Formats and examples | §3.6, §3.7 + three complete examples from `results/` | Member 1 (code, reference format), Member 2 (tests, verdicts) |
| 4. Execution results (coverage option) | 4. Results | Both `summary.md` files + §3.11 metrics | Member 2 |
| 5. Each member's contribution | 5. Contributions | `Contributions.md`, PR #1, PR #2, commit history | Both |

Also include:
- **Limitations:** ambiguous MBPP descriptions; some branches may be impossible to reach; one model;
  12 problems; high coverage does not prove the code is correct.
- **Tools used:** the OpenRouter model, and any AI assistants used during development (the assignment
  expects AI tools to be used, so say which ones).

---

## 12. Demo plan

Both members must be able to explain every part.

1. **(1 min)** The problem and the pipeline, using the §3.1 diagram.
2. **(3 min)** A live run: `python pipeline.py --mode full --task-ids 92 --out runs/demo`. It comes from the
   cache, so there is no network or quota risk.
   **[Phase 2 decision]** the plan assumed we would demo a problem that needed two rounds, but in the official
   run round 1 met the goal for all 12 problems (report §4.2), so there is no such problem. Demo problem 92
   instead: MBPP's asserts reach 75% branch coverage and the generated suite reaches 100%. To show the loop
   itself, run `pytest -q tests/test_pipeline.py::test_feedback_round_closes_the_coverage_gap -v`, which drives
   a round-1 suite at 50% branch coverage and a round 2 that closes the gap.
3. Walk through the output folder: `solution.py` → `round_1/test_solution.py` → `round_1/execution.json`
   → `validation.json` → `verdict.json`. Then open `reference/coverage_html/index.html` and
   `round_1/coverage_html/index.html` side by side: the same file, with the missing lines highlighted in one and
   not the other.
4. `summary.md`: baseline vs generated coverage (94.2% / 89.6% → 100% / 100%, goal met 7/12 → 12/12).
5. Problem 71 `comb_sort` (3 `BUG_FOUND`) and problem 11 (4 `MISLEADING`), and what they show about the oracle
   problem. `python verify_run.py results/phase2_branch100` shows the verdicts were not taken on trust.
6. `llm_calls.jsonl`: the exact prompts, temperature, and `reasoning_tokens = 0`.

**Questions to prepare for:**
- What is the difference between statement and branch coverage?
- Why is the Executor not an LLM?
- How do you know a test is correct?
- Is the feedback loop "chain of thought"?
- Why these 12 problems?
- What does temperature change?
- Does 100% coverage mean the code is correct?

---

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| The free model is rate-limited upstream (`qwen` was during planning) | Retries with backoff, fallback models, cache |
| Daily quota of 50 | 12 problems, committed cache, two keys, `--quota` check before runs |
| LLM output is not usable (no code, wrong function name) | Extraction + `ast` check + entry-point check; recorded as `CODEGEN_FAILED` / `TESTGEN_FAILED` and counted in the results |
| Generated code loops forever | 30 s subprocess timeout → `ERROR` |
| Running LLM-written code on a laptop | Run it in a separate process, in a throw-away folder, with a timeout. The functions are small and use only the standard library; glance at the `solution.py` files after the baseline run. (A Docker sandbox is possible but out of scope.) |
| Tests with wrong expected values | Validation labels against the reference (§3.7) |
| Some branches cannot be reached | The target is not met after max rounds → reported as `COVERAGE_NOT_MET` and discussed |
| The model is unavailable during the demo | Demo from the cache |
| Merge conflicts between the two phases | File-freeze rule (§8) |
| OneDrive slows down the venv or git | Pause OneDrive sync while working if needed |

---

## Appendix A — Facts verified on 30 Sep 2026

**MBPP sanitized**
- 427 problems, with fields `task_id, prompt, code, test_imports, test_list, source_file`.
- 257 are in the test split (11–510), and 113 of those have zero decision points.
- 90 problems meet the selection rule; the 12 selected all pass their own asserts.
- `entry_point` can be extracted for all 427 problems.

**coverage.py 7.16.2 / pytest 9.1.1 on Python 3.12.10**
- `coverage json` gives, for each file, a `summary` with `percent_statements_covered` and
  `percent_branches_covered` (the latter is `100.0` when `num_branches` is 0).
- `percent_covered` mixes statements and branches, so we don't use it.
- `missing_branches` is a list of `[from, to]` pairs.
- `--junitxml` gives a pass/fail result for each test.
- The §2.3 numbers (50% / 25%) were produced with these exact versions.

**OpenRouter**
- 16 free models were listed.
- `cohere/north-mini-code:free` returned a clean code block with `reasoning_tokens: 0` and supports `seed`.
- `qwen/qwen3.8-27b:free` returned an upstream HTTP 429 (rate-limited).
- The key is on the free tier with a daily limit of 50 free-model requests; the 429 did not count against it.

---

## Appendix B — Draft prompts

Placeholders use `string.Template` syntax (`$name`). These are drafts: Phase 1 finalises the Code Generator
prompts and Phase 2 finalises the Test Generator prompts. The final versions go into the report exactly as
they are.

**`prompts/code_generator_system.txt`**

```
You are a Python code generator.
Write a correct Python 3 function that solves the problem you are given.
Reply with exactly one Python code block and nothing else.
Use only the Python standard library.
Do not include explanations, example usage, print statements, input() calls,
or an `if __name__ == "__main__":` block.
```

**`prompts/code_generator_user.txt`**

```
Problem:
$prompt

Implement this function, keeping exactly this name and these parameters:
$signature

Your function must satisfy this example:
$example_test
```

**`prompts/test_generator_system.txt`**

```
You are a software tester who writes pytest unit tests.
Reply with exactly one Python code block containing a complete pytest file and nothing else.
Rules:
- The function under test is in the module `solution`. Import it with: from solution import $entry_point
- Write each test as a separate top-level function whose name starts with test_ and describes what it checks.
- Use plain assert statements. Use pytest.raises only if the problem says an exception is raised.
- Take every expected value from the problem description, not from the code under test.
- Do not define or change $entry_point. Do not use randomness, files, the network, or print.
- Use only pytest and the Python standard library.
```

**`prompts/test_generator_user.txt`**

```
Problem description:
$prompt

Example of correct behaviour:
$example_test

Function under test (file solution.py; the line numbers on the left are not part of the code):
$numbered_code

Coverage goal: $criterion_goal
Write between 3 and 10 tests.
```

**`prompts/test_generator_feedback.txt`**

```
Problem description:
$prompt

Function under test (file solution.py; the line numbers on the left are not part of the code):
$numbered_code

These tests already exist:
$existing_tests

Coverage after running them: statements $statement_coverage%, branches $branch_coverage%.
Coverage goal: $criterion_goal

Not covered yet:
$missing_description

Write only NEW test functions that make the uncovered lines and branches run.
Do not repeat the existing tests. Start the file with: from solution import $entry_point
```

**`CRITERION_GOALS` in `config.py`** (`$target` is filled in from `--target`):

| Criterion | Goal text |
|---|---|
| `statement` | `Reach $target% statement coverage: every executable line of solution.py must be run by at least one test.` |
| `branch` | `Reach $target% branch coverage: every if/elif/while condition must be True in some test and False in some test, and every loop must run its body at least once and also finish at least once.` |
