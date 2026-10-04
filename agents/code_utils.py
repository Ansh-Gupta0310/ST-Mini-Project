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

SOLUTION_MODULE = "solution"
# Modules a unit test of a pure function has no business importing: they break either determinism
# (random) or the "no files, no network" rule in PROJECT_PLAN.md §3.6.
FORBIDDEN_TEST_MODULES = frozenset({
    "random", "secrets", "socket", "subprocess", "requests", "urllib", "http", "httpx", "shutil", "tempfile",
})


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


# --- Phase 2 helpers ---------------------------------------------------------------------

MAX_DESCRIBED_PAIRS = 12  # a long list of edge pairs would crowd out the rest of the prompt


def describe_missing(code: str, missing_lines: list[int], missing_branches: list[list[int]],
                     missing_edge_pairs: list[list[int]] | None = None) -> str:
    """Turn coverage.py's numbers into plain sentences the Test Generator can act on.

    Example (the sign() function of PROJECT_PLAN.md §2.3, covered by sign(5) only):

        - line 4 `elif x < 0:` was never run
        - line 2 `if x > 0:` never went to line 4 `elif x < 0:`

    A negative `to_line` in missing_branches means "never left the function from that line".
    `missing_edge_pairs` is only filled in for the `loops` criterion: each one is three line numbers
    that never ran in that order (agents/path_coverage.py).
    """
    lines = code.splitlines()

    def text(number: int) -> str:
        return lines[number - 1].strip() if 1 <= number <= len(lines) else "?"

    out = [f"- line {number} `{text(number)}` was never run" for number in missing_lines]
    for branch in missing_branches:
        if len(branch) != 2:
            continue
        source, target = branch
        if target < 0:
            out.append(f"- line {source} `{text(source)}` never exited the function from there")
        else:
            out.append(f"- line {source} `{text(source)}` never went to line {target} `{text(target)}`")

    pairs = [pair for pair in (missing_edge_pairs or []) if len(pair) == 3]
    for first, second, third in pairs[:MAX_DESCRIBED_PAIRS]:
        last = f"back to line {third}" if third == first else f"line {third} `{text(third)}`"
        out.append(f"- line {first} `{text(first)}` -> line {second} `{text(second)}` -> {last} "
                   "never ran in that order")
    if len(pairs) > MAX_DESCRIBED_PAIRS:
        out.append(f"- ... and {len(pairs) - MAX_DESCRIBED_PAIRS} more orderings like the ones above")
    return "\n".join(out) or "- nothing: every line and branch is already covered"


def merge_test_files(existing: str, new: str, round_no: int) -> str:
    """Join two pytest files: every import once, then the existing tests, then the new ones.

    A new top-level function or class whose name already exists is renamed to `<name>_r<round_no>`, so a
    feedback round can never silently replace a test from an earlier round. Comments between top-level
    statements are not carried over; the merged file is machine-made and every round is also kept
    unmerged in its own round_<k>/ folder.
    """
    existing_tree, new_tree = _parse(existing), _parse(new)
    if new_tree is None:
        return existing
    if existing_tree is None:
        return new

    imports: list[str] = []
    seen_imports: set[str] = set()
    body: list[str] = []
    taken = _top_level_names(existing_tree)

    for tree, source, rename in ((existing_tree, existing, False), (new_tree, new, True)):
        for node in tree.body:
            text = _source_of(node, source)
            if not text.strip():
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                key = " ".join(text.split())
                if key not in seen_imports:
                    seen_imports.add(key)
                    imports.append(text)
            elif rename and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = node.name
                if name in taken:
                    name = f"{node.name}_r{round_no}"
                    while name in taken:
                        name += "x"
                    text = re.sub(rf"\b(def|class)\s+{re.escape(node.name)}\b", rf"\1 {name}", text, count=1)
                taken.add(name)
                body.append(text)
            else:
                body.append(text)

    parts = ["\n".join(imports)] if imports else []
    return "\n\n\n".join(parts + body) + "\n"


def check_test_file(test_code: str, entry_point: str) -> str | None:
    """Check a generated pytest file against the rules in PROJECT_PLAN.md §3.6.

    Returns an error message for the first rule broken, or None if the file is usable.
    """
    tree = _parse(test_code)
    if tree is None:
        return "the test file does not parse as Python"

    tests = [node for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")]
    if not tests:
        return "the file has no top-level function whose name starts with test_"

    if _redefines(tree, entry_point):
        return (f"the file defines {entry_point} itself, so it would test its own copy "
                "instead of the code in solution.py")

    imported = {module for node in ast.walk(tree) for module in _imported_modules(node)}
    if SOLUTION_MODULE not in imported:
        return f"the file never imports the module `{SOLUTION_MODULE}`, so it does not test the generated code"

    forbidden = sorted(imported & FORBIDDEN_TEST_MODULES)
    if forbidden:
        return f"the file imports {', '.join(forbidden)}; tests must use only pytest and the standard library"
    return None


def _top_level_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _source_of(node: ast.stmt, code: str) -> str:
    """The exact source lines of one top-level statement, including any decorators."""
    lines = code.splitlines()
    start = min([node.lineno, *(item.lineno for item in getattr(node, "decorator_list", []))])
    return "\n".join(lines[start - 1:node.end_lineno]).rstrip()


def _redefines(tree: ast.Module, name: str) -> bool:
    """True if the file defines `name` anywhere, or binds it at the top level (e.g. name = lambda ...)."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return True
    return name in _top_level_names(tree)


def _imported_modules(node: ast.AST) -> set[str]:
    """The top-level package names a single import statement brings in."""
    if isinstance(node, ast.Import):
        return {alias.name.split(".")[0] for alias in node.names}
    if isinstance(node, ast.ImportFrom) and node.module and not node.level:
        return {node.module.split(".")[0]}
    return set()
