"""End-to-end harness test: fake Salesforce + a scripted 'model' standing in for OpenRouter."""
import json, os, shutil, sys, types
from pathlib import Path

SCR = os.path.dirname(__file__)
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [PROJ, SCR]
os.chdir(PROJ)
from fake_sf import FakeSF

sf = FakeSF()
sys.modules["sf_client"] = types.SimpleNamespace(connect=lambda: sf)
os.environ["OPENROUTER_API_KEY"] = "test"
import run_bench as RB

calls = {"n": 0}


def tool_call(name, args, i):
    return {"id": f"call_{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def fake_chat(model, provider, messages, temperature, tools=None):
    """Behaves like a model: reads tool results from the conversation to decide the next step."""
    calls["n"] += 1
    assert messages[0]["role"] == "system" and "Today is" in messages[0]["content"]
    user = messages[1]["content"]
    tool_msgs = [m for m in messages if m["role"] == "tool"]
    usage = {"usage": {"cost": 0.0012}, "provider": provider or "FakeProvider"}

    def reply(content=None, calls_=None):
        msg = {"role": "assistant", "content": content}
        if calls_:
            msg["tool_calls"] = calls_
        return {"choices": [{"message": msg}], **usage}

    if "Northwind renewal" in user:
        if len(tool_msgs) == 0:
            return reply(None, [tool_call("search_records", {"object": "Opportunity", "text": "northwind"}, 1)])
        if len(tool_msgs) == 1:
            opps = json.loads(tool_msgs[0]["content"])
            oid = next(o["Id"] for o in opps if o["Name"] == "Northwind - 2027 Renewal")
            return reply(None, [
                tool_call("update_record", {"record_id": oid, "fields": {"StageName": "Negotiation/Review"}}, 2),
                tool_call("create_record", {"object": "Task", "fields": {
                    "Subject": "Pricing sent", "Status": "Completed", "WhatId": oid}}, 3)])
        return reply("Moved the renewal to Negotiation/Review and logged that pricing was sent.")
    if "Wayne" in user:
        if len(tool_msgs) == 0:
            return reply(None, [tool_call("search_records", {"object": "Task", "text": "Lucius"}, 1)])
        return reply("Legal finished the security addendum review with two redlines; target signing end of month.")
    if "Initech" in user:  # malformed arguments, then gives up -> tests error handling and max steps
        return reply(None, [{"id": "bad", "type": "function", "function": {"name": "get_record", "arguments": "{not json"}}])
    return reply("I'm not sure.")


RB.chat = fake_chat
sys.argv = ["run_bench.py", "--models", "test/model-a", "test/model-b@SomeHost", "--tasks", "7", "18", "10",
            "--runs", "2", "--max-steps", "3"]
before = set(Path("results").glob("*")) if Path("results").exists() else set()
RB.main()
new = sorted(set(Path("results").glob("*")) - before)
assert len(new) == 1
out = new[0]
rows = list(__import__("csv").DictReader(open(out / "results.csv")))
assert len(rows) == 2 * 2 * 3, len(rows)
by = {(r["model"], r["task"]): r for r in rows}
assert by[("test/model-a", "7")]["passed"] == "True"
assert by[("test/model-a", "18")]["passed"] == "True"
assert by[("test/model-a", "10")]["stopped"].startswith("hit max steps") and by[("test/model-a", "10")]["passed"] == "False"
assert by[("test/model-b@SomeHost", "7")]["providers"] == "SomeHost"
meta = json.load(open(out / "meta.json"))
assert meta["providers_seen"]["test/model-b@SomeHost"] == ["SomeHost"]
tr = json.load(open(out / "transcripts" / "test_model-a__task07__run1.json"))
assert any(m["role"] == "tool" for m in tr["messages"])
bad = json.load(open(out / "transcripts" / "test_model-a__task10__run1.json"))
assert "not valid JSON" in bad["tool_calls"][0]["output"]
print("\nHARNESS TEST PASSED;", calls["n"], "model calls; Salesforce calls:", sf.calls)
shutil.rmtree(out)
if not any(Path("results").iterdir()):
    Path("results").rmdir()
