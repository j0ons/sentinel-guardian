"""
test_safety.py — proves the deterministic safety floor catches a threat port across EVERY
event-key shape. Regression guard for the bug where listen:...:4444 silently bypassed the
floor (substring ':4444:' never matched a key ending in the port).

Run:  cd src && python test_safety.py
"""
from safety import (event_is_threat_signature, is_threat_entity_key,
                    is_threat_port, THREAT_PORTS)

THREAT = 4444
SAFE = 9000

# Every entity-key SHAPE the system actually produces, on a threat port — all must match.
THREAT_KEYS = [
    f"outbound:{THREAT}:185.220.101.5",   # connection key (port mid-string)
    f"listen:0.0.0.0:{THREAT}",           # listen key (port at END — the bug)
    f"listen:127.0.0.1:{THREAT}",
    f"outbound:{THREAT}:10.0.0.1",
]
# Keys that must NOT trip the floor (benign ports / partial matches).
SAFE_KEYS = [
    f"outbound:{SAFE}:10.10.10.50",
    "proc:restic",
    "outbound:14444:1.2.3.4",             # 14444 contains 4444 — must NOT match
    "listen:0.0.0.0:44440",               # 44440 contains 4444 — must NOT match
    "login:mohamed@10.10.10.2",
]


def main():
    fails = 0
    for k in THREAT_KEYS:
        if not is_threat_entity_key(k):
            print(f"  FAIL: threat key NOT caught: {k}"); fails += 1
    for k in SAFE_KEYS:
        if is_threat_entity_key(k):
            print(f"  FAIL: safe key wrongly flagged: {k}"); fails += 1
    # structured-port path
    assert is_threat_port(4444) and is_threat_port("1337") and not is_threat_port(9000)
    assert not is_threat_port(None) and not is_threat_port("x")
    # combined check prefers structured detail
    assert event_is_threat_signature({"port": 4444}, "anything")
    assert event_is_threat_signature({"port": 9000}, "listen:0.0.0.0:4444")  # key still catches
    assert not event_is_threat_signature({"port": 9000}, "outbound:9000:1.2.3.4")

    if fails:
        print(f"\n{fails} FAILURES"); raise SystemExit(1)
    print(f"OK — safety floor catches all {len(THREAT_KEYS)} threat-key shapes "
          f"(incl. listen-at-end), rejects all {len(SAFE_KEYS)} benign/partial-match keys. "
          f"Threat ports: {sorted(THREAT_PORTS)}")


if __name__ == "__main__":
    main()
