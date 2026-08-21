"""Shared fixtures for black-box tests of the 5G core lab."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import pytest
from pymongo import MongoClient

NRF_URL = os.getenv("NRF_URL", "http://10.33.0.10:7777")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://10.33.0.2:27017")
UE_CONTAINER = os.getenv("UE_CONTAINER", "o5g-ue")
TEST_IMSI = os.getenv("TEST_IMSI", "999700000000001")
UNKNOWN_IMSI = "999700000009999"
BADKEY_IMSI = "999700000000002"
READY_TIMEOUT = int(os.getenv("READY_TIMEOUT", "180"))
UERANSIM_IMAGE = os.getenv("IMAGE_UERANSIM", "open5gs-lab/ueransim:3.3.0")
HOST_PROJECT_DIR = os.getenv("HOST_PROJECT_DIR", "/opt/open5gs-lab")
EXPECTED_NF_TYPES = {"AMF", "SMF", "AUSF", "UDM", "UDR", "PCF", "BSF", "NSSF"}


def run(cmd, timeout=30):
    """Run a command with a hard timeout and return (exit code, combined output)."""
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def ue_cli(command, container=None, imsi=None, timeout=30):
    container = container or UE_CONTAINER
    imsi = imsi or TEST_IMSI
    return run(
        ["docker", "exec", container, "nr-cli", f"imsi-{imsi}", "-e", command],
        timeout=timeout,
    )


def container_logs(container, tail=400, since=None):
    cmd = ["docker", "logs"]
    if since is not None:
        cmd += ["--since", str(max(0, int(since)))]
    cmd += ["--tail", str(tail), container]
    return run(cmd)[1]


def container_state(name):
    code, out = run(["docker", "inspect", "-f", "{{.State.Status}}", name])
    return out.strip() if code == 0 else "missing"


def wait_until(predicate, timeout, interval=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


@dataclass
class NrfResponse:
    status_code: int
    http_version: str
    text: str

    def json(self):
        return json.loads(self.text) if self.text else {}


class NrfClient:
    """Minimal h2c client backed by curl.

    Open5GS SBI uses clear-text HTTP/2. httpx negotiates HTTP/2 over TLS but
    does not guarantee h2c prior knowledge, so curl is explicit here.
    """

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def get(self, path, params=None):
        query = f"?{urlencode(params)}" if params else ""
        marker = "__O5G_META__"
        code, output = run(
            [
                "curl", "--silent", "--show-error", "--http2-prior-knowledge",
                "--max-time", "10", "--write-out", f"\n{marker}%{{http_code}}:%{{http_version}}",
                f"{self.base_url}{path}{query}",
            ],
            timeout=15,
        )
        if code != 0 or marker not in output:
            raise RuntimeError(f"NRF request failed: {output.strip()}")
        body, meta = output.rsplit(f"\n{marker}", 1)
        status, version = meta.strip().split(":", 1)
        return NrfResponse(int(status), f"HTTP/{version}", body)


def registered_nf_types(nrf):
    response = nrf.get("/nnrf-nfm/v1/nf-instances", params={"limit": 100})
    if response.status_code != 200:
        return set()
    links = response.json().get("_links", {}).get("items", [])
    found = set()
    for item in links:
        href = item.get("href", "")
        instance_id = href.rstrip("/").rsplit("/", 1)[-1]
        if not instance_id:
            continue
        profile = nrf.get(f"/nnrf-nfm/v1/nf-instances/{instance_id}")
        if profile.status_code == 200:
            found.add(profile.json().get("nfType"))
    return found


def run_throwaway_ue(config_name, name, seconds=25):
    code, out = run(
        [
            "docker", "run", "--rm", "--name", name,
            "--network", "open5gs-core",
            "--cap-add", "NET_ADMIN", "--device", "/dev/net/tun",
            "-v", f"{HOST_PROJECT_DIR}/config:/ueransim/config:ro",
            "--entrypoint", "timeout", UERANSIM_IMAGE,
            str(seconds), "nr-ue", "-c", f"/ueransim/config/{config_name}",
        ],
        timeout=seconds + 30,
    )
    # timeout(1) returns 124 after the observation window; that is expected.
    if code not in (0, 124):
        raise RuntimeError(f"temporary UE failed before the scenario ran: {out}")
    return out


@pytest.fixture(scope="session")
def nrf():
    return NrfClient(NRF_URL)


@pytest.fixture(scope="session")
def mongo():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    yield client
    client.close()


@pytest.fixture(scope="session")
def subscribers(mongo):
    return mongo["open5gs"]["subscribers"]


@pytest.fixture(scope="session", autouse=True)
def core_is_ready(nrf):
    ready = wait_until(
        lambda: EXPECTED_NF_TYPES.issubset(registered_nf_types(nrf)),
        READY_TIMEOUT,
    )
    if not ready:
        found = registered_nf_types(nrf)
        pytest.fail(
            f"5G core did not register all NF types in {READY_TIMEOUT}s; "
            f"missing={sorted(EXPECTED_NF_TYPES - found)}, found={sorted(x for x in found if x)}"
        )

    ue_ready = wait_until(
        lambda: (lambda result: result[0] == 0 and "RM-REGISTERED" in result[1])(
            ue_cli("status")
        ),
        READY_TIMEOUT,
    )
    if not ue_ready:
        pytest.fail(f"UE {TEST_IMSI} did not reach RM-REGISTERED in {READY_TIMEOUT}s")


@pytest.fixture
def ue_status():
    code, out = ue_cli("status")
    if code != 0:
        pytest.fail(f"nr-cli is unavailable in {UE_CONTAINER}: {out.strip()}")
    return out
