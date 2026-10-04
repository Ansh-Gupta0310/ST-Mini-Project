"""Offline tests for agents/path_coverage.py (edge-pair coverage, the `loops` criterion)."""
import pytest

from agents import path_coverage

# One loop with one decision inside it. Hand-worked below, so the numbers are not taken on trust.
CLASSIFY = """def classify(nums):
    total = 0
    for n in nums:
        if n > 0:
            total += n
    return total
"""
# Arcs: 2->3, 3->4, 3->6, 4->3, 4->5, 5->3   (plus exits, which are dropped)
# Pairs: (2,3,4) (2,3,6) (3,4,3) (3,4,5) (4,3,4) (4,3,6) (4,5,3) (5,3,4) (5,3,6)  -> 9
CLASSIFY_PAIRS = {(2, 3, 4), (2, 3, 6), (3, 4, 3), (3, 4, 5), (4, 3, 4), (4, 3, 6), (4, 5, 3), (5, 3, 4),
                  (5, 3, 6)}
NO_DECISIONS = "def mul(a, b):\n    return a * b\n"


def test_possible_arcs_includes_loop_back_edges_and_drops_exits():
    arcs = path_coverage.possible_arcs(CLASSIFY)
    assert (4, 3) in arcs and (5, 3) in arcs      # the loop goes back to its header
    assert (3, 6) in arcs                         # and leaves the loop
    assert all(source >= 0 and target >= 0 for source, target in arcs)


def test_required_pairs_are_the_consecutive_arc_pairs():
    assert path_coverage.required_pairs(CLASSIFY) == CLASSIFY_PAIRS


def test_code_without_decisions_requires_no_pairs():
    assert path_coverage.required_pairs(NO_DECISIONS) == set()


def test_covered_pairs_are_read_from_the_line_sequences():
    # classify([1, 2]): header, loop, body twice, then leave the loop.
    traces = {"test_pos": [2, 3, 4, 5, 3, 4, 5, 3, 6]}
    assert path_coverage.covered_pairs(traces) == {(2, 3, 4), (3, 4, 5), (4, 5, 3), (5, 3, 4), (5, 3, 6)}


def test_covered_pairs_of_a_too_short_trace_is_empty():
    assert path_coverage.covered_pairs({"t": [2, 3], "u": [], "v": [7]}) == set()


def test_measure_reports_the_percentage_and_what_is_missing():
    traces = {"test_pos": [2, 3, 4, 5, 3, 4, 5, 3, 6]}       # 5 of the 9 pairs
    result = path_coverage.measure(CLASSIFY, traces)
    assert (result["num_edge_pairs"], result["edge_pair_coverage"]) == (9, 55.56)
    assert [2, 3, 6] in result["missing_edge_pairs"]          # the loop is never skipped
    assert [3, 4, 3] in result["missing_edge_pairs"]          # the condition is never False
    assert len(result["missing_edge_pairs"]) == 4


def test_measure_counts_code_without_decisions_as_fully_covered():
    result = path_coverage.measure(NO_DECISIONS, {"t": [2]})
    assert (result["edge_pair_coverage"], result["num_edge_pairs"]) == (100.0, 0)


def test_measure_with_no_traces_at_all_is_zero():
    assert path_coverage.measure(CLASSIFY, {})["edge_pair_coverage"] == 0.0


def test_unparseable_code_is_reported_not_crashed():
    with pytest.raises(path_coverage.EdgePairUnavailable):
        path_coverage.required_pairs("def broken(:\n")


def test_prepare_writes_the_tracer_and_clears_an_old_trace_file(tmp_path):
    (tmp_path / path_coverage.TRACE_FILE).write_text('{"stale": [1]}', encoding="utf-8")
    path_coverage.prepare(tmp_path)
    assert "sys.settrace" in (tmp_path / path_coverage.CONFTEST_FILE).read_text(encoding="utf-8")
    assert not (tmp_path / path_coverage.TRACE_FILE).exists()
    assert path_coverage.read_traces(tmp_path) == {}


def test_read_traces_survives_a_damaged_file(tmp_path):
    (tmp_path / path_coverage.TRACE_FILE).write_text("{not json", encoding="utf-8")
    assert path_coverage.read_traces(tmp_path) == {}


def test_covered_pairs_keeps_call_frames_apart():
    """One sequence per frame. Chaining across frames would invent pairs that never ran."""
    traces = {"test_nested": [[2, 3, 4, 5, 3, 8], [2, 3, 4, 7, 3, 8]]}   # outer frame, then the inner call
    pairs = path_coverage.covered_pairs(traces)
    assert (4, 5, 3) in pairs          # outer: recursive call, then back to the loop header
    assert (5, 3, 8) in pairs          # outer: recursive call, then the loop ends
    assert (5, 3, 4) not in pairs      # not executed, and not invented either
    assert (8, 2, 3) not in pairs      # the two frames are never chained together


def test_covered_pairs_still_accepts_a_single_flat_sequence():
    assert path_coverage.covered_pairs({"t": [2, 3, 4]}) == {(2, 3, 4)}
    assert path_coverage.covered_pairs({"t": []}) == set()
