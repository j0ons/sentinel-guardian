"""
fleet_mind.py — THE WINNING BET: one mind over the whole fleet.

Per-host, Sentinel correctly marks each of these as normal:
  host A: a new ssh source (valid creds)     host C: a first-ever :8443 listener
  host B: a first-time pg_dumpall            host F: a first external egress
Individually benign, on different hosts, days apart. No per-host detector — and no retriever —
can connect them.

The Fleet Mind runs once over the ENTIRE fleet's timeline held in qwen3.7-max's large context
and asks one question a stateless/retrieval system can't: "across ALL hosts and ALL days, is
there a single actor moving laterally?" When it finds the chain it raises a FLEET-level
intrusion that names the campaign, the hosts, and the order of compromise — and the nightly
dream then writes that pattern into EVERY host's baseline at once (one host's lesson immunizes
the fleet).

This is additive: it does NOT touch the per-host agent. It reads the shared event store the
schema already keys by `host`.

Run:  cd src && SENTINEL_SIM=0 python fleet_mind.py            # over whatever is in the DB
      cd src && SENTINEL_SIM=0 python fleet_mind.py --demo     # seed a staged fleet + run
"""
from __future__ import annotations

import os
import sys
import time

from memory import Event, Memory
from qwen_client import chat, is_live

# Reuse the per-event safety-floor vocabulary so fleet reasoning is consistent with the agent.
FLEET_PROMPT = """You are Sentinel's FLEET MIND — a cross-host threat correlator. You are given the
recent security-event timeline of an ENTIRE fleet of hosts (each event tagged with its host and
time). Each event has already been judged benign ON ITS OWN HOST.

Your job is the one thing a per-host monitor cannot do: look ACROSS hosts and time for a SINGLE
actor moving laterally — an APT campaign whose individual steps are each unremarkable but which
together form an intrusion (e.g. a new external login on one host, then a first-time data-export
process on another, then a new listener on a third, then a first external egress on a fourth —
classic recon -> collection -> staging -> exfil across machines).

Respond in this exact format:
VERDICT: <CLEAR | CAMPAIGN_DETECTED>
If CAMPAIGN_DETECTED, then:
ACTOR: <one-line description of the inferred actor/campaign>
CHAIN: <host:step -> host:step -> ...> (the ordered cross-host kill-chain you found)
WHY: <why these specific events are one campaign and not coincidence>
Be precise and only raise CAMPAIGN_DETECTED if the cross-host pattern is genuinely an intrusion."""


def assemble_fleet_timeline(mem: Memory, max_events: int = 5000, token_budget: int = 200_000) -> tuple[str, int, set]:
    """The full fleet history in one block, budgeted for large context. Returns (text, n, hosts)."""
    events = mem.recent_events(limit=max_events)        # already across all hosts
    char_budget = token_budget * 4
    kept, used = [], 0
    for e in reversed(events):
        line = f"[{time.strftime('%m-%d %H:%M', time.localtime(e.ts))}] [{e.host}] {e.to_text()}"
        if used + len(line) > char_budget:
            break
        kept.append((line, e.host)); used += len(line)
    kept.reverse()
    hosts = {h for _, h in kept}
    body = "\n".join(l for l, _ in kept)
    return body, len(kept), hosts


def run_fleet_mind(mem: Memory) -> dict:
    body, n, hosts = assemble_fleet_timeline(mem)
    if not n:
        return {"verdict": "CLEAR", "n_events": 0, "hosts": []}
    user = (f"FLEET: {len(hosts)} hosts. TIMELINE ({n} events across the fleet):\n{body}\n\n"
            "Correlate across hosts. Is there a single actor moving laterally?")
    resp = chat([{"role": "system", "content": FLEET_PROMPT},
                 {"role": "user", "content": user}], max_tokens=600)
    text = (resp.get("text") or "").strip()
    detected = "CAMPAIGN_DETECTED" in text.upper()
    return {"verdict": "CAMPAIGN_DETECTED" if detected else "CLEAR",
            "n_events": n, "hosts": sorted(hosts), "report": text, "live": is_live()}


# --- staged demo: a low-and-slow lateral campaign hidden in fleet noise ----------------------
def seed_demo_fleet(mem: Memory):
    hosts = ["web-01", "db-02", "ci-03", "nas-04", "app-05"]
    now = time.time()
    day = 86400
    # noise: routine activity on each host
    routine = ["cron job ran", "backup completed", "health probe", "metrics scrape",
               "cert check", "log rotation", "package refresh", "session opened"]
    for d in range(6):
        for h in hosts:
            for i in range(6):
                mem.record_event(Event(ts=now - (6 - d) * day + i * 600, kind="process",
                                       summary=f"{routine[i % len(routine)]}", host=h), embed_now=False)
    # the 4 needles, scattered across hosts and days (each benign on its own host):
    mem.record_event(Event(ts=now - 5 * day, kind="login",
                           summary="ssh login from 10.0.0.9 (new external source, valid creds)", host="web-01"), embed_now=False)
    mem.record_event(Event(ts=now - 3 * day, kind="process",
                           summary="new process started: pg_dumpall (first time on this host)", host="db-02"), embed_now=False)
    mem.record_event(Event(ts=now - 2 * day, kind="listen",
                           summary="new listening port 0.0.0.0:8443 (first ever on this host)", host="ci-03"), embed_now=False)
    mem.record_event(Event(ts=now - 1 * day, kind="connection",
                           summary="new outbound connection 203.0.113.66:8443 (first external egress)", host="nas-04"), embed_now=False)


def main():
    demo = "--demo" in sys.argv
    mem = Memory(db_path=":memory:", archive_path="/tmp/fleet_mind.jsonl") if demo \
        else Memory()
    if demo:
        print("Seeding a staged fleet (5 hosts, 6 days of noise + a hidden 4-step lateral APT)…")
        seed_demo_fleet(mem)
    mode = "LIVE qwen3.7-max" if is_live() else "STUB"
    print(f"\nFLEET MIND — correlating the whole fleet in one context — mode: {mode}\n")
    out = run_fleet_mind(mem)
    print(f"  reasoned over {out['n_events']} events across {len(out['hosts'])} hosts: "
          f"{', '.join(out['hosts'])}")
    print(f"\n  VERDICT: {out['verdict']}")
    if out.get("report"):
        print("\n  --- fleet mind report ---")
        for line in out["report"].splitlines():
            print("  " + line)


if __name__ == "__main__":
    main()
