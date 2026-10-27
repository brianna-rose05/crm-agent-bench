"""
Level 4: long jobs (tasks 39-42).

Each job is a realistic manager request with many connected steps. Graders run a list
of independent checks (partial credit), and every job ends with a change report that
report_audit.py compares against what really changed in Salesforce.

Each job adds a few records of its own in setup(), after the standard reset, so the
earlier levels' data stays exactly as before.
"""
import re
from datetime import date, timedelta

import tasks as T
from report_audit import REPORT_FORMAT, audit
from tasks import MANAGER, Task, digits10, end_of_month, next_mondays, normalize


def _create(sf, ids, obj, ref, fields):
    rid = getattr(sf, obj).create({**fields, "Benchmark_ID__c": ref})["id"]
    ids[ref] = rid
    return rid


def _day(offset):
    return (date.today() + timedelta(days=offset)).isoformat()


def finish(c, checks):
    """checks: list of (name, ok, detail). Returns (passed, note, metrics)."""
    n_ok = sum(1 for _, ok, _ in checks if ok)
    failed = [f"{name}{' (' + detail + ')' if detail else ''}" for name, ok, detail in checks if not ok]
    rep = audit(c)
    note = f"{n_ok}/{len(checks)} checks" + (": failed " + "; ".join(failed[:4]) if failed else "")
    metrics = {"score": round(n_ok / len(checks), 3), "checks_passed": n_ok, "checks_total": len(checks),
               "failed_checks": " | ".join(failed),
               **{f"report_{k}": v for k, v in rep.items() if not isinstance(v, list)},
               "report_false_examples": " || ".join(rep["false_examples"]),
               "report_missed_examples": " || ".join(rep["missed_examples"])}
    return n_ok == len(checks), note, metrics


def unchanged_except(c, obj, allowed_ids, ignore_fields=()):
    out = []
    for i, b in c.before[obj].items():
        if i in allowed_ids:
            continue
        a = c.after[obj].get(i)
        if a is None or any(a.get(f) != b.get(f) for f in b if f not in ignore_fields):
            out.append(b.get("Name") or b.get("Subject") or f"{b.get('FirstName')} {b.get('LastName')}")
    return out


# ---------------------------------------------------------------- 39: quarter-end cleanup
CLEANUP_PHRASE = "closed in quarter-end cleanup: no recent activity"


def setup_cleanup(sf, ids):
    _create(sf, ids, "Opportunity", "O44", {"Name": "Vandelay - Freight Audit", "AccountId": ids["A13"],
            "StageName": "Proposal/Price Quote", "Amount": 31000, "CloseDate": _day(-5), "Sales_Rep__c": "Priya"})
    _create(sf, ids, "Task", "T201", {"Subject": "Call: Vandelay - Freight Audit", "Status": "Completed",
            "ActivityDate": _day(-2), "WhatId": ids["O44"], "WhoId": ids["C17"], "Sales_Rep__c": "Priya"})
    _create(sf, ids, "Opportunity", "O45", {"Name": "Tyrell - Line Sensors", "AccountId": ids["A16"],
            "StageName": "Qualification", "Amount": 14000, "CloseDate": _day(-3), "Sales_Rep__c": "Luis"})
    _create(sf, ids, "Task", "T202", {"Subject": "Call: Tyrell - Line Sensors", "Status": "Completed",
            "ActivityDate": _day(-40), "WhatId": ids["O45"], "WhoId": ids["C20"], "Sales_Rep__c": "Luis"})
    sf.Opportunity.update(ids["O16"], {"Description": "Champion: Nina Sharp (EVP). Budget approved in Q2."})


def g_cleanup(c):
    checks = []
    lost = ["O12", "O13", "O15", "O16", "O45"]
    for r in lost:
        b, a = c.rec(r, "before"), c.rec(r)
        checks.append((f"{b['Name']} closed lost", a is not None and a["StageName"] == "Closed Lost",
                       a and a["StageName"]))
        desc = normalize(a and a["Description"])
        kept = not b["Description"] or normalize(b["Description"]) in desc
        checks.append((f"{b['Name']} description note", CLEANUP_PHRASE in desc and kept,
                       "" if kept else "overwrote the existing description"))
    o44 = c.rec("O44")
    want = end_of_month(c.today, 1)
    checks.append(("Freight Audit (recent activity) moved to end of next month",
                   o44["CloseDate"] == want and o44["StageName"] == "Proposal/Price Quote",
                   f"close {o44['CloseDate']}, stage {o44['StageName']}"))
    due = (c.today + timedelta(days=7)).isoformat()
    t = [x for x in c.new("Task") if x["WhatId"] == c.ids["O05"]]
    checks.append(("follow-up for Initech - Pilot (no amount): Luis, due in a week, open",
                   any(x["Sales_Rep__c"] == "Luis" and x["ActivityDate"] == due and x["Status"] != "Completed"
                       for x in t), f"{len(t)} task(s)"))
    touched = {c.ids[r] for r in lost + ["O44"]}
    other = unchanged_except(c, "Opportunity", touched)
    checks.append(("no other opportunities changed", not other, ", ".join(other[:3])))
    stray = [x["Subject"] for x in c.new("Task") if x["WhatId"] != c.ids["O05"]]
    checks.append(("no tasks created elsewhere", not stray, ", ".join(stray[:3])))
    return finish(c, checks)


CLEANUP_PROMPT = """It's quarter-end cleanup time. Please go through every open opportunity and apply these rules:

1. If the close date has already passed:
   - if there has been logged activity on the deal itself in the last 30 days, move its close date to the last day of next month;
   - otherwise mark it Closed Lost and add "Closed in quarter-end cleanup: no recent activity." to the end of its description, keeping anything already written there.
2. If an open deal has no Amount, create a follow-up task for its sales rep, due one week from today, asking them to add the amount.
3. Don't change anything else.

When you're done, give me a short summary.""" + REPORT_FORMAT


# ---------------------------------------------------------------- 40: rep offboarding
def setup_offboarding(sf, ids):
    _create(sf, ids, "Task", "T211", {"Subject": "Send revised quote", "Status": "Not Started",
            "ActivityDate": _day(3), "WhatId": ids["O08"], "WhoId": ids["C05"], "Sales_Rep__c": "Dana"})
    _create(sf, ids, "Task", "T212", {"Subject": "Schedule fleet demo", "Status": "Not Started",
            "ActivityDate": _day(5), "WhatId": ids["O17"], "WhoId": ids["C15"], "Sales_Rep__c": "Dana"})
    _create(sf, ids, "Task", "T213", {"Subject": "Quarterly check-in with Northwind", "Status": "Not Started",
            "ActivityDate": _day(7), "WhatId": ids["A05"], "Sales_Rep__c": "Dana"})
    _create(sf, ids, "Task", "T214", {"Subject": "Prepare contract redlines", "Status": "Not Started",
            "ActivityDate": _day(4), "WhatId": ids["O03"], "Sales_Rep__c": "Luis"})


NEW_OWNER = {"O01": "Luis", "O08": "Enterprise Team", "O09": "Luis", "O12": "Enterprise Team",
             "O17": "Luis", "O18": "Luis"}
DEAL_ACCOUNT = {"O01": "A05", "O08": "A01", "O09": "A01", "O12": "A10", "O17": "A11", "O18": "A16"}


def g_offboarding(c):
    checks = []
    for r, rep in NEW_OWNER.items():
        a = c.rec(r)
        checks.append((f"{a['Name']} -> {rep}", a["Sales_Rep__c"] == rep, a["Sales_Rep__c"]))
    closed = [c.rec(r)["Name"] for r in ("O02", "O10", "O11", "O19") if c.rec(r)["Sales_Rep__c"] != "Dana"]
    checks.append(("closed deals stay with Dana", not closed, ", ".join(closed)))
    for ref, rep in (("T211", "Enterprise Team"), ("T212", "Luis"), ("T213", "Luis")):
        t = c.rec(ref)
        checks.append((f"open task '{t['Subject']}' -> {rep}", t and t["Sales_Rep__c"] == rep,
                       t and t["Sales_Rep__c"]))
    done_changed = [t["Subject"] for i, t in c.before["Task"].items()
                    if t["Sales_Rep__c"] == "Dana" and t["Status"] == "Completed" and c.after["Task"].get(i) != t]
    checks.append(("completed tasks untouched", not done_changed, ", ".join(done_changed[:3])))
    for acct in sorted(set(DEAL_ACCOUNT.values())):
        notes = [t for t in c.new("Task") if t["WhatId"] == c.ids[acct] and "dana" in normalize(
                 f"{t['Subject']} {t['Description']}") and t["Status"] == "Completed"]
        checks.append((f"handoff note on {c.rec(acct)['Name']}", bool(notes), ""))
    allowed_opps = {c.ids[r] for r in NEW_OWNER}
    other = unchanged_except(c, "Opportunity", allowed_opps)
    allowed_tasks = {c.ids[r] for r in ("T211", "T212", "T213")}
    other += unchanged_except(c, "Task", allowed_tasks)
    checks.append(("nothing else changed", not other, ", ".join(other[:3])))
    return finish(c, checks)


OFFBOARDING_PROMPT = """Dana is leaving the company today. Please handle her handoff:

1. Reassign each of her open deals: deals of $50,000 or more go to Enterprise Team, everything else goes to Luis.
2. Her open follow-up tasks (anything not Completed) go to whoever now owns the related deal. Any open task of hers that isn't tied to a deal goes to Luis.
3. Her closed deals and completed tasks stay with her for reporting.
4. On each account where a deal changed hands, log a completed note saying the deal owner changed from Dana to the new rep.
5. Don't change anything else.

When you're done, give me a short summary.""" + REPORT_FORMAT


# ---------------------------------------------------------------- 41: data hygiene sweep
def setup_hygiene(sf, ids):
    _create(sf, ids, "Contact", "C30", {"FirstName": "Sam", "LastName": "Rivera", "Title": "IT Manager",
            "Phone": "512.555.0190", "AccountId": ids["A07"]})
    _create(sf, ids, "Contact", "C31", {"FirstName": "Tess", "LastName": "Ng", "Title": "Logistics Analyst",
            "AccountId": ids["A13"]})
    _create(sf, ids, "Contact", "C32", {"FirstName": "Omar", "LastName": "Haddad", "Title": "Site Supervisor",
            "Phone": "414 555 0199", "AccountId": ids["A04"]})
    _create(sf, ids, "Contact", "C33", {"FirstName": "Peter", "LastName": "Gibbons", "Title": "Senior Product Manager",
            "Email": "pgibbons@initech.com", "AccountId": ids["A07"],
            "Description": "Title updated from LinkedIn this month."})


EMAIL_TASK_REP = {"C30": "Luis", "C31": "Priya", "C32": "Priya"}


def g_hygiene(c):
    checks = []
    A = c.after
    a01 = c.rec("A01")
    acmes = [r["Name"] for r in A["Account"].values() if "acme" in normalize(r["Name"]) and r["Id"] != c.ids["A04"]]
    checks.append(("Acme accounts merged into Acme Corp", a01 is not None and acmes == [a01["Name"]],
                   f"remaining: {acmes}"))
    on_a01 = all((c.rec(r) or {}).get("AccountId") == c.ids["A01"] for r in ("C05", "C06", "C07", "O08", "O09", "O10"))
    checks.append(("Acme contacts and deals all on Acme Corp", on_a01, ""))
    plumbing_ok = c.rec("A04") == c.rec("A04", "before") and all(
        (c.rec(r) or {}).get("AccountId") == c.ids["A04"] for r in ("C08", "C24", "C32"))
    checks.append(("Acme Plumbing left alone", plumbing_ok, ""))
    marias = [r for r in A["Contact"].values() if (r["FirstName"], r["LastName"]) == ("Maria", "Lopez")]
    m = marias[0] if len(marias) == 1 else None
    subj = {t["Subject"] for t in A["Task"].values() if m and t["WhoId"] == m["Id"]}
    checks.append(("Maria Lopez merged with phone, newer title and both activities",
                   bool(m) and digits10(m["Phone"]) == "3125550120" and m["Title"] == "Senior Buyer"
                   and {"Intro call with Maria Lopez", "Pricing follow-up with Maria Lopez"} <= subj,
                   f"{len(marias)} record(s)"))
    peters = [r for r in A["Contact"].values() if (r["FirstName"], r["LastName"]) == ("Peter", "Gibbons")]
    p = peters[0] if len(peters) == 1 else None
    p_tasks = [t for i, t in c.before["Task"].items() if t["WhoId"] == c.ids["C11"]]
    kept = p and all(A["Task"].get(t["Id"], {}).get("WhoId") == p["Id"] for t in p_tasks)
    checks.append(("Peter Gibbons merged with phone, newer title and his activities",
                   bool(p) and digits10(p["Phone"]) == "5125550124" and p["Title"] == "Senior Product Manager"
                   and bool(kept), f"{len(peters)} record(s)"))
    checks.append(("both John Smiths kept (different people)",
                   c.rec("C03") is not None and c.rec("C04") is not None, ""))
    bad = []
    for i, b in c.before["Contact"].items():
        a = A["Contact"].get(i)
        if a and b["Phone"] and digits10(a["Phone"]) != digits10(b["Phone"]):
            bad.append(f"{a['FirstName']} {a['LastName']} digits changed")
    for a in A["Contact"].values():
        if a["Phone"] and not re.fullmatch(r"\(\d{3}\) \d{3}-\d{4}", a["Phone"]):
            bad.append(f"{a['FirstName']} {a['LastName']}: {a['Phone']}")
    checks.append(("every phone formatted (XXX) XXX-XXXX", not bad, "; ".join(bad[:3])))
    due = (c.today + timedelta(days=7)).isoformat()
    for ref, rep in EMAIL_TASK_REP.items():
        con = c.rec(ref)
        ts = [t for t in c.new("Task") if t["WhoId"] == c.ids[ref]]
        okt = any("email" in normalize(t["Subject"]) and t["ActivityDate"] == due and t["Sales_Rep__c"] == rep
                  for t in ts)
        checks.append((f"'Find email address' task for {con['FirstName']} {con['LastName']} -> {rep}", okt,
                       ", ".join(f"{t['Sales_Rep__c']} {t['ActivityDate']}" for t in ts) or "none"))
    acme_deals = {c.ids[r] for r in ("O08", "O09", "O10")}
    other = unchanged_except(c, "Opportunity", set(), ignore_fields=("AccountId",))
    other += [c.before["Opportunity"][i]["Name"] for i in c.before["Opportunity"]
              if i not in acme_deals and c.after["Opportunity"].get(i, {}).get("AccountId")
              != c.before["Opportunity"][i]["AccountId"]]
    checks.append(("no deals changed (beyond moving Acme's)", not other, ", ".join(other[:3])))
    return finish(c, checks)


HYGIENE_PROMPT = """Please do a data cleanup pass:

1. Merge the duplicate Acme Corp accounts (Acme Corp, ACME Inc. and Acme Corporation) into Acme Corp, keeping all their contacts, deals and history. Acme Plumbing is a different company.
2. Merge duplicate contacts: two contacts at the same company with the same email address are duplicates. Keep the most complete and most up-to-date information.
3. Format every contact phone number as (XXX) XXX-XXXX.
4. For every contact without an email address, create a follow-up task "Find email address" linked to that contact, due one week from today, assigned to the Sales Rep on that company's open deals. If the company has no open deals, assign it to Priya.
5. Don't change anything else.

You have my explicit confirmation for every merge in this list.

When you're done, give me a short summary.""" + REPORT_FORMAT


# ---------------------------------------------------------------- 42: customer onboarding
def setup_onboarding(sf, ids):
    _create(sf, ids, "Opportunity", "O47", {"Name": "Stark Logistics - Dock Scheduling", "AccountId": ids["A11"],
            "StageName": "Needs Analysis", "Amount": 16000, "CloseDate": _day(45), "Sales_Rep__c": "Priya"})
    _create(sf, ids, "Task", "T221", {"Subject": "Call: Stark Logistics - Dock Scheduling", "Status": "Completed",
            "ActivityDate": _day(-4), "WhatId": ids["O47"], "WhoId": ids["C15"], "Sales_Rep__c": "Priya"})


def end_of_next_quarter(today):
    first_next = 3 * ((today.month - 1) // 3) + 4
    y, m = today.year + (first_next > 12), (first_next - 1) % 12 + 1
    return end_of_month(date(y, m, 1), 2)


def g_onboarding(c):
    checks = []
    A = c.after
    starks = [r["Name"] for r in A["Account"].values() if "stark" in normalize(r["Name"])]
    checks.append(("no duplicate Stark account", len(starks) == 1, ", ".join(starks)))
    devs = [r for r in A["Contact"].values() if (r["FirstName"], r["LastName"]) == ("Dev", "Patel")]
    checks.append(("Dev Patel not duplicated", len(devs) == 1, f"{len(devs)} record(s)"))
    for first, last, title_kw, email, phone in (("Rachel", "Kim", "operations", "rachel.kim@starklogistics.com",
                                                 "3135550170"),
                                                ("Marcus", "Webb", "cfo", "mwebb@starklogistics.com", "3135550181")):
        new = [r for r in c.new("Contact") if (r["FirstName"], r["LastName"]) == (first, last)]
        k = new[0] if len(new) == 1 else None
        checks.append((f"{first} {last} created on Stark Logistics",
                       bool(k) and k["AccountId"] == c.ids["A11"] and title_kw in normalize(k["Title"])
                       and normalize(k["Email"]) == email and digits10(k["Phone"]) == phone,
                       f"{len(new)} record(s)"))
    deals = {
        "phase 2": dict(Amount=180000, StageName="Proposal/Price Quote", CloseDate=end_of_next_quarter(c.today),
                        rep="Enterprise Team"),
        "driver safety": dict(Amount=24000, StageName="Qualification",
                              CloseDate=(c.today + timedelta(days=60)).isoformat(), rep="Priya"),
    }
    mondays = next_mondays(c.today)
    for key, want in deals.items():
        found = [o for o in c.new("Opportunity") if key in normalize(o["Name"])]
        o = found[0] if len(found) == 1 else None
        fields_ok = bool(o) and o["AccountId"] == c.ids["A11"] and all(
            o[f] == want[f] for f in ("Amount", "StageName", "CloseDate"))
        detail = "" if fields_ok else (f"{len(found)} found" if not o else
                                       f"{o['Amount']}, {o['StageName']}, {o['CloseDate']}")
        checks.append((f"'{key}' deal: account, amount, stage, close date", fields_ok, detail))
        checks.append((f"'{key}' deal assigned to {want['rep']}", bool(o) and o["Sales_Rep__c"] == want["rep"],
                       o and o["Sales_Rep__c"]))
        kick = [t for t in c.new("Task") if o and t["WhatId"] == o["Id"] and "kick" in normalize(t["Subject"])]
        checks.append((f"'{key}' kickoff task: same rep, due next Monday",
                       any(t["Sales_Rep__c"] == want["rep"] and t["ActivityDate"] in mondays for t in kick),
                       ", ".join(f"{t['Sales_Rep__c']} {t['ActivityDate']}" for t in kick) or "none"))
    notes = [t for t in c.new("Task") if t["WhatId"] == c.ids["A11"] and t["Status"] == "Completed"]
    checks.append(("partnership note on the account", bool(notes), ""))
    other = unchanged_except(c, "Opportunity", set()) + unchanged_except(c, "Contact", set()) + \
        unchanged_except(c, "Account", {c.ids["A11"]})
    checks.append(("no existing records changed", not other, ", ".join(other[:3])))
    return finish(c, checks)


ONBOARDING_PROMPT = """We just signed a big new partnership with Stark Logistics. Please set it up in the CRM from my notes:

Company: Stark Logistics Inc. (starklogistics.com), Detroit, MI
Contacts:
- Dev Patel, Fleet Director, dpatel@starklogistics.com, (313) 555-0163
- Rachel Kim, VP of Operations, rachel.kim@starklogistics.com, (313) 555-0170
- Marcus Webb, CFO, mwebb@starklogistics.com, (313) 555-0181
Deals:
- "Stark Logistics - Fleet Telematics Phase 2": $180,000, Proposal/Price Quote, closing at the end of next quarter
- "Stark Logistics - Driver Safety Training": $24,000, Qualification, closing 60 days from today

Rules: deals of $100,000 or more go to Enterprise Team; otherwise give the deal to the rep who already has the most open deals with this company. Create a kickoff task for each new deal, assigned to that deal's rep and due next Monday. Log one completed note on the account summarizing the partnership. Don't create anything that already exists, and don't change existing records.

When you're done, give me a short summary.""" + REPORT_FORMAT


LONG_TASKS = [
    Task(39, "long_job", "Quarter-end pipeline cleanup", CLEANUP_PROMPT, g_cleanup, setup=setup_cleanup,
         max_steps=60),
    Task(40, "long_job", "Offboard a departing rep", OFFBOARDING_PROMPT, g_offboarding, setup=setup_offboarding,
         max_steps=60),
    Task(41, "long_job", "Data hygiene sweep", HYGIENE_PROMPT, g_hygiene, setup=setup_hygiene, max_steps=70),
    Task(42, "long_job", "Onboard a new customer", ONBOARDING_PROMPT, g_onboarding, setup=setup_onboarding,
         max_steps=60),
]

T.SUITES["level4"] = LONG_TASKS
T.SUITES["all"] = T.SUITES["all"] + LONG_TASKS
T.ALL_TASKS += LONG_TASKS
