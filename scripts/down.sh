#!/usr/bin/env bash
# Погасить стенд. По умолчанию данные абонентов сохраняются;
# полный сброс — scripts/down.sh --purge
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--purge" ]]; then
  echo "── полный снос вместе с базой ──"
  docker compose down -v --remove-orphans
else
  docker compose down --remove-orphans
fi
echo "стенд остановлен"
