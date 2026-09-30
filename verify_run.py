"""Independent check of a run folder: do the verdicts match the measured numbers, and do the
final test files follow the PROJECT_PLAN.md §3.6 rules? (Reviewer checklist, §8 item 4.)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from agents.code_utils import check_test_file
from agents.test_executor import coverage_target_met, decide_verdict

out = Path(sys.argv[1])
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
criterion = summary["config"]["criterion"]
target = summary["config"]["target"]
problems = {p["task_id"]: p for p in summary["problems"]}
errors = []

for task_id, v in problems.items():
    folder = out / f"Mbpp_{task_id}"
    # 1. every execution folder's verdict follows from its own numbers
    for execution in sorted(folder.glob("*/execution.json")):
        r = json.loads(execution.read_text(encoding="utf-8"))
        expected_met = coverage_target_met(r["criterion"], r["target"], r["statement_coverage"],
                                          r["branch_coverage"])
        expected = decide_verdict(r["status"], r["tests_total"], r["tests_failed"], expected_met)
        if (expected_met, expected) != (r["target_met"], r["verdict"]):
            errors.append(f"{execution}: verdict {r['verdict']}/{r['target_met']} but the numbers give "
                          f"{expected}/{expected_met}")
        if r["tests_passed"] + r["tests_failed"] != r["tests_total"]:
            errors.append(f"{execution}: passed + failed != total")
    # 2. verdict.json agrees with the folders it summarises
    for key, sub in (("round_1", "round_1"), ("final", None)):
        block = v.get(key)
        if not block:
            continue
        if sub:
            r = json.loads((folder / sub / "execution.json").read_text(encoding="utf-8"))
            for field in ("verdict", "tests_total", "tests_passed", "statement_coverage", "branch_coverage",
                          "target_met"):
                if block[field] != r[field]:
                    errors.append(f"Mbpp_{task_id} {key}.{field}: {block[field]} != {sub}/{r[field]}")
    if v.get("final_round"):
        r = json.loads((folder / f"round_{v['final_round']}" / "execution.json").read_text(encoding="utf-8"))
        if v["final"]["verdict"] != r["verdict"]:
            errors.append(f"Mbpp_{task_id}: final verdict does not match round_{v['final_round']}")
    # 3. the final test file follows the §3.6 rules and matches the labels
    tests = folder / "test_solution.py"
    if v.get("final"):
        if not tests.exists():
            errors.append(f"Mbpp_{task_id}: final result but no test_solution.py")
        else:
            broken = check_test_file(tests.read_text(encoding="utf-8"), v["entry_point"])
            if broken:
                errors.append(f"Mbpp_{task_id}/test_solution.py breaks a rule: {broken}")
        labels = json.loads((folder / "validation.json").read_text(encoding="utf-8"))
        if sum(labels["counts"].values()) != v["final"]["tests_total"]:
            errors.append(f"Mbpp_{task_id}: {sum(labels['counts'].values())} labels for "
                          f"{v['final']['tests_total']} tests")
        if labels["counts"] != v["test_labels"]:
            errors.append(f"Mbpp_{task_id}: validation.json counts != verdict.json test_labels")
    elif tests.exists():
        errors.append(f"Mbpp_{task_id}: no final result but test_solution.py exists")
    # 4. no key material anywhere in the problem folder
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".jsonl", ".txt", ".py", ".xml"):
            if "sk-or-v1-" in path.read_text(encoding="utf-8", errors="replace"):
                errors.append(f"{path}: looks like it contains an API key")

agg = summary["aggregate"]
print(f"checked {len(problems)} problems in {out}")
print(f"criterion {criterion} >= {target}; goal met final {agg['generated_target_met_final']}, "
      f"round 1 {agg['generated_target_met_round_1']}")
if errors:
    print(f"\n{len(errors)} PROBLEM(S):")
    print("\n".join(f"  - {e}" for e in errors))
    sys.exit(1)
print("all verdicts follow from the measured numbers; all final test files follow the rules")
