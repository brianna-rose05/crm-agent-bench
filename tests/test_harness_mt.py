import json, os, sys, types, csv, shutil
SCR = os.path.dirname(__file__); PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [PROJ, SCR]; os.chdir(PROJ)
from fake_sf import FakeSF
import tasks as TK
from datetime import date
sf = FakeSF()
sys.modules["sf_client"] = types.SimpleNamespace(connect=lambda: sf)
os.environ["OPENROUTER_API_KEY"] = "test"
import run_bench as RB
seen = {"sim_systems": []}

def tc(name, args, i):
    return {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}

def fake_chat(model, provider, messages, temperature, tools='AGENT'):
    if tools is None:  # simulated user
        sys_prompt = messages[0]["content"]; seen["sim_systems"].append(sys_prompt)
        assert "Acme - Maintenance Contract" in sys_prompt and "Hey, can you update the Acme deal" in sys_prompt
        assert messages[1]["role"] == "assistant"  # its own opening line
        n_agent = sum(m["role"] == "user" for m in messages)
        reply = {1: "the maintenance contract one, bump it to 50k", 2: "oh and push the close date to the end of next month",
                 3: "###DONE###"}[n_agent]
        return {"choices": [{"message": {"content": reply}}], "usage": {"cost": 0.0005}}
    users = [m["content"] for m in messages if m["role"] == "user"]
    tools_done = [m for m in messages if m["role"] == "tool"]
    last = messages[-1]
    r = lambda content=None, calls=None: {"choices": [{"message": {"content": content, **({"tool_calls": calls} if calls else {})}}],
                                         "usage": {"cost": 0.001}, "provider": "P"}
    if len(users) == 1:
        return r("Which Acme deal do you mean?")
    if len(users) == 2:
        if last["role"] == "user":
            return r(None, [tc("search_records", {"object": "Opportunity", "text": "maintenance"}, 1)])
        if last["role"] == "tool" and "Maintenance" in last["content"] and "success" not in last["content"]:
            oid = json.loads(last["content"])[0]["Id"]; seen["oid"] = oid
            return r(None, [tc("update_record", {"record_id": oid, "fields": {"Amount": 50000}}, 2)])
        return r("Updated the amount to $50,000.")
    if last["role"] == "user":
        return r(None, [tc("update_record", {"record_id": seen["oid"], "fields": {"CloseDate": TK.end_of_month(date.today(), 1)}}, 3)])
    return r("Close date moved to the end of next month.")

RB.chat = fake_chat
sys.argv = ["run_bench.py", "--models", "m/x", "--tasks", "19", "--out", "results/mt"]
RB.main()
row = list(csv.DictReader(open("results/mt/results.csv")))[0]
print(row["passed"], row["note"], "user_turns", row["user_turns"], "sim cost", row["user_sim_cost_usd"])
assert row["passed"] == "True" and row["user_turns"] == "3"
tr = json.load(open("results/mt/transcripts/m_x__task19__run1.json"))
assert len(tr["agent_replies"]) == 3
meta = json.load(open("results/mt/meta.json")); assert meta["user_model"] == "openai/gpt-6.1-sol"
shutil.rmtree("results/mt"); print("MULTI-TURN HARNESS TEST PASSED")
