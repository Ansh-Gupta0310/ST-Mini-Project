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
| `<Member 1 name>` (GitHub @Ansh-Gupta0310) | Phase 1 | Project plan; LLM client; dataset selection; Code Generator and Test Executor agents; baseline pipeline and run; offline test suite; README and Phase 1 report sections | PR #1 (`phase-1-foundation`) |
| `<Member 2 name>` (GitHub @`<username>`) | Phase 2 | `<fill in>` | PR #2 (`phase-2-test-generation`) |

---

## Member 1: `<name>` (`<roll no.>`, GitHub @Ansh-Gupta0310)

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

**AI tools used:** Claude Code (AI coding assistant) for planning, implementation and verification.

---

## Member 2: `<name>` (`<roll no.>`, GitHub @`<username>`)

**Phase 2** ([PROJECT_PLAN.md §7](PROJECT_PLAN.md#7-phase-2--member-2-via-pull-request-step-by-step)): pull
request #2 from branch `phase-2-test-generation`.

Planned work (PROJECT_PLAN.md §5): the Test Generator agent and its prompts, the coverage feedback loop, test
validation against MBPP's reference solution, `pipeline.py --mode full`, the official experiment and the final
report.

| Plan step | What I did | Files |
|---|---|---|
| 2.0 Setup | `<fill in>` | – |
| 2.1 Test Generator prompts | `<fill in>` | `<fill in>` |
| 2.2 Helpers in `code_utils.py` | `<fill in>` | `<fill in>` |
| 2.3 Test Generator agent | `<fill in>` | `<fill in>` |
| 2.4 Test validation | `<fill in>` | `<fill in>` |
| 2.5 `pipeline.py --mode full` and the feedback loop | `<fill in>` | `<fill in>` |
| 2.6 Official experiment | `<fill in>` | `<fill in>` |
| 2.7 Report | `<fill in>` | `<fill in>` |
| Tests | `<fill in>` | `<fill in>` |

**Checks and results**

- `<result of pytest -q>`
- `<key numbers from results/phase2_branch100/summary.md>`

**AI tools used:** `<fill in>`

---

## Done together

- `<fill in: for example, reviewing each other's pull requests, preparing the demo, finalising and submitting the report>`
