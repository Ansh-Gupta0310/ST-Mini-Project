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
