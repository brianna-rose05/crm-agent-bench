"""Final numbers: scoreboard with 95% bootstrap ranges, failures by task, costs, re-read rates, Level 4."""
import csv, json, random, collections, glob, os
random.seed(7)
rows = list(csv.DictReader(open("analysis/all_runs.csv")))
for r in rows:
    r["passed"] = r["passed"] == "True"; r["level"] = int(r["level"]); r["task"] = int(r["task"]); r["cost"] = float(r["cost"])
MODELS = ["claude-opus-5.5", "claude-sonnet-5.5", "deepseek-v4.1-flash-1017", "claude-haiku-5.5", "gpt-6.1-sol"]
SHARED = (1, 2, 3, 5)

def units(m):  # (level, task) -> list of pass booleans
    u = collections.defaultdict(list)
    for r in rows:
        if r["model"] == m and r["level"] in SHARED:
            u[(r["level"], r["task"])].append(r["passed"])
    return u

def boot(m, B=4000):
    u = units(m); keys = sorted(u)
    rates = []
    for _ in range(B):
        s = [u[keys[random.randrange(len(keys))]] for _ in keys]
        rates.append(sum(sum(x) for x in s) / sum(len(x) for x in s))
    rates.sort(); return rates[int(.025 * B)], rates[int(.975 * B)]

def boot_diff(a, b, B=4000):  # paired by task
    ua, ub = units(a), units(b); keys = sorted(set(ua) & set(ub)); d = []
    for _ in range(B):
        ks = [keys[random.randrange(len(keys))] for _ in keys]
        pa = sum(sum(ua[k]) for k in ks) / sum(len(ua[k]) for k in ks)
        pb = sum(sum(ub[k]) for k in ks) / sum(len(ub[k]) for k in ks)
        d.append(pa - pb)
    d.sort(); return d[int(.025 * B)], d[int(.975 * B)]

out = {}
print("SCOREBOARD (shared levels 1,2,3,5)")
for m in MODELS:
    R = [r for r in rows if r["model"] == m and r["level"] in SHARED]
    lv = {L: (sum(r["passed"] for r in R if r["level"] == L), sum(1 for r in R if r["level"] == L)) for L in SHARED}
    tot = sum(r["passed"] for r in R); n = len(R); lo, hi = boot(m)
    cost = sum(r["cost"] for r in R)
    out[m] = dict(levels=lv, total=tot, n=n, lo=lo, hi=hi, cost=cost, cost_per_run=cost / n)
    print(f"{m:26} " + " ".join(f"L{L}:{p}/{k}" for L, (p, k) in lv.items()) +
          f"  total {tot}/{n} = {tot/n:.1%} [{lo:.1%}, {hi:.1%}]  cost ${cost:.3f} = {100*cost/n:.3f}c/run")
print("\nPAIRWISE DIFFERENCES (row minus col, 95% range)")
for i, a in enumerate(MODELS):
    for b in MODELS[i + 1:]:
        lo, hi = boot_diff(a, b)
        pa = out[a]["total"] / out[a]["n"]; pb = out[b]["total"] / out[b]["n"]
        print(f"  {a[:14]:14} - {b[:14]:14}: {pa-pb:+.1%} [{lo:+.1%}, {hi:+.1%}] {'SEPARATED' if lo > 0 or hi < 0 else ''}")
print("\nFAILURES BY TASK (shared levels)")
fails = collections.defaultdict(lambda: collections.Counter()); tot = collections.defaultdict(lambda: collections.Counter())
for r in rows:
    if r["level"] in SHARED:
        tot[(r["level"], r["task"])][r["model"]] += 1
        if not r["passed"]:
            fails[(r["level"], r["task"])][r["model"]] += 1
for k in sorted(fails):
    print(f"  L{k[0]} t{k[1]:>2}: " + "  ".join(f"{m[:8]} {fails[k][m]}/{tot[k][m]}" for m in MODELS))
print("\nLEVEL 5 OUTCOMES")
for m in MODELS:
    print(f"  {m:26}", dict(collections.Counter(r["outcome"] for r in rows if r["model"] == m and r["level"] == 5)))
print("\nLEVEL 4")
for m in MODELS:
    R = [r for r in rows if r["model"] == m and r["level"] == 4]
    if not R: print(f"  {m:26} not run"); continue
    cp = sum(int(r["checks_passed"] or 0) for r in R); ct = sum(int(r["checks_total"] or 0) for r in R)
    print(f"  {m:26} jobs passed {sum(r['passed'] for r in R)}/{len(R)}  checks {cp}/{ct}  cost ${sum(r['cost'] for r in R):.3f}")
json.dump(out, open("analysis/summary.json", "w"), indent=1, default=str)
