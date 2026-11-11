#!/usr/bin/env bash
# Publishes WhyBot. Run it yourself: it creates public things under your accounts.
#   1. a public GitHub repo "whybot" (CI runs on the first push)
#   2. a public Hugging Face dataset "whybot-rca-bench" (benchmark v1 + dataset card)
set -euo pipefail
cd "$(dirname "$0")/.."

if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create whybot --public --source . --push \
    --description "Cited root-cause analysis agent: explains why a metric moved, with proof."
else
  git push -u origin main
fi

out="$(mktemp -d)"
cp bench/data/v1/metrics.csv bench/data/v1/documents.jsonl bench/data/v1/MANIFEST.json bench/data/v1/README.md "$out/"
grep '"split": "dev"' bench/data/v1/scenarios.jsonl > "$out/scenarios_dev.jsonl"
grep '"split": "test"' bench/data/v1/scenarios.jsonl > "$out/scenarios_test.jsonl"
hf_user="$(hf auth whoami | sed -n 's/^user=\([^ ]*\).*/\1/p')"
hf upload "$hf_user/whybot-rca-bench" "$out" . --repo-type dataset --commit-message "WhyBot RCA Bench v1"

echo
echo "GitHub:  $(gh repo view --json url -q .url)"
echo "CI:      $(gh repo view --json url -q .url)/actions"
echo "Dataset: https://huggingface.co/datasets/$hf_user/whybot-rca-bench"
