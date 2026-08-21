#!/usr/bin/env bash
# Fail fast with an actionable message before a long image build.

set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This lab requires a Linux kernel (native Linux or WSL2)." >&2
  exit 1
fi

command -v docker >/dev/null || { echo "docker is not installed" >&2; exit 1; }
docker info >/dev/null || { echo "docker daemon is not reachable" >&2; exit 1; }
docker compose version >/dev/null || { echo "docker compose v2 is required" >&2; exit 1; }

if [[ ! -c /dev/net/tun ]]; then
  echo "/dev/net/tun is missing; load the tun kernel module on the host" >&2
  exit 1
fi

if [[ ! -r /proc/net/sctp/assocs ]]; then
  echo "SCTP is unavailable; load the sctp kernel module on the host" >&2
  exit 1
fi

echo "preflight OK: Docker, Compose, TUN and SCTP are available"
