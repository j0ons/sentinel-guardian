#!/usr/bin/env bash
# Place the Qwen/DashScope API key into the project .env and verify a LIVE connection.
# The key is read from your terminal (hidden input) — it is never echoed or stored in shell history.
#
# Usage:  ./scripts/set-key.sh
set -e
cd "$(dirname "$0")/.."

printf "Paste your DashScope sk-... key (input hidden), then Enter: "
read -rs KEY
echo

if [[ -z "$KEY" ]]; then echo "No key entered. Aborting."; exit 1; fi
if [[ "$KEY" != sk-* ]]; then
  echo "Warning: key does not start with 'sk-'. Continuing anyway."
fi

# Write .env at repo root (gitignored). Preserve any other vars already there.
touch .env
# strip any existing QWEN_API_KEY line, then append the new one
grep -v '^QWEN_API_KEY=' .env > .env.tmp 2>/dev/null || true
mv .env.tmp .env
echo "QWEN_API_KEY=$KEY" >> .env
chmod 600 .env
echo "✓ Wrote QWEN_API_KEY to $(pwd)/.env (perms 600, gitignored)"

echo
echo "Verifying LIVE connection to qwen3.7-max ..."
source .venv/bin/activate
cd src
# is_live() returns true when QWEN_API_KEY is set; a tiny call confirms the endpoint+credit.
python - <<'PY'
from qwen_client import is_live, MODEL_REASON, BASE_URL
print("base_url:", BASE_URL)
print("model   :", MODEL_REASON)
print("is_live :", is_live())
if not is_live():
    raise SystemExit("Key not detected by client — check .env")
try:
    from openai import OpenAI
    import os
    c = OpenAI(api_key=os.getenv("QWEN_API_KEY"), base_url=BASE_URL)
    r = c.chat.completions.create(
        model=MODEL_REASON,
        messages=[{"role": "user", "content": "Reply with the single word: OK"}],
        max_tokens=5,
    )
    print("live reply:", r.choices[0].message.content.strip())
    print("\n✅ LIVE: Sentinel can reach qwen3.7-max. Coupon credit will cover usage.")
except Exception as e:
    print("\n❌ Connection failed:", type(e).__name__, str(e)[:300])
    print("   Most likely: wrong region (need Singapore/intl) or model name. See docs/GO-LIVE.md")
    raise SystemExit(1)
PY
