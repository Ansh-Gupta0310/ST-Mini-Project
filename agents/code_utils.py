"""Helpers for the Python source that the LLM agents produce.

Phase 1: extract_python_code, remove_example_usage, defines_function, number_lines.
Phase 2 adds: describe_missing, merge_test_files, check_test_file (PROJECT_PLAN.md §3.5).
"""
from __future__ import annotations

import ast
import re
import textwrap
import warnings

_FENCED_PYTHON = re.compile(r"```[ \t]*(?:python3?|py)[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)
_FENCED_ANY = re.compile(r"```[^\n`]*\r?\n(.*?)```", re.DOTALL)
_OPEN_FENCE = re.compile(r"```[^\n`]*\r?\n(.*)", re.DOTALL)  # reply cut off before its closing fence


def _parse(code: str) -> ast.Module | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)  # e.g. regexes written as "\d" instead of r"\d"
            return ast.parse(code)
    except (SyntaxError, ValueError):
        return None


def extract_python_code(text: str) -> str | None:
    """The Python source in an LLM reply, or None if the reply contains no parseable code.

    Tries, in order: the first ```python block, the first ``` block of any kind, an opening fence
    whose closing fence is missing, and finally the whole reply.
    """
    if not text or not text.strip():
        return None
    for pattern in (_FENCED_PYTHON, _FENCED_ANY, _OPEN_FENCE):
        match = pattern.search(text)
        if match:
            candidate = match.group(1)
            break
    else:
        candidate = text
    candidate = textwrap.dedent(candidate.replace("\r\n", "\n")).strip("\n")
    if not candidate.strip() or _parse(candidate) is None:
        return None
    return candidate + "\n"


def remove_example_usage(code: str) -> str:
    """Delete top-level code that only demonstrates the function.

    Removes `if __name__ == "__main__":` blocks, bare top-level calls such as print(f(2)), and top-level
    asserts. They are not part of the unit under test, no test could ever cover them, and they would
    run on import. Imports, constants and definitions are kept exactly as written.
    """
    tree = _parse(code)
    if tree is None:
        return code
    drop: set[int] = set()
    for node in tree.body:
        if (_is_main_guard(node) or isinstance(node, ast.Assert)
                or (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call))):
            drop.update(range(node.lineno, node.end_lineno + 1))
    if not drop:
        return code
    kept = [line for number, line in enumerate(code.splitlines(), start=1) if number not in drop]
    return "\n".join(kept).rstrip() + "\n"


def _is_main_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    parts = [node.test.left, *node.test.comparators]
    names = {part.id for part in parts if isinstance(part, ast.Name)}
    values = {part.value for part in parts if isinstance(part, ast.Constant)}
    return "__name__" in names and "__main__" in values


def defines_function(code: str, name: str) -> bool:
    """True if `name` is a top-level function in code."""
    tree = _parse(code)
    return tree is not None and any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name for node in tree.body)


def number_lines(code: str) -> str:
    """Prefix each line with its number, e.g. '  1 | def f(x):'. The numbers match coverage.py's."""
    lines = code.splitlines()
    width = max(3, len(str(len(lines))))
    return "\n".join(f"{number:>{width}} | {line}" for number, line in enumerate(lines, start=1))
