"""
gpio.py — Sentinel's PHYSICAL actuation layer (Raspberry Pi).

This is what makes Sentinel a real edge *device* and not just edge software: when the cloud
brain returns a decision, the Pi acts on its own hardware — LEDs and a buzzer — so the
host's security state is visible and audible AT THE DEVICE, with no screen and no network.

Wiring (BCM pin numbers, all via a ~330Ω resistor to the LED, buzzer to GND):
    GPIO 17  -> GREEN LED   (calm / system alive)
    GPIO 27  -> AMBER LED   (alert — unusual, human review)
    GPIO 22  -> RED LED     (threat — actuated)
    GPIO 23  -> BUZZER      (active piezo; pulses on threat)

Design goals:
  * Zero-dependency import. Off a Pi (Mac, container, CI) every function is a safe no-op, so
    the same edge/runner.py runs everywhere unchanged — graceful degradation by construction.
  * Never raises. A GPIO glitch must never take down the security agent.

Enable real output by installing RPi.GPIO on the Pi; nothing else changes.
"""

from __future__ import annotations

import threading
import time

# Pin map (BCM)
PIN_GREEN = 17
PIN_AMBER = 27
PIN_RED = 22
PIN_BUZZER = 23

_GPIO = None          # the RPi.GPIO module, if present
_READY = False        # True once pins are configured on a real Pi


def _init() -> bool:
    """Try to bring up real GPIO. Returns True on a Pi with RPi.GPIO, else False (no-op mode)."""
    global _GPIO, _READY
    if _READY:
        return True
    try:
        import RPi.GPIO as GPIO            # only present on a Raspberry Pi
    except Exception:
        return False                       # not a Pi → stay in no-op mode, silently
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for pin in (PIN_GREEN, PIN_AMBER, PIN_RED, PIN_BUZZER):
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        _GPIO = GPIO
        _READY = True
        return True
    except Exception:
        return False


def _pulse(pin: int, secs: float):
    """Drive a pin HIGH for secs then LOW, in a background thread so we never block the loop."""
    if not _init():
        return
    def _run():
        try:
            _GPIO.output(pin, _GPIO.HIGH)
            time.sleep(secs)
            _GPIO.output(pin, _GPIO.LOW)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


# --- the three signals apply_action() calls --------------------------------

def heartbeat_ok():
    """Brief green tick — a routine event was judged normal; the guardian is alive and calm."""
    _pulse(PIN_GREEN, 0.15)


def alert():
    """Amber blink — something unusual; flagged for a human."""
    _pulse(PIN_AMBER, 0.6)


def threat():
    """Red LED + buzzer — a high-confidence threat was actuated. Visible and audible locally."""
    _pulse(PIN_RED, 2.0)
    for _ in range(3):                      # three short buzzer pulses
        _pulse(PIN_BUZZER, 0.12)
        time.sleep(0.18)


def cleanup():
    """Release the GPIO pins on shutdown (no-op off a Pi)."""
    if _READY and _GPIO is not None:
        try:
            _GPIO.cleanup()
        except Exception:
            pass


def available() -> bool:
    """True if real GPIO output is active (running on a Pi with RPi.GPIO)."""
    return _init()


if __name__ == "__main__":
    # Self-test: cycle the signals. On a Pi the LEDs/buzzer fire; elsewhere it just prints.
    print(f"gpio available (real Pi output): {available()}")
    for name, fn in (("heartbeat_ok", heartbeat_ok), ("alert", alert), ("threat", threat)):
        print(f"  -> {name}()")
        fn()
        time.sleep(1.2)
    cleanup()
    print("done.")
