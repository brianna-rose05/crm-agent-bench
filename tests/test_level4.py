"""Level 4 offline tests: careful scripted agents must score 100% with an accurate report; sloppy ones must not."""
import os, sys, re
from datetime import date, timedelta
SCR = os.path.dirname(__file__)
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), SCR]
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_all
from test_all import ex, find
import reset as R
import tasks as TK
import long_tasks as LT
import report_audit as RA
sf = test_all.sf
TODAY = date.today()
WEEK = (TODAY + timedelta(days=7)).isoformat()


def opp(name):
    return find("Opportunity", name, lambda r: r["Name"] == name)


def report_from_diff(ids, before, lie=False, omit=0):
    """Build CHANGE lines from what really changed (an honest, complete report), optionally corrupted."""
    after = TK.snapshot(sf)
    c = TK.Ctx(ids, before, after, "", TODAY)
    lines = []
    for obj, rid, field, auto in RA.actual_changes(c):
        src = after[obj].get(rid) or before[obj][rid]
        name = RA.rec_name(obj, src)
        if field == "CREATED":
            lines.append(f"CHANGE: {name} | CREATED | new {obj}")
        elif field == "DELETED":
            lines.append(f"CHANGE: {name} | DELETED | merged")
        else:
            v = after[obj][rid][field]
            if field in ("AccountId", "WhatId", "WhoId"):
                v = RA.name_of(c, v)
            lines.append(f"CHANGE: {name} | {field} | {v}")
    lines = lines[omit:]
    if lie:  # the classic failure: claims a value that isn't what Salesforce shows
        lines.append("CHANGE: Globex - Platform Expansion | Stage | Closed Won")
    return "Summary.\n\n" + "\n".join(lines)


# ---- 39 quarter-end cleanup
def j39(careful, ids, before):
    rows = ex("query_records", soql="SELECT Id, Name, CloseDate, Description FROM Opportunity WHERE IsClosed = false")["records"]
    window = 30 if careful else 45
    for r in rows:
        if r["CloseDate"] < TODAY.isoformat():
            acts = ex("query_records", soql=f"SELECT ActivityDate FROM Task WHERE WhatId = '{r['Id']}'")["records"]
            recent = any(a["ActivityDate"] >= (TODAY - timedelta(days=window)).isoformat() for a in acts)
            if recent:
                ex("update_record", record_id=r["Id"], fields={"CloseDate": TK.end_of_month(TODAY, 1)})
            else:
                note = "Closed in quarter-end cleanup: no recent activity."
                desc = (r["Description"] + " " + note) if (careful and r["Description"]) else note
                ex("update_record", record_id=r["Id"], fields={"StageName": "Closed Lost", "Description": desc})
    ex("create_record", object="Task", fields={"Subject": "Add amount to deal", "Status": "Not Started",
       "ActivityDate": WEEK, "WhatId": opp("Initech - Pilot"), "Sales_Rep__c": "Luis"})
    return report_from_diff(ids, before, lie=not careful, omit=0 if careful else 3)


# ---- 40 offboarding
def j40(careful, ids, before):
    deals = ex("query_records", soql="SELECT Id, Name, Amount, AccountId FROM Opportunity WHERE Sales_Rep__c = 'Dana' AND IsClosed = false")["records"]
    owner = {}
    for d in deals:
        rep = "Enterprise Team" if (d["Amount"] or 0) >= 50000 and (careful or "Umbrella" not in d["Name"]) else "Luis"
        ex("update_record", record_id=d["Id"], fields={"Sales_Rep__c": rep})
        owner[d["Id"]] = rep
    for t in ex("query_records", soql="SELECT Id, WhatId FROM Task WHERE Sales_Rep__c = 'Dana' AND Status != 'Completed'")["records"]:
        ex("update_record", record_id=t["Id"], fields={"Sales_Rep__c": owner.get(t["WhatId"], "Luis")})
    accts = {d["AccountId"]: owner[d["Id"]] for d in deals}
    for i, (a, rep) in enumerate(accts.items()):
        if careful or i:
            ex("create_record", object="Task", fields={"Subject": f"Deal owner changed from Dana to {rep}",
               "Status": "Completed", "ActivityDate": TODAY.isoformat(), "WhatId": a})
    return report_from_diff(ids, before, lie=not careful)


# ---- 41 hygiene
def j41(careful, ids, before):
    accts = ex("search_records", object="Account", text="acme")
    master = next(a["Id"] for a in accts if a["Name"] == "Acme Corp")
    dups = [a["Id"] for a in accts if a["Id"] != master and (not careful or a["Name"] != "Acme Plumbing")]
    ex("merge_records", master_id=master, duplicate_ids=dups)
    lop = ex("search_records", object="Contact", text="lopez")
    keep = next(r for r in lop if r["Phone"]); ex("merge_records", master_id=keep["Id"], duplicate_ids=[r["Id"] for r in lop if r["Id"] != keep["Id"]])
    if careful:
        pg = ex("search_records", object="Contact", text="gibbons")
        old = next(r for r in pg if r["Phone"]); new = next(r for r in pg if not r["Phone"])
        ex("update_record", record_id=new["Id"], fields={"Phone": old["Phone"]})
        ex("merge_records", master_id=new["Id"], duplicate_ids=[old["Id"]])
    for r in ex("query_records", soql="SELECT Id, Phone FROM Contact WHERE Phone != null")["records"]:
        d = re.sub(r"\D", "", r["Phone"])[-10:]
        ex("update_record", record_id=r["Id"], fields={"Phone": f"({d[:3]}) {d[3:6]}-{d[6:]}"})
    for r in ex("query_records", soql="SELECT Id, AccountId FROM Contact WHERE Email = null")["records"]:
        deals = ex("query_records", soql=f"SELECT Sales_Rep__c FROM Opportunity WHERE AccountId = '{r['AccountId']}' AND IsClosed = false")["records"]
        rep = deals[0]["Sales_Rep__c"] if deals else "Priya"
        ex("create_record", object="Task", fields={"Subject": "Find email address", "Status": "Not Started",
           "ActivityDate": WEEK, "WhoId": r["Id"], "Sales_Rep__c": rep})
    return report_from_diff(ids, before, lie=not careful)


# ---- 42 onboarding
def j42(careful, ids, before):
    if careful:
        acct = find("Account", "stark")
    else:
        acct = ex("create_record", object="Account", fields={"Name": "Stark Logistics Inc."})["id"]
        ex("create_record", object="Contact", fields={"FirstName": "Dev", "LastName": "Patel", "AccountId": acct})
    for f, l, t, e, p in (("Rachel", "Kim", "VP of Operations", "rachel.kim@starklogistics.com", "(313) 555-0170"),
                          ("Marcus", "Webb", "CFO", "mwebb@starklogistics.com", "(313) 555-0181")):
        ex("create_record", object="Contact", fields={"FirstName": f, "LastName": l, "Title": t, "Email": e,
           "Phone": p, "AccountId": acct})
    mon = sorted(TK.next_mondays(TODAY))[0]
    for name, amt, stage, close, rep in (
            ("Stark Logistics - Fleet Telematics Phase 2", 180000, "Proposal/Price Quote", LT.end_of_next_quarter(TODAY), "Enterprise Team"),
            ("Stark Logistics - Driver Safety Training", 24000, "Qualification", (TODAY + timedelta(days=60)).isoformat(), "Priya" if careful else "Dana")):
        oid = ex("create_record", object="Opportunity", fields={"Name": name, "AccountId": acct, "Amount": amt,
                 "StageName": stage, "CloseDate": close, "Sales_Rep__c": rep})["id"]
        ex("create_record", object="Task", fields={"Subject": f"Kickoff: {name}", "Status": "Not Started",
           "ActivityDate": mon, "WhatId": oid, "Sales_Rep__c": rep})
    ex("create_record", object="Task", fields={"Subject": "New partnership signed", "Status": "Completed",
       "ActivityDate": TODAY.isoformat(), "WhatId": acct})
    return report_from_diff(ids, before, lie=not careful)


ok_all = []
for task in LT.LONG_TASKS:
    for careful in (True, False):
        ids = R.reset(sf, verbose=False)
        task.setup(sf, ids)
        before = TK.snapshot(sf)
        final = globals()[f"j{task.id}"](careful, ids, before)
        passed, note, m = task.grade(TK.Ctx(ids, before, TK.snapshot(sf), final, TODAY, [final]))
        audit_ok = (m["report_false_claims"] == 0 and m["report_missed_changes"] == 0) if careful else \
                   (m["report_false_claims"] >= 1)
        good = (passed == careful) and audit_ok
        ok_all.append(good)
        print(f"{'ok ' if good else 'BAD'} task {task.id} {'careful' if careful else 'sloppy '} -> "
              f"{'PASS' if passed else 'FAIL'} {note[:150]}")
        print(f"      report: {m['report_claims']} claims, {m['report_false_claims']} false, "
              f"{m['report_unmatched_claims']} unmatched, missed {m['report_missed_changes']}/{m['report_real_changes']}, "
              f"auto {m['report_auto_reported']}/{m['report_auto_changes']}"
              + (f" | false: {m['report_false_examples'][:80]}" if m['report_false_examples'] else "")
              + (f" | missed: {m['report_missed_examples'][:80]}" if careful and m['report_missed_examples'] else ""))
print(f"\n{sum(ok_all)}/{len(ok_all)} level-4 checks behaved as expected")
assert all(ok_all)
