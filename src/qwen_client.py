"""
qwen_client.py — Sentinel's single point of contact with Qwen Cloud.

THIS IS THE PROOF-OF-ALIBABA-CLOUD-DEPLOYMENT FILE for the hackathon submission:
it calls the Alibaba Cloud (Qwen Cloud / DashScope-intl) OpenAI-compatible endpoint.

Design goals:
  - One wrapper for the whole project. Everything else imports `chat()` / `embed()`.
  - Works in STUB mode with no API key (so we can build the entire system while
    hackathon credits are being verified), then switches to the real endpoint the
    instant QWEN_API_KEY is present. No other file changes.

Models (per Qwen Cloud model-selection docs):
  - qwen3.7-max    : complex reasoning / long-horizon agent decisions + consolidation
  - qwen3.6-flash  : cheap, fast first-pass / triage
  - qwen3.7-plus   : balanced (vision-capable, unused in the system-guardian build)
  - text-embedding-v4 : embeddings for the recall-memory tier
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Transient-failure retry policy for live API calls (see chat()).
MAX_RETRIES = int(os.getenv("QWEN_MAX_RETRIES", "3"))
RETRY_BACKOFF = float(os.getenv("QWEN_RETRY_BACKOFF", "1.0"))   # seconds, doubled each attempt

# --- Qwen Cloud (Alibaba Cloud) OpenAI-compatible endpoint -------------------
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
API_KEY = os.getenv("QWEN_API_KEY", "").strip()

MODEL_REASON = os.getenv("QWEN_MODEL_REASON", "qwen3.7-max")
MODEL_FAST = os.getenv("QWEN_MODEL_FAST", "qwen3.6-flash")
MODEL_EMBED = os.getenv("QWEN_MODEL_EMBED", "text-embedding-v4")

# STUB mode = no key yet. Lets us build/run the whole pipeline before credits land.
STUB = not API_KEY

_client = None
if not STUB:
    from openai import OpenAI

    _client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


def is_live() -> bool:
    """True when we are talking to the real Qwen Cloud endpoint."""
    return not STUB


def chat(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    tools: list[dict] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """
    Send a chat completion to Qwen Cloud and return a normalized dict:
        {"text": str, "tool_calls": [ {name, arguments(dict)} ], "raw": <sdk obj or None>}

    In STUB mode returns a deterministic placeholder so the agent loop runs end-to-end
    without credits. Swapping to live mode requires no caller changes.
    """
    model = model or MODEL_REASON

    if STUB:
        return _stub_chat(messages, tools)

    kwargs: dict[str, Any] = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if tools:
        kwargs["tools"] = tools

    # Retry transient failures (network blips, 429/5xx). Without this, a single hiccup at
    # dream time would silently fall back to the deterministic stub baseline and the
    # self-improvement loop would quietly stop using Qwen. Bounded, with backoff.
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = _client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message
            tool_calls = []
            for tc in (msg.tool_calls or []):
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {"_raw": tc.function.arguments}
                tool_calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
            return {"text": msg.content or "", "tool_calls": tool_calls, "raw": resp}
        except Exception as e:                      # noqa: BLE001 — any SDK/transport error
            last_err = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF * (2 ** attempt))

    # Exhausted retries: surface a clear, logged failure rather than silently degrading.
    print(f"[qwen_client] chat() failed after {MAX_RETRIES} attempts: "
          f"{type(last_err).__name__}: {last_err}", flush=True)
    return {"text": "", "tool_calls": [], "raw": None, "error": str(last_err)}


def embed(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    """Return an embedding vector per input string. STUB returns cheap hashed vectors."""
    model = model or MODEL_EMBED
    if STUB:
        return [_stub_embed(t) for t in texts]
    resp = _client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]


# --- Stubs (used only until QWEN_API_KEY is set) -----------------------------

def _stub_chat(messages, tools):
    """
    Offline stand-in for qwen3.7-max. Two modes:
      - SENTINEL_SIM=1 : heuristic that MIMICS real judgment (alert on unknown, trust
        learned-normal entities, always flag obvious threats). Lets us validate the
        learning-curve measurement before credits land. NOT used in the live submission.
      - default        : always picks the first tool (pure plumbing test).
    """
    last = messages[-1]["content"] if messages else ""
    if tools:
        if os.getenv("SENTINEL_SIM") == "1":
            return _sim_judgment(messages)
        first = tools[0]["function"]["name"]
        return {
            "text": "",
            "tool_calls": [{"id": "stub-0", "name": first, "arguments": {
                "reason": "STUB decision (no credits yet)",
            }}],
            "raw": None,
        }
    return {"text": f"[STUB reply] received {len(str(last))} chars.", "tool_calls": [], "raw": None}


def _sim_judgment(messages):
    """Heuristic stand-in for real reasoning, used only with SENTINEL_SIM=1."""
    text = messages[-1]["content"]
    # parse the event line and the known-normal set out of the assembled prompt
    new_event = text.split("=== NEW EVENT TO JUDGE ===")[-1]
    known_block = ""
    if "KNOWN-NORMAL ENTITIES" in text:
        known_block = text.split("KNOWN-NORMAL ENTITIES")[1].split("===")[1]

    entity = ""
    if "entity:" in new_event:
        entity = new_event.split("entity:")[-1].strip().splitlines()[0]

    # obvious threat: reverse-shell-ish high port to an unknown host
    if ":4444" in new_event or "reverse" in new_event.lower():
        return _tool("actuate", {"action": "kill_process", "target": entity or "unknown",
                                 "reason": "unknown host on suspicious high port 4444; not in baseline"})
    # learned-normal -> trust it
    if entity and entity in known_block:
        return _tool("mark_normal", {"reason": "matches learned baseline", "entity": entity})
    # unknown but benign-looking -> early caution (this is what consolidation later teaches away)
    return _tool("alert_user", {"severity": "low", "reason": "not yet in baseline; reviewing"})


def _tool(name, args):
    return {"text": "", "tool_calls": [{"id": "sim", "name": name, "arguments": args}], "raw": None}


def _stub_embed(text: str, dim: int = 64) -> list[float]:
    """Deterministic pseudo-embedding from a hash — good enough to test the recall plumbing."""
    import hashlib

    h = hashlib.sha256(text.encode()).digest()
    return [((h[i % len(h)] / 255.0) * 2 - 1) for i in range(dim)]


# --- Smoke test: `python src/qwen_client.py` ---------------------------------
if __name__ == "__main__":
    mode = "LIVE (Qwen Cloud)" if is_live() else "STUB (no QWEN_API_KEY yet)"
    print(f"Sentinel Qwen client — mode: {mode}")
    print(f"  endpoint : {BASE_URL}")
    print(f"  reason   : {MODEL_REASON}")
    r = chat([{"role": "user", "content": "Say 'Sentinel online' in three words."}])
    print(f"  chat     : {r['text']!r}")
    v = embed(["hello"])[0]
    print(f"  embed    : dim={len(v)} sample={v[:3]}")
