"""In-memory stand-in for simple_salesforce with a small SOQL subset, for offline testing."""
import itertools
import re

PREFIX = {"Account": "001", "Contact": "003", "Opportunity": "006", "Task": "00T", "Event": "00U", "Note": "002"}
FIELDS = {"Account": ["Benchmark_ID__c", "BillingStateCode"], "Contact": ["Benchmark_ID__c"],
          "Opportunity": ["Benchmark_ID__c", "Sales_Rep__c"], "Task": ["Benchmark_ID__c", "Sales_Rep__c"]}
STATE_NAMES = {"IL": "Illinois"}


class SFError(Exception):
    pass


STAGE_PROB = {"Prospecting": 10, "Qualification": 10, "Needs Analysis": 20, "Value Proposition": 50,
              "Id. Decision Makers": 60, "Perception Analysis": 70, "Proposal/Price Quote": 75,
              "Negotiation/Review": 90, "Closed Won": 100, "Closed Lost": 0}


def opp_rules(rec, fields, today):
    """Mimic Salesforce (verified on a real org): stage sets default probability unless Probability is in the
    same update; closing pulls a future close date to today; reopening keeps the date."""
    if "StageName" in fields:
        if "Probability" not in fields:
            rec["Probability"] = float(STAGE_PROB[fields["StageName"]])
        # Verified: Closed Won pulls a future close date to today; Closed Lost leaves it alone.
        if fields["StageName"] == "Closed Won" and "CloseDate" not in fields and rec.get("CloseDate", "") > today:
            rec["CloseDate"] = today


class Handle:
    def __init__(self, sf, name):
        self.sf, self.name = sf, name

    def describe(self):
        return {"fields": [{"name": f} for f in FIELDS.get(self.name, []) + ["Id", "Name"]]}

    def create(self, fields):
        return {"id": self.sf._insert(self.name, fields), "success": True}

    def update(self, rid, fields):
        if rid not in self.sf.db[self.name]:
            raise SFError(f"ENTITY_IS_DELETED or not found: {rid}")
        rec = self.sf.db[self.name][rid]
        rec.update(fields)
        if self.name == "Opportunity":
            import datetime
            opp_rules(rec, fields, datetime.date.today().isoformat())
        return 204

    def delete(self, rid):
        if rid not in self.sf.db[self.name]:
            raise SFError(f"not found: {rid}")
        self.sf._delete(rid)
        return 204


class FakeSF:
    sf_instance = "fake.my.salesforce.com"

    def __init__(self):
        self.db = {o: {} for o in PREFIX}
        self.n = itertools.count(1)
        self.calls = 0

    def __getattr__(self, name):
        if name in PREFIX:
            return Handle(self, name)
        raise AttributeError(name)

    def _insert(self, obj, fields):
        for k, v in fields.items():
            if k in ("AccountId", "WhatId", "WhoId") and v and not self._find(v):
                raise SFError(f"INVALID_CROSS_REFERENCE_KEY {k}={v}")
        rid = f"{PREFIX[obj]}{next(self.n):012d}AAA"
        rec = {"Id": rid, **fields}
        if obj == "Opportunity" and "Probability" not in fields:
            rec["Probability"] = float(STAGE_PROB[rec["StageName"]])
        if obj == "Account" and "BillingStateCode" in rec:
            rec["BillingState"] = STATE_NAMES.get(rec["BillingStateCode"], rec["BillingStateCode"])
        self.db[obj][rid] = rec
        return rid

    def _find(self, rid):
        for o in self.db:
            if rid in self.db[o]:
                return o, self.db[o][rid]
        return None

    def _delete(self, rid):
        obj, rec = self._find(rid)
        del self.db[obj][rid]
        if obj == "Account":  # cascade like Salesforce
            for o in ("Contact", "Opportunity"):
                for i in [i for i, r in self.db[o].items() if r.get("AccountId") == rid]:
                    self._delete(i)
        for i, t in list(self.db["Task"].items()):
            if t.get("WhatId") == rid or (t.get("WhoId") == rid and not t.get("WhatId")):
                self.db["Task"].pop(i, None)
            elif t.get("WhoId") == rid:
                t["WhoId"] = None

    # ----- REST composite (used by reset.py) -----
    def restful(self, path, params=None, method="GET", json=None, **kw):
        self.calls += 1
        if method == "DELETE":
            out = []
            for i in params["ids"].split(","):
                if self._find(i):
                    self._delete(i); out.append({"id": i, "success": True})
                else:
                    out.append({"id": i, "success": False, "errors": [{"statusCode": "ENTITY_IS_DELETED"}]})
            return out
        return [{"id": self._insert(r["attributes"]["type"], {k: v for k, v in r.items() if k != "attributes"}),
                 "success": True} for r in json["records"]]

    # ----- SOQL subset -----
    def _value(self, obj, rec, field):
        if field == "Name" and obj == "Contact":
            return f"{rec.get('FirstName') or ''} {rec.get('LastName') or ''}".strip()
        if field == "IsClosed":
            return (rec.get("StageName") or "").startswith("Closed")
        if "." in field:
            rel, sub = field.split(".", 1)
            target = self._find(rec.get(rel + "Id") or "")
            if not target:
                return None
            return self._value(target[0], target[1], sub)
        return rec.get(field)

    def _cond(self, obj, rec, field, op, raw):
        v = self._value(obj, rec, field)
        if raw.lower() == "null":
            lit = None
        elif raw.lower() in ("true", "false"):
            lit = raw.lower() == "true"
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            lit = raw
        elif raw.startswith("'"):
            lit = raw[1:-1].replace("\\'", "'").replace("\\\\", "\\")
        else:
            lit = float(raw)
        if op in ("LIKE", "NOT LIKE"):
            pat = "^" + re.escape(lit).replace("%", ".*").replace("_", ".") + "$"
            m = v is not None and re.match(pat, str(v), re.I | re.S) is not None
            return m if op == "LIKE" else not m
        if op == "=":
            return (v == lit) if not isinstance(lit, str) else (str(v).lower() == lit.lower() if v is not None else False)
        if op == "!=":
            return v != lit
        a, b = (v, lit) if not isinstance(lit, float) else (float(v or 0), lit)
        return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op] if v is not None else False

    def query(self, soql):
        self.calls += 1
        m = re.match(r"^\s*SELECT\s+(.+?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+?))?(?:\s+ORDER BY\s+([\w.]+)(\s+DESC|\s+ASC)?)?"
                     r"(?:\s+LIMIT\s+(\d+))?\s*$", soql, re.I | re.S)
        if not m:
            raise SFError(f"MALFORMED_QUERY (fake parser): {soql}")
        fields, obj, where, order, desc, limit = m.groups()
        rows = list(self.db[obj].values())
        if where:
            toks = re.findall(r"([\w.]+)\s*(NOT LIKE|LIKE|!=|<=|>=|=|<|>)\s*('(?:[^'\\]|\\.)*'|null|true|false|\d{4}-\d{2}-\d{2}|[\d.]+)"
                              r"\s*(AND|OR)?", where, re.I)
            def keep(r):
                result, conn = None, None
                for f, op, raw, nxt in toks:
                    val = self._cond(obj, r, f, op.upper(), raw)
                    result = val if result is None else (result and val if conn == "AND" else result or val)
                    conn = (nxt or "").upper()
                return result
            rows = [r for r in rows if keep(r)]
        if order:
            rows.sort(key=lambda r: str(self._value(obj, r, order) or ""), reverse=bool(desc and "DESC" in desc.upper()))
        if limit:
            rows = rows[:int(limit)]
        if fields.strip().upper() == "COUNT()":
            return {"totalSize": len(rows), "records": []}
        out = []
        for r in rows:
            rec = {"attributes": {"type": obj}}
            for f in [x.strip() for x in fields.split(",")]:
                if "." in f:
                    rel, sub = f.split(".", 1)
                    val = self._value(obj, r, f)
                    rec[rel] = None if val is None and not self._find(r.get(rel + "Id") or "") else {"Name": val}
                else:
                    rec[f] = self._value(obj, r, f)
            out.append(rec)
        return {"totalSize": len(out), "records": out}

    query_all = query
