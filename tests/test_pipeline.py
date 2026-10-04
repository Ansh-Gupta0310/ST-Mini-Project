"""Offline tests for pipeline.py --mode baseline: real agents and executor, only the network is faked."""
import json

import pytest

import config
import pipeline
from agents import llm_client
from agents.models import load_problems

PROBLEMS = {p.task_id: p for p in load_problems(config.DATA_FILE)}


class FakeReply:
    def __init__(self, status_code, payload):
        self.status_code, self._payload, self.headers = status_code, payload, {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def reply_with(content):
    return FakeReply(200, {"model": "fake/model", "choices": [{"message": {"content": content}}],
                           "usage": {"prompt_tokens": 10, "completion_tokens": 20}})


def code_reply(code):
    return reply_with(f"```python\n{code}```")


@pytest.fixture
def network(monkeypatch, tmp_path):
    """Replies are chosen by the function name in the prompt. Nothing touches the real llm_cache/."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "MIN_SECONDS_BETWEEN_CALLS", 0)
    monkeypatch.setattr(config, "RETRY_WAITS_S", [0])
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-FAKE-KEY-FOR-TESTS")
    replies, sent = {}, []

    def fake_post(url, json=None, headers=None, timeout=None):
        prompt = json["messages"][-1]["content"]
        sent.append(prompt)
        for name, reply in replies.items():
            if f"def {name}(" in prompt:
                return reply
        raise AssertionError("no scripted reply for this prompt")

    monkeypatch.setattr(llm_client.requests, "post", fake_post)
    return replies, sent


def run(tmp_path, *task_ids):
    out = tmp_path / "out"
    exit_code = pipeline.main(["--mode", "baseline", "--out", str(out), "--task-ids", *map(str, task_ids)])
    return exit_code, out, json.loads((out / "summary.json").read_text(encoding="utf-8"))


def test_baseline_run_end_to_end(network, tmp_path):
    replies, _ = network
    replies["remove_Occ"] = code_reply(PROBLEMS[11].reference_code)
    replies["is_woodall"] = reply_with("I don't know.")
    exit_code, out, summary = run(tmp_path, 11, 20)

    assert exit_code == 0
    v11, v20 = summary["problems"]
    assert (v11["status"], v11["code_correct"]) == ("COMPLETED", True)
    assert (v11["baseline"]["tests_passed"], v11["baseline"]["tests_total"]) == (3, 3)
    assert (v20["status"], v20["code_correct"], v20["baseline"]) == ("CODEGEN_FAILED", False, None)
    assert (out / "Mbpp_20" / "codegen_reply.txt").read_text(encoding="utf-8") == "I don't know."
    for name in ("problem.json", "llm_calls.jsonl", "solution.py", "verdict.json", "reference/execution.json"):
        assert (out / "Mbpp_11" / name).exists(), name

    agg = summary["aggregate"]
    assert (agg["problems_run"], agg["code_generated"], agg["code_correct"]) == (2, 1, 1)
    assert (agg["llm_calls"], agg["llm_requests_sent"], agg["models_used"]) == (2, 2, ["fake/model"])
    assert json.loads((out / "config.json").read_text(encoding="utf-8"))["task_ids"] == [11, 20]
    assert "| 11 | `remove_Occ` | COMPLETED | yes | 3/3 |" in (out / "summary.md").read_text(encoding="utf-8")


def test_rerun_is_served_from_the_cache(network, tmp_path):
    replies, sent = network
    replies["remove_Occ"] = code_reply(PROBLEMS[11].reference_code)
    run(tmp_path, 11)
    _, _, summary = run(tmp_path, 11)
    assert len(sent) == 1
    assert (summary["aggregate"]["llm_cached_calls"], summary["aggregate"]["llm_requests_sent"]) == (1, 0)


def test_used_up_quota_stops_the_run(network, tmp_path):
    replies, sent = network
    replies["remove_Occ"] = FakeReply(429, {"error": {"code": 429,
                                                      "message": "Rate limit exceeded: free-models-per-day"}})
    exit_code, _, summary = run(tmp_path, 11, 20)
    assert exit_code == 1 and len(sent) == 1
    assert "quota" in summary["stopped_early"].lower()
    assert summary["aggregate"]["problems_run"] == 0


def test_one_broken_problem_does_not_stop_the_run(network, tmp_path, monkeypatch):
    replies, _ = network
    replies["remove_Occ"] = code_reply(PROBLEMS[11].reference_code)
    replies["is_woodall"] = code_reply(PROBLEMS[20].reference_code)
    original = pipeline.reference_tests_to_pytest

    def crash_on_11(problem):
        if problem.task_id == 11:
            raise RuntimeError("simulated crash")
        return original(problem)

    monkeypatch.setattr(pipeline, "reference_tests_to_pytest", crash_on_11)
    exit_code, out, summary = run(tmp_path, 11, 20)
    assert exit_code == 0
    assert [v["status"] for v in summary["problems"]] == ["PIPELINE_ERROR", "COMPLETED"]
    assert "simulated crash" in (out / "Mbpp_11" / "error.txt").read_text(encoding="utf-8")


def test_unknown_task_id_is_rejected(tmp_path):
    with pytest.raises(SystemExit):
        pipeline.main(["--mode", "baseline", "--out", str(tmp_path / "out"), "--task-ids", "9999"])


# --- --mode full: the coverage feedback loop and validation (PROJECT_PLAN.md §7, step 2.5) ------

# A solution with two decisions, so MBPP's own asserts cannot reach 100% branch coverage:
# none of them passes a character that is absent, or one that occurs exactly once.
SOLUTION_11 = (
    "def remove_Occ(s, ch):\n"
    "    if ch not in s:\n"
    "        return s\n"
    "    first = s.find(ch)\n"
    "    last = s.rfind(ch)\n"
    "    if first == last:\n"
    "        return s[:first] + s[first + 1:]\n"
    "    return s[:first] + s[first + 1:last] + s[last + 1:]\n"
)
# The same function, but it only ever removes the first occurrence: MBPP's asserts fail on it.
BUGGY_11 = ("def remove_Occ(s, ch):\n"
            "    if ch not in s:\n"
            "        return s\n"
            "    return s.replace(ch, '', 1)\n")
ROUND_1_TESTS = ("from solution import remove_Occ\n\n\n"
                 "def test_removes_first_and_last():\n    assert remove_Occ('hello', 'l') == 'heo'\n")
# Round 2 reuses a test name on purpose, to exercise the rename in merge_test_files.
ROUND_2_TESTS = ("from solution import remove_Occ\n\n\n"
                 "def test_removes_first_and_last():\n    assert remove_Occ('abc', 'z') == 'abc'\n\n\n"
                 "def test_single_occurrence_is_removed():\n    assert remove_Occ('abc', 'b') == 'ac'\n")


@pytest.fixture
def full_network(monkeypatch, tmp_path):
    """Scripted replies chosen by which prompt arrived; the last reply of a kind is reused if needed."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "MIN_SECONDS_BETWEEN_CALLS", 0)
    monkeypatch.setattr(config, "RETRY_WAITS_S", [0])
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-FAKE-KEY-FOR-TESTS")
    replies: dict[str, list] = {}
    sent: list[str] = []

    def fake_post(url, json=None, headers=None, timeout=None):
        prompt = json["messages"][-1]["content"]
        sent.append(prompt)
        kind = ("codegen" if "Implement this function" in prompt
                else "feedback" if "These tests already exist" in prompt else "testgen")
        queue = replies.get(kind)
        if not queue:
            raise AssertionError(f"no scripted {kind} reply for this prompt")
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(llm_client.requests, "post", fake_post)
    return replies, sent


def run_full(tmp_path, *task_ids, max_rounds=3, criterion="branch", target="100"):
    out = tmp_path / "out"
    exit_code = pipeline.main(["--mode", "full", "--out", str(out), "--criterion", criterion,
                               "--target", target, "--max-rounds", str(max_rounds),
                               "--task-ids", *map(str, task_ids)])
    return exit_code, out, json.loads((out / "summary.json").read_text(encoding="utf-8"))


def test_feedback_round_closes_the_coverage_gap(full_network, tmp_path):
    replies, sent = full_network
    replies.update(codegen=[code_reply(SOLUTION_11)], testgen=[code_reply(ROUND_1_TESTS)],
                   feedback=[code_reply(ROUND_2_TESTS)])
    exit_code, out, summary = run_full(tmp_path, 11)
    v = summary["problems"][0]

    assert exit_code == 0
    assert (v["status"], v["code_correct"]) == ("COMPLETED", True)
    assert (v["baseline"]["statement_coverage"], v["baseline"]["branch_coverage"]) == (75.0, 50.0)
    assert (v["rounds_used"], v["final_round"], v["llm_calls"]) == (2, 2, 3)
    assert (v["round_1"]["branch_coverage"], v["round_1"]["verdict"]) == (50.0, "COVERAGE_NOT_MET")
    assert v["round_1"]["target_met"] is False
    assert (v["final"]["statement_coverage"], v["final"]["branch_coverage"]) == (100.0, 100.0)
    assert (v["final"]["tests_total"], v["final"]["tests_passed"], v["final"]["verdict"]) == (3, 3, "PASS")
    assert v["final"]["target_met"] is True
    assert v["test_labels"] == {"VALID": 3, "BUG_FOUND": 0, "INVALID_TEST": 0, "MISLEADING": 0, "NOT_RUN": 0}


def test_feedback_prompt_reports_the_measured_gap_and_the_merge_keeps_both_rounds(full_network, tmp_path):
    replies, sent = full_network
    replies.update(codegen=[code_reply(SOLUTION_11)], testgen=[code_reply(ROUND_1_TESTS)],
                   feedback=[code_reply(ROUND_2_TESTS)])
    _, out, _ = run_full(tmp_path, 11)

    feedback_prompt = next(prompt for prompt in sent if "These tests already exist" in prompt)
    assert "statements 75%, branches 50%" in feedback_prompt
    assert "- line 3 `return s` was never run" in feedback_prompt
    assert "def test_removes_first_and_last():" in feedback_prompt      # round 1 is shown, not guessed at
    assert "  1 | def remove_Occ(s, ch):" in feedback_prompt

    merged = (out / "Mbpp_11" / "test_solution.py").read_text(encoding="utf-8")
    assert merged.count("from solution import remove_Occ") == 1
    assert merged.count("def test_") == 3
    assert "def test_removes_first_and_last_r2():" in merged            # the duplicate name was renamed
    labels = json.loads((out / "Mbpp_11" / "validation.json").read_text(encoding="utf-8"))
    assert sorted(labels["labels"]) == ["test_removes_first_and_last", "test_removes_first_and_last_r2",
                                        "test_single_occurrence_is_removed"]
    assert labels["on_generated"] == labels["on_reference"]             # all three pass on both solutions


def test_full_run_writes_every_file_the_plan_lists(full_network, tmp_path):
    replies, _ = full_network
    replies.update(codegen=[code_reply(SOLUTION_11)], testgen=[code_reply(ROUND_1_TESTS)],
                   feedback=[code_reply(ROUND_2_TESTS)])
    _, out, summary = run_full(tmp_path, 11)
    for name in ("problem.json", "llm_calls.jsonl", "solution.py", "verdict.json", "reference/execution.json",
                 "round_1/execution.json", "round_1/coverage_html/index.html", "round_2/execution.json",
                 "test_solution.py", "validation/execution.json", "validation.json"):
        assert (out / "Mbpp_11" / name).exists(), name
    markdown = (out / "summary.md").read_text(encoding="utf-8")
    assert "Test Generator settings" in markdown and "Max test-generation rounds | 3" in markdown
    assert "| 11 | `remove_Occ` | COMPLETED | yes | 75.0% | 50.0% of 4 | 2 | 3/3 | 100.0% |" in markdown
    assert json.loads((out / "config.json").read_text(encoding="utf-8"))["test_generator"]["temperature"] == 0.4


def test_single_shot_switches_the_loop_off(full_network, tmp_path):
    replies, sent = full_network
    replies.update(codegen=[code_reply(SOLUTION_11)], testgen=[code_reply(ROUND_1_TESTS)])
    _, out, summary = run_full(tmp_path, 11, max_rounds=1)
    v = summary["problems"][0]
    assert (v["rounds_used"], v["final_round"]) == (1, 1)
    assert v["round_1"] == v["final"] and v["final"]["verdict"] == "COVERAGE_NOT_MET"
    assert not any("These tests already exist" in prompt for prompt in sent)
    assert not (out / "Mbpp_11" / "round_2").exists()
    agg = summary["aggregate"]
    assert (agg["generated_target_met_round_1"], agg["generated_target_met_final"]) == (0, 0)


def test_validation_finds_the_bug_in_the_generated_code(full_network, tmp_path):
    replies, _ = full_network
    replies.update(codegen=[code_reply(BUGGY_11)], testgen=[code_reply(ROUND_1_TESTS)])
    _, out, summary = run_full(tmp_path, 11, max_rounds=1)
    v = summary["problems"][0]
    assert v["code_correct"] is False
    assert (v["final"]["tests_passed"], v["final"]["verdict"]) == (0, "TESTS_FAILED")
    assert v["test_labels"]["BUG_FOUND"] == 1
    labels = json.loads((out / "Mbpp_11" / "validation.json").read_text(encoding="utf-8"))
    assert labels["labels"] == {"test_removes_first_and_last": "BUG_FOUND"}
    agg = summary["aggregate"]
    assert (agg["problems_with_incorrect_code"], agg["problems_with_bug_found"]) == (1, 1)
    assert agg["fault_detection_rate"] == 100.0


def test_unusable_round_is_thrown_away_and_the_next_round_tries_again(full_network, tmp_path):
    replies, sent = full_network
    replies.update(codegen=[code_reply(SOLUTION_11)],
                   testgen=[reply_with("I cannot write tests for this."), code_reply(ROUND_1_TESTS)],
                   feedback=[code_reply(ROUND_2_TESTS)])
    _, out, summary = run_full(tmp_path, 11, max_rounds=3)
    v = summary["problems"][0]
    assert v["status"] == "COMPLETED"
    assert (v["rounds_used"], v["final_round"]) == (3, 3)
    assert v["round_1"] is None                                  # round 1 produced nothing to measure
    assert [e["round"] for e in v["testgen_errors"]] == [1]
    assert (out / "Mbpp_11" / "testgen_reply_round_1.txt").exists()
    assert not (out / "Mbpp_11" / "round_1").exists()
    assert v["final"]["verdict"] == "PASS"
    # The retried prompt says what was wrong, so the cache cannot answer with the same unusable reply.
    assert "Attempt 1 could not be used" in sent[2]
    assert summary["aggregate"]["generated_target_met_round_1"] == 0


def test_no_usable_test_suite_at_all_is_reported_as_testgen_failed(full_network, tmp_path):
    replies, sent = full_network
    replies.update(codegen=[code_reply(SOLUTION_11)], testgen=[reply_with("Sorry, I can't help.")])
    exit_code, out, summary = run_full(tmp_path, 11, max_rounds=2)
    v = summary["problems"][0]
    assert exit_code == 0
    assert (v["status"], v["rounds_used"]) == ("TESTGEN_FAILED", 2)
    assert (v["final"], v["test_labels"], v["round_1"]) == (None, None, None)
    assert v["code_correct"] is True                             # the baseline still holds
    assert not (out / "Mbpp_11" / "test_solution.py").exists()
    assert len(sent) == 3                                        # 1 code generation + 2 real attempts
    agg = summary["aggregate"]
    assert (agg["testgen_failed"], agg["suites_produced"], agg["testgen_problems"]) == (1, 0, 1)
    assert agg["test_validity_rate"] is None


def test_codegen_failure_skips_test_generation(full_network, tmp_path):
    replies, sent = full_network
    replies.update(codegen=[reply_with("I don't know.")])
    _, out, summary = run_full(tmp_path, 11, max_rounds=3)
    v = summary["problems"][0]
    assert (v["status"], v["rounds_used"], v["final"]) == ("CODEGEN_FAILED", 0, None)
    assert len(sent) == 1
    assert summary["aggregate"]["testgen_problems"] == 0


def test_statement_criterion_is_passed_through_to_the_prompt_and_the_verdict(full_network, tmp_path):
    replies, sent = full_network
    replies.update(codegen=[code_reply(SOLUTION_11)], testgen=[code_reply(ROUND_1_TESTS)])
    _, _, summary = run_full(tmp_path, 11, max_rounds=1, criterion="statement", target="75")
    v = summary["problems"][0]
    assert "Reach 75% statement coverage" in sent[1]
    assert (v["criterion"], v["target"]) == ("statement", 75.0)
    assert (v["final"]["statement_coverage"], v["final"]["target_met"]) == (75.0, True)
    assert v["final"]["verdict"] == "PASS"


# --- --mode full --criterion loops: edge-pair coverage demands a round branch coverage would not ---

# A loop-based remove_Occ that passes MBPP's 3 asserts. Its 12 edge pairs include two that a single
# straightforward test cannot reach: skipping the loop entirely, and `continue` on the last iteration.
LOOPY_11 = (
    "def remove_Occ(s, ch):\n"
    "    first = s.find(ch)\n"
    "    last = s.rfind(ch)\n"
    "    out = ''\n"
    "    for i, c in enumerate(s):\n"
    "        if i == first or i == last:\n"
    "            continue\n"
    "        out += c\n"
    "    return out\n"
)
LOOPS_ROUND_1 = ("from solution import remove_Occ\n\n\n"
                 "def test_removes_first_and_last():\n    assert remove_Occ('hello', 'l') == 'heo'\n")
LOOPS_ROUND_2 = ("from solution import remove_Occ\n\n\n"
                 "def test_empty_string_skips_the_loop():\n    assert remove_Occ('', 'x') == ''\n\n\n"
                 "def test_last_character_is_removed():\n    assert remove_Occ('ab', 'b') == 'a'\n")


def test_loops_criterion_needs_a_second_round_where_branch_coverage_would_stop(full_network, tmp_path):
    replies, sent = full_network
    replies.update(codegen=[code_reply(LOOPY_11)], testgen=[code_reply(LOOPS_ROUND_1)],
                   feedback=[code_reply(LOOPS_ROUND_2)])
    exit_code, out, summary = run_full(tmp_path, 11, criterion="loops")
    v = summary["problems"][0]

    assert exit_code == 0
    assert (v["criterion"], v["code_correct"]) == ("loops", True)
    # Round 1 already satisfies both weaker criteria, so a branch run would have stopped here...
    assert (v["round_1"]["statement_coverage"], v["round_1"]["branch_coverage"]) == (100.0, 100.0)
    # ...but two orderings are untested, so the loops criterion is not met and the loop runs again.
    assert v["round_1"]["edge_pair_coverage"] == 83.33
    assert v["round_1"]["target_met"] is False
    assert (v["rounds_used"], v["final_round"]) == (2, 2)
    assert (v["final"]["edge_pair_coverage"], v["final"]["num_edge_pairs"]) == (100.0, 12)
    assert (v["final"]["target_met"], v["final"]["verdict"]) == (True, "PASS")


def test_loops_feedback_prompt_names_the_missing_orderings(full_network, tmp_path):
    replies, sent = full_network
    replies.update(codegen=[code_reply(LOOPY_11)], testgen=[code_reply(LOOPS_ROUND_1)],
                   feedback=[code_reply(LOOPS_ROUND_2)])
    _, out, _ = run_full(tmp_path, 11, criterion="loops")
    prompt = next(p for p in sent if "These tests already exist" in p)
    assert "skips its body completely" in prompt            # the loops goal sentence
    assert "never ran in that order" in prompt              # describe_missing's edge-pair lines
    markdown = (out / "summary.md").read_text(encoding="utf-8")
    assert "Final pairs %" in markdown and "100.0% of 12" in markdown


def test_loops_run_records_edge_pairs_but_other_criteria_do_not(full_network, tmp_path):
    replies, _ = full_network
    replies.update(codegen=[code_reply(SOLUTION_11)], testgen=[code_reply(ROUND_1_TESTS)],
                   feedback=[code_reply(ROUND_2_TESTS)])
    _, _, summary = run_full(tmp_path, 11, max_rounds=1, criterion="branch")
    assert summary["problems"][0]["final"]["num_edge_pairs"] == 0
    assert "Final pairs %" not in (tmp_path / "out" / "summary.md").read_text(encoding="utf-8")
