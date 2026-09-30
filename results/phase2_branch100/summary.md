# Run summary: full

| Setting | Value |
|---|---|
| Mode | full (Code Generator + Test Generator + coverage feedback loop + validation) |
| Coverage goal used for the verdict | branch coverage >= 100% |
| Model | `cohere/north-mini-code:free` (fallbacks: `nvidia/nemotron-3-super-120b-a12b:free`, `google/gemma-4-31b-it:free`) |
| Code Generator settings | temperature 0.2, top_p 1.0, max_tokens 1024, seed 42, reasoning disabled |
| Test Generator settings | temperature 0.4, top_p 1.0, max_tokens 2048, seed 42, reasoning disabled |
| Max test-generation rounds | 3 |
| Started / finished (UTC) | 2026-09-30T21:51:22+00:00 / 2026-09-30T21:58:51+00:00 |

## Results per problem

| Task | Function | Status | Code correct | Baseline stmt % | Baseline branch % | Rounds | Tests passed | Final stmt % | Final branch % | Goal met | Verdict | Test labels V/B/I/M | LLM calls (cached) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 11 | `remove_Occ` | COMPLETED | yes | 83.3% | 50.0% of 2 | 1 | 7/10 | 100.0% | 100.0% of 2 | yes | TESTS_FAILED | 3/1/2/4 | 2 (2) |
| 20 | `is_woodall` | COMPLETED | yes | 90.9% | 83.3% of 6 | 1 | 6/6 | 100.0% | 100.0% of 6 | yes | PASS | 6/0/0/0 | 2 (1) |
| 65 | `recursive_list_sum` | COMPLETED | yes | 100.0% | 100.0% of 4 | 1 | 7/7 | 100.0% | 100.0% of 4 | yes | PASS | 7/0/0/0 | 2 (1) |
| 66 | `pos_count` | COMPLETED | yes | 100.0% | no branches | 1 | 7/7 | 100.0% | no branches | yes | PASS | 6/0/0/1 | 2 (1) |
| 67 | `bell_number` | COMPLETED | yes | 100.0% | 100.0% of 6 | 1 | 7/7 | 100.0% | 100.0% of 6 | yes | PASS | 7/0/0/0 | 2 (1) |
| 69 | `is_sublist` | COMPLETED | yes | 88.9% | 83.3% of 6 | 1 | 9/9 | 100.0% | 100.0% of 6 | yes | PASS | 8/0/0/1 | 2 (1) |
| 70 | `get_equal` | COMPLETED | yes | 87.5% | 83.3% of 6 | 1 | 7/7 | 100.0% | 100.0% of 6 | yes | PASS | 7/0/0/0 | 2 (1) |
| 71 | `comb_sort` | COMPLETED | no | 100.0% | 100.0% of 6 | 1 | 4/7 | 100.0% | 100.0% of 6 | yes | TESTS_FAILED | 4/3/0/0 | 2 (1) |
| 79 | `word_len` | COMPLETED | no | 100.0% | no branches | 1 | 1/6 | 100.0% | no branches | yes | TESTS_FAILED | 0/4/1/1 | 2 (1) |
| 83 | `get_Char` | COMPLETED | no | 100.0% | no branches | 1 | 1/6 | 100.0% | no branches | yes | TESTS_FAILED | 0/2/3/1 | 2 (1) |
| 90 | `len_log` | COMPLETED | yes | 100.0% | no branches | 1 | 6/8 | 100.0% | no branches | yes | TESTS_FAILED | 6/0/2/0 | 2 (1) |
| 92 | `is_undulating` | COMPLETED | yes | 80.0% | 75.0% of 8 | 1 | 8/8 | 100.0% | 100.0% of 8 | yes | PASS | 7/0/0/1 | 2 (1) |

Verdict = the Test Executor's verdict for the generated tests with the goal "branch coverage >= 100%": PASS (all passed, goal met), COVERAGE_NOT_MET (all passed, goal not met), TESTS_FAILED (at least one test failed), ERROR (could not run).

## Aggregate

- Problems run: 12 of 12 planned
- Code generated: 12/12; code correct (passes all 3 MBPP asserts): 9/12 (75.0%)
- Mean coverage of the generated code by MBPP's own tests: statements 94.2%, branches 89.6% (over the 12 problem(s) with generated code)
- Coverage goal (branch coverage >= 100%) reached by MBPP's own tests: 7/12; with all 3 asserts also passing (verdict PASS): 4/12
- **Mean coverage of the generated code by the LLM's own tests: statements 100.0%, branches 100.0%** (over 12 suite(s); baseline was 94.2% / 89.6%)
- **Coverage goal (branch coverage >= 100%) reached: 12/12 (100.0%) with feedback, 12/12 (100.0%) single-shot (round 1 only)**; baseline reached it 7/12
- Verdict PASS (all generated tests passed and the goal was met): 7/12; no usable test suite (TESTGEN_FAILED): 0/12
- Mean test-generation rounds used: 1.0 of at most 3
- Generated tests: 88; passing on the generated code: 70 (79.5%)
- Validation against MBPP's reference solution (88 test(s)): VALID 61, BUG_FOUND 10, INVALID_TEST 8, MISLEADING 9; test validity rate 69.3%
- Fault detection: 3/3 (100.0%) of the problems with incorrect generated code have at least one BUG_FOUND test
- LLM calls: 24 (13 from the cache); HTTP requests sent: 11; tokens: 5846 prompt, 3277 completion, 0 reasoning
- Models that answered: `cohere/north-mini-code:free`
