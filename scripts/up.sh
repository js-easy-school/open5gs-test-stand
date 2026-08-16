#!/usr/bin/env bash
# Поднять стенд целиком: собрать образы, запустить ядро, завести абонента,
# дождаться регистрации. Один вход для человека и для CI.

set -euo pipefail

cd "$(dirname "$0")/.."

IMSI="${IMSI:-999700000000001}"
WAIT_SECONDS="${WAIT_SECONDS:-120}"

echo "── сборка образов ──"
docker compose build

echo "── запуск ядра и радиосети ──"
docker compose up -d

echo "── жду MongoDB ──"
until docker exec o5g-mongo mongosh --quiet --eval "db.adminCommand('ping').ok" >/dev/null 2>&1; do
  sleep 2
done

echo "── завожу абонента ──"
./scripts/add-subscriber.sh "${IMSI}"

# абонент появился после старта UE — перезапускаем его, чтобы он зарегистрировался
docker compose restart ue >/dev/null

echo "── жду регистрацию абонента (до ${WAIT_SECONDS} c) ──"
deadline=$(( SECONDS + WAIT_SECONDS ))
while (( SECONDS < deadline )); do
  if docker exec o5g-ue nr-cli "imsi-${IMSI}" -e status 2>/dev/null | grep -q "RM-REGISTERED"; then
    echo "абонент зарегистрирован"
    docker exec o5g-ue nr-cli "imsi-${IMSI}" -e status || true
    echo
    echo "стенд готов. тесты:  ./scripts/test.sh"
    exit 0
  fi
  sleep 3
done

echo "абонент так и не зарегистрировался за ${WAIT_SECONDS} c" >&2
echo "смотрите: docker compose logs amf | tail -50" >&2
exit 1
