# AI-Assisted Unit Testing Pipeline — Project Report

**Course:** CSE731 Software Testing, IIIT Bangalore · Mid-term Project, Term I (2026-27)
**Team:** `<Ansh Gupta, IMT2023540>` · `<Satyam Dewangan, IMT2023545>`
**Repository:** https://github.com/Ansh-Gupta0310/ST-Mini-Project
**Requirement chosen:** (1) test cases that achieve a **user-specified coverage criterion**. The assignment's
own examples are *"cover all statements, cover all loops, cover all decision statements"*, and all three are
implemented: `--criterion statement|branch|loops`.

> Every number in this report comes from a committed run folder under `results/`: `phase1_baseline/` (Phase 1,
> the dataset's own tests), `phase2_branch100/` (the main Phase 2 experiment) and `phase2_statement100/` (the
> same experiment with the other coverage criterion). `python verify_run.py <folder>` re-derives the verdicts in
> a run from the measurements they were computed from.

---

## 1. The pipeline and the dataset

### 1.1 Overview

The pipeline is written in plain Python. There is no agent framework, no retrieval (RAG) and no
chain-of-thought prompting. `pipeline.py` calls three agents in a fixed order for every problem:

```
MBPP problem ──► [1] Code Generator agent (LLM) ──► solution.py
                                                        │
                 [2] Test Executor agent (pytest + coverage.py) runs MBPP's 3 reference asserts
                     against solution.py ──► code_correct + baseline coverage          (Phase 1)
                                                        │
                 [3] Test Generator agent (LLM) ──► test_solution.py aimed at the coverage goal
                 [4] Test Executor agent ──► pass/fail, statement %, branch %, verdict
                     └─ goal not met? missing lines/branches go back to [3] (max rounds)
                 [5] Validation: the final tests are re-run against MBPP's reference solution  (Phase 2)
```

| Agent | Uses an LLM? | Input | Output |
|---|---|---|---|
| Code Generator | Yes | Problem text, required function signature, one example assert | `solution.py` |
| Test Generator | Yes | Problem text, example assert, generated code with line numbers, coverage goal | `test_solution.py` (pytest) |
| Test Executor | No: runs pytest and coverage.py | Solution, test file, criterion, target | Per-test pass/fail, coverage, verdict |

- **Why the Executor has no LLM:** the verdict has to be a measured fact, not a model's opinion. The Executor
  runs pytest under coverage.py in a separate process with a 30 s timeout, reads the JUnit XML and coverage
  JSON reports, and applies fixed rules (§3.3).
- **Isolation:** each execution runs in its own folder. The API key is removed from the environment of the
  process that runs the generated code.

### 1.2 Dataset and problem selection

- **Dataset:** MBPP, sanitized version (427 problems): `sanitized-mbpp.json` from the google-research
  repository. Each problem has a short English description, a reference solution and three reference asserts.
- **Selection:** `data/prepare_dataset.py` picks 12 problems deterministically. It keeps problems from the
  official test split (task_id 11–510, 257 problems) whose reference solution has **at least 2 decision
  points** (if/elif, for, while, ternary, try, comprehension-if) and **at most 25 lines**. That gives 90
  candidates; the first 12 by task_id are used.
- **Why at least 2 decision points:** 113 of the 257 test-split problems contain no decision at all, so a
  single test gives 100% coverage and there is nothing to measure.
- **Why 12:** the free API tier allows about 50 requests per day.

Selected problems: 11 `remove_Occ`, 20 `is_woodall`, 65 `recursive_list_sum`, 66 `pos_count`, 67 `bell_number`,
69 `is_sublist`, 70 `get_equal`, 71 `comb_sort`, 79 `word_len`, 83 `get_Char`, 90 `len_log`, 92 `is_undulating`.

All 12 reference solutions pass their own asserts (`python -m agents.test_executor --self-check`). Even for these
reference solutions, MBPP's 3 asserts reach 100% branch coverage in only 6 of the 12 problems. This is the gap
that coverage-targeted test generation is meant to close.

### 1.3 Functionality of the test-case generator

The assignment asks for a test-case generator that satisfies **one** requirement. Ours satisfies requirement
(1): the tests must achieve a **user-specified coverage criterion**. The criterion and the target are command
line arguments, not constants:

```
python pipeline.py --mode full --criterion branch --target 100 --max-rounds 3 --out results/phase2_branch100
python pipeline.py --mode full --criterion loops --target 100 --max-rounds 3 --out results/phase2_loops100
python pipeline.py --mode full --criterion statement --target 90 --max-rounds 1 --out runs/statement90
```

The three criteria are the three the assignment names, and they are the bottom three levels of the standard
subsumption hierarchy:

| `--criterion` | What a test suite must achieve | Course name | Measured by |
|---|---|---|---|
| `statement` | every executable line runs | node coverage | coverage.py |
| `branch` | every decision goes both ways; every loop body runs and the loop exits | edge coverage | coverage.py |
| `loops` | every pair of consecutive edges `a → b → c`; at a loop header this means the body must be skipped in some test, run once in some test, and run twice in some test | **edge-pair coverage** | `agents/path_coverage.py` |

`prime path ⊃ edge-pair ⊃ edge ⊃ node`. Prime path coverage is not implemented (§6).

**How `loops` is measured.** coverage.py reports *which* arcs ran but not the *order* they ran in, and an edge
pair is an ordering. So two things happen. The set of required pairs comes from coverage.py's own parser
(`PythonParser.arcs()` gives every possible arc, loop back-edges included), which means the control-flow graph
is not ours to get wrong. The covered pairs come from running the tests a **second time** with a
`sys.settrace` hook that records each test's line sequence; the consecutive triples of those sequences are the
pairs that were covered. The second pass cannot be merged into the first: `coverage run` and our tracer both
install a trace hook and the second one to install wins — measured, coverage.py dropped to 16.7% statements and
0% branches. The traced pass therefore runs without coverage.py, and only for `--criterion loops`, so the other
two criteria are measured exactly as before.

**What the generator sees.** The prompt is white-box, because the goal is stated in terms of the code: to cover
a branch you have to know it is there. The Test Generator receives the problem description, one example assert,
and the generated `solution.py` with line numbers added, plus the goal sentence for the chosen criterion. It
never sees MBPP's reference solution, and the system prompt tells it to take **expected values from the problem
description, not from the code under test**. That instruction is what keeps the generator from simply agreeing
with a buggy implementation, and §1.4 below measures how well it worked.

**What comes back is checked, not trusted.** The reply must contain a Python code block that parses, contains at
least one top-level `test_` function, imports the module `solution`, does not define the function under test
(otherwise it would test its own copy), and does not import anything that breaks determinism or the "no files,
no network" rule. A reply that fails any of these checks is discarded and the round counts as unusable.

**The coverage feedback loop.** The generated suite is executed by the Test Executor, which measures statement
and branch coverage of `solution.py`. If the goal is not met and rounds remain, the *measured* gap is turned
into plain sentences by `describe_missing` and sent back with the existing tests:

```
Coverage after running them: statements 75%, branches 50%.
Not covered yet:
- line 3 `return s` was never run
- line 2 `if ch not in s:` never went to line 3 `return s`
```

The model is asked for **new** tests only, and `merge_test_files` joins them to the existing suite with `ast`:
every import once, round 1's tests first, then the new ones, and a new test whose name already exists is renamed
`<name>_r<round>` so that no earlier test is silently replaced. Each round is executed in its own folder
(`round_1/`, `round_2/`, …), so the single-shot result (round 1) and the result with feedback are both available
from one run. `--max-rounds 1` switches the loop off altogether.

This loop is ordinary control flow: a program passes a measurement from one tool (coverage.py) back into the
next prompt. It is not chain-of-thought — the model is never asked to reason, explain or think step by step, and
every request sends `reasoning: {"enabled": false}` (§2.2).

**Validation of the tests (the oracle problem).** A passing test proves nothing if its expected value is wrong,
and a test written from the code will agree with the code's bugs. So after the loop, the final suite is run a
second time against MBPP's reference solution, and each test is labelled from the two outcomes:

| On the generated code | On MBPP's reference | Label | Meaning |
|---|---|---|---|
| pass | pass | `VALID` | Correct test |
| fail | pass | `BUG_FOUND` | The test caught a real bug in the generated code |
| fail | fail | `INVALID_TEST` | The test's expected value is wrong |
| pass | fail | `MISLEADING` | The test and the generated code share the same wrong behaviour |

Coverage tells us how much of the code the tests reach; these labels tell us whether the tests are *right*. The
project reports both, because one without the other would be misleading.

---

## 2. Prompts and settings

### 2.1 Code Generator prompts

**System prompt** (`prompts/code_generator_system.txt`, sent as-is):

```
You are a Python code generator.
Write a correct Python 3 function that solves the problem you are given.
Reply with exactly one Python code block and nothing else.
Use only the Python standard library.
Do not include explanations, example usage, print statements, input() calls,
or an `if __name__ == "__main__":` block.
```

**User prompt template** (`prompts/code_generator_user.txt`). The pipeline fills the `$` placeholders with
Python's `string.Template`:

```
Problem:
$prompt

Implement this function, keeping exactly this name and these parameters:
$signature

Your function must satisfy this example:
$example_test
```

**Example of a prompt generated by the system** (problem 11, taken from
`results/phase1_baseline/Mbpp_11/llm_calls.jsonl`):

```
Problem:
Write a python function to remove first and last occurrence of a given character from the string.

Implement this function, keeping exactly this name and these parameters:
def remove_Occ(s, ch):

Your function must satisfy this example:
assert remove_Occ("hello","l") == "heo"
```

Only the first of MBPP's three asserts is shown to the model; it fixes the input/output format. The model never
sees the reference solution. All three asserts are used afterwards to decide whether the generated code is
correct.

### 2.2 Settings

| Setting | Code Generator | Notes |
|---|---|---|
| Provider / endpoint | OpenRouter, `POST /api/v1/chat/completions` | Plain HTTP with `requests` |
| Model | `cohere/north-mini-code:free` | Fallbacks, used only if it keeps failing: `nvidia/nemotron-3-super-120b-a12b:free`, `google/gemma-4-31b-it:free` (no fallback was needed) |
| temperature | 0.2 | Low: code must be precise |
| top_p | 1.0 | |
| max_tokens | 1024 | |
| seed | 42 | For repeatability |
| reasoning | `{"enabled": false}` | No hidden chain of thought; every logged call shows `reasoning_tokens = 0` |
| Retries | 4 per model (waits 5, 15, 30, 60 s) on HTTP 429/5xx/timeouts; then the next model | |
| Cache | A request identical in prompt, model and settings is answered from `llm_cache/` | Makes runs reproducible and saves quota |

Executor settings: 30 s timeout per execution. The default criterion is branch coverage with a 100% target;
both can be set on the command line (`--criterion statement|branch --target N`). Every run stores its full
settings in `config.json`.

### 2.3 Test Generator prompts and settings

**System prompt** (`prompts/test_generator_system.txt`; `$entry_point` is the function under test):

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

**User prompt for the first round** (`prompts/test_generator_user.txt`):

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

**User prompt for a feedback round** (`prompts/test_generator_feedback.txt`):

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

`$criterion_goal` is the sentence for the criterion the user asked for (`config.CRITERION_GOALS`, with the
target filled in):

| Criterion | Goal sentence |
|---|---|
| `statement` | Reach $target% statement coverage: every executable line of solution.py must be run by at least one test. |
| `branch` | Reach $target% branch coverage: every if/elif/while condition must be True in some test and False in some test, and every loop must run its body at least once and also finish at least once. |
| `loops` | Reach $target% loop coverage: for every loop there must be a test that skips its body completely, a test that runs exactly one iteration, and a test that runs two or more iterations; and every pair of consecutive decision outcomes must occur in that order in some test. |

**Example of a first-round prompt as actually sent** (problem 11, from
`results/phase2_branch100/Mbpp_11/llm_calls.jsonl`):

```
Problem description:
Write a python function to remove first and last occurrence of a given character from the string.

Example of correct behaviour:
assert remove_Occ("hello","l") == "heo"

Function under test (file solution.py; the line numbers on the left are not part of the code):
  1 | def remove_Occ(s, ch):
  2 |     # Find first occurrence
  3 |     first = s.find(ch)
  4 |     # Find last occurrence
  5 |     last = s.rfind(ch)
  6 |     # If character not found or only one occurrence, return original string
  7 |     if first == -1 or first == last:
  8 |         return s
  9 |     # Remove first and last occurrences
 10 |     return s[:first] + s[first+1:last] + s[last+1:]

Coverage goal: Reach 100% branch coverage: every if/elif/while condition must be True in some test and False in some test, and every loop must run its body at least once and also finish at least once.
Write between 3 and 10 tests.
```

If a round produces nothing usable, the next request ends with one extra line — for example `Attempt 1 could
not be used: the reply contains no parseable Python code. Reply with exactly one Python code block containing a
complete pytest file and nothing else.` This is also what makes the retry meaningful: responses are cached by
the exact request, so re-sending an identical prompt would return the same unusable reply.

**Settings**

| Setting | Code Generator | Test Generator | Why the difference |
|---|---|---|---|
| Model | `cohere/north-mini-code:free` | same | One model for both agents |
| temperature | 0.2 | **0.4** | Code must be precise; tests benefit from more varied inputs |
| top_p | 1.0 | 1.0 | Default |
| max_tokens | 1024 | **2048** | A test file with 3–10 tests is longer than a solution |
| seed | 42 | 42 | Repeatability where the provider supports it |
| reasoning | `{"enabled": false}` | same | No hidden chain of thought |

---

## 3. Formats of the code, the tests and the verdict

### 3.1 Generated code (`solution.py`)

`solution.py` contains the required function with the exact signature; helper functions and standard-library
imports are allowed. The reply is post-processed deterministically:

1. The first ```` ```python ```` block is extracted.
2. It must parse (`ast.parse`) and must define the required function at top level; otherwise the problem is
   recorded as `CODEGEN_FAILED`.
3. Top-level example code (an `if __name__ == "__main__":` block, bare calls such as `print(...)`, top-level
   asserts) is removed. It is not part of the unit and could never be covered by tests.

### 3.2 Test files (pytest)

MBPP's reference asserts are wrapped as pytest functions (`reference_tests_to_pytest`). Example for problem 11:

```python
from solution import *


def test_reference_1():
    assert remove_Occ("hello","l") == "heo"

def test_reference_2():
    assert remove_Occ("abcda","a") == "bcd"

def test_reference_3():
    assert remove_Occ("PHP","P") == "H"
```

**Generated test files** follow the same shape, and the rules are enforced by `check_test_file` rather than
assumed (a file that breaks one is discarded and the round counts as unusable):

```python
from solution import remove_Occ


def test_removes_first_and_last_occurrence():
    assert remove_Occ("hello", "l") == "heo"


def test_character_not_present_returns_the_same_string():
    assert remove_Occ("abc", "z") == "abc"
```

- import from `solution`; one top-level `test_` function per test, named after what it checks;
- plain `assert` statements (`pytest.raises` only if the problem says an exception is raised);
- **must not define the function under test** — a file that does would be testing its own copy;
- only pytest and the standard library, and nothing that breaks determinism or the "no files, no network" rule.

When the feedback loop adds a round, the final `test_solution.py` is the merged file: every import once, then
the tests of each round in order, with a duplicate test name renamed `<name>_r<round>`. Each round's own,
unmerged file stays in `round_<k>/test_solution.py`.

### 3.3 Verdict

The Test Executor runs:

```
python -m coverage run --branch --include=solution.py -m pytest -q --junitxml=junit.xml test_solution.py
```

It then reads `junit.xml` (the result of each test) and the `coverage json` report (statement %, branch %,
missing lines and branches), and writes `execution.json`. The verdict rules are checked in this order:

| Verdict | Condition |
|---|---|
| `ERROR` | The file could not be run: syntax/import error, no tests collected, or timeout |
| `TESTS_FAILED` | At least one test failed |
| `COVERAGE_NOT_MET` | All tests passed, but coverage is below the target |
| `PASS` | All tests passed and coverage is at or above the target |

- **Statement criterion:** statement coverage ≥ target.
- **Branch criterion:** branch coverage ≥ target **and** statement coverage ≥ target.
- **Loops criterion:** edge-pair coverage ≥ target **and** branch ≥ target **and** statement ≥ target.
- Each criterion also demands the weaker ones it subsumes, for a measurement reason rather than a pedantic one:
  a function with no decisions has no branches and no edge pairs, and 0 of 0 reads as 100%, so either criterion
  on its own would pass code that no test ever calls.
- **Test assertion failures and coverage are reported separately:** coverage also counts lines run by a test
  whose assertion fails.

### 3.4 Example: problem 11 (`remove_Occ`)

Generated code (`results/phase1_baseline/Mbpp_11/solution.py`):

```python
def remove_Occ(s, ch):
    # Find first occurrence
    first = s.find(ch)
    # Find last occurrence
    last = s.rfind(ch)
    # If character not found or only one occurrence, return original string
    if first == -1 or first == last:
        return s
    # Remove first and last occurrences
    return s[:first] + s[first+1:last] + s[last+1:]
```

Executor result for MBPP's 3 asserts (`reference/execution.json`, abridged):

```json
{
  "status": "RAN", "tests_total": 3, "tests_passed": 3, "tests_failed": 0,
  "statement_coverage": 83.33, "branch_coverage": 50.0,
  "missing_lines": [8], "missing_branches": [[7, 8]],
  "criterion": "branch", "target": 100.0, "target_met": false,
  "verdict": "COVERAGE_NOT_MET"
}
```

All three dataset asserts pass, but line 8 (`return s`) never runs, because every MBPP assert uses a character
that occurs at least twice. That untested branch hides a real difference from the reference solution:
`remove_Occ("abc", "b")` returns `"abc"` from the generated code but `"ac"` from MBPP's reference.

### 3.5 Examples of generated tests and verdicts

All three examples come from the committed run `results/phase2_branch100/` (criterion: branch, target 100%,
max 3 rounds). Each folder can be re-run by hand: `cd results/phase2_branch100/Mbpp_92/round_1` and then
`python -m pytest test_solution.py`.

#### Example 1 — problem 92 `is_undulating`: the goal is reached and the tests are right

MBPP's own 3 asserts leave 2 of the 8 branches unexecuted. Generated code
(`results/phase2_branch100/Mbpp_92/solution.py`):

```python
def is_undulating(n):
    s = str(n)
    if len(s) < 3:
        return False
    if len(set(s)) != 2:
        return False
    for i in range(len(s) - 2):
        if s[i] == s[i+1] or s[i+1] == s[i+2]:
            return False
    return True
```

| | Tests | Passed | Statement coverage | Branch coverage | Verdict |
|---|---|---|---|---|---|
| Baseline: MBPP's 3 asserts | 3 | 3 | 80.0% | 75.0% of 8 | `COVERAGE_NOT_MET` |
| Generated suite, round 1 | 8 | 8 | **100.0%** | **100.0%** | `PASS` |

The baseline misses lines 4 and 6 and the branches `3 → 4` and `5 → 6`: none of MBPP's asserts uses a number
shorter than three digits or one with more than two distinct digits. The generated suite
(`Mbpp_92/test_solution.py`) adds exactly those cases:

```python
from solution import is_undulating

def test_undulating_true():
    assert is_undulating(1212121) == True

def test_undulating_false_length_less_than_3():
    assert is_undulating(12) == False

def test_undulating_false_more_than_two_unique_digits():
    assert is_undulating(123123) == False

def test_undulating_false_adjacent_equal_digits():
    assert is_undulating(121121) == False
...
```

Validation: 7 of the 8 tests are `VALID`. The eighth, `assert is_undulating(111) == False`, is labelled
`MISLEADING`, and the label is worth reading carefully: MBPP's reference only checks that every digit equals
the digit two places before it, so it answers `True` for `111`. The generated code also requires two distinct
digits, so it answers `False`. Here the *test and the generated code* are the defensible reading of
"undulating" and the reference is the odd one out; the label only says the two implementations disagree.

#### Example 2 — problem 71 `comb_sort`: the tests catch a real bug

```python
def comb_sort(nums):
    n = len(nums)
    gap = n
    shrink = 1.3
    sorted_flag = False

    while not sorted_flag:
        sorted_flag = True
        gap = max(1, int(gap / shrink))
        for i in range(n - gap):
            if nums[i] > nums[i + gap]:
                nums[i], nums[i + gap] = nums[i + gap], nums[i]
                sorted_flag = False
    return nums
```

The loop stops as soon as one pass makes no swap, even while the gap is still greater than 1, so the list can
be left unsorted. Note what the coverage numbers say on their own: the baseline already reaches **100%
statement and 100% branch coverage** on this function, and it is still wrong. Coverage is not correctness.

| | Tests | Passed | Coverage (stmt / branch) | Verdict |
|---|---|---|---|---|
| Baseline: MBPP's 3 asserts | 3 | 2 | 100% / 100% | `TESTS_FAILED` |
| Generated suite, round 1 | 7 | 4 | 100% / 100% | `TESTS_FAILED` |

Validation labels the three failing tests `BUG_FOUND` — they fail on the generated code and pass on MBPP's
reference:

```python
def test_comb_sort_reverse_sorted():
    assert comb_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]          # BUG_FOUND

def test_comb_sort_gap_reduction_true():
    result = comb_sort([5, 15, 37, 25, 79])
    assert result == [5, 15, 25, 37, 79]                           # BUG_FOUND

def test_comb_sort_sorted_flag_false():
    result = comb_sort([10, 3, 7, 1, 9])
    assert result == [1, 3, 7, 9, 10]                              # BUG_FOUND
```

`verdict.json` (abridged):

```json
{"task_id": 71, "code_correct": false,
 "baseline": {"tests_total": 3, "tests_passed": 2, "statement_coverage": 100.0, "branch_coverage": 100.0,
              "verdict": "TESTS_FAILED"},
 "criterion": "branch", "target": 100.0, "rounds_used": 1, "final_round": 1,
 "final": {"tests_total": 7, "tests_passed": 4, "statement_coverage": 100.0, "branch_coverage": 100.0,
           "target_met": true, "verdict": "TESTS_FAILED"},
 "test_labels": {"VALID": 4, "BUG_FOUND": 3, "INVALID_TEST": 0, "MISLEADING": 0, "NOT_RUN": 0}}
```

The same effect is even clearer for problem 79 `word_len`, where the description asks whether a word's length is
**odd** and the generated code returns `len(s) % 2 == 0`. The generator was told to take expected values from
the description, so it wrote the tests for "odd" and 4 of its 6 tests are labelled `BUG_FOUND`. Had it read the
expected values off the code instead, all six would have passed and the bug would have gone unnoticed.

#### Example 3 — problem 11 `remove_Occ`: tests that agree with the code, and tests that are simply wrong

This is the problem from §3.4, where MBPP's asserts never reach the `return s` branch. The generated suite
reaches 100% branch coverage, but only 3 of its 10 tests are `VALID`:

| Label | Count | Example | Why |
|---|---|---|---|
| `VALID` | 3 | `remove_Occ("hello", "l") == "heo"` | Passes on both implementations |
| `BUG_FOUND` | 1 | `remove_Occ("xabc", "x") == "abc"` | Fails on the generated code, passes on the reference |
| `MISLEADING` | 4 | `remove_Occ("abc", "a") == "abc"` | The generated code returns the string unchanged when the character occurs once, and the test agrees with it; MBPP's reference removes it |
| `INVALID_TEST` | 2 | `remove_Occ("abracadabra", "a") == "brcdbr"` | Wrong expected value: removing only the first and last "a" gives `"bracadabr"` |

The four `MISLEADING` tests are the oracle problem in its purest form: the model was given the code, and for the
one branch the description does not pin down ("remove first and last occurrence" when there is only one
occurrence) it wrote tests that agree with the implementation in front of it. Nothing in a coverage number
reveals this — only the second run against an independent implementation does.

Problem 90 `len_log` shows the third failure mode, plain arithmetic mistakes:
`len_log(["Python", "pYTHON", "PYTHON"]) == 7` (every word has 6 characters) and
`len_log(["café", "coffee", "☕️"]) == 4` (`"coffee"` has 6) fail on both implementations and are labelled
`INVALID_TEST`.

---

## 4. Execution results

### 4.1 Phase 1 baseline: generated code checked with MBPP's own tests

Run: `python pipeline.py --mode baseline --out results/phase1_baseline`. The goal used for the verdict is 100%
branch coverage.

| Task | Function | Code correct | MBPP asserts passed | Statement coverage | Branch coverage | Verdict |
|---|---|---|---|---|---|---|
| 11 | `remove_Occ` | yes | 3/3 | 83.3% of 6 | 50.0% of 2 | COVERAGE_NOT_MET |
| 20 | `is_woodall` | yes | 3/3 | 90.9% of 11 | 83.3% of 6 | COVERAGE_NOT_MET |
| 65 | `recursive_list_sum` | yes | 3/3 | 100.0% of 7 | 100.0% of 4 | PASS |
| 66 | `pos_count` | yes | 3/3 | 100.0% of 2 | no branches | PASS |
| 67 | `bell_number` | yes | 3/3 | 100.0% of 12 | 100.0% of 6 | PASS |
| 69 | `is_sublist` | yes | 3/3 | 88.9% of 9 | 83.3% of 6 | COVERAGE_NOT_MET |
| 70 | `get_equal` | yes | 3/3 | 87.5% of 8 | 83.3% of 6 | COVERAGE_NOT_MET |
| 71 | `comb_sort` | no | 2/3 | 100.0% of 13 | 100.0% of 6 | TESTS_FAILED |
| 79 | `word_len` | no | 0/3 | 100.0% of 2 | no branches | TESTS_FAILED |
| 83 | `get_Char` | no | 0/3 | 100.0% of 4 | no branches | TESTS_FAILED |
| 90 | `len_log` | yes | 3/3 | 100.0% of 2 | no branches | PASS |
| 92 | `is_undulating` | yes | 3/3 | 80.0% of 10 | 75.0% of 8 | COVERAGE_NOT_MET |

**Aggregate numbers**

- **Code correctness:** 12/12 solutions generated; **9/12 (75%) correct** (pass all 3 MBPP asserts).
- **Mean coverage by MBPP's own tests:** statements 94.2%, branches 89.6%.
- **Coverage goal:** 100% branch coverage is reached for 7/12 problems. **PASS** (all asserts pass and the goal
  is met) for only 4/12.
- **Untested branches in correct code:** 5 of the 9 correct solutions (11, 20, 69, 70, 92) contain branches
  that MBPP's tests never execute.
- **LLM usage:** 12 calls, 1537 prompt tokens, 919 completion tokens, 0 reasoning tokens, all answered by the
  primary model. The committed `summary.md` was regenerated from the response cache after a file-handling fix,
  with identical results.

**Why the three incorrect solutions fail** (verified by running them)

| Task | Cause |
|---|---|
| 71 `comb_sort` | Real algorithmic bug. The loop stops after the first pass without swaps even while the gap is still larger than 1, so `comb_sort([5, 15, 37, 25, 79])` returns the list unsorted. |
| 79 `word_len` | Inverted condition. The problem asks whether the length is odd; the code returns `len(s) % 2 == 0`, contradicting even the example it was given. |
| 83 `get_Char` | Misleading specification. The text says "adding the ASCII value of all the characters … modulo 26", but MBPP's expected answers use alphabet positions (a = 1). The model followed the text and ignored the example. MBPP's own reference solution also returns the integer `122` instead of `"z"` when the sum is a multiple of 26. |

**What the baseline shows:** a correct solution according to the dataset's 3 asserts can still contain
branches no test has run, as in problem 11. Coverage-targeted tests (Phase 2) aim to close exactly this gap.

### 4.2 Phase 2: coverage-targeted generated tests

Run: `python pipeline.py --mode full --criterion branch --target 100 --max-rounds 3 --out results/phase2_branch100`.
The generated solutions are identical to the baseline's, because code generation came from the response cache,
so the two columns below describe exactly the same 12 functions.

| Task | Function | Code correct | Baseline stmt / branch | Rounds | Generated tests (passed) | Final stmt / branch | Goal met | Verdict | Labels V/B/I/M |
|---|---|---|---|---|---|---|---|---|---|
| 11 | `remove_Occ` | yes | 83.3% / 50.0% | 1 | 10 (7) | 100% / 100% | yes | TESTS_FAILED | 3/1/2/4 |
| 20 | `is_woodall` | yes | 90.9% / 83.3% | 1 | 6 (6) | 100% / 100% | yes | PASS | 6/0/0/0 |
| 65 | `recursive_list_sum` | yes | 100% / 100% | 1 | 7 (7) | 100% / 100% | yes | PASS | 7/0/0/0 |
| 66 | `pos_count` | yes | 100% / no branches | 1 | 7 (7) | 100% / no branches | yes | PASS | 6/0/0/1 |
| 67 | `bell_number` | yes | 100% / 100% | 1 | 7 (7) | 100% / 100% | yes | PASS | 7/0/0/0 |
| 69 | `is_sublist` | yes | 88.9% / 83.3% | 1 | 9 (9) | 100% / 100% | yes | PASS | 8/0/0/1 |
| 70 | `get_equal` | yes | 87.5% / 83.3% | 1 | 7 (7) | 100% / 100% | yes | PASS | 7/0/0/0 |
| 71 | `comb_sort` | no | 100% / 100% | 1 | 7 (4) | 100% / 100% | yes | TESTS_FAILED | 4/3/0/0 |
| 79 | `word_len` | no | 100% / no branches | 1 | 6 (1) | 100% / no branches | yes | TESTS_FAILED | 0/4/1/1 |
| 83 | `get_Char` | no | 100% / no branches | 1 | 6 (1) | 100% / no branches | yes | TESTS_FAILED | 0/2/3/1 |
| 90 | `len_log` | yes | 100% / no branches | 1 | 8 (6) | 100% / no branches | yes | TESTS_FAILED | 6/0/2/0 |
| 92 | `is_undulating` | yes | 80.0% / 75.0% | 1 | 8 (8) | 100% / 100% | yes | PASS | 7/0/0/1 |

#### The main question: do coverage-targeted LLM tests cover more than the dataset's own tests?

Yes, and the gap is entirely in the branches the dataset never exercises.

| Metric | Baseline: MBPP's 3 asserts | Generated tests (branch, 100%) |
|---|---|---|
| Mean statement coverage | 94.2% | **100.0%** |
| Mean branch coverage | 89.6% | **100.0%** |
| Coverage goal reached | 7/12 (58%) | **12/12 (100%)** |
| Tests per problem | 3 | 7.3 on average (88 in total) |
| Verdict `PASS` (all tests passed *and* goal met) | 4/12 | 7/12 |

The five problems where the baseline fell short (11, 20, 69, 70, 92) all reached 100% branch coverage with the
generated tests. For the other seven the baseline was already at 100% for the chosen criterion — four of them
because the generated function has no decision at all, which is also why `PASS` does not simply follow the
coverage numbers.

#### Single-shot vs with feedback

| | Goal reached | Mean rounds used |
|---|---|---|
| Round 1 only (single-shot) | 12/12 | — |
| Up to 3 rounds (feedback loop enabled) | 12/12 | 1.0 |

**The feedback loop never had to run.** One white-box prompt was enough to reach 100% statement and branch
coverage for every one of the 12 problems, so the loop stopped after round 1 each time and the two rows are
identical. This is a real result rather than a missing measurement, and it says something about the scale of
the benchmark: these functions have at most 8 branches, and their branch conditions are directly visible in the
numbered source the model is given. We would expect the loop to matter for larger functions, for branches that
need a particular combination of inputs, or with a weaker model — but on MBPP we cannot show that, and we do not
claim it. What we can show is that the mechanism works: the offline test
`tests/test_pipeline.py::test_feedback_round_closes_the_coverage_gap` drives a solution whose round-1 suite
reaches only 50% branch coverage, and the second round, given the measured gap, closes it to 100%.

A side effect worth noting for the API budget: because the goal was met in round 1 everywhere, the run cost 12
test-generation calls instead of the 36 the plan budgeted for.

#### Are the generated tests any good? (test validity and fault detection)

Coverage says nothing about whether a test checks the right thing, so every test in the final suites was run a
second time against MBPP's reference solution (§1.3).

| Label | Tests | Share |
|---|---|---|
| `VALID` — correct test | 61 | 69.3% |
| `BUG_FOUND` — caught a real bug in the generated code | 10 | 11.4% |
| `INVALID_TEST` — wrong expected value | 8 | 9.1% |
| `MISLEADING` — agrees with the generated code's wrong behaviour | 9 | 10.2% |
| **Total** | **88** | |

- **Test pass rate:** 70 of 88 tests (79.5%) pass on the generated code. The 18 failures are not noise: 10 of
  them are `BUG_FOUND`.
- **Fault detection: 3/3.** All three problems with incorrect generated code (71, 79, 83) have at least one
  `BUG_FOUND` test. For 79 `word_len`, MBPP's own asserts and the generated tests both catch the bug; for 71
  `comb_sort` the generated suite fails 3 tests where MBPP's asserts fail 1.
- **Where the 17 wrong tests come from:** 9 `MISLEADING` and 8 `INVALID_TEST`. Five of the nine `MISLEADING`
  labels (problems 11 and 92) are cases where the problem description does not pin the behaviour down, and the
  model, which was shown the code, resolved the ambiguity the same way the code did — the oracle problem,
  measured. The `INVALID_TEST` cases are simpler: expected values the model got arithmetically wrong (§3.5,
  problem 90).
- **One caveat on the labels themselves:** they treat MBPP's reference as the oracle, and for problem 92 the
  reference is arguably the one that is wrong (§3.5). `MISLEADING` therefore means "the two implementations
  disagree here", not always "the test is bad".

#### API usage and reproducibility

- 24 LLM calls for the whole run: 12 code generations (all answered from the committed cache) and 12
  test generations. Only **11 HTTP requests** were actually sent, because problem 11's round-1 call was already
  in the cache from the smoke run. No fallback model was needed, and no call was retried.
- Tokens: 5,846 prompt, 3,277 completion, **0 reasoning tokens** in every call — the evidence that no hidden
  chain of thought was used (§2.2).
- Re-running the command now costs 0 requests: every call is in `llm_cache/`, so the numbers above reproduce
  exactly.
- `verify_run.py results/phase2_branch100` re-derives every verdict from the measured numbers, checks the
  labels against the two runs they come from, and checks every final test file against the §3.2 rules.

### 4.3 The three criteria compared

The criterion is a command-line argument, so the whole experiment was run three times over the same 12
generated solutions (code generation came from the cache every time, so the code under test is identical):

| | Baseline: MBPP's 3 asserts | `--criterion statement` | `--criterion branch` | `--criterion loops` |
|---|---|---|---|---|
| Mean statement coverage | 94.2% | 100.0% | 100.0% | 100.0% |
| Mean branch coverage | 89.6% | 100.0% | 100.0% | 100.0% |
| Mean edge-pair coverage | 89.0% | 97.1% | 97.1% | 97.1% |
| **Its own goal reached** | 4/12 | **12/12** | **12/12** | **8/12** |
| Tests generated | 36 | 80 | 88 | **140** |
| Tests passing on the generated code | 33/36 | 83.8% | 79.5% | 83.6% |
| **Test validity rate** | — | 73.8% | 69.3% | **80.0%** |
| `MISLEADING` tests | — | 8 | 9 | **5** |
| Mean rounds used | — | 1.0 | 1.0 | **1.67** |
| Fault detection | — | 3/3 | 3/3 | 3/3 |

Three findings, and the third one is the only honest headline:

**1. Every criterion beats the dataset's own tests.** MBPP's 3 asserts per problem reach 94.2% / 89.6% / 89.0%;
every generated suite reaches 100% / 100% / 97.1%. That is the result the project set out to measure.

**2. The criterion changes the suite, not the coverage reached.** Asking for statement coverage produced 80
tests, branch coverage 88, and loop coverage 140 — and the per-problem test sets differ throughout. But all
three suites end at the *same* coverage: 100% statement, 100% branch, 97.1% edge pairs. On functions of 25
lines or fewer, a test that runs a line usually also takes both ways out of the decision above it and exercises
the orderings around it, so the stronger criteria have little left to ask for. The criteria would come apart on
larger functions, where reaching a line, covering the decision that guards it, and covering the order in which
decisions combine are three different problems.

**3. Only the `loops` criterion reveals that 97.1% is a ceiling.** Under `statement` and `branch` the verdict is
a clean 12/12, which quietly hides the fact that four of the twelve functions contain orderings that no input
can execute. Under `loops` those four come back as `COVERAGE_NOT_MET` with the exact missing requirement named
in `verdict.json` (§4.4). Put the other way round: **all three criteria met every requirement that was
reachable** — the 2.9% shortfall is entirely infeasible requirements, not missing tests.

A fourth observation worth reporting, though we cannot prove the cause from one run: the `loops` suites were
the **most valid** (80.0% `VALID`, 5 `MISLEADING`) despite being the largest, where the `branch` suites were the
least valid (69.3%, 9 `MISLEADING`). Asking for orderings seems to push the model towards ordinary edge cases —
an empty list, a single element, a value that fails on the last iteration — where asking for branches pushed it
towards contrived inputs chosen to flip a condition, which is where it tended to read the expected value off
the code.

**The feedback loop finally ran.** `loops` is the first criterion whose goal round 1 did not already meet, so
the loop fired for 5 problems and used 1.67 rounds on average (against 1.0 for the other two). It could not
raise coverage, because what was missing was infeasible — but it did keep adding usable tests: problem 92 grew
from 7 tests in round 1 to 25 after round 3, and **all 25 are labelled `VALID`**. So the loop improved the size
and the quality of the suite even where it could not improve the number it was aiming at.

Per-problem edge-pair coverage, measured with
`python -m agents.path_coverage --run <folder>` (which replays a finished run's suite under the tracer in a
temporary folder, without touching the run):

| Task | Edge pairs | MBPP's 3 asserts | Generated (`loops`) | Rounds | Verdict |
|---|---|---|---|---|---|
| 11 `remove_Occ` | 3 | 66.7% | **100%** | 1 | TESTS_FAILED (3 `INVALID_TEST`) |
| 20 `is_woodall` | 9 | 100% | 100% | 1 | TESTS_FAILED (3 `INVALID_TEST`) |
| 65 `recursive_list_sum` | 10 | 90.0% | **100%** | 1 | PASS |
| 66 `pos_count` | 0 | — | — | 1 | PASS (no decisions, so no pairs) |
| 67 `bell_number` | 18 | 88.9% | 94.4% | 3 | COVERAGE_NOT_MET — infeasible |
| 69 `is_sublist` | 9 | 77.8% | **100%** | 1 | PASS |
| 70 `get_equal` | 7 | 85.7% | 85.7% | 3 | COVERAGE_NOT_MET — infeasible |
| 71 `comb_sort` | 19 | 89.5% | 94.7% | 3 | COVERAGE_NOT_MET — infeasible |
| 79 `word_len` | 0 | — | — | 1 | TESTS_FAILED (6 `BUG_FOUND`) |
| 83 `get_Char` | 1 | 100% | 100% | 1 | TESTS_FAILED (2 `BUG_FOUND`) |
| 90 `len_log` | 0 | — | — | 1 | TESTS_FAILED (1 `INVALID_TEST`) |
| 92 `is_undulating` | 10 | 70.0% | 90.0% | 3 | COVERAGE_NOT_MET — infeasible |
| **Mean** | | **89.0%** | **97.1%** | 1.67 | 8/12 met the goal |

### 4.4 Infeasible test requirements

Every shortfall above is a requirement **no input can satisfy**. All four have the same shape — a loop whose
body cannot be skipped, because a guard above it has already established that the loop has work to do — and the
proof is short in each case.

```python
# problem 70, missing 4 -> 5 -> 8  ("reach the loop, skip the body, return")
1  def get_equal(Input):
2      if not Input:
3          return True            # <- an empty Input returns here
4      first_len = len(Input[0])
5      for tup in Input:          # <- so by line 5, Input is non-empty
6          if len(tup) != first_len:
7              return False
8      return True                # <- reaching line 8 directly from line 5 is impossible
```

| Task | Missing pair | Why no input can reach it |
|---|---|---|
| 67 `bell_number` | `9→10→17` | the inner `range(i)` is entered with `i ≥ 1`, so it always iterates at least once |
| 70 `get_equal` | `4→5→8` | the `if not Input` guard above means the loop always has an element |
| 71 `comb_sort` | `5→7→14` | `sorted_flag = False` is set immediately above, so `while not sorted_flag` always enters |
| 92 `is_undulating` | `5→7→10` | line 3 guarantees `len(s) ≥ 3`, so `range(len(s) - 2)` is never empty |

This is the classic **infeasible test requirement** of structural coverage: the stronger the criterion, the more
of its requirements no input can satisfy, and 100% stops being a meaningful target. It is also why the three
rounds of feedback for these four problems could not help — the model was being asked, in plain language, for
something impossible, and it responded by adding more tests of other cases (which is why problem 92 ends with
25 valid tests and the same 90% coverage).

The pipeline handles this the only honest way available to it: the goal is not met after the last round, so the
verdict is `COVERAGE_NOT_MET` and the unmet requirement is named in `verdict.json` for a human to judge. We
deliberately did **not** lower the target to make the table green. The remedy used in the literature — best
effort touring with sidetrips — requires a judgement about which requirements to excuse, and we had no way to
make that judgement automatically and still call the verdict a measurement.

**A note on validating the measurement itself.** The first `loops` run reported 70% for problem 65 with three
missing pairs. Problem 65 is recursive, and the tracer was recording one line sequence per *test*: when line 5
calls the function again, the inner call's lines were spliced into the outer call's sequence, so the line after
5 was never the loop header. Those three pairs were unobservable by construction rather than untested. The
tracer now keeps **one sequence per call frame**, which is also how coverage.py tracks arcs, and problem 65 went
to 100% with exactly the same tests. Two regression tests pin this down
(`test_covered_pairs_keeps_call_frames_apart`,
`test_edge_pairs_of_a_recursive_function_are_measured_per_call_frame`). The lesson generalises: a new coverage
metric is only as trustworthy as the instrument that measures it, which is the reason the other two criteria are
read straight out of coverage.py rather than computed by us.

---

## 5. Contributions

| Member | Contribution |
|---|---|
| `<Member 1>` | Phase 1 (PR #1): project plan; OpenRouter client with cache, retries, model fallback and logging; dataset selection; Code Generator agent and prompts; Test Executor agent (pytest + coverage.py, verdict rules, sandboxing); baseline pipeline and run; offline test suite for the pipeline code; report sections 1.1–1.2, 2.1–2.2, 3.1–3.4, 4.1 |
| `<Member 2>` | Phase 2 (PR #2): Test Generator agent and its three prompts (system, first round, feedback); the coverage helpers `describe_missing`, `merge_test_files` and `check_test_file`; test validation against MBPP's reference solution (`validate`, `classify_tests`); `pipeline.py --mode full` with the coverage feedback loop and the Phase 2 metrics; `verify_run.py`; the two official experiments (`results/phase2_branch100/`, `results/phase2_statement100/`); the third coverage criterion `--criterion loops` (edge-pair coverage, `agents/path_coverage.py`) with its infeasibility analysis; 58 further offline tests; report sections 1.3, 2.3, 3.2, 3.5, 4.2, 4.3, 4.4 and the limitations |

The steps, files and checks of each member are listed in detail in [`Contributions.md`](../Contributions.md).

## 6. Limitations

- **Small sample:** 12 problems and one model, limited by the free API tier.
- **Ambiguous specifications:** some MBPP descriptions are ambiguous or misleading (problem 83), so "incorrect"
  sometimes means "a different reasonable reading".
- **Coverage is not correctness:** 100% coverage shows every branch ran, not that every result was checked
  correctly.
- **Unreachable code:** some branches in generated code may be impossible to reach, which makes a 100% target
  impossible. This did not happen in our runs, but it is the reason the pipeline reports `COVERAGE_NOT_MET`
  after the last round instead of retrying for ever.
- **The feedback loop could not be shown to improve coverage.** Round 1 already met the goal for every
  problem under `statement` and `branch`, so the loop never ran there (§4.2). Under `loops` it did run, for 5
  problems and 1.67 rounds on average — but all 5 were short by an *infeasible* requirement, so the extra
  rounds added tests without adding coverage (§4.4). That the mechanism works is shown by an offline test,
  `tests/test_pipeline.py::test_loops_criterion_needs_a_second_round_where_branch_coverage_would_stop`, which
  drives a suite at 100% statement and 100% branch coverage but 83.3% edge-pair coverage and closes it to 100%
  in round 2. On this benchmark we cannot put a number on what the loop is worth.
- **The three criteria could not be told apart by the coverage they reached** — all three suites ended at
  100% statement, 100% branch and 97.1% edge-pair coverage (§4.3). They differ in the number of tests (80 / 88
  / 140) and in test validity (73.8% / 69.3% / 80.0%), but on functions of 25 lines or fewer the stronger
  criteria had nothing extra to reach. Larger functions would be needed to separate them.
- **100% edge-pair coverage is not reachable on this benchmark.** Four of the 12 problems contain a provably
  infeasible pair (§4.4), so for them the criterion can only ever report `COVERAGE_NOT_MET`. That is a property
  of structural coverage, not a defect of the pipeline, but it does mean a 100% target is the wrong instrument
  for grading a suite under this criterion.
- **Prime path coverage is not implemented.** It would need path enumeration on top of the control-flow graph
  and a policy for sidetrips around infeasible paths; no standard Python tool measures it, so unlike the other
  three it could not be reduced to a measurement we trust.
- **Validation depends on MBPP's reference being right.** The labels compare two implementations. When the
  reference itself is questionable — problem 92, where it calls `111` undulating, or problem 83, where it
  returns the integer `122` instead of `"z"` — a reasonable test is labelled `MISLEADING` or `INVALID_TEST`.
  The labels are evidence about disagreement, not a verdict on the test alone.
- **31% of the generated tests were not valid** (9 `MISLEADING`, 8 `INVALID_TEST` of 88). A coverage-targeted
  generator produces tests that *run* the code; making them *check* the right thing is the harder half, and the
  white-box prompt that makes high coverage easy is also what pulls the expected values towards the code.
  Automatically generated tests of this kind are a starting point for a human reviewer, not a test suite to
  commit unread.
- **One measurement per problem.** Temperature is 0.4 for test generation, so a second run with a different
  seed would give somewhat different suites; we did not repeat the experiment to measure that variance.

## 7. Tools used

- **LLM:** `cohere/north-mini-code:free` via OpenRouter (free tier).
- **Testing tools:** pytest 9.1.1, coverage.py 7.16.2, Python 3.12. Statement and branch coverage come from
  `coverage json`; edge-pair coverage is computed in `agents/path_coverage.py` from coverage.py's own
  control-flow graph plus per-test line traces recorded with `sys.settrace`.
- **AI assistance during development:** Claude Code (Anthropic's CLI coding assistant) was used by both
  members for planning, writing the pipeline code and its tests, and drafting this report. Every number quoted
  here was produced by running the committed code, not by the assistant.
- **No agent framework:** the only third-party runtime dependencies are `requests`, `pytest` and `coverage`.
  There is no LangChain/LangGraph, no vector store and no retrieval step.
