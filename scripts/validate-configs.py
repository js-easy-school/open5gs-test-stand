#!/usr/bin/env python3
"""Fast, Docker-free validation of the lab topology and configuration."""

from __future__ import annotations

from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path):
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


compose = load_yaml(ROOT / "docker-compose.yml")
services = compose.get("services", {})
required_services = {
    "mongo", "nrf", "scp", "ausf", "udm", "udr", "pcf", "bsf", "nssf",
    "amf", "smf", "upf", "gnb", "ue", "tests",
}
missing = required_services - set(services)
if missing:
    fail(f"compose is missing services: {sorted(missing)}")

expected_addresses = {
    "nrf": "10.33.0.10",
    "scp": "10.33.0.11",
    "ausf": "10.33.0.12",
    "udm": "10.33.0.13",
    "udr": "10.33.0.14",
    "pcf": "10.33.0.15",
    "bsf": "10.33.0.16",
    "nssf": "10.33.0.17",
    "amf": "10.33.0.20",
    "smf": "10.33.0.21",
    "upf": "10.33.0.22",
}

for name, address in expected_addresses.items():
    actual = services[name]["networks"]["core"]["ipv4_address"]
    if actual != address:
        fail(f"{name}: compose address {actual} != expected {address}")

    config = load_yaml(ROOT / "config" / f"{name}.yaml")
    section = config[name]
    protocol = "sbi" if name not in {"upf"} else "pfcp"
    configured = section[protocol]["server"][0]["address"]
    if configured != address:
        fail(f"{name}: advertised {protocol} address {configured} != compose {address}")

for config_path in sorted((ROOT / "config").glob("*.yaml")):
    data = load_yaml(config_path)
    if not isinstance(data, dict):
        fail(f"{config_path.name}: top level must be a mapping")
    if "0.0.0.0" in config_path.read_text(encoding="utf-8"):
        fail(f"{config_path.name}: wildcard address must not be advertised by an NF")

for name, service in services.items():
    environment = service.get("environment") or {}
    if "WAIT_FOR" in environment:
        fail(f"{name}: legacy WAIT_FOR performs invalid TCP probes")
    wait_targets = environment.get("WAIT_FOR_TCP", "")
    if any(port in wait_targets for port in (":8805", ":38412", ":4997")):
        fail(f"{name}: UDP/SCTP endpoint is incorrectly configured as a TCP wait target")

udm_text = (ROOT / "config" / "udm.yaml").read_text(encoding="utf-8")
if "/opt/open5gs/etc/open5gs/hnet/" not in udm_text:
    fail("UDM does not reference the hnet keys installed in the Open5GS image")

open5gs_dockerfile = (ROOT / "docker" / "Dockerfile.open5gs").read_text(encoding="utf-8")
ueransim_dockerfile = (ROOT / "docker" / "Dockerfile.ueransim").read_text(encoding="utf-8")
for needle, text in [
    ("OPEN5GS_VERSION=v2.8.0", open5gs_dockerfile),
    ("157f611a530e292e40ec50f9d23f0ef5d4fcd6a6", open5gs_dockerfile),
    ("UERANSIM_VERSION=v3.3.0", ueransim_dockerfile),
    ("6bf5a1a96aaef6ae8778b9d8b477ac6e2bbf8156", ueransim_dockerfile),
]:
    if needle not in text:
        fail(f"reproducible build pin is missing: {needle}")

feature = (ROOT / "features" / "registration.feature").read_text(encoding="utf-8")
for keyword in ("Feature:", "Scenario:", "Given ", "When ", "Then "):
    if keyword not in feature:
        fail(f"Gherkin feature is missing {keyword.strip()}")

print(f"OK: {len(required_services)} services, {len(list((ROOT / 'config').glob('*.yaml')))} YAML configs, pinned images and Gherkin")
