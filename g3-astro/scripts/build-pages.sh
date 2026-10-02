#!/usr/bin/env bash
# Cloudflare Pages build gate. No live ingestion or secrets are needed here.
set -euo pipefail

web_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$web_dir"

if [[ "${PUBLIC_DEMO_MODE:-false}" != "false" ]]; then
  printf 'Pages releases must not enable PUBLIC_DEMO_MODE.\n' >&2
  exit 1
fi

npm ci
npm audit --audit-level=high
make -C "$web_dir/.." verify

# Astro copies public/ verbatim. Never publish local ingestion bookkeeping.
rm -f -- dist/data/.ingest.lock dist/data/media/.og-attempts.json
printf 'Verified static Pages artifact: %s/dist\n' "$web_dir"
