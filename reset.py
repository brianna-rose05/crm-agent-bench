"""
Wipe the benchmark org and reload the seed data.

    python reset.py          # asks you to confirm first
    python reset.py --yes    # no prompt (the harness uses this before every task)

WARNING: this deletes EVERY Account, Contact, Opportunity, Task, Event and Note
in the org, including anything an agent created during a task. Only run it
against your dedicated benchmark Developer Edition org.

Dates in seed_data/ are stored as offsets from today ("close_in_days": 35 means
35 days from now), so planted conditions like "no activity in 70 days" stay
true whenever you run it.
"""
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

SEED = Path(__file__).parent / "seed_data"
COMPOSITE = "composite/sobjects"
WIPE_ORDER = ["Task", "Event", "Note", "Opportunity", "Contact", "Account"]
REQUIRED_FIELDS = {
    "Account": ["Benchmark_ID__c"],
    "Contact": ["Benchmark_ID__c"],
    "Opportunity": ["Benchmark_ID__c", "Sales_Rep__c"],
    "Task": ["Benchmark_ID__c", "Sales_Rep__c"],
}


def read(name):
    with open(SEED / name, newline="") as f:
        return list(csv.DictReader(f))


def day(offset, today=None):
    return ((today or date.today()) + timedelta(days=int(offset))).isoformat()


def blank_to_none(v):
    return v if v not in ("", None) else None


# ---------- Salesforce helpers ----------
def check_fields(sf):
    problems = []
    for obj, fields in REQUIRED_FIELDS.items():
        have = {f["name"] for f in getattr(sf, obj).describe()["fields"]}
        problems += [f"{obj}.{f}" for f in fields if f not in have]
    if problems:
        sys.exit("Missing custom fields: " + ", ".join(problems) +
                 "\nCreate them first. See SETUP_SALESFORCE.md.")


def count_all(sf):
    return {o: sf.query(f"SELECT COUNT() FROM {o}")["totalSize"] for o in WIPE_ORDER}


def delete_all(sf, sobject):
    ids = [r["Id"] for r in sf.query_all(f"SELECT Id FROM {sobject}")["records"]]
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        res = sf.restful(COMPOSITE, method="DELETE",
                         params={"ids": ",".join(chunk), "allOrNone": "false"})
        failed = [r for r in res if not r.get("success")]
        # Children may already be gone via cascade delete; that's fine.
        real = [r for r in failed
                if not any(e.get("statusCode") == "ENTITY_IS_DELETED" for e in r.get("errors", []))]
        if real:
            raise RuntimeError(f"Could not delete some {sobject} records: {real[:3]}")
    return len(ids)


def create(sf, sobject, records):
    """Insert records (in order) and return their new Salesforce Ids in the same order."""
    ids = []
    for i in range(0, len(records), 200):
        chunk = records[i:i + 200]
        payload = {"allOrNone": True,
                   "records": [{"attributes": {"type": sobject}, **r} for r in chunk]}
        res = sf.restful(COMPOSITE, method="POST", json=payload)
        bad = [r for r in res if not r.get("success")]
        if bad:
            raise RuntimeError(f"Insert into {sobject} failed: {bad[:3]}")
        ids += [r["id"] for r in res]
    return ids


# ---------- build records from the CSVs ----------
STATE_CODES = {"Illinois": "IL"}  # full names used in the seed data -> codes


def address_fields(state, picklists):
    """Orgs with State/Country picklists need a country and a state *code*."""
    if not state:
        return {}
    if picklists:
        return {"BillingCountryCode": "US", "BillingStateCode": STATE_CODES.get(state, state)}
    return {"BillingCountry": "United States", "BillingState": state}


def build_accounts(picklists=False):
    return [{"Benchmark_ID__c": r["ref"], "Name": r["name"], "Website": blank_to_none(r["website"]),
             "Industry": blank_to_none(r["industry"]),
             **address_fields(blank_to_none(r["billing_state"]), picklists),
             "Phone": blank_to_none(r["phone"]), "Description": blank_to_none(r["description"])}
            for r in read("accounts.csv")]


def build_contacts(acct_ids):
    return [{"Benchmark_ID__c": r["ref"], "FirstName": r["first_name"], "LastName": r["last_name"],
             "Email": blank_to_none(r["email"]), "Phone": blank_to_none(r["phone"]),
             "Title": blank_to_none(r["title"]), "AccountId": acct_ids[r["account_ref"]],
             "Description": blank_to_none(r["description"])}
            for r in read("contacts.csv")]


def build_opps(acct_ids, today=None):
    out = []
    for r in read("opportunities.csv"):
        out.append({"Benchmark_ID__c": r["ref"], "Name": r["name"], "AccountId": acct_ids[r["account_ref"]],
                    "StageName": r["stage"],
                    "Amount": float(r["amount"]) if r["amount"] else None,
                    "CloseDate": day(r["close_in_days"], today),
                    "Sales_Rep__c": blank_to_none(r["sales_rep"]),
                    "Description": blank_to_none(r["description"])})
    return out


def build_tasks(ids, today=None):
    out = []
    for r in read("tasks.csv"):
        rec = {"Benchmark_ID__c": r["ref"], "Subject": r["subject"], "Status": r["status"],
               "ActivityDate": day(r["activity_in_days"], today),
               "Sales_Rep__c": blank_to_none(r["sales_rep"]),
               "Description": blank_to_none(r["description"])}
        if r["what_ref"]:
            rec["WhatId"] = ids[r["what_ref"]]
        if r["who_ref"]:
            rec["WhoId"] = ids[r["who_ref"]]
        out.append(rec)
    return out


_PICKLISTS = {}


def reset(sf, verbose=True, check=True):
    """check=False skips the field checks (saves API calls when resetting many times in a row)."""
    log = print if verbose else (lambda *a, **k: None)
    if check or sf.sf_instance not in _PICKLISTS:
        check_fields(sf)
        _PICKLISTS[sf.sf_instance] = "BillingStateCode" in {f["name"] for f in sf.Account.describe()["fields"]}
    picklists = _PICKLISTS[sf.sf_instance]

    for obj in WIPE_ORDER:
        n = delete_all(sf, obj)
        if n:
            log(f"  deleted {n} {obj}")

    ids = {}
    accts = build_accounts(picklists)
    ids.update(zip([a["Benchmark_ID__c"] for a in accts], create(sf, "Account", accts)))
    cons = build_contacts(ids)
    ids.update(zip([c["Benchmark_ID__c"] for c in cons], create(sf, "Contact", cons)))
    opps = build_opps(ids)
    ids.update(zip([o["Benchmark_ID__c"] for o in opps], create(sf, "Opportunity", opps)))
    tasks = build_tasks(ids)
    create(sf, "Task", tasks)

    log(f"  loaded {len(accts)} accounts, {len(cons)} contacts, "
        f"{len(opps)} opportunities, {len(tasks)} tasks")
    return ids


if __name__ == "__main__":
    from sf_client import connect
    sf = connect()
    print(f"Org: {sf.sf_instance}")
    if "--yes" not in sys.argv:
        counts = count_all(sf)
        print("This will DELETE everything below and reload the benchmark seed data:")
        for obj, n in counts.items():
            print(f"  {obj}: {n}")
        if input("Type RESET to continue: ").strip() != "RESET":
            sys.exit("Cancelled.")
    reset(sf)
    print("Done.")
