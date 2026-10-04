# Contributions

CSE731 Software Testing, mid-term project. This file records what each team member did. It is the source for
section 5 of the report (assignment item 5: "Each member's contribution to the project").

**How to fill it in**

- Each member edits **only their own section**, in their own pull request (Member 2: in PR #2).
- Replace every `<...>` placeholder, and list the files you created or changed for each plan step.
- Keep it factual: name the files, the checks you ran and the results you got.

## Summary

| Member | Phase | Main contribution | Pull request |
|---|---|---|---|
| `Ansh Gupta IMT2023540` (GitHub @Ansh-Gupta0310) | Phase 1 | Project plan; LLM client; dataset selection; Code Generator and Test Executor agents; baseline pipeline and run; offline test suite; README and Phase 1 report sections | PR #1 (`phase-1-foundation`) |
| `Satyam Dewangan IMT2023545` (GitHub @Satyamashu05) | Phase 2 | Test Generator agent and its three prompts; coverage feedback loop; merging of test rounds; test validation against MBPP's reference solution; `pipeline.py --mode full` and the Phase 2 metrics; the official experiment; Phase 2 report sections | PR #2 (`phase-2-test-generation`) |

---

## Member 1: `Ansh Gupta` (`IMT2023540`, GitHub @Ansh-Gupta0310)

**Phase 1** ([PROJECT_PLAN.md §6](PROJECT_PLAN.md#6-phase-1--member-1-step-by-step)): pull request #1 from
branch `phase-1-foundation`, with one commit per plan step.

| Plan step | What I did | Files |
|---|---|---|
| Planning | Designed the pipeline, the split into two phases and the data contracts between them. Before building, checked the MBPP data, coverage.py's report format and the free API limits | `PROJECT_PLAN.md` |
| 1.1–1.2 | Set up the repository, the dependencies and the test configuration | `.gitignore`, `requirements.txt`, `pytest.ini`, `.github/pull_request_template.md` |
| 1.3 | Central configuration: models, temperatures, seed, timeouts, coverage defaults | `config.py` |
| 1.4 | OpenRouter client over plain HTTP: response cache, retries with backoff, model fallback, one log line per call, quota and ping helpers. The API key is never printed, logged or cached | `agents/llm_client.py`, `agents/models.py` |
| 1.5 | Deterministic selection of 12 MBPP problems (official test split, at least 2 decision points, at most 25 lines) | `data/prepare_dataset.py`, `data/mbpp_subset.json` |
| 1.6 | Test Executor agent: runs pytest under coverage.py in a separate process with a timeout, reads the JUnit and coverage reports, and applies the verdict rules. The generated code cannot read the API key | `agents/test_executor.py` |
| 1.7 | Code Generator agent and its prompts; extraction and clean-up of the generated code | `agents/code_generator.py`, `agents/code_utils.py`, `prompts/code_generator_system.txt`, `prompts/code_generator_user.txt` |
| 1.8 | Pipeline, baseline mode: calls the agents in order and writes one folder per problem, plus `config.json`, `summary.json` and `summary.md` for the run | `pipeline.py` |
| 1.9 | Baseline run on all 12 problems, and analysis of the three incorrect solutions | `results/phase1_baseline/`, `llm_cache/` |
| 1.10 | README; report sections 1.1–1.2, 2.1–2.2, 3.1–3.4 and 4.1; handover notes for Phase 2 ([PROJECT_PLAN.md §7.0](PROJECT_PLAN.md#70-handover-notes-from-phase-1)); this file | `README.md`, `report/report.md`, `Contributions.md` |
| Tests | 54 offline tests for our own code: LLM client, Test Executor, code helpers, Code Generator and pipeline. None of them calls the API | `tests/` |

**Checks and results**

- `pytest -q`: 54 passed. `python -m agents.test_executor --self-check`: all 12 MBPP reference solutions pass
  their own tests.
- Baseline ([summary](results/phase1_baseline/summary.md)): 9 of the 12 generated solutions are correct. MBPP's
  own tests cover 94.2% of statements and 89.6% of branches on average, and give verdict PASS for only 4 of 12.
- Found and fixed a bug: re-running into an existing results folder failed inside OneDrive, which marks synced
  folders read-only. The fix comes with a regression test.

---

## Member 2: `Satyam Dewangan` (`IMT2023545`, GitHub @`<username>`)

**Phase 2** ([PROJECT_PLAN.md §7](PROJECT_PLAN.md#7-phase-2--member-2-via-pull-request-step-by-step)): pull
request #2 from branch `phase-2-test-generation`.

Planned work (PROJECT_PLAN.md §5): the Test Generator agent and its prompts, the coverage feedback loop, test
validation against MBPP's reference solution, `pipeline.py --mode full`, the official experiment and the final
report.

| Plan step | What I did | Files |
|---|---|---|
| 2.0 Setup | Cloned the repository, installed the dependencies, set up my own OpenRouter key, and checked that a baseline run is answered entirely from the committed cache (0 quota) | – |
| 2.1 Test Generator prompts | Wrote the system prompt, the first-round prompt and the feedback prompt; added `TESTGEN_SETTINGS` (temperature 0.4, max_tokens 2048, seed 42), `CRITERION_GOALS` and `criterion_goal()`, which fills the user-chosen target into the goal sentence | `prompts/test_generator_system.txt`, `prompts/test_generator_user.txt`, `prompts/test_generator_feedback.txt`, `config.py` |
| 2.2 Helpers in `code_utils.py` | `describe_missing` turns coverage.py's missing lines and branches into plain sentences; `merge_test_files` joins two rounds with `ast` (imports once, duplicate test names renamed `<name>_r<round>`); `check_test_file` rejects a test file that does not parse, has no `test_` function, redefines the function under test, never imports `solution`, or imports something non-deterministic | `agents/code_utils.py` |
| 2.3 Test Generator agent | The agent: builds the first-round or feedback prompt, calls the LLM with `TESTGEN_SETTINGS`, extracts the code and applies `check_test_file`. Added the `retry_note` argument, because the response cache would otherwise answer a repeated prompt with the same unusable reply | `agents/test_generator.py` |
| 2.4 Test validation | `validate` re-runs the final suite against MBPP's reference solution in its own folder; `classify_tests` applies the VALID / BUG_FOUND / INVALID_TEST / MISLEADING table, with `NOT_RUN` for a test the reference run never reported; `count_labels` counts them for the summary | `agents/test_executor.py` |
| 2.5 `pipeline.py --mode full` and the feedback loop | Split steps [1]–[2] into `generate_and_check` so both modes share them, added `run_full_problem` and `generate_tests` (the loop of §3.8, unusable rounds thrown away, each round in its own folder, the final suite merged and validated), and extended `config.json`, `verdict.json`, `summary.json` and `summary.md` with the §3.11 metrics and the baseline-vs-generated comparison | `pipeline.py` |
| 2.6 Official experiment | `python pipeline.py --mode full --criterion branch --target 100 --max-rounds 3 --out results/phase2_branch100`, plus a one-problem smoke run first | `results/phase2_branch100/`, `llm_cache/` |
| 2.7 Report | Report sections 1.3 (how the generator targets a criterion, the loop, validation), 2.3 (prompts and settings), the generated-test format in 3.2, the worked examples in 3.5, and all of section 4.2 (results); recorded the decisions that extend the plan in `PROJECT_PLAN.md`, marked **[Phase 2 decision]** | `report/report.md`, `PROJECT_PLAN.md`, `README.md`, `Contributions.md` |
| Tests | 35 more offline tests, none of which calls the API: the three new `code_utils` helpers, the Test Generator agent (prompt content, rejected replies, settings), `classify_tests`/`validate` against a deliberately buggy `sign()`, and nine `--mode full` pipeline tests with a faked network (feedback round, merge and rename, single-shot, `TESTGEN_FAILED`, an unusable round, and a bug found by validation) | `tests/test_code_utils.py`, `tests/test_test_generator.py`, `tests/test_executor.py`, `tests/test_pipeline.py` |

**Checks and results**

- `pytest -q`: 114 passed, 1 skipped (a Windows-only test), no API calls.
- `python verify_run.py results/phase2_branch100` and the same for `results/phase2_statement100`: every verdict
  follows from the measured numbers, and every final test file follows the §3.6 rules.
- Official run ([summary](results/phase2_branch100/summary.md)), criterion branch, target 100%: mean coverage
  rose from 94.2% / 89.6% (MBPP's own asserts) to **100% / 100%**, and the goal was reached for **12/12**
  problems instead of 7/12. 88 tests: 61 `VALID`, 10 `BUG_FOUND`, 8 `INVALID_TEST`, 9 `MISLEADING`; all 3
  problems with incorrect code have at least one `BUG_FOUND` test. 11 HTTP requests, 0 reasoning tokens.
- The feedback loop never ran: round 1 already met the goal for all 12 problems (mean 1.0 rounds), so the run
  cost 12 test-generation calls instead of the 36 budgeted. Reported as a finding in report §4.2, with the loop
  itself covered by an offline test.
- Also ran the optional second criterion ([summary](results/phase2_statement100/summary.md)),
  `--criterion statement --target 100`: 12/12, 80 tests, validity 73.8%.
- Found while building the loop: retrying after an unusable round only works if the prompt changes, because the
  request cache is keyed on the exact request body. The retry now carries the reason the previous reply was
  rejected, and a pipeline test asserts it.

### Third coverage criterion: `--criterion loops` (edge-pair coverage)

Added after the Phase 2 run: the assignment's requirement (1) names three example criteria ("cover all
statements, cover all loops, cover all decision statements") and only two of them were implemented.

| What I did | Files |
|---|---|
| Edge-pair coverage. The control-flow graph comes from coverage.py's own parser, so there is no CFG analysis of ours to trust; required pairs are every `(a, b, c)` with arcs `a->b` and `b->c`; covered pairs come from per-test line traces | `agents/path_coverage.py` |
| Found that a `sys.settrace` tracer cannot share a process with `coverage run` — measured: coverage.py dropped to 16.7% statements and 0% branches — so the traced measurement is a second pytest pass, run only for `--criterion loops` | `agents/test_executor.py` |
| `loops` in `CRITERIA` and `CRITERION_GOALS`; the target rule `edge-pair >= t and branch >= t and statement >= t`; the new `ExecutionResult` fields; missing orderings described for the feedback loop; the edge-pair columns in `summary.md` | `config.py`, `agents/models.py`, `agents/code_utils.py`, `pipeline.py` |
| 26 more offline tests, including one that shows the criterion earning its place: a suite at 100% statement **and** 100% branch coverage sits at 83.3% edge-pair coverage, so the feedback loop runs a second round where a branch run would have stopped | `tests/test_path_coverage.py`, `tests/test_executor.py`, `tests/test_code_utils.py`, `tests/test_pipeline.py` |
| Checked for regressions: `summary.md` for the Phase 1 baseline and for the Phase 2 branch run both still reproduce byte for byte | `verify_run.py` |

**Checks and results**

- Official run ([summary](results/phase2_loops100/summary.md)), `--criterion loops --target 100`: **140 tests**
  (against 88 for branch), mean edge-pair coverage **97.1%** against **89.0%** for MBPP's own asserts, and the
  highest test validity of the three criteria (**80.0%**, with only 5 `MISLEADING`). Goal reached 8/12. 22 HTTP
  requests.
- The four problems below 100% (67, 70, 71, 92) are short by a **provably infeasible** pair: each needs a loop
  body to be skipped, and in each case a guard above the loop forces at least one iteration. All *reachable*
  requirements were met, by all three criteria.
- This criterion is the only one for which the feedback loop had anything to do: 1.67 rounds on average against
  1.0 for the other two. It could not raise coverage (what was missing was infeasible) but it kept adding
  usable tests — problem 92 went from 7 tests to 25, all 25 labelled `VALID`.
- Found and fixed a bug in my own measurement before trusting the numbers: the first run reported 70% for the
  recursive problem 65, because the tracer kept one line sequence per test, so a recursive call's lines were
  spliced into the caller's sequence. Keeping one sequence per call frame — which is what coverage.py does for
  arcs — put problem 65 at 100% with the same tests. Two regression tests cover it.

---
