#!/usr/bin/env bash
# Установка Docker для стенда. Работает и в WSL2 Debian, и на обычном VPS.
#
#   ./scripts/setup-docker.sh            обычная установка
#   MIRROR=1 ./scripts/setup-docker.sh   добавить зеркала реестра (если Docker Hub недоступен)

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "нужен root: sudo $0" >&2
  exit 1
fi

echo "── ставим docker и compose ──"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg lsb-release iproute2 iptables

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Зеркала: из России registry-1.docker.io часто недоступен напрямую.
if [[ "${MIRROR:-0}" == "1" ]]; then
  echo "── прописываю зеркала реестра ──"
  mkdir -p /etc/docker
  cat > /etc/docker/daemon.json <<'JSON'
{
  "registry-mirrors": [
    "https://mirror.gcr.io",
    "https://dockerhub.timeweb.cloud",
    "https://huecker.io"
  ],
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
fi

# В WSL нет systemd по умолчанию — демон запускается через sysvinit-скрипт.
if grep -qi microsoft /proc/version 2>/dev/null; then
  echo "── WSL: запускаю демон без systemd ──"
  service docker start || dockerd >/var/log/dockerd.log 2>&1 &
  sleep 3
else
  systemctl enable --now docker
fi

# Модуль туннеля нужен UPF и UE.
modprobe tun 2>/dev/null || true
if [[ ! -e /dev/net/tun ]]; then
  echo "ВНИМАНИЕ: нет /dev/net/tun — UPF и UE не поднимут туннель" >&2
fi

# Пользователь без sudo для docker.
TARGET_USER="${SUDO_USER:-$USER}"
if [[ -n "${TARGET_USER}" && "${TARGET_USER}" != "root" ]]; then
  usermod -aG docker "${TARGET_USER}"
  echo "пользователь ${TARGET_USER} добавлен в группу docker (нужен повторный вход)"
fi

echo
docker --version
docker compose version
echo "готово"
