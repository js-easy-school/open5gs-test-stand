#!/bin/sh
# Wait only for TCP dependencies. PFCP is UDP and NGAP is SCTP; probing those
# with `nc -z` (TCP) makes a healthy lab time out forever.

set -eu

WAIT_TIMEOUT="${WAIT_TIMEOUT:-90}"

for target in ${WAIT_FOR_TCP:-}; do
  host="${target%%:*}"
  port="${target##*:}"
  echo "waiting for TCP ${host}:${port} ..."
  waited=0
  while ! nc -z "${host}" "${port}" 2>/dev/null; do
    waited=$((waited + 1))
    if [ "${waited}" -ge "${WAIT_TIMEOUT}" ]; then
      echo "TCP ${host}:${port} did not become ready in ${WAIT_TIMEOUT}s" >&2
      exit 1
    fi
    sleep 1
  done
done

if [ "${SETUP_TUN:-0}" = "1" ]; then
  test -c /dev/net/tun || {
    echo "/dev/net/tun is unavailable; load the tun kernel module on the host" >&2
    exit 1
  }
  ip tuntap add name ogstun mode tun 2>/dev/null || true
  ip addr replace 10.45.0.1/16 dev ogstun
  ip link set ogstun up
  sysctl -w net.ipv4.ip_forward=1 >/dev/null
  iptables -t nat -C POSTROUTING -s 10.45.0.0/16 ! -o ogstun -j MASQUERADE 2>/dev/null \
    || iptables -t nat -A POSTROUTING -s 10.45.0.0/16 ! -o ogstun -j MASQUERADE
fi

echo "starting: $*"
exec "$@"
