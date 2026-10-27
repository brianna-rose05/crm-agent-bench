"""Level 3 re-read rate: share of update_record calls followed later in the run by a read of the same record."""
import json, glob, collections, sys
maxrun = int(sys.argv[1]) if len(sys.argv) > 1 else 5
c = collections.defaultdict(lambda: [0, 0])
for f in glob.glob("results/level3-final/transcripts/*.json"):
    name = f.split("/")[-1]; model = name.split("__")[0].split("_", 1)[1]; run = int(name.split("run")[-1].split(".")[0])
    if run > maxrun: continue
    calls = json.load(open(f))["tool_calls"]
    for i, t in enumerate(calls):
        if t["tool"] != "update_record": continue
        rid = t["args"].get("record_id"); c[model][1] += 1
        later = calls[i + 1:]
        if any((u["tool"] == "get_record" and u["args"].get("record_id") == rid) or
               (u["tool"] in ("query_records", "get_related", "search_records") and rid and rid in str(u["output"]))
               for u in later):
            c[model][0] += 1
for m, (a, b) in sorted(c.items(), key=lambda x: -x[1][0] / x[1][1]):
    print(f"{m:32} {a}/{b} = {a/b:.0%}")
