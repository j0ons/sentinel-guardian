"""
sensors.py — PHYSICAL edge sensors (Raspberry Pi GPIO). Sentinel doesn't just read host
telemetry — it perceives the physical world around the device.

A Track-5 EdgeAgent perceives via edge sensors. Sentinel's primary sensing is host activity
(processes/connections/logins — the "edge SOC sensor"), but the same agent also reads REAL
hardware inputs wired to the Pi and reasons about them in the same perceive→reason→act loop:

  - PIR motion sensor (GPIO 24)  -> a "motion" event: someone is physically at the device/rack.
  - tamper/door reed switch (GPIO 25) -> a "tamper" event: the enclosure was opened.

These cross the same wire as host events (compact JSON) and are judged by qwen3.7-max against
the host's learned context — e.g. "motion at 3am on an unattended server = investigate; motion
during a known admin SSH session = expected." Physical + digital perception in one mind.

Off a Pi (no RPi.GPIO), every read is a safe no-op returning no events, so the same edge runner
works on a Mac/container unchanged (graceful degradation by construction). Enable real sensing
by installing RPi.GPIO on the Pi and wiring the pins below.

Wiring (BCM):  PIR OUT -> GPIO 24 ;  reed switch -> GPIO 25 (to GND, internal pull-up).
"""
from __future__ import annotations

import time

PIN_PIR = 24        # PIR motion sensor output
PIN_TAMPER = 25     # tamper / door reed switch (closed = intact)

_GPIO = None
_READY = False
_state = {"motion": 0, "tamper_open": False}


def _init() -> bool:
    global _GPIO, _READY
    if _READY:
        return True
    try:
        import RPi.GPIO as GPIO
    except Exception:
        return False
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(PIN_PIR, GPIO.IN)
        GPIO.setup(PIN_TAMPER, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # closed=LOW=intact
        _GPIO = GPIO
        _READY = True
        return True
    except Exception:
        return False


def available() -> bool:
    """True if real GPIO sensors are active (running on a Pi with RPi.GPIO + wiring)."""
    return _init()


def poll() -> list[dict]:
    """Read the physical sensors and return any new events (edge-triggered). Off a Pi: [].

    Returns event dicts shaped like the host events the collector emits, so the runner can POST
    them on the same path:  {"kind","summary","detail"}.
    """
    if not _init():
        return []
    events = []
    try:
        # motion: rising edge (no motion -> motion)
        m = 1 if _GPIO.input(PIN_PIR) else 0
        if m and not _state["motion"]:
            events.append({"kind": "motion", "summary": "PIR motion detected at the device",
                           "detail": {"sensor": "pir", "pin": PIN_PIR, "ts": time.time()}})
        _state["motion"] = m
        # tamper: enclosure opened (reed switch goes HIGH when the magnet leaves)
        open_now = bool(_GPIO.input(PIN_TAMPER))
        if open_now and not _state["tamper_open"]:
            events.append({"kind": "tamper", "summary": "enclosure tamper switch OPENED",
                           "detail": {"sensor": "reed", "pin": PIN_TAMPER, "ts": time.time()}})
        _state["tamper_open"] = open_now
    except Exception:
        pass
    return events


if __name__ == "__main__":
    print(f"physical sensors available (real Pi GPIO): {available()}")
    if available():
        print("polling for 10s — wave at the PIR / open the tamper switch...")
        for _ in range(20):
            for e in poll():
                print("  EVENT:", e["summary"])
            time.sleep(0.5)
    else:
        print("(no Pi GPIO here — poll() returns [] as a safe no-op; runs anywhere)")
