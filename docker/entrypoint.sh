#!/bin/sh
# Ждём зависимость, потом запускаем сетевую функцию.
# WAIT_FOR — список "хост:порт" через пробел, WAIT_TIMEOUT — секунды.

set -e

WAIT_TIMEOUT="${WAIT_TIMEOUT:-60}"

for target in ${WAIT_FOR}; do
  host="${target%%:*}"
  port="${target##*:}"
  echo "ожидание ${host}:${port} ..."
  waited=0
  while ! nc -z "${host}" "${port}" 2>/dev/null; do
    waited=$((waited + 1))
    if [ "${waited}" -ge "${WAIT_TIMEOUT}" ]; then
      echo "не дождались ${host}:${port} за ${WAIT_TIMEOUT} c" >&2
      exit 1
    fi
    sleep 1
  done
  echo "${host}:${port} доступен"
done

# UPF поднимает туннельный интерфейс для пользовательского трафика.
# Делается здесь, а не в конфиге: интерфейса ogstun в контейнере изначально нет.
if [ "${SETUP_TUN}" = "1" ]; then
  ip tuntap add name ogstun mode tun 2>/dev/null || true
  ip addr add 10.45.0.1/16 dev ogstun 2>/dev/null || true
  ip link set ogstun up
  sysctl -w net.ipv4.ip_forward=1 >/dev/null
  iptables -t nat -C POSTROUTING -s 10.45.0.0/16 ! -o ogstun -j MASQUERADE 2>/dev/null \
    || iptables -t nat -A POSTROUTING -s 10.45.0.0/16 ! -o ogstun -j MASQUERADE
  echo "ogstun поднят: 10.45.0.1/16"
fi

echo "старт: $*"
exec "$@"
