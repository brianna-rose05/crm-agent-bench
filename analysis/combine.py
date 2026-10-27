"""Combine all graded runs into one table: model, level, task, run, passed, outcome, cost."""
import csv, sys
R = "results/"
SRC = [  # (folder, level for tasks in range, task filter)
    ("haiku-full", 1, range(1, 19)), ("cheap-models", 1, range(1, 19)), ("top-models", 1, range(1, 19)),
    ("haiku-multiturn", 2, range(19, 29)), ("cheap-multiturn", 2, range(19, 29)), ("top-models", 2, range(19, 29)),
    ("level2-extra", 2, range(19, 29)), ("level3-final", 3, range(25, 39)), ("level4", 4, range(39, 43)),
    ("level5", 5, range(43, 51)),
]
rows = []
for folder, level, tasks in SRC:
    for r in csv.DictReader(open(R + folder + "/results.csv")):
        if int(r["task"]) not in tasks:
            continue
        run = int(r["run"]) + (1 if folder == "level2-extra" else 0)  # extra L2 runs become runs 2-5
        rows.append({"model": r["model"].split("/")[1], "level": level, "task": int(r["task"]), "run": run,
                     "passed": r["passed"] == "True", "outcome": r.get("outcome", ""), "cost": float(r["cost_usd"] or 0),
                     "sim_cost": float(r.get("user_sim_cost_usd") or 0), "score": r.get("score", ""),
                     "checks_passed": r.get("checks_passed", ""), "checks_total": r.get("checks_total", ""),
                     "tool_calls": int(r["tool_calls"] or 0), "src": folder})
w = csv.DictWriter(open("analysis/all_runs.csv", "w"), fieldnames=list(rows[0]))
w.writeheader(); w.writerows(rows)
print(len(rows), "runs")
