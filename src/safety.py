"""
safety.py — the deterministic safety floor, in ONE place.

A single source of truth for "this entity carries a known attack-port signature", used by
both the agent (never fast-path / never ignore it) and consolidation (never promote it to
known-normal). Previously this logic was duplicated in agent.py and consolidate.py with a
fragile `":4444:" in key` substring check — which silently FAILED for listen-port entities
whose keys END in the port (e.g. `listen:0.0.0.0:4444`, no trailing colon), letting a
bind-shell backdoor on exactly the "protected" ports slip through the floor.

We match the port by POSITION (bounded by ':' or end-of-string), and — preferably — against
the structured port from event.detail, not a substring of the key.
"""

from __future__ import annotations

import re

# Ephemeral/uncommon ports strongly associated with reverse shells / C2 / bind shells.
THREAT_PORTS = frozenset({4444, 1337, 31337, 5555, 6667})

# Match a threat port as a whole field in an entity key: preceded by ':' and followed by ':'
# or end-of-string. Works for connection keys ('outbound:4444:1.2.3.4') AND listen keys
# ('listen:0.0.0.0:4444'). The old ':4444:'-substring check missed the latter entirely.
_THREAT_KEY_RE = re.compile(r":(?:" + "|".join(str(p) for p in sorted(THREAT_PORTS)) + r")(?::|$)")


def is_threat_port(port) -> bool:
    """True if a structured port value is a known attack-port signature. Prefer this."""
    try:
        return int(port) in THREAT_PORTS
    except (TypeError, ValueError):
        return False


def is_threat_entity_key(key: str) -> bool:
    """True if an entity key contains a threat port as a bounded field (position-aware).
    Use when only the canonical key string is available (e.g. the consolidation loop)."""
    return bool(key) and bool(_THREAT_KEY_RE.search(key))


def event_is_threat_signature(detail: dict | None, entity_key: str | None) -> bool:
    """Combined check: structured port first (authoritative), key-pattern as fallback."""
    if detail and is_threat_port(detail.get("port")):
        return True
    return bool(entity_key) and is_threat_entity_key(entity_key)
