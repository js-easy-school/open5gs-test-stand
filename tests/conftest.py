"""Общие фикстуры и помощники для тестов стенда 5G-ядра.

Тесты работают снаружи ядра, как настоящий QA: дёргают SBI сетевых функций,
смотрят базу абонентов, выполняют команды внутри контейнеров UE и читают логи AMF.
"""

import os
import subprocess
import time

import httpx
import pytest
from pymongo import MongoClient

NRF_URL = os.getenv("NRF_URL", "http://10.33.0.10:7777")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://10.33.0.2:27017")
UE_CONTAINER = os.getenv("UE_CONTAINER", "o5g-ue")
AMF_CONTAINER = os.getenv("AMF_CONTAINER", "o5g-amf")
TEST_IMSI = os.getenv("TEST_IMSI", "999700000000001")
READY_TIMEOUT = int(os.getenv("READY_TIMEOUT", "120"))
UERANSIM_IMAGE = os.getenv("IMAGE_UERANSIM", "open5gs-lab/ueransim:3.2.6")
# путь к проекту на хосте: разовые контейнеры создаются через докер хоста,
# и пути томов он понимает только свои, а не пути внутри контейнера тестов
HOST_PROJECT_DIR = os.getenv("HOST_PROJECT_DIR", "/opt/open5gs-lab")


# ─────────────────────────── помощники ───────────────────────────

def run(cmd, timeout=30):
    """Выполнить команду и вернуть (код возврата, вывод).

    Таймаут обязателен: зависший docker exec иначе остановит весь прогон.
    """
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def ue_cli(command, container=None, imsi=None, timeout=30):
    """Выполнить команду nr-cli внутри контейнера абонентского устройства."""
    container = container or UE_CONTAINER
    imsi = imsi or TEST_IMSI
    return run(
        ["docker", "exec", container, "nr-cli", f"imsi-{imsi}", "-e", command],
        timeout=timeout,
    )


def container_logs(container, tail=400):
    return run(["docker", "logs", "--tail", str(tail), container])[1]


def container_state(name):
    code, out = run(["docker", "inspect", "-f", "{{.State.Status}}", name])
    return out.strip() if code == 0 else "missing"


def wait_until(predicate, timeout, interval=2.0, description=""):
    """Ждать выполнения условия. Возвращает True/False, не бросает исключение."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            last = predicate()
            if last:
                return True
        except Exception:
            last = None
        time.sleep(interval)
    return bool(last)


# ─────────────────────────── фикстуры ───────────────────────────

@pytest.fixture(scope="session")
def nrf():
    """Клиент к NRF. Сигнальный обмен в 5G идёт по HTTP/2 без TLS,
    поэтому нужен httpx с http2=True, а не requests."""
    with httpx.Client(base_url=NRF_URL, http2=True, timeout=10.0) as client:
        yield client


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
    """Ждём готовности ядра до первого теста.

    Без этой фикстуры тесты падают не из-за дефектов, а из-за гонки со стартом
    контейнеров — самая частая причина «мигающих» тестов на стендах.
    """
    def nf_registered():
        response = nrf.get("/nnrf-nfm/v1/nf-instances", params={"limit": 50})
        if response.status_code not in (200, 204):
            return False
        types = {item.get("nfType") for item in response.json().get("_links", {}).get("items", [])} \
            if isinstance(response.json(), dict) else set()
        return True if response.status_code == 200 else bool(types)

    ready = wait_until(nf_registered, READY_TIMEOUT, description="регистрация NF в NRF")
    if not ready:
        pytest.fail(
            f"ядро не поднялось за {READY_TIMEOUT} c: NRF по адресу {NRF_URL} не отвечает "
            "или сетевые функции не зарегистрировались"
        )

    def ue_registered():
        code, out = ue_cli("status")
        return code == 0 and "RM-REGISTERED" in out

    wait_until(ue_registered, READY_TIMEOUT, description="регистрация абонента")


@pytest.fixture
def ue_status():
    """Свежий статус абонентского устройства перед каждым тестом."""
    code, out = ue_cli("status")
    if code != 0:
        pytest.fail(f"nr-cli недоступен в контейнере {UE_CONTAINER}: {out.strip()}")
    return out
