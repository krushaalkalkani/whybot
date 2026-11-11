#!/usr/bin/env bash
# Saves your Anthropic API key for WhyBot. Run it yourself; the key is never printed.
#   1. writes ANTHROPIC_API_KEY to .env (git-ignored) for local runs and evals
#   2. adds it to the Vercel project whybot-api (production) for the live demo
set -euo pipefail
cd "$(dirname "$0")/.."

read -r -s -p "Paste your Anthropic API key, then press Enter: " key
echo
if [[ "$key" != sk-ant-* ]]; then
  echo "That does not look like an Anthropic key (it should start with sk-ant-). Nothing was saved."
  exit 1
fi

grep -v '^ANTHROPIC_API_KEY=' .env > .env.tmp 2>/dev/null || true
printf 'ANTHROPIC_API_KEY=%s\n' "$key" >> .env.tmp
mv .env.tmp .env
echo "Saved to .env"

if printf '%s' "$key" | vercel env add ANTHROPIC_API_KEY production >/dev/null 2>&1; then
  echo "Saved to Vercel (whybot-api, production)"
else
  echo "Vercel already has this variable or the add failed. Local .env is saved; tell Claude."
fi
echo "Done. You can close this tab."
