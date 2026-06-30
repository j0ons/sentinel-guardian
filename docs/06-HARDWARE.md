# Sentinel — Hardware (the physical edge device)

Sentinel runs on a **Raspberry Pi** as a true edge device: it perceives the host via sensors
and **acts locally on its own hardware** — a 3-LED + buzzer status head driven over GPIO. The
cloud reasons; the Pi signals the verdict physically, with no screen and no dependency on the
network being up.

## Bill of materials (minimal)

| Part | Qty | Notes |
|---|---|---|
| Raspberry Pi (any with the 40-pin header) | 1 | already owned |
| 5mm LED — green / amber(yellow) / red | 3 | status head |
| ~330 Ω resistor | 3 | one per LED |
| Active piezo buzzer (3.3 V) | 1 | pulses on threat |
| PIR motion sensor (HC-SR501) | 1 | physical perception — motion at the device |
| Reed/tamper switch (optional) | 1 | enclosure-opened detection |
| Breadboard + jumper wires | 1 | |

### Physical sensors (so Sentinel perceives the world, not just host telemetry)

| Sensor | GPIO (BCM) | Event it produces |
|---|---|---|
| PIR motion (HC-SR501 OUT) | GPIO 24 | `motion` — someone is physically at the device/rack |
| Tamper reed switch → GND | GPIO 25 | `tamper` — the enclosure was opened |

These feed the **same** perceive→reason→act loop (`edge/sensors.py` → `edge/runner.py`): a
`motion` event at 3 am on an unattended server is judged against the host's learned context by
qwen3.7-max, alongside the process/connection events. Physical + digital perception in one mind.
Test:  `cd edge && python3 sensors.py` (no-op off a Pi). The same agent that kills a reverse
shell can alert on someone opening the rack.

Even just the **red LED** alone is enough to demonstrate physical local actuation; the rest is polish.

## Wiring (BCM pin numbers)

```
 Pi GPIO (BCM)            Component
 ───────────────         ─────────────────────────────
 GPIO17  ──[330Ω]──►|──┐  GREEN  LED  (calm / normal)
 GPIO27  ──[330Ω]──►|──┤  AMBER  LED  (alert)
 GPIO22  ──[330Ω]──►|──┤  RED    LED  (threat / actuated)
 GPIO23  ───────────███─┤  BUZZER     (pulses on threat)
                       │
 GND  ─────────────────┘  common ground rail
```
LED long leg (anode) → resistor → GPIO; short leg (cathode) → GND. Buzzer + → GPIO23, − → GND.

## What each signal means (set in `edge/runner.py` → `apply_action`)

| Cloud decision | Physical signal | Meaning |
|---|---|---|
| `mark_normal` | green tick (0.15 s) | routine event, guardian alive & calm |
| `alert_user` | amber blink (0.6 s) | unusual — flagged for a human |
| `actuate` | **red LED 2 s + 3 buzzer pulses** | high-confidence threat, acted on locally |

## Bring-up

```bash
# on the Pi
./scripts/pi-setup.sh                 # installs psutil, requests, RPi.GPIO
cd edge && python3 gpio.py            # self-test: cycles green -> amber -> threat
# point at the cloud brain (Proxmox CT201 over tailnet, or the Mac):
SENTINEL_CLOUD=http://10.10.10.201:8000 python3 runner.py
```

## Graceful degradation (by construction)

`edge/gpio.py` imports `RPi.GPIO` lazily. Off a Pi (Mac, container, CI) **every signal is a
silent no-op** and the identical `runner.py` still runs — so development, testing, and the
container deployment are unaffected, and a GPIO fault can never crash the security agent
(`gpio.py` never raises). The buffer-and-replay logic (`outbox.jsonl`) means a weak or dropped
network delays cloud reasoning but the local red-LED/buzzer threat response and the audit
trail keep working. Perceive-and-act survives offline; only the cloud *reasoning* pauses.
```
```
