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
| Phase 2: Test Generator, coverage feedback loop, test validation, experiments | Member 2 | To do ([PROJECT_PLAN.md §7](PROJECT_PLAN.md#7-phase-2--member-2-via-pull-request-step-by-step)) |

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
3. **Restart VS Code completely**, so its terminals see the new variable.
4. Check it without printing the key:

   ```powershell
   python -c "import os; print('set' if os.getenv('OPENROUTER_API_KEY') else 'missing')"
   ```

The key is only read from the environment. It is never printed, logged, cached or passed to the generated
code.

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
| Baseline run, one problem (smoke test) | `python pipeline.py --mode baseline --task-ids 11 --out runs/smoke` | 0 if cached |
| Baseline run, all 12 problems | `python pipeline.py --mode baseline --out results/phase1_baseline` | 0 if cached |

Other `pipeline.py` options: `--task-ids 11 20`, `--limit N`, `--criterion statement|branch`, `--target 100`.
`--mode full` (with `--max-rounds`) is added in Phase 2.

### Output of a run

```
<out>/config.json      every setting used (models, temperatures, seed, prompt hashes, package versions)
<out>/summary.md       results table (summary.json has the same data)
<out>/Mbpp_<id>/       problem.json, llm_calls.jsonl, solution.py, verdict.json
                       reference/  = MBPP's 3 asserts run against solution.py: test_solution.py, junit.xml,
                                     coverage.json, execution.json, output.txt, coverage_html/index.html
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
agents/              llm_client.py, code_generator.py, test_executor.py, code_utils.py, models.py
prompts/             prompt templates ($placeholders, filled with string.Template)
data/                prepare_dataset.py and mbpp_subset.json (the 12 problems)
tests/               offline tests for our own code (no API calls)
llm_cache/           cached LLM responses (committed)
results/             official runs (committed)
report/report.md     the project report
Contributions.md     what each team member did (each member fills in their own section)
```
