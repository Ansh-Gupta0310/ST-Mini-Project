"""Edge-pair coverage, the `loops` criterion (PROJECT_PLAN.md §2.3, §3.7).

The assignment's first requirement lists three example criteria: "cover all statements, cover all loops,
cover all decision statements". Statements are node coverage and decisions are edge coverage, both of which
coverage.py measures directly. "Cover all loops" is this module: **edge-pair coverage**, every path of two
consecutive edges in the control-flow graph. At a loop header that is exactly the classic loop requirement
-- skip the body, run one iteration, run two or more, and leave the loop -- which is why the criterion is
called `loops` on the command line.

Two facts decide how this is implemented:

1. coverage.py already knows the whole control-flow graph: `PythonParser.arcs()` returns every *possible*
   (from_line, to_line) edge, loop back-edges included. We therefore do not write our own CFG analysis, and
   the required test requirements come from the same tool that measures the other two criteria.
2. Edge pairs need the *order* in which lines ran, and coverage.py only reports a set of arcs. So the tests
   are run a second time with the tracer in TRACE_CONFTEST. That pass must not be under `coverage run`:
   both install a sys.settrace hook, the second one wins, and the coverage numbers collapse.

Command line:
    python -m agents.path_coverage --run results/phase2_branch100    edge-pair coverage of a finished run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TRACE_FILE = "traces.json"
CONFTEST_FILE = "conftest.py"

# Written into the execution folder for the second (uninstrumented) pytest pass.
TRACE_CONFTEST = '''\
"""Records the line sequences each test runs inside solution.py (written by agents/path_coverage.py).

Used only for the `loops` criterion, and only in a pytest run WITHOUT coverage.py: both install a
sys.settrace hook, and whichever installs second wins, so they cannot share a process.

One sequence is kept **per call frame**, not one per test. A recursive function (or a helper called from
the function under test) would otherwise have the inner call's lines spliced into the outer call's
sequence, so the line after `total += f(x)` would be the first line of the inner call instead of the
loop header, and the edge pair that really was executed would look untested.
"""
import json
import os
import sys

import pytest

_TRACES = {}


@pytest.fixture(autouse=True)
def _record_solution_path(request):
    sequences = []      # one list of line numbers per call frame
    active = {}

    def tracer(frame, event, arg):
        # basename, not endswith: "test_solution.py" also ends with "solution.py".
        if os.path.basename(frame.f_code.co_filename) != "solution.py":
            return None                      # do not trace the test file or the library
        key = id(frame)
        if event == "call":
            active[key] = []
            sequences.append(active[key])
        elif event == "line":
            active.setdefault(key, sequences[-1] if sequences else []).append(frame.f_lineno)
        elif event == "return":
            active.pop(key, None)
        return tracer

    sys.settrace(tracer)
    try:
        yield
    finally:
        sys.settrace(None)
        _TRACES[request.node.name] = [seq for seq in sequences if seq]


def pytest_sessionfinish(session, exitstatus):
    with open("traces.json", "w", encoding="utf-8") as handle:
        json.dump(_TRACES, handle)
'''


class EdgePairUnavailable(RuntimeError):
    """The control-flow graph could not be read, so edge-pair coverage cannot be measured."""


def possible_arcs(code: str) -> set[tuple[int, int]]:
    """Every control-flow edge the code could take, from coverage.py's own parser.

    Arcs with a negative line number are coverage.py's way of writing "leaves this scope". They are
    dropped: a pair (a, b, exit) asks for nothing beyond the edge (a, b) plus a return that always happens,
    and keeping them would tie this module to an undocumented numbering convention.
    """
    try:
        from coverage.parser import PythonParser
    except ImportError as exc:  # pragma: no cover - coverage.py is a hard requirement of the project
        raise EdgePairUnavailable(
            "coverage.py's parser is not importable, so --criterion loops cannot be measured; "
            "install the pinned version with: pip install -r requirements.txt") from exc
    try:
        parser = PythonParser(text=code)
        parser.parse_source()
        arcs = parser.arcs()
    except Exception as exc:  # a syntax error, or a coverage.py version with a different parser API
        raise EdgePairUnavailable(f"could not read the control-flow graph: {type(exc).__name__}: {exc}") from exc
    return {(source, target) for source, target in arcs if source >= 0 and target >= 0}


def required_pairs(code: str) -> set[tuple[int, int, int]]:
    """Every pair of consecutive edges: (a, b, c) such that a->b and b->c are both possible."""
    arcs = possible_arcs(code)
    successors: dict[int, set[int]] = {}
    for source, target in arcs:
        successors.setdefault(source, set()).add(target)
    return {(a, b, c) for a, b in arcs for c in successors.get(b, ())}


def _sequences(traces: dict) -> list[list[int]]:
    """Every recorded line sequence, whether a test holds one sequence or one per call frame."""
    out: list[list[int]] = []
    for value in traces.values():
        if value and isinstance(value[0], list):
            out.extend(sequence for sequence in value if sequence)
        elif value:
            out.append(value)
    return out


def covered_pairs(traces: dict) -> set[tuple[int, int, int]]:
    """Every pair of consecutive edges some test actually ran, from the recorded line sequences.

    Pairs are taken within one call frame: chaining across frames would invent pairs that never happened
    and hide pairs that did, which is exactly what recursion does to a single flat sequence.
    """
    seen: set[tuple[int, int, int]] = set()
    for sequence in _sequences(traces):
        seen.update(zip(sequence, sequence[1:], sequence[2:]))
    return seen


def measure(code: str, traces: dict) -> dict:
    """Edge-pair coverage of `code` under these traces, in the shape ExecutionResult expects.

    Code without decisions has no edge pairs at all; that counts as 100%, exactly as coverage.py reports
    100% branch coverage for such code. `coverage_target_met` guards against the obvious trap by also
    requiring statement coverage.
    """
    required = required_pairs(code)
    covered = covered_pairs(traces) & required
    percent = round(100.0 * len(covered) / len(required), 2) if required else 100.0
    return {
        "edge_pair_coverage": percent,
        "num_edge_pairs": len(required),
        "missing_edge_pairs": sorted(list(pair) for pair in required - covered),
    }


def prepare(work_dir: Path) -> None:
    """Put the tracer in place and delete any trace file from an earlier run."""
    (work_dir / CONFTEST_FILE).write_text(TRACE_CONFTEST, encoding="utf-8")
    trace_file = work_dir / TRACE_FILE
    if trace_file.exists():
        trace_file.unlink()


def read_traces(work_dir: Path) -> dict:
    """The recorded line sequences, or {} if the traced pass did not get as far as writing them."""
    try:
        traces = json.loads((work_dir / TRACE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(traces, dict):
        return {}
    return {name: value for name, value in traces.items() if isinstance(value, list)}


# --- command line ------------------------------------------------------------------------

def _measure_folder(folder: Path, suite: str, timeout_s: float) -> dict | None:
    """Re-run one problem's suite with the tracer and measure edge-pair coverage.

    The work happens in a temporary folder: reading a finished run must never add files to it.
    """
    import tempfile

    from agents.test_executor import SOLUTION_FILE, TEST_FILE, TestExecutorAgent  # avoids a circular import

    source = folder / "reference" if suite == "reference" else folder
    solution, tests = source / SOLUTION_FILE, source / TEST_FILE
    if not (solution.exists() and tests.exists()):
        return None
    executor = TestExecutorAgent(timeout_s=timeout_s, html=False)
    with tempfile.TemporaryDirectory(prefix="edge_pairs_") as work_dir:
        result = executor.run(solution.read_text(encoding="utf-8"), tests.read_text(encoding="utf-8"),
                              Path(work_dir), criterion="loops", target=100.0)
    return {"edge_pair_coverage": result.edge_pair_coverage, "num_edge_pairs": result.num_edge_pairs,
            "missing_edge_pairs": result.missing_edge_pairs, "tests_total": result.tests_total}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Edge-pair coverage of a finished run folder.")
    parser.add_argument("--run", type=Path, required=True, help="e.g. results/phase2_branch100")
    parser.add_argument("--suite", choices=["final", "reference"], default="final",
                        help="which test suite to measure (default: %(default)s; 'reference' = MBPP's asserts)")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)

    folders = sorted(args.run.glob("Mbpp_*"), key=lambda path: int(path.name.split("_")[1]))
    if not folders:
        print(f"No Mbpp_* folders in {args.run}")
        return 2
    print(f"Edge-pair coverage of the {args.suite} suite in {args.run}\n")
    print(f"{'task':>5}  {'tests':>5}  {'pairs':>5}  {'edge pairs':>10}  missing")
    measured = []
    for folder in folders:
        row = _measure_folder(folder, args.suite, args.timeout)
        if row is None:
            print(f"{folder.name.split('_')[1]:>5}  {'-':>5}  {'-':>5}  {'no suite':>10}")
            continue
        measured.append(row["edge_pair_coverage"])
        missing = ", ".join("->".join(str(line) for line in pair) for pair in row["missing_edge_pairs"][:3])
        if len(row["missing_edge_pairs"]) > 3:
            missing += f", ... ({len(row['missing_edge_pairs'])} in total)"
        print(f"{folder.name.split('_')[1]:>5}  {row['tests_total']:>5}  {row['num_edge_pairs']:>5}  "
              f"{row['edge_pair_coverage']:>9.1f}%  {missing}")
    if measured:
        print(f"\nmean edge-pair coverage: {sum(measured) / len(measured):.1f}% over {len(measured)} problem(s); "
              f"at 100%: {sum(1 for value in measured if value == 100.0)}/{len(measured)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
