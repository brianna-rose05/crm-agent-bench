"""
The tools the AI agent can call. Each one wraps Salesforce API calls.

TOOLS    -> the tool definitions sent to the model (OpenAI / OpenRouter format)
execute  -> runs one tool call and returns a JSON string for the model to read
"""
import json
import re

PREFIX = {"001": "Account", "003": "Contact", "006": "Opportunity", "00T": "Task"}
FIELDS = {
    "Account": "Id, Name, Website, Phone, Industry, BillingState, Description",
    "Contact": "Id, FirstName, LastName, Email, Phone, Title, AccountId, Account.Name, Description",
    "Opportunity": "Id, Name, AccountId, Account.Name, StageName, Probability, Amount, CloseDate, Sales_Rep__c, "
                   "Description",
    "Task": "Id, Subject, Status, ActivityDate, WhatId, What.Name, WhoId, Who.Name, Sales_Rep__c, Description",
}
OBJECTS = list(FIELDS)
MAX_CHARS = 12000


def _obj_param(desc="Salesforce object"):
    return {"type": "string", "enum": OBJECTS, "description": desc}


TOOLS = [
    {"type": "function", "function": {
        "name": "search_records",
        "description": "Find records whose name contains some text (case-insensitive). Searches Name for "
                       "Account and Opportunity, Name and Email for Contact, Subject for Task.",
        "parameters": {"type": "object", "properties": {
            "object": _obj_param(),
            "text": {"type": "string", "description": "Text to look for, e.g. 'acme'"}},
            "required": ["object", "text"]}}},
    {"type": "function", "function": {
        "name": "get_record",
        "description": "Get all standard fields of one record by its Id.",
        "parameters": {"type": "object", "properties": {
            "record_id": {"type": "string"}}, "required": ["record_id"]}}},
    {"type": "function", "function": {
        "name": "get_related",
        "description": "For an Account: its contacts, opportunities and activities. For a Contact or "
                       "Opportunity: its activities (tasks, calls, emails, notes), newest first.",
        "parameters": {"type": "object", "properties": {
            "record_id": {"type": "string"}}, "required": ["record_id"]}}},
    {"type": "function", "function": {
        "name": "query_records",
        "description": "Run a read-only SOQL SELECT query (max 200 rows returned). Useful for reports, "
                       "e.g. SELECT Name, Amount FROM Opportunity WHERE IsClosed = false",
        "parameters": {"type": "object", "properties": {
            "soql": {"type": "string"}}, "required": ["soql"]}}},
    {"type": "function", "function": {
        "name": "create_record",
        "description": "Create a record. Fields use Salesforce API names, e.g. for a Contact "
                       "{FirstName, LastName, Email, Phone, Title, AccountId}; for a Task (also used for "
                       "notes and logged calls) {Subject, Status, ActivityDate (YYYY-MM-DD), WhatId, "
                       "WhoId, Sales_Rep__c, Description}. Returns the new Id.",
        "parameters": {"type": "object", "properties": {
            "object": _obj_param(),
            "fields": {"type": "object", "description": "Field API name -> value"}},
            "required": ["object", "fields"]}}},
    {"type": "function", "function": {
        "name": "update_record",
        "description": "Update fields on one record. Only the fields you pass are changed.",
        "parameters": {"type": "object", "properties": {
            "record_id": {"type": "string"},
            "fields": {"type": "object", "description": "Field API name -> new value"}},
            "required": ["record_id", "fields"]}}},
    {"type": "function", "function": {
        "name": "delete_record",
        "description": "Delete one record by Id.",
        "parameters": {"type": "object", "properties": {
            "record_id": {"type": "string"}}, "required": ["record_id"]}}},
    {"type": "function", "function": {
        "name": "merge_records",
        "description": "Merge duplicate Accounts or Contacts into a master record. Moves the duplicates' "
                       "related records (contacts, opportunities, activities) onto the master, then "
                       "deletes the duplicates. Field values on the duplicates are NOT copied: update "
                       "the master with any values you want to keep BEFORE merging.",
        "parameters": {"type": "object", "properties": {
            "master_id": {"type": "string"},
            "duplicate_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["master_id", "duplicate_ids"]}}},
]


# ---------- helpers ----------
def esc(s):
    return str(s).replace("\\", "\\\\").replace("'", "\\'")


def object_of(record_id):
    obj = PREFIX.get(str(record_id)[:3])
    if not obj:
        raise ValueError(f"Unrecognized record Id '{record_id}'. Ids start with 001 (Account), "
                         "003 (Contact), 006 (Opportunity) or 00T (Task).")
    return obj


def clean(rec):
    """Drop Salesforce metadata and flatten Account: {Name: x} into 'Account.Name': x."""
    out = {}
    for k, v in rec.items():
        if k == "attributes":
            continue
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if k2 != "attributes":
                    out[f"{k}.{k2}"] = v2
        else:
            out[k] = v
    return out


def q(sf, soql):
    return [clean(r) for r in sf.query_all(soql)["records"]]


# ---------- tool implementations ----------
def search_records(sf, object, text):
    t = esc(text)
    where = {
        "Account": f"Name LIKE '%{t}%'",
        "Contact": f"Name LIKE '%{t}%' OR Email LIKE '%{t}%'",
        "Opportunity": f"Name LIKE '%{t}%'",
        "Task": f"Subject LIKE '%{t}%'",
    }[object]
    return q(sf, f"SELECT {FIELDS[object]} FROM {object} WHERE {where} LIMIT 25")


def get_record(sf, record_id):
    obj = object_of(record_id)
    rows = q(sf, f"SELECT {FIELDS[obj]} FROM {obj} WHERE Id = '{esc(record_id)}'")
    if not rows:
        return {"error": f"No {obj} with Id {record_id}"}
    return rows[0]


def get_related(sf, record_id):
    obj = object_of(record_id)
    rid = esc(record_id)
    out = {}
    if obj == "Account":
        out["contacts"] = q(sf, f"SELECT {FIELDS['Contact']} FROM Contact WHERE AccountId = '{rid}'")
        out["opportunities"] = q(sf, f"SELECT {FIELDS['Opportunity']} FROM Opportunity WHERE AccountId = '{rid}'")
    field = "WhoId" if obj == "Contact" else "WhatId"
    out["activities"] = q(sf, f"SELECT {FIELDS['Task']} FROM Task WHERE {field} = '{rid}' "
                              f"ORDER BY ActivityDate DESC")
    return out


def query_records(sf, soql):
    if not re.match(r"^\s*select\s", soql, re.I):
        return {"error": "Only SELECT queries are allowed."}
    res = sf.query_all(soql)
    rows = [clean(r) for r in res["records"]]
    if not rows and res.get("totalSize"):  # SELECT COUNT() returns only a total
        return {"count": res["totalSize"]}
    return {"total_rows": len(rows), "records": rows[:200]}


def create_record(sf, object, fields):
    res = getattr(sf, object).create(fields)
    return {"success": True, "id": res["id"]}


def update_record(sf, record_id, fields):
    getattr(sf, object_of(record_id)).update(record_id, fields)
    return {"success": True}


def delete_record(sf, record_id):
    getattr(sf, object_of(record_id)).delete(record_id)
    return {"success": True}


def merge_records(sf, master_id, duplicate_ids):
    obj = object_of(master_id)
    if obj not in ("Account", "Contact"):
        return {"error": "Only Accounts and Contacts can be merged."}
    dups = [d for d in duplicate_ids if d != master_id]
    if any(object_of(d) != obj for d in dups):
        return {"error": "All duplicates must be the same object type as the master."}
    moved = {"contacts": 0, "opportunities": 0, "activities": 0}
    for d in dups:
        rid = esc(d)
        if obj == "Account":
            for r in q(sf, f"SELECT Id FROM Contact WHERE AccountId = '{rid}'"):
                sf.Contact.update(r["Id"], {"AccountId": master_id}); moved["contacts"] += 1
            for r in q(sf, f"SELECT Id FROM Opportunity WHERE AccountId = '{rid}'"):
                sf.Opportunity.update(r["Id"], {"AccountId": master_id}); moved["opportunities"] += 1
            for r in q(sf, f"SELECT Id FROM Task WHERE WhatId = '{rid}'"):
                sf.Task.update(r["Id"], {"WhatId": master_id}); moved["activities"] += 1
        else:
            for r in q(sf, f"SELECT Id FROM Task WHERE WhoId = '{rid}'"):
                sf.Task.update(r["Id"], {"WhoId": master_id}); moved["activities"] += 1
        getattr(sf, obj).delete(d)
    return {"success": True, "master_id": master_id, "deleted": dups, "moved": moved}


IMPL = {"search_records": search_records, "get_record": get_record, "get_related": get_related,
        "query_records": query_records, "create_record": create_record, "update_record": update_record,
        "delete_record": delete_record, "merge_records": merge_records}
WRITE_TOOLS = {"create_record", "update_record", "delete_record", "merge_records"}


def execute(sf, name, args):
    """Run one tool call. Errors are returned to the model as text, never raised."""
    try:
        if name not in IMPL:
            raise ValueError(f"Unknown tool '{name}'")
        result = IMPL[name](sf, **(args or {}))
    except TypeError as e:
        result = {"error": f"Bad arguments: {e}"}
    except Exception as e:  # Salesforce errors come back to the agent so it can recover
        result = {"error": str(e)[:600]}
    text = json.dumps(result, default=str)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + '... [truncated]'
    return text
