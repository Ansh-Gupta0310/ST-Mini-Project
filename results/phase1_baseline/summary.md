# Run summary: baseline

| Setting | Value |
|---|---|
| Mode | baseline (Code Generator + MBPP's 3 reference asserts) |
| Coverage goal used for the verdict | branch coverage >= 100% |
| Model | `cohere/north-mini-code:free` (fallbacks: `nvidia/nemotron-3-super-120b-a12b:free`, `google/gemma-4-31b-it:free`) |
| Code Generator settings | temperature 0.2, top_p 1.0, max_tokens 1024, seed 42, reasoning disabled |
| Started / finished (UTC) | 2026-09-30T19:05:07+00:00 / 2026-09-30T19:05:25+00:00 |

## Results per problem

| Task | Function | Status | Code correct | MBPP asserts passed | Statement coverage | Branch coverage | Verdict | LLM calls (cached) |
|---|---|---|---|---|---|---|---|---|
| 11 | `remove_Occ` | COMPLETED | yes | 3/3 | 83.3% of 6 | 50.0% of 2 | COVERAGE_NOT_MET | 1 (1) |
| 20 | `is_woodall` | COMPLETED | yes | 3/3 | 90.9% of 11 | 83.3% of 6 | COVERAGE_NOT_MET | 1 (1) |
| 65 | `recursive_list_sum` | COMPLETED | yes | 3/3 | 100.0% of 7 | 100.0% of 4 | PASS | 1 (1) |
| 66 | `pos_count` | COMPLETED | yes | 3/3 | 100.0% of 2 | no branches | PASS | 1 (1) |
| 67 | `bell_number` | COMPLETED | yes | 3/3 | 100.0% of 12 | 100.0% of 6 | PASS | 1 (1) |
| 69 | `is_sublist` | COMPLETED | yes | 3/3 | 88.9% of 9 | 83.3% of 6 | COVERAGE_NOT_MET | 1 (1) |
| 70 | `get_equal` | COMPLETED | yes | 3/3 | 87.5% of 8 | 83.3% of 6 | COVERAGE_NOT_MET | 1 (1) |
| 71 | `comb_sort` | COMPLETED | no | 2/3 | 100.0% of 13 | 100.0% of 6 | TESTS_FAILED | 1 (1) |
| 79 | `word_len` | COMPLETED | no | 0/3 | 100.0% of 2 | no branches | TESTS_FAILED | 1 (1) |
| 83 | `get_Char` | COMPLETED | no | 0/3 | 100.0% of 4 | no branches | TESTS_FAILED | 1 (1) |
| 90 | `len_log` | COMPLETED | yes | 3/3 | 100.0% of 2 | no branches | PASS | 1 (1) |
| 92 | `is_undulating` | COMPLETED | yes | 3/3 | 80.0% of 10 | 75.0% of 8 | COVERAGE_NOT_MET | 1 (1) |

Verdict = the Test Executor's verdict for MBPP's own 3 asserts with the goal "branch coverage >= 100%": PASS (all passed, goal met), COVERAGE_NOT_MET (all passed, goal not met), TESTS_FAILED (at least one assert failed), ERROR (could not run).

## Aggregate

- Problems run: 12 of 12 planned
- Code generated: 12/12; code correct (passes all 3 MBPP asserts): 9/12 (75.0%)
- Mean coverage of the generated code by MBPP's own tests: statements 94.2%, branches 89.6% (over the 12 problem(s) with generated code)
- Coverage goal (branch coverage >= 100%) reached by MBPP's own tests: 7/12; with all 3 asserts also passing (verdict PASS): 4/12
- LLM calls: 12 (12 from the cache); HTTP requests sent: 0; tokens: 1537 prompt, 919 completion, 0 reasoning
- Models that answered: `cohere/north-mini-code:free`
