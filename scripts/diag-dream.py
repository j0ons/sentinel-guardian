"""Read-only diagnostic: why does consolidate() fall back to (auto) on the production DB?

Reproduces the EXACT consolidate() chat call against the live DB, prints the prompt size and
the model's raw response, WITHOUT saving anything. Run on CT201:
    cd /root/sentinel/src && SENTINEL_SIM=0 /root/sentinel/.venv/bin/python ../scripts/diag-dream.py
"""
import os
os.environ.setdefault("SENTINEL_SIM", "0")

from memory import Memory
from consolidate import CONSOLIDATION_PROMPT
import qwen_client

DB = "/root/sentinel/data/sentinel.db"
m = Memory(db_path=DB)
host = "edge-0"

prev_version = m.baseline_version(host)
prev_baseline = m.current_baseline(host)
entities = m.db.execute(
    "SELECT name, kind, seen_count, normal FROM entities ORDER BY seen_count DESC").fetchall()
decisions = m.db.execute(
    "SELECT action, reason FROM decisions ORDER BY id DESC LIMIT 200").fetchall()

ent_lines = [f"  {r['name']} (x{r['seen_count']}, normal={r['normal']})" for r in entities]
dec_lines = [f"  {r['action']}: {r['reason']}" for r in decisions]
user = (f"PREVIOUS BASELINE (v{prev_version}):\n{prev_baseline}\n\n"
        f"ENTITIES SEEN ON THIS HOST:\n" + "\n".join(ent_lines) + "\n\n"
        f"TODAY'S DECISIONS:\n" + "\n".join(dec_lines) + "\n\nRewrite the baseline.")

print(f"is_live={qwen_client.is_live()}  prev_version={prev_version}")
print(f"entities={len(entities)}  decisions={len(decisions)}")
print(f"prompt chars: system={len(CONSOLIDATION_PROMPT)}  user={len(user)}  total≈{len(CONSOLIDATION_PROMPT)+len(user)}")

resp = qwen_client.chat(
    [{"role": "system", "content": CONSOLIDATION_PROMPT}, {"role": "user", "content": user}],
    max_tokens=1200)
text = (resp.get("text") or "").strip()
print(f"\nchat() error: {resp.get('error')}")
print(f"chat() text length: {len(text)}")
print(f"chat() tool_calls: {resp.get('tool_calls')}")
print(f"would hit stub branch? {(not text)}  (empty text => (auto) fallback)")
print("\n--- first 500 chars of model baseline ---")
print(text[:500] if text else "(EMPTY)")
