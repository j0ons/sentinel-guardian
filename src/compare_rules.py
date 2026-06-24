"""
compare_rules.py — Sentinel vs a static rule engine, on the same event stream.

The Impact case: a generic signature/rule engine (Suricata/CrowdSec-style) can only match what
it has a rule for. It has no memory of THIS host and cannot correlate events into a chain. So it
faces an unwinnable trade-off:
  - tight rules  -> misses the NOVEL kill-chain (no signature for port 8443) = false negative;
  - loose rules  -> fires on every unknown process/port = false-positive storm.

Sentinel reasons against a learned per-host baseline and CORRELATES events, so it does both:
clears host-routine activity AND catches the novel chain. This script makes that concrete.

It runs OFFLINE/deterministically (no API) — it compares the *detection logic*, using
Sentinel's real safety-floor + correlation rules from safety.py, against a representative
static ruleset. Run:  cd src && python compare_rules.py
"""
from __future__ import annotations

from safety import is_threat_port

# --- the shared event stream: a day on a home/lab host, ending in a novel intrusion ----------
# (kind, entity_key, port, external, label) where label tags which INCIDENT an event belongs to:
#   "benign" | "chain" (one intrusion across 3 events) | "revshell" (a classic signature threat)
# Scoring is per-INCIDENT: catching the chain at ANY step neutralizes it (1 threat, not 3).
STREAM = [
    ("process", "proc:pickup", None, False, "benign"),
    ("process", "proc:restic", None, False, "benign"),
    ("connection", "outbound:9000:10.10.10.50", 9000, False, "benign"),   # backup to NAS (odd port!)
    ("process", "proc:jellyfin-ffmpeg", None, False, "benign"),
    ("connection", "outbound:445:10.10.10.60", 445, False, "benign"),     # SMB to NAS
    ("login", "login:mohamed@10.10.10.2", None, False, "benign"),
    ("process", "proc:node_exporter", None, False, "benign"),
    ("connection", "outbound:8123:10.10.10.70", 8123, False, "benign"),   # home-assistant (odd port!)
    # --- the novel kill-chain: three steps, port 8443, NO known signature (ONE incident) ---
    ("process", "proc:dbus-daemon-helper", None, False, "chain"),         # masquerading process
    ("listen", "listen:0.0.0.0:8443", 8443, False, "chain"),              # opens a listener
    ("connection", "outbound:8443:203.0.113.66", 8443, True, "chain"),    # external egress
    # --- a classic known-signature threat (both should catch this) ---
    ("connection", "outbound:4444:185.220.101.5", 4444, True, "revshell"),# reverse shell
]
THREAT_INCIDENTS = {"chain", "revshell"}

KNOWN_BENIGN_PROCS = {"pickup", "restic", "jellyfin-ffmpeg", "node_exporter", "nginx", "sshd"}


def static_rules_tight(ev):
    """Signature engine, TIGHT: only flags known-bad ports. Misses anything novel."""
    kind, key, port, ext, _ = ev
    if port is not None and is_threat_port(port):
        return "alert"
    return "allow"


def static_rules_loose(ev):
    """Signature engine, LOOSE: flags any unknown process / any external egress / any new
    listener. Catches the novel chain but at the cost of alerting on normal host activity."""
    kind, key, port, ext, _ = ev
    if kind == "process":
        name = key.split(":", 1)[1]
        return "alert" if name not in KNOWN_BENIGN_PROCS else "allow"
    if kind == "listen":
        return "alert"
    if kind == "connection" and (ext or (port is not None and is_threat_port(port))):
        return "alert"
    if kind == "connection" and port not in (443, 80, 53):
        return "alert"            # any "unusual" port — the false-positive driver
    return "allow"


def sentinel(ev, recent):
    """Sentinel's logic: safety floor + per-host baseline + CORRELATION across recent events.
    Mirrors the deployed agent's decision rule (deterministic core, no API needed here)."""
    kind, key, port, ext, _ = ev
    # 1. deterministic safety floor — known attack signatures always caught
    if port is not None and is_threat_port(port):
        return "actuate"
    # 2. learned baseline — internal NAS/home-lab activity on this host is known-normal
    if not ext and (key in BASELINE or kind in ("login", "process") and _baseline_proc(key)):
        return "allow"
    # 3. correlation — is this part of a chain? (unknown proc -> new listener -> external egress)
    if _is_chain(ev, recent):
        return "actuate"
    # 4. external egress to an unknown destination → worth a look, not a false-positive storm
    if kind == "connection" and ext:
        return "alert"
    return "allow"


# Sentinel's learned baseline for THIS host (what the nightly dream would have promoted).
BASELINE = {"outbound:9000:10.10.10.50", "outbound:445:10.10.10.60",
            "outbound:8123:10.10.10.70", "login:mohamed@10.10.10.2"}


def _baseline_proc(key):
    return key.startswith("proc:") and key.split(":", 1)[1] in KNOWN_BENIGN_PROCS


def _is_chain(ev, recent):
    """A novel kill-chain = an unknown process AND a new listener AND external egress, all in
    the recent window. This is the correlation a stateless ruleset structurally cannot do."""
    kinds = {r[0] for r in recent} | {ev[0]}
    unknown_proc = any(r[0] == "process" and not _baseline_proc(r[1]) for r in recent + [ev])
    new_listener = "listen" in kinds
    ext_egress = any(r[0] == "connection" and r[3] for r in recent + [ev])
    return unknown_proc and new_listener and ext_egress


def score(decider, correlated=False):
    """Run the stream; score per-INCIDENT. Returns (false_positives, missed_incidents,
    caught_incidents, total_incidents). A threat incident counts as caught if ANY of its
    events is flagged (catching a kill-chain at one step neutralizes the whole intrusion)."""
    fp = 0
    flagged_incident = set()
    recent = []
    for ev in STREAM:
        label = ev[4]
        verdict = decider(ev, recent[-6:]) if correlated else decider(ev)
        flagged = verdict in ("alert", "actuate")
        if label in THREAT_INCIDENTS:
            if flagged: flagged_incident.add(label)
        elif flagged:
            fp += 1
        recent.append(ev)
    total = len(THREAT_INCIDENTS)
    caught = len(flagged_incident)
    return fp, total - caught, caught, total


def main():
    benign = sum(1 for e in STREAM if e[4] == "benign")
    print(f"Event stream: {len(STREAM)} events on a home/lab host — {benign} benign + "
          f"{len(THREAT_INCIDENTS)} threat incidents "
          f"(1 NOVEL kill-chain on :8443, 1 classic reverse shell on :4444)\n")
    rows = [
        ("Static rules (tight signatures)", score(static_rules_tight)),
        ("Static rules (loose heuristics)", score(static_rules_loose)),
        ("SENTINEL (baseline + correlation)", score(sentinel, correlated=True)),
    ]
    print(f"  {'detector':36} {'false+':>7} {'missed':>7} {'caught':>8}")
    print("  " + "-" * 62)
    for name, (fp, fn, caught, threats) in rows:
        print(f"  {name:36} {fp:>7} {fn:>7} {str(caught)+'/'+str(threats):>8}")
    print("\n  Tight rules: 0 false alarms but MISS the novel :8443 chain (no signature).")
    print("  Loose rules: catch more but storm false alarms on normal host activity.")
    print("  Sentinel: catches BOTH threats (incl. the novel chain it has no signature for)")
    print("  AND stays quiet on host-routine activity — because it learned this host and")
    print("  correlated the chain. That combination is what a stateless ruleset cannot do.")


if __name__ == "__main__":
    main()
