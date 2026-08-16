#!/usr/bin/env bash
# Быстрый доступ к логам: scripts/logs.sh amf 100
set -euo pipefail
cd "$(dirname "$0")/.."
SERVICE="${1:-amf}"
LINES="${2:-100}"
docker compose logs --tail "${LINES}" "${SERVICE}"
