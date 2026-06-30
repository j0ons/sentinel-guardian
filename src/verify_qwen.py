"""
verify_qwen.py — prove this project really runs on Qwen Cloud (anyone can re-run it).

Makes one live call to the dashscope-intl endpoint with the project's configured model and
prints the full evidence: the endpoint, the model id requested, the model id the server echoes
back, the response, and token usage. A judge can run this to confirm the proof-of-deployment
is real — or read docs/proof-of-qwen.txt for a captured run.

Run:  cd src && SENTINEL_SIM=0 python verify_qwen.py
"""
from __future__ import annotations

import os
import time

from qwen_client import API_KEY, BASE_URL, MODEL_REASON, MODEL_FAST


def main():
    from openai import OpenAI
    if not API_KEY:
        print("No QWEN_API_KEY set — put it in .env. (This is the proof-of-deployment check.)")
        return
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=20)
    print("=" * 64)
    print("PROOF OF QWEN CLOUD DEPLOYMENT")
    print("=" * 64)
    print(f"endpoint : {BASE_URL}")
    print(f"models   : reason={MODEL_REASON}  fast={MODEL_FAST}")
    print(f"time     : {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("-" * 64)
    for label, model in (("reasoning", MODEL_REASON), ("triage", MODEL_FAST)):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "In one short sentence, what are you?"}],
                max_tokens=40)
            print(f"[{label}] requested model : {model}")
            print(f"[{label}] server echoed    : {r.model}")
            print(f"[{label}] response         : {r.choices[0].message.content.strip()}")
            if r.usage:
                print(f"[{label}] tokens           : prompt={r.usage.prompt_tokens} "
                      f"completion={r.usage.completion_tokens}")
        except Exception as e:
            print(f"[{label}] FAILED: {type(e).__name__}: {str(e)[:90]}")
        print("-" * 64)
    print("If the 'server echoed' model matches and a response came back, this project is "
          "genuinely calling Qwen on Alibaba Cloud. Re-run any time.")


if __name__ == "__main__":
    main()
