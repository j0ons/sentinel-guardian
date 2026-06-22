# Sentinel — Privacy & Data Handling

Sentinel guards a host by watching its most sensitive signals — processes, network
connections, logins. Privacy is therefore a design constraint, not an afterthought. This
documents what data exists, where it goes, and what deliberately never leaves the device.

## Principle: minimize what crosses the wire

The edge perceives rich state but **emits only compact, derived events** — never raw streams.

| Data | Stays on edge | Sent to cloud |
|---|---|---|
| Full process table, memory/CPU, raw socket lists | ✅ (in-memory only, per snapshot) | ❌ |
| Raw packet/payload capture | ✅ never captured at all | ❌ |
| A *change* (new process name, new `ip:port`, new login user) | — | ✅ as one small JSON line |

Perception is **change-driven** (`collectors.diff_events`): an idle host sends almost
nothing. There is no video, no audio, no file contents, no keystrokes — by design. The cloud
reasons over short event summaries like `new outbound connection 10.10.10.50:9000`, not over
the host's raw state.

## Transport & exposure

- **Edge → cloud** is a simple authenticated HTTPS POST of the event JSON.
- The live dashboard and cloud API are published **Tailscale-only** (tailnet, WireGuard),
  **not** a public Funnel — reachable from the owner's own devices, never the open internet.
  (`deploy/serve-dashboard.sh` uses `tailscale serve`, explicitly not `tailscale funnel`.)
- No third party but the model endpoint sees any event; the model call is the only egress.

## Data at rest & retention

- **Recall tier** — SQLite on the cloud node holds entities, baselines, and decisions. It is
  derived metadata (entity keys like `proc:restic`, `outbound:9000:10.10.10.50`), not raw host
  data.
- **Archival tier** — an append-only JSONL audit trail. Relocatable / scopable via
  `SENTINEL_DATA_DIR` so an operator controls exactly where history lives (e.g. an encrypted
  volume). Self-hostable end to end — the entire stack runs on hardware the owner controls.
- **Secrets** — the Qwen API key lives only in `.env` (gitignored, `chmod 600`); it is never
  committed, logged, or sent to the edge.

## Local autonomy = privacy under weak/no network

Because actuation can happen **on the device** (GPIO threat signal; armed kill/block), the
most security-critical response does **not** depend on the cloud or even the network being up.
Events that can't be sent are **buffered to disk** (`outbox.jsonl`) and replayed on reconnect —
so a degraded link delays cloud reasoning but never leaks data and never drops the audit trail.

## What we deliberately did NOT build

- No cloud account, no telemetry to us, no analytics SDK.
- No raw-data exfiltration path — the wire format is incapable of carrying payloads.
- No public exposure — tailnet-only by default.

The result: a guardian that sees everything locally, but whose *footprint off the device* is a
thin stream of derived security events to a single model endpoint the owner chose.
