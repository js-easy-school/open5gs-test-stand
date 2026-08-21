#!/usr/bin/env bash
# Прогон автотестов в контейнере. Отчёты складываются в ./reports.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p reports

echo "── прогон тестов ──"
HOST_PROJECT_DIR="$(pwd)" docker compose --profile test run --rm tests \
  pytest -v --junitxml=/reports/junit.xml --html=/reports/report.html --self-contained-html "$@"

echo
echo "отчёты: reports/junit.xml, reports/report.html"
