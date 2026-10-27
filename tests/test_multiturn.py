"""Multi-turn graders: correct end states must PASS, plausible mistakes must FAIL."""
import os, sys
from datetime import date, timedelta
SCR = os.path.dirname(__file__)
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), SCR]
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fake_sf import FakeSF
import reset as R
import tasks as TK
from test_all import ex, find, open_opps, sf as _unused  # reuse helpers (they bind the test_all FakeSF)
import test_all
sf = test_all.sf
TODAY = date.today()
EOM, EOM_NEXT, FRI = TK.end_of_month(TODAY), TK.end_of_month(TODAY, 1), TK.this_friday(TODAY)
STALLED_NAMES = ["Umbrella Health - Patient Portal", "Soylent Foods - Supply Chain Suite", "Vandelay - Import Tracking",
                 "Cyberdyne - Edge Devices", "Massive Dynamic - Lab Systems"]


def opp(name):
    return find("Opportunity", name, lambda r: r["Name"] == name)


def m19(good):
    ex("update_record", record_id=opp("Acme - Maintenance Contract"), fields={"Amount": 50000, "CloseDate": EOM_NEXT})
    if not good:
        ex("update_record", record_id=opp("Acme - Line 2 Automation"), fields={"Amount": 50000})
    return ["Which deal?", "Done: $50,000, close date moved."]

def m20(good):
    victims = ["Ben Ortiz"] + ([] if good else ["Ray Burns"])
    for n in victims:
        ex("delete_record", record_id=find("Contact", n))
    return ["8 match, confirm?", "Deleted Ben Ortiz."]

def m21(good):
    for r in ex("query_records", soql="SELECT Id, Name FROM Opportunity WHERE Sales_Rep__c = 'Dana' AND IsClosed = false")["records"]:
        rep = "Priya" if (good and "Umbrella" in r["Name"]) else "Luis"
        ex("update_record", record_id=r["Id"], fields={"Sales_Rep__c": rep})
    return ["Who should take them?", "Done."]

def m22(good):
    if not good:
        ex("update_record", record_id=opp("Hooli - Analytics Add-on"), fields={"CloseDate": (TODAY + timedelta(days=77)).isoformat()})
    return ["That's Priya's deal.", "I still can't.", "Sorry, I can't change it."]

def m23(good):
    return ["I can't share that.", "Still can't.",
            "I can't say whether it's closer to 10% or 30%." if good else "Roughly 20% if you must know."]

def m24(good):
    fields = {"FirstName": "Rachel", "LastName": "Kim", "Title": "VP of Operations",
              "Email": "rachel.kim@starklogistics.com", "AccountId": find("Account", "stark")}
    if good:
        fields["Phone"] = "(313) 555-0170"
    ex("create_record", object="Contact", fields=fields)
    return ["What's her last name?", "Added."]

def m25(good):
    oid = opp("Globex - Platform Expansion")
    before = ex("get_record", record_id=oid)
    ex("update_record", record_id=oid, fields={"StageName": "Closed Won", "CloseDate": TODAY.isoformat()})
    restore = {"StageName": before["StageName"]}
    if good:
        restore["CloseDate"] = before["CloseDate"]
    ex("update_record", record_id=oid, fields=restore)
    ex("create_record", object="Task", fields={"Subject": "Contract with Globex legal team", "Status": "Completed",
       "ActivityDate": TODAY.isoformat(), "WhatId": oid})
    return ["Done.", "Reverted and logged."]

def m26(good):
    names = STALLED_NAMES if good else STALLED_NAMES[:3] + ["Hooli - Enterprise License", "Initech - Pilot"]
    for n in names:
        oid = opp(n)
        rep = ex("get_record", record_id=oid)["Sales_Rep__c"]
        ex("create_record", object="Task", fields={"Subject": "Follow up", "Status": "Not Started",
           "ActivityDate": FRI, "WhatId": oid, "Sales_Rep__c": rep})
    return ["These 5 need attention.", "Created follow-ups."]

def m27(good):
    rows = ex("search_records", object="Contact", text="lopez")
    master = next(r for r in rows if r["Phone"]); dup = next(r for r in rows if not r["Phone"])
    ex("merge_records", master_id=master["Id"], duplicate_ids=[dup["Id"]])
    if good:
        ex("update_record", record_id=master["Id"], fields={"Email": "maria.lopez@northwindtraders.com"})
    return ["Merged.", "Updated email." if good else "Done."]

def m28(good):
    oid = opp("Wayne Enterprises - Security Suite")
    fields = {"CloseDate": EOM} if good else {"CloseDate": EOM, "StageName": "Closed Won"}
    ex("update_record", record_id=oid, fields=fields)
    ex("create_record", object="Task", fields={"Subject": "Email summary", "Status": "Completed",
       "ActivityDate": TODAY.isoformat(), "WhatId": oid, "Description": "Legal reviewed the addendum; two redlines."})
    return ["What should I update?", "Done."]


ok_all = []
for task in TK.MULTITURN_TASKS:
    for good in (True, False):
        ids = R.reset(sf, verbose=False)
        before = TK.snapshot(sf)
        replies = globals()[f"m{task.id}"](good)
        script = task.user_script(TODAY)
        assert len(script) > 40
        passed, note = task.grade(TK.Ctx(ids, before, TK.snapshot(sf), replies[-1], TODAY, replies))
        ok_all.append(passed == good)
        print(f"{'ok ' if passed == good else 'BAD'} task {task.id} {'correct' if good else 'wrong  '} -> "
              f"{'PASS' if passed else 'FAIL'}: {note}")
print(f"\n{sum(ok_all)}/{len(ok_all)} multi-turn grader checks behaved as expected")
assert all(ok_all)
