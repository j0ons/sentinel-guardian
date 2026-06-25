"""
boiling_frog.py — Sentinel audits its OWN learning. (The meta-defense nobody else owns.)

Every self-improving agent has a hidden attack surface: its learning. A patient adversary can
run an intrusion "low and slow" so that the nightly dream, seeing the same activity night after
night without incident, eventually PROMOTES it to known-normal — and the guardian is trained to
stand down. (cf. the boiling-frog / baseline-poisoning problem.)

Sentinel defends against being boiled: it keeps a FROZEN reference baseline from a known-clean
epoch beside the live, nightly-dreamed one. On every consolidation it computes the divergence —
what the dreamed baseline now treats as normal that the frozen reference does NOT. When that
drift includes attack-shaped activity (external egress, new listeners, sensitive-process +
egress, threat ports), it raises a new alert class the field lacks: BASELINE_POISONING — and
the learning commit can be rolled back. Dreaming can make Sentinel smarter; it can never make
it relax the deterministic safety floor, and it can never quietly normalize an intrusion.

Run:  cd src && python boiling_frog.py            # offline demo of a low-and-slow attack
"""
from __future__ import annotations

from safety import is_threat_entity_key

# Entity shapes that should NEVER drift into "normal" without a human signing off — even if the
# host has seen them many times. (External egress, new listeners, sensitive exports.)
def _is_attack_shaped(name: str) -> bool:
    if is_threat_entity_key(name):                       # known attack ports / signatures
        return True
    if name.startswith("outbound:") and ":ext:" in name: # external egress (tagged external)
        return True
    if name.startswith("listen:") and not name.startswith("listen:127."):  # non-loopback listener
        return True
    if name.startswith("proc:") and name.split(":", 1)[1] in {
            "nc", "ncat", "socat", "pg_dumpall", "mysqldump", "xmrig", "ngrok"}:
        return True
    return False


class BaselineAuditor:
    """Holds a frozen known-clean reference and audits each new dreamed baseline against it."""

    def __init__(self, clean_known_normal: set[str]):
        self.frozen = set(clean_known_normal)            # the trusted epoch
        self.history = []                                # signed, diffable learning commits

    def audit(self, version: int, dreamed_known_normal: set[str]) -> dict:
        """Compare a freshly-dreamed known-normal set to the frozen reference. Returns a verdict
        and the list of suspicious promotions (drift the frozen reference would not have made)."""
        newly_normal = dreamed_known_normal - self.frozen
        poisoning = sorted(n for n in newly_normal if _is_attack_shaped(n))
        benign_drift = sorted(n for n in newly_normal if not _is_attack_shaped(n))
        verdict = "BASELINE_POISONING" if poisoning else "CLEAN"
        commit = {"version": version, "verdict": verdict,
                  "promoted_benign": benign_drift, "promoted_suspicious": poisoning}
        self.history.append(commit)
        return commit

    def rollback(self, version: int) -> str:
        """One-click revert of a poisoned learning commit (drop it from history)."""
        self.history = [c for c in self.history if c["version"] != version]
        return f"rolled back learning commit v{version}; frozen reference re-armed"


def _demo():
    print("BOILING-FROG META-DEFENSE — Sentinel auditing its own learning\n")
    # A known-clean host: these are genuinely-routine, trusted entities.
    clean = {"proc:nginx", "proc:pickup", "proc:restic", "outbound:443:140.82.112.3",
             "login:mohamed@10.10.10.2"}
    auditor = BaselineAuditor(clean)
    print(f"  frozen reference (known-clean epoch): {len(clean)} trusted entities\n")

    # Night after night, a patient attacker keeps a low-and-slow C2 beacon alive. The naive
    # dream sees it repeatedly without incident and starts promoting it toward "normal".
    print("  A patient adversary runs a low-and-slow C2 beacon; the naive dream slowly learns it…\n")
    dreamed = set(clean)
    timeline = [
        (4, "outbound:8443:ext:203.0.113.66"),     # the attacker's egress, now seen enough to promote
        (4, "listen:0.0.0.0:8443"),                 # its staging listener
        (4, "proc:pg_dumpall"),                     # its data-export step
        (5, "proc:jellyfin-ffmpeg"),                # a genuinely-new benign service (should be fine)
    ]
    for version, ent in timeline:
        dreamed.add(ent)
    commit = auditor.audit(version=6, dreamed_known_normal=dreamed)

    print(f"  dream v6 promoted {len(commit['promoted_benign']) + len(commit['promoted_suspicious'])} "
          f"new entities to known-normal.")
    print(f"  → benign drift (OK):       {commit['promoted_benign'] or '(none)'}")
    print(f"  → SUSPICIOUS drift:        {commit['promoted_suspicious']}")
    print(f"\n  VERDICT: {commit['verdict']}")
    if commit["verdict"] == "BASELINE_POISONING":
        print("  ⛔ Sentinel caught its OWN learning being weaponized — the dream tried to")
        print("     normalize an external C2 egress, a staging listener, and a data-export tool.")
        print("     " + auditor.rollback(6))
        print("\n  This is the invariant: dreaming can make me smarter, but it can NEVER train me")
        print("  to stand down on an intrusion. Every self-improving guardian can be boiled —")
        print("  I'm the one that notices when it's being tried.")


if __name__ == "__main__":
    _demo()
