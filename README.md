# AI-Assisted Unit Testing Pipeline

CSE731 Software Testing (IIIT Bangalore), mid-term project. A small agentic pipeline, written in plain Python
with no agent framework, that:

1. asks an LLM to write a function for an MBPP problem (**Code Generator agent**),
2. asks an LLM to write pytest tests aimed at a user-chosen **coverage criterion**, such as 100% branch coverage
   (**Test Generator agent**, Phase 2),
3. runs the tests with coverage.py and gives a verdict (**Test Executor agent**).

The full design, the work split and every decision are in **[PROJECT_PLAN.md](PROJECT_PLAN.md)**.

| Phase | Owner | Status |
|---|---|---|
| Phase 1: LLM client, dataset, Code Generator, Test Executor, baseline run | Member 1 | Done ([results](results/phase1_baseline/summary.md)) |
| Phase 2: Test Generator, coverage feedback loop, test validation, experiments | Member 2 | Done (branch 100%: [results](results/phase2_branch100/summary.md); statement 100%: [results](results/phase2_statement100/summary.md)) |

## Setup

You need Python 3.10 or newer (developed on 3.12) and git. The commands below are for PowerShell on Windows;
on macOS/Linux use `source venv/bin/activate` instead of the `Activate.ps1` line.

```powershell
git clone https://github.com/Ansh-Gupta0310/ST-Mini-Project.git
cd ST-Mini-Project
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell says running scripts is disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
once, then activate again.

### Set your API key (never put it in a file in this repo)

1. Create a free account at [openrouter.ai](https://openrouter.ai) and create a key under **Keys**.
2. Windows: press Start, type **"environment variables"**, and open **"Edit environment variables for your
   account"**. Under *User variables* click **New…**, enter the name `OPENROUTER_API_KEY` and paste the key
   as the value. macOS/Linux: add `export OPENROUTER_API_KEY=...` to your shell profile.
   Alternatively, create a file called `.env` in the repository folder with one line,
   `OPENROUTER_API_KEY=sk-or-v1-...`. It is git-ignored, and a real environment variable always wins over it.
3. **Restart VS Code completely**, so its terminals see the new variable.
4. Check it without printing the key:

   ```powershell
   python -c "import os; print('set' if os.getenv('OPENROUTER_API_KEY') else 'missing')"
   ```

The key is only read from the environment (`config.load_env_file` copies a local `.env` into it at start-up).
It is never printed, logged, cached, committed or passed to the generated code.

## Commands

All commands run from the repository folder with the venv active.

| What | Command | API calls |
|---|---|---|
| Run our own tests (offline) | `pytest -q` | 0 |
| Show today's free quota | `python -m agents.llm_client --quota` | 0 |
| Check the model works | `python -m agents.llm_client --ping` | 1 the first time, then cached |
| Rebuild the 12-problem subset | `python data/prepare_dataset.py` | 0 (downloads MBPP) |
| Run each reference solution against MBPP's tests | `python -m agents.test_executor --self-check` | 0 |
| Generate the solution for one problem | `python -m agents.code_generator --task-id 11` | 1, or 0 if cached |
| Generate tests for one problem (round 1) | `python -m agents.test_generator --task-id 11 --solution results/phase1_baseline/Mbpp_11/solution.py` | 1, or 0 if cached |
| Baseline run, one problem (smoke test) | `python pipeline.py --mode baseline --task-ids 11 --out runs/smoke` | 0 if cached |
| Baseline run, all 12 problems | `python pipeline.py --mode baseline --out results/phase1_baseline` | 0 if cached |
| Full run, one problem (smoke test) | `python pipeline.py --mode full --task-ids 11 --out runs/smoke2` | up to 3, or 0 if cached |
| Full run, all 12 problems (the Phase 2 experiment) | `python pipeline.py --mode full --criterion branch --target 100 --max-rounds 3 --out results/phase2_branch100` | up to 36, or 0 if cached |
| Full run without the feedback loop (single-shot) | `python pipeline.py --mode full --max-rounds 1 --out runs/single_shot` | up to 12, or 0 if cached |
| Full run with the other criterion | `python pipeline.py --mode full --criterion statement --target 100 --out results/phase2_statement100` | 0 if cached |
| Check a finished run (verdicts vs measured numbers, test-file rules) | `python verify_run.py results/phase2_branch100` | 0 |

Other `pipeline.py` options: `--task-ids 11 20`, `--limit N`, `--criterion statement|branch`, `--target 100`,
`--max-rounds N` (`--mode full` only; `1` switches the feedback loop off).

**The two modes**

- `--mode baseline` runs steps [1]–[2]: generate `solution.py`, then run MBPP's own 3 asserts against it. This
  gives `code_correct` and the coverage the *dataset's* tests reach — the baseline to compare against.
- `--mode full` adds steps [3]–[5]: generate pytest tests aimed at the coverage goal, re-generate while the
  goal is not met (up to `--max-rounds`, new tests are added to the existing ones), and finally re-run the
  tests against MBPP's reference solution to label each one `VALID`, `BUG_FOUND`, `INVALID_TEST` or
  `MISLEADING`. Code generation comes from the cache, so a full run repeats no Phase 1 call.

### Output of a run

```
<out>/config.json      every setting used (models, temperatures, seed, prompt hashes, package versions)
<out>/summary.md       results table (summary.json has the same data)
<out>/Mbpp_<id>/       problem.json, llm_calls.jsonl, solution.py, verdict.json
                       reference/  = MBPP's 3 asserts run against solution.py: test_solution.py, junit.xml,
                                     coverage.json, execution.json, output.txt, coverage_html/index.html
                       --mode full also writes:
                       round_1/ … round_k/  one execution folder per test-generation round
                       test_solution.py     the final merged test suite
                       validation/          the final suite run against MBPP's reference solution
                       validation.json      the label of every test, and how it behaved on both solutions
```

Every execution folder can be re-run by hand: `cd <folder>` and then `python -m pytest test_solution.py`.

## Good to know

- **Free quota:** about 50 free-model requests per day per OpenRouter account. Check with `--quota`; the
  counter can lag behind by a few minutes.
- **`llm_cache/` is committed on purpose.** A request with the same prompt, model and settings is answered from
  the cache, so re-runs, reviews and the demo cost no quota and give identical results. Changing a prompt, a
  setting in `config.py` or the model makes new requests.
- **`runs/` is for scratch output** and is git-ignored. `results/` holds the official runs and is committed.
  `coverage_html/` folders are regenerated on every run (coverage.py marks them git-ignored).
- **OneDrive:** the project works inside a OneDrive folder. OneDrive marks synced folders read-only;
  `agents/test_executor.py:remove_path` handles that when old results are replaced.

## Repository layout

```
config.py            all settings (models, temperatures, timeouts, coverage defaults)
pipeline.py          orchestrator (command line)
verify_run.py        re-checks a finished run: every verdict against the numbers it was computed from
agents/              llm_client.py, code_generator.py, test_generator.py, test_executor.py,
                     code_utils.py, models.py
prompts/             prompt templates ($placeholders, filled with string.Template)
data/                prepare_dataset.py and mbpp_subset.json (the 12 problems)
tests/               offline tests for our own code (no API calls)
llm_cache/           cached LLM responses (committed)
results/             official runs (committed): phase1_baseline, phase2_branch100, phase2_statement100
report/report.md     the project report
Contributions.md     what each team member did (each member fills in their own section)
```
