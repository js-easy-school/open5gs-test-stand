#!/usr/bin/env bash
# Build and start the complete lab, provision subscribers, and wait for 5G registration.

set -euo pipefail
cd "$(dirname "$0")/.."

IMSI="${IMSI:-999700000000001}"
WAIT_SECONDS="${WAIT_SECONDS:-180}"

./scripts/preflight.sh

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "── building pinned Open5GS and UERANSIM images ──"
  docker compose build
fi

echo "── starting MongoDB and 5G core functions ──"
docker compose up -d mongo nrf scp ausf udm udr pcf bsf nssf amf upf smf

deadline=$((SECONDS + WAIT_SECONDS))
until docker exec o5g-mongo mongosh --quiet --eval "db.adminCommand('ping').ok" >/dev/null 2>&1; do
  if ((SECONDS >= deadline)); then
    echo "MongoDB did not become ready in ${WAIT_SECONDS}s" >&2
    docker compose ps --all >&2
    exit 1
  fi
  sleep 2
done

echo "── provisioning positive and bad-key test subscribers ──"
./scripts/add-subscriber.sh "${IMSI}"
./scripts/add-subscriber.sh "999700000000002"

echo "── starting simulated gNB and UE ──"
docker compose up -d gnb ue

echo "── waiting for subscriber registration (up to ${WAIT_SECONDS}s) ──"
deadline=$((SECONDS + WAIT_SECONDS))
while ((SECONDS < deadline)); do
  if docker exec o5g-ue nr-cli "imsi-${IMSI}" -e status 2>/dev/null | grep -q "RM-REGISTERED"; then
    echo "subscriber ${IMSI} is registered"
    docker exec o5g-ue nr-cli "imsi-${IMSI}" -e status || true
    exit 0
  fi
  sleep 3
done

echo "subscriber ${IMSI} did not register in ${WAIT_SECONDS}s" >&2
docker compose ps --all >&2
docker compose logs --tail 80 amf gnb ue >&2 || true
exit 1
