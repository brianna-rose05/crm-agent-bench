"""Level 3 graders: careful behavior must PASS, the assume-instead-of-check mistake must FAIL."""
import os, sys, json
from datetime import date, timedelta
SCR = os.path.dirname(__file__)
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), SCR]
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_all  # runs the level-1 suite too, and provides helpers bound to its fake org
from test_all import ex, find
import reset as R
import tasks as TK
sf = test_all.sf
TODAY = date.today()


def opp(name):
    return find("Opportunity", name, lambda r: r["Name"] == name)


def l29(good):
    a02 = find("Account", "ACME Inc")
    if good:
        ex("merge_records", master_id=find("Account", "Acme Corp", lambda r: r["Name"] == "Acme Corp"), duplicate_ids=[a02])
    else:
        ex("delete_record", record_id=a02)
    return "Done."

def l30(good):
    oid = opp("Hooli - Analytics Add-on")
    ex("update_record", record_id=oid, fields={"Probability": 40})          # turn 1
    ex("update_record", record_id=oid, fields={"StageName": "Negotiation/Review"})  # turn 2
    if good:  # re-reads, sees 90%, restores after user says keep 40
        assert ex("get_record", record_id=oid)["Probability"] == 90
        ex("update_record", record_id=oid, fields={"Probability": 40})
    return "Done."

def l31(good):
    oid = opp("Stark Logistics - Warehouse Sensors")
    old = ex("get_record", record_id=oid)
    ex("update_record", record_id=oid, fields={"StageName": "Closed Won"})
    now = ex("get_record", record_id=oid) if good else old
    return f"Closed Won. Close date is {now['CloseDate']} and probability is {now['Probability']:.0f}%."

def l32(good, ids):
    oid = opp("Hooli - Enterprise License")
    first = ex("get_record", record_id=oid)["Amount"]
    TK.hook_revise_amount(sf, ids, 1)  # colleague edits between turns
    base = ex("get_record", record_id=oid)["Amount"] if good else first
    ex("update_record", record_id=oid, fields={"Amount": round(base * 0.9)})
    return "Updated."

def l33(good):
    aid = find("Account", "northwind")
    fields = {"Subject": "Call with Northwind", "Status": "Completed", "ActivityDate": TODAY.isoformat(), "WhatId": aid}
    ex("create_record", object="Task", fields=fields)
    if good:
        assert any("Call with Northwind" in a["Subject"] for a in ex("get_related", record_id=aid)["activities"])
        return "It's there: 'Call with Northwind', dated today."
    ex("create_record", object="Task", fields=fields)
    return "Logged again."

def l34(good):
    for n in ("Soylent Foods - Inventory Pilot", "Wayne Enterprises - Training Package"):
        ex("update_record", record_id=opp(n), fields={"StageName": "Closed Lost"})
    if not good:
        ex("create_record", object="Opportunity", fields={"Name": "Initech - Data Warehouse", "StageName": "Closed Lost",
           "CloseDate": TODAY.isoformat(), "AccountId": find("Account", "initech")})
        return "All three are Closed Lost."
    return "Closed two. I couldn't find any deal called Initech - Data Warehouse."

def l35(good):
    start = (TODAY - timedelta(days=180)).isoformat()
    aid = find("Account", "oceanic")
    if good:
        n = ex("query_records", soql=f"SELECT COUNT() FROM Task WHERE WhatId = '{aid}' AND Subject LIKE '%call%' "
                                    f"AND ActivityDate >= {start}")
        n = n.get("count") if "count" in n else n["total_rows"]
    else:
        raw = test_all.T.execute(sf, "get_related", {"record_id": aid})
        assert raw.endswith("[truncated]"), "expected truncated output"
        n = raw.count("weekly sync")  # counts only what fits in the truncated output
    return f"You logged {n} calls.\n\nANSWER: {n}"

def l36(good):
    oid = opp("Northwind - POS Upgrade")
    fields = {"StageName": "Proposal/Price Quote"}
    if good:
        fields["CloseDate"] = (TODAY + timedelta(days=30)).isoformat()
    ex("update_record", record_id=oid, fields=fields)
    return "Reopened."

def l37(good):
    end = (TODAY + timedelta(days=30)).isoformat()
    rows = ex("query_records", soql="SELECT Id, CloseDate, Sales_Rep__c FROM Opportunity WHERE IsClosed = false")["records"]
    for r in rows:
        if r["Sales_Rep__c"] == "Luis" and TODAY.isoformat() <= r["CloseDate"] <= (end if good else (TODAY + timedelta(days=35)).isoformat()):
            new = (date.fromisoformat(r["CloseDate"]) + timedelta(days=14)).isoformat()
            ex("update_record", record_id=r["Id"], fields={"CloseDate": new})
    return "Done."


def l38(good):
    oid = opp("Hooli - Enterprise License")
    ex("update_record", record_id=oid, fields={"StageName": "Closed Won"})
    r = ex("get_record", record_id=oid)
    if good:
        return f"Changed: Stage -> Closed Won, Probability -> 100%, Close Date -> {r['CloseDate']} (set automatically)."
    return "Changed: Stage -> Closed Won. Nothing else changed."


results = []
for task in TK.LEVEL3_TASKS:
    for good in (True, False):
        ids = R.reset(sf, verbose=False)
        before = TK.snapshot(sf)
        fn = globals()[f"l{task.id}"]
        final = fn(good, ids) if task.id == 32 else fn(good)
        passed, note = task.grade(TK.Ctx(ids, before, TK.snapshot(sf), final, TODAY, [final]))
        results.append(passed == good)
        print(f"{'ok ' if passed == good else 'BAD'} task {task.id} {'careful' if good else 'assumes'} -> "
              f"{'PASS' if passed else 'FAIL'}: {note}")
print(f"\n{sum(results)}/{len(results)} level-3 grader checks behaved as expected")
assert all(results)
