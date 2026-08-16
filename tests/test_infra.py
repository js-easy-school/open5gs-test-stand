"""Проверки тестовой схемы: контейнеры подняты, сетевые функции зарегистрированы.

Это smoke-уровень: если он красный, остальные тесты разбирать бессмысленно —
сначала чинят стенд.
"""

import pytest

from conftest import container_state, container_logs

pytestmark = pytest.mark.infra

# NF, которые обязаны быть в схеме. UPF в списке нет намеренно:
# он работает по PFCP и в NRF себя не регистрирует.
EXPECTED_CONTAINERS = [
    "o5g-mongo", "o5g-nrf", "o5g-scp", "o5g-ausf", "o5g-udm", "o5g-udr",
    "o5g-pcf", "o5g-bsf", "o5g-nssf", "o5g-amf", "o5g-smf", "o5g-upf",
    "o5g-gnb", "o5g-ue",
]

EXPECTED_NF_TYPES = {"AMF", "SMF", "AUSF", "UDM", "UDR", "PCF", "BSF", "NSSF"}


@pytest.mark.parametrize("container", EXPECTED_CONTAINERS)
def test_container_is_running(container):
    state = container_state(container)
    assert state == "running", f"контейнер {container} в состоянии {state}, ожидалось running"


def test_nrf_answers_on_sbi(nrf):
    response = nrf.get("/nnrf-nfm/v1/nf-instances", params={"limit": 50})
    assert response.status_code in (200, 204), (
        f"NRF ответил {response.status_code}: сигнальный интерфейс SBI недоступен"
    )


def test_nrf_speaks_http2(nrf):
    """В 5G сигнальный обмен между NF идёт по HTTP/2 — проверяем версию протокола."""
    response = nrf.get("/nnrf-nfm/v1/nf-instances", params={"limit": 1})
    assert response.http_version == "HTTP/2", (
        f"NRF ответил по {response.http_version}, ожидался HTTP/2"
    )


def test_all_expected_nf_registered_in_nrf(nrf):
    response = nrf.get("/nnrf-nfm/v1/nf-instances", params={"limit": 100})
    assert response.status_code == 200, f"NRF вернул {response.status_code}"

    body = response.json()
    links = body.get("_links", {}).get("items", []) if isinstance(body, dict) else []
    hrefs = [item.get("href", "") for item in links]

    found = set()
    for href in hrefs:
        instance_id = href.rstrip("/").rsplit("/", 1)[-1]
        profile = nrf.get(f"/nnrf-nfm/v1/nf-instances/{instance_id}")
        if profile.status_code == 200:
            found.add(profile.json().get("nfType"))

    missing = EXPECTED_NF_TYPES - found
    assert not missing, f"в NRF не зарегистрированы: {sorted(missing)} (найдены: {sorted(found)})"


def test_amf_started_ngap_listener():
    """AMF обязан слушать SCTP 38412 — без этого базовая станция не подключится."""
    logs = container_logs("o5g-amf")
    assert "ngap_server" in logs or "38412" in logs, (
        "в логе AMF нет признаков поднятого NGAP-интерфейса"
    )


def test_gnb_connected_to_amf():
    logs = container_logs("o5g-gnb")
    assert "NG Setup procedure is successful" in logs, (
        "базовая станция не установила NG-соединение с AMF — смотрите логи gnb и amf"
    )


def test_no_fatal_errors_in_core_logs():
    """Фатальных ошибок в логах быть не должно даже при зелёных функциональных тестах."""
    problems = []
    for container in ["o5g-amf", "o5g-smf", "o5g-upf", "o5g-nrf"]:
        logs = container_logs(container, tail=500)
        for line in logs.splitlines():
            if "[fatal]" in line.lower() or "assertion" in line.lower():
                problems.append(f"{container}: {line.strip()}")
    assert not problems, "в логах ядра найдены фатальные сообщения:\n" + "\n".join(problems[:10])
