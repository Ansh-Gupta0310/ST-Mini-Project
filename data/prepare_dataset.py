"""Build data/mbpp_subset.json: the 12 MBPP problems used by the pipeline (PROJECT_PLAN.md §3.4).

Standalone script (standard library only). Problems are taken in task_id order and kept if:
  1. they are in MBPP's official test split (task_id 11-510);
  2. the reference solution has at least 2 decision points
     (if/elif, for, while, ternary, try, if inside a comprehension);
  3. the reference solution is at most 25 lines;
  4. the function called by the first reference assert is a top-level function of the reference solution;
  5. the reference solution passes its own 3 asserts.
The first 12 problems that pass every rule are written out.

Usage:  python data/prepare_dataset.py [--source <local copy of sanitized-mbpp.json>]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import urllib.request
import warnings
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/google-research/google-research/master/mbpp/sanitized-mbpp.json"
OUT_FILE = Path(__file__).resolve().parent / "mbpp_subset.json"
TEST_SPLIT = range(11, 511)
MIN_DECISIONS = 2
MAX_LINES = 25
N_PROBLEMS = 12


def parse(code: str) -> ast.Module:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)  # some MBPP regexes use escapes like "\w"
        return ast.parse(code)


def count_decisions(tree: ast.AST) -> int:
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.IfExp, ast.Try, ast.AsyncFor)):
            count += 1
        elif isinstance(node, ast.comprehension):
            count += len(node.ifs)
    return count


def find_entry_point(first_test: str, tree: ast.Module) -> str | None:
    """The first function called in the first reference assert that the reference solution defines."""
    defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    for node in ast.walk(parse(first_test)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in defined:
            return node.func.id
    return None


def top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def signature(node: ast.FunctionDef) -> str:
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"def {node.name}({ast.unparse(node.args)}){returns}:"


def passes_own_tests(item: dict) -> bool:
    namespace: dict = {}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            exec("\n".join([*item["test_imports"], item["code"]]), namespace)
            for test in item["test_list"]:
                exec(test, namespace)
    except Exception:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select the MBPP problem subset.")
    parser.add_argument("--source", help="local copy of sanitized-mbpp.json (default: download it)")
    args = parser.parse_args(argv)

    if args.source:
        raw = Path(args.source).read_bytes()
    else:
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as reply:
            raw = reply.read()
    items = json.loads(raw.decode("utf-8"))
    print(f"Loaded {len(items)} problems from {args.source or SOURCE_URL}")
    print(f"  sha256 of the source file: {hashlib.sha256(raw).hexdigest()}")

    in_split = sorted((it for it in items if it["task_id"] in TEST_SPLIT), key=lambda it: it["task_id"])
    candidates, selected, failed_own_tests = 0, [], []
    for item in in_split:
        code = item["code"].replace("\r\n", "\n")
        tree = parse(code)
        if count_decisions(tree) < MIN_DECISIONS or len(code.splitlines()) > MAX_LINES:
            continue
        entry = find_entry_point(item["test_list"][0], tree)
        node = top_level_function(tree, entry) if entry else None
        if node is None:
            continue
        candidates += 1
        if len(selected) == N_PROBLEMS:
            continue  # keep counting candidates, but the subset is complete
        if not passes_own_tests(item):
            failed_own_tests.append(item["task_id"])
            continue
        selected.append({
            "task_id": item["task_id"],
            "prompt": item["prompt"].strip(),
            "entry_point": entry,
            "signature": signature(node),
            "reference_code": code.rstrip() + "\n",
            "reference_tests": [test.strip() for test in item["test_list"]],
            "test_imports": list(item["test_imports"]),
        })

    print(f"Test split (task_id 11-510): {len(in_split)} problems; {candidates} meet rules 1-4")
    if len(selected) < N_PROBLEMS:
        raise SystemExit(f"Only {len(selected)} problems matched; expected {N_PROBLEMS}.")
    print(f"Selected {N_PROBLEMS} problems: {', '.join(str(p['task_id']) for p in selected)}")
    for p in selected:
        print(f"  {p['task_id']:>4}  {p['signature']}")
    checked = N_PROBLEMS + len(failed_own_tests)
    print(f"{N_PROBLEMS}/{checked} reference solutions pass their own tests"
          + (f" (skipped: {failed_own_tests})" if failed_own_tests else ""))

    OUT_FILE.write_text(json.dumps(selected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_FILE.parent.name}/{OUT_FILE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
