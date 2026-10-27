"""Re-grade saved Level 4 transcripts (checks + change-report audit) without rerunning the models.

    python reaudit.py results/level4
"""
import csv
import glob
import json
import sys
from datetime import date

import long_tasks  # noqa: F401  (registers Level 4)
from tasks import ALL_TASKS, Ctx

out = sys.argv[1]
by_id = {t.id: t for t in ALL_TASKS}
rows = {(r["model"], r["run"], r["task"]): r for r in csv.DictReader(open(f"{out}/results.csv"))}
for f in sorted(glob.glob(f"{out}/transcripts/*.json")):
    d = json.load(open(f))
    if "before" not in d:
        continue
    r = d["row"]
    task = by_id[int(r["task"])]
    c = Ctx(d["ids"], d["before"], d["after"], d["final_reply"], date.fromisoformat(d["today"]), d["agent_replies"])
    passed, note, metrics = task.grade(c)
    key = (r["model"], str(r["run"]), str(r["task"]))
    if key in rows:
        rows[key].update({"passed": passed, "note": note, **metrics})
    print(f"{r['model']} run {r['run']} task {r['task']}: {note[:70]} | false {metrics['report_false_claims']}, "
          f"missed {metrics['report_missed_changes']}/{metrics['report_real_changes']}, "
          f"auto {metrics['report_auto_reported']}/{metrics['report_auto_changes']}")
fields = list(dict.fromkeys(k for r in rows.values() for k in r))
with open(f"{out}/results.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=fields, restval="")
    w.writeheader()
    w.writerows(rows.values())
