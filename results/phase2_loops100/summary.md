# Run summary: full

| Setting | Value |
|---|---|
| Mode | full (Code Generator + Test Generator + coverage feedback loop + validation) |
| Coverage goal used for the verdict | loops coverage >= 100% |
| Model | `cohere/north-mini-code:free` (fallbacks: `nvidia/nemotron-3-super-120b-a12b:free`, `google/gemma-4-31b-it:free`) |
| Code Generator settings | temperature 0.2, top_p 1.0, max_tokens 1024, seed 42, reasoning disabled |
| Test Generator settings | temperature 0.4, top_p 1.0, max_tokens 2048, seed 42, reasoning disabled |
| Max test-generation rounds | 3 |
| Started / finished (UTC) | 2026-10-04T16:15:33+00:00 / 2026-10-04T16:18:42+00:00 |

## Results per problem

| Task | Function | Status | Code correct | Baseline stmt % | Baseline branch % | Baseline pairs % | Rounds | Tests passed | Final stmt % | Final branch % | Final pairs % | Goal met | Verdict | Test labels V/B/I/M | LLM calls (cached) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 11 | `remove_Occ` | COMPLETED | yes | 83.3% | 50.0% of 2 | 66.7% of 3 | 1 | 6/9 | 100.0% | 100.0% of 2 | 100.0% of 3 | yes | TESTS_FAILED | 5/0/3/1 | 2 (2) |
| 20 | `is_woodall` | COMPLETED | yes | 90.9% | 83.3% of 6 | 100.0% of 9 | 1 | 5/8 | 100.0% | 100.0% of 6 | 100.0% of 9 | yes | TESTS_FAILED | 5/0/3/0 | 2 (2) |
| 65 | `recursive_list_sum` | COMPLETED | yes | 100.0% | 100.0% of 4 | 90.0% of 10 | 1 | 9/9 | 100.0% | 100.0% of 4 | 100.0% of 10 | yes | PASS | 9/0/0/0 | 2 (2) |
| 66 | `pos_count` | COMPLETED | yes | 100.0% | no branches | no edge pairs | 1 | 9/9 | 100.0% | no branches | no edge pairs | yes | PASS | 7/0/0/2 | 2 (2) |
| 67 | `bell_number` | COMPLETED | yes | 100.0% | 100.0% of 6 | 88.9% of 18 | 3 | 16/16 | 100.0% | 100.0% of 6 | 94.4% of 18 | no | COVERAGE_NOT_MET | 16/0/0/0 | 4 (4) |
| 69 | `is_sublist` | COMPLETED | yes | 88.9% | 83.3% of 6 | 77.8% of 9 | 1 | 7/7 | 100.0% | 100.0% of 6 | 100.0% of 9 | yes | PASS | 7/0/0/0 | 2 (2) |
| 70 | `get_equal` | COMPLETED | yes | 87.5% | 83.3% of 6 | 85.7% of 7 | 3 | 16/16 | 100.0% | 100.0% of 6 | 85.7% of 7 | no | COVERAGE_NOT_MET | 16/0/0/0 | 4 (4) |
| 71 | `comb_sort` | COMPLETED | no | 100.0% | 100.0% of 6 | 89.5% of 19 | 3 | 14/18 | 100.0% | 100.0% of 6 | 94.7% of 19 | no | TESTS_FAILED | 14/4/0/0 | 4 (4) |
| 79 | `word_len` | COMPLETED | no | 100.0% | no branches | no edge pairs | 1 | 1/7 | 100.0% | no branches | no edge pairs | yes | TESTS_FAILED | 0/6/0/1 | 2 (2) |
| 83 | `get_Char` | COMPLETED | no | 100.0% | no branches | 100.0% of 1 | 1 | 1/7 | 100.0% | no branches | 100.0% of 1 | yes | TESTS_FAILED | 0/2/4/1 | 2 (2) |
| 90 | `len_log` | COMPLETED | yes | 100.0% | no branches | no edge pairs | 1 | 8/9 | 100.0% | no branches | no edge pairs | yes | TESTS_FAILED | 8/0/1/0 | 2 (2) |
| 92 | `is_undulating` | COMPLETED | yes | 80.0% | 75.0% of 8 | 70.0% of 10 | 3 | 25/25 | 100.0% | 100.0% of 8 | 90.0% of 10 | no | COVERAGE_NOT_MET | 25/0/0/0 | 4 (4) |

Verdict = the Test Executor's verdict for the generated tests with the goal "loops coverage >= 100%": PASS (all passed, goal met), COVERAGE_NOT_MET (all passed, goal not met), TESTS_FAILED (at least one test failed), ERROR (could not run).

## Aggregate

- Problems run: 12 of 12 planned
- Code generated: 12/12; code correct (passes all 3 MBPP asserts): 9/12 (75.0%)
- Mean coverage of the generated code by MBPP's own tests: statements 94.2%, branches 89.6% (over the 12 problem(s) with generated code)
- Coverage goal (loops coverage >= 100%) reached by MBPP's own tests: 4/12; with all 3 asserts also passing (verdict PASS): 2/12
- **Mean coverage of the generated code by the LLM's own tests: statements 100.0%, branches 100.0%, edge pairs 97.1%** (over 12 suite(s); baseline was 94.2% / 89.6% / 89.0%)
- **Coverage goal (loops coverage >= 100%) reached: 8/12 (66.7%) with feedback, 8/12 (66.7%) single-shot (round 1 only)**; baseline reached it 4/12
- Verdict PASS (all generated tests passed and the goal was met): 3/12; no usable test suite (TESTGEN_FAILED): 0/12
- Mean test-generation rounds used: 1.67 of at most 3
- Generated tests: 140; passing on the generated code: 117 (83.6%)
- Validation against MBPP's reference solution (140 test(s)): VALID 112, BUG_FOUND 12, INVALID_TEST 11, MISLEADING 5; test validity rate 80.0%
- Fault detection: 3/3 (100.0%) of the problems with incorrect generated code have at least one BUG_FOUND test
- LLM calls: 32 (32 from the cache); HTTP requests sent: 0; tokens: 14185 prompt, 10375 completion, 0 reasoning
- Models that answered: `cohere/north-mini-code:free`
