"""
consolidate.py — the "dreaming" loop. THIS IS THE NOVEL CORE.

Once per simulated night, qwen3.7-max reads the day's working memory and REWRITES the
host's "what is normal here" baseline, then promotes frequently-seen, non-alerted entities
to known-normal. The next day the agent reasons against a sharper baseline, so false alarms
fall. This self-improvement — memory reorganizing itself to make future decisions better —
is what needs the 1M context and is the thing other entries won't have.
"""

from __future__ import annotations

import time

from memory import Memory
from qwen_client import chat, is_live

CONSOLIDATION_PROMPT = """You are Sentinel's nightly consolidation process ("dreaming").
You are given: the previous baseline, the full list of entities seen on this host (with how
often each appeared and whether it was ever alerted on), and the day's decisions.

Write the host's behavioral baseline FRESH from the evidence: an analytical, operational
description of what is NORMAL on this host — the specific processes, ports, destinations, and
users that routinely appear and are benign, and WHY each is expected. Fold in anything seen
many times without incident. Be concrete and specific to the evidence below.

The "previous baseline" is given only for continuity — do NOT copy its wording or format. In
particular, NEVER prefix your answer with "Baseline vN (auto)" or restate a generic template:
that "(auto)" form is a placeholder used when no model was available, and echoing it back
defeats the purpose. Produce genuine analysis in your own words, grouped by category
(Processes / Ports / Destinations / Users / Notable patterns).

CRITICAL: NEVER add attack signatures to the normal baseline, no matter how often they were
seen. Connections to ephemeral high ports (4444, 1337, 31337…), known-bad destinations
(Tor exits), or reverse-shell/C2 patterns are NEVER normal — frequency does not make an
attack benign. The baseline must keep scrutinizing these. Repeated exposure to a threat is a
persistent attack, not a new normal.

Return ONLY the new baseline text (no preamble, no "Baseline vN" prefix)."""

# Entities carrying an attack-port signature must NEVER be auto-promoted to known-normal,
# however often seen — the deterministic safety floor for the dreaming pass, guarding against
# "seen-it-a-lot → trust-it" eroding threat sensitivity. Single source of truth in safety.py
# (position-aware: also catches listen:...:4444, which the old substring check missed).
from safety import is_threat_entity_key as _is_threat_entity  # noqa: E402


def consolidate(memory: Memory, host: str = "edge-0",
                promote_after: int = 3) -> dict:
    """Run one nightly consolidation pass. Returns a summary of what changed."""
    prev_version = memory.baseline_version(host)
    prev_baseline = memory.current_baseline(host)

    # gather the day's material
    entities = memory.db.execute(
        "SELECT name, kind, seen_count, normal FROM entities ORDER BY seen_count DESC"
    ).fetchall()
    decisions = memory.db.execute(
        "SELECT action, reason FROM decisions ORDER BY id DESC LIMIT 200"
    ).fetchall()

    ent_lines = [f"  {r['name']} (x{r['seen_count']}, normal={r['normal']})" for r in entities]
    dec_lines = [f"  {r['action']}: {r['reason']}" for r in decisions]

    # Strip any prior "(auto)" stub framing so the model never sees the placeholder format to
    # copy — early SIM-mode baselines were stubs and the model was parroting them back.
    prev_for_prompt = prev_baseline
    if "(auto)" in prev_for_prompt:
        prev_for_prompt = "(no prior model-written baseline — write the first one from the evidence)"

    user = (
        f"PREVIOUS BASELINE (v{prev_version}):\n{prev_for_prompt}\n\n"
        f"ENTITIES SEEN ON THIS HOST:\n" + "\n".join(ent_lines) + "\n\n"
        f"TODAY'S DECISIONS:\n" + "\n".join(dec_lines) + "\n\n"
        "Rewrite the baseline."
    )

    resp = chat(
        [{"role": "system", "content": CONSOLIDATION_PROMPT},
         {"role": "user", "content": user}],
        max_tokens=1200,
    )
    new_baseline = resp.get("text", "").strip()

    if not new_baseline or not is_live():
        # STUB / empty: synthesize a deterministic baseline so the loop is testable offline.
        frequent = [r["name"] for r in entities
                    if r["seen_count"] >= promote_after and not _is_threat_entity(r["name"])]
        new_baseline = (
            f"Baseline v{prev_version + 1} (auto). Routinely-seen, benign on this host: "
            + (", ".join(frequent) if frequent else "(still learning)")
            + ". Treat these as normal; scrutinize anything outside this set."
        )

    new_version = prev_version + 1
    memory.save_baseline(new_version, new_baseline, host)

    # promote frequently-seen, never-alerted entities to known-normal — but NEVER promote a
    # threat-signature entity, however often it appears (the safety floor).
    promoted = 0
    for r in entities:
        if _is_threat_entity(r["name"]):
            continue
        if r["seen_count"] >= promote_after and not r["normal"]:
            memory.db.execute("UPDATE entities SET normal=1 WHERE name=?", (r["name"],))
            promoted += 1
    memory.db.commit()

    return {
        "version": new_version,
        "promoted": promoted,
        "baseline_preview": new_baseline[:160],
        "live": is_live(),
        "ts": time.time(),
    }


if __name__ == "__main__":
    import time as _t
    from memory import Event

    mem = Memory(db_path=":memory:", archive_path="/tmp/sentinel_consol_test.jsonl")
    # seed a few repeated benign entities
    for i in range(5):
        e = Event(ts=_t.time(), kind="connection", summary="outbound 443 -> api.github.com",
                  detail={"ip": "140.82.112.3", "port": 443})
        mem.record_event(e)
        mem.touch_entity("outbound:443:140.82.112.3", "connection", _t.time())
    out = consolidate(mem)
    print("consolidation:", out)
    print("known-normal now:", mem.known_normal_entities())
