"""Основной сценарий: абонент регистрируется в сети и получает передачу данных.

Проверяется не только «UE говорит, что всё хорошо», но и следы операции:
запись в логе AMF, поднятый туннельный интерфейс, реальный проход трафика.
"""

import re

import pytest

from conftest import TEST_IMSI, UE_CONTAINER, container_logs, run, ue_cli, wait_until

pytestmark = pytest.mark.registration


def test_ue_is_registered(ue_status):
    assert "RM-REGISTERED" in ue_status, (
        f"абонент не зарегистрирован в сети:\n{ue_status.strip()}"
    )


def test_ue_has_5g_mm_state_registered(ue_status):
    assert "MM-REGISTERED" in ue_status or "RM-REGISTERED" in ue_status, (
        f"состояние управления мобильностью не REGISTERED:\n{ue_status.strip()}"
    )


def test_amf_logged_successful_registration():
    logs = container_logs("o5g-amf", tail=800)
    pattern = re.compile(r"(Registration complete|InitialContextSetupResponse|Registration accept)", re.I)
    assert pattern.search(logs), (
        "в логе AMF нет записи об успешной регистрации абонента"
    )
    assert TEST_IMSI in logs, f"в логе AMF не встречается IMSI {TEST_IMSI}"


def test_pdu_session_is_active():
    code, out = ue_cli("ps-list")
    assert code == 0, f"nr-cli ps-list завершился с ошибкой: {out.strip()}"
    assert "PS-ACTIVE" in out, f"сессия передачи данных не активна:\n{out.strip()}"
    assert "internet" in out, "сессия установлена не к точке доступа internet"


def test_ue_got_ip_from_core_pool():
    """Адрес абоненту выдаёт SMF из пула 10.45.0.0/16, заданного в конфиге."""
    code, out = run(["docker", "exec", UE_CONTAINER, "ip", "-4", "addr", "show", "uesimtun0"])
    assert code == 0, f"интерфейс uesimtun0 не создан — сессия не установлена:\n{out.strip()}"

    match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
    assert match, f"у uesimtun0 нет IPv4-адреса:\n{out.strip()}"
    assert match.group(1).startswith("10.45."), (
        f"адрес {match.group(1)} выдан не из пула 10.45.0.0/16"
    )


def test_user_plane_reaches_gateway():
    """Пакеты абонента должны доходить до шлюза сети данных через UPF."""
    code, out = run(
        ["docker", "exec", UE_CONTAINER, "ping", "-I", "uesimtun0", "-c", "3", "-W", "3", "10.45.0.1"],
        timeout=30,
    )
    assert code == 0, f"трафик через туннель не проходит:\n{out.strip()}"
    assert "0% packet loss" in out or " 0% packet loss" in out, (
        f"потери пакетов в пользовательской плоскости:\n{out.strip()}"
    )


def test_smf_created_session_in_log():
    logs = container_logs("o5g-smf", tail=500)
    assert re.search(r"(UE IMSI|Session|PDU session)", logs, re.I), (
        "SMF не записал создание сессии"
    )


@pytest.mark.slow
def test_ue_reregisters_after_deregistration():
    """Дерегистрация и повторный вход — проверка, что узел не залипает в старом состоянии."""
    code, out = ue_cli("deregister normal")
    assert code == 0, f"команда дерегистрации не выполнилась: {out.strip()}"

    def deregistered():
        return "RM-DEREGISTERED" in ue_cli("status")[1]

    assert wait_until(deregistered, 30), "абонент не перешёл в состояние DEREGISTERED"

    # UERANSIM сам инициирует повторную регистрацию
    def registered_again():
        return "RM-REGISTERED" in ue_cli("status")[1]

    assert wait_until(registered_again, 60), (
        "абонент не вернулся в сеть после дерегистрации — узел завис в промежуточном состоянии"
    )
