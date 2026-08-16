"""Негативные сценарии: сеть обязана отказывать, а не пускать кого попало.

Здесь запускаются разовые контейнеры UE с «плохими» конфигами: неизвестный
абонент и абонент с неверным ключом. Оба должны получить отказ, а ядро —
остаться работоспособным для легального абонента.
"""

import pytest

from conftest import (
    HOST_PROJECT_DIR, TEST_IMSI, UERANSIM_IMAGE, container_logs, run, ue_cli, wait_until,
)

pytestmark = pytest.mark.negative

NETWORK = "open5gs-core"


def run_throwaway_ue(config_name, seconds=20):
    """Поднять UE с указанным конфигом на несколько секунд и вернуть его вывод.

    Контейнер создаётся через сокет докера на хосте, поэтому путь к конфигам
    берётся хостовый (HOST_PROJECT_DIR), а не путь внутри контейнера тестов.
    """
    code, out = run(
        [
            "docker", "run", "--rm",
            "--network", NETWORK,
            "--cap-add", "NET_ADMIN",
            "--device", "/dev/net/tun",
            "-v", f"{HOST_PROJECT_DIR}/config:/ueransim/config:ro",
            "--entrypoint", "timeout",
            UERANSIM_IMAGE,
            str(seconds), "nr-ue", "-c", f"/ueransim/config/{config_name}",
        ],
        timeout=seconds + 30,
    )
    return out


def test_unknown_subscriber_is_rejected():
    """IMSI, которого нет в базе, не должен получать доступ в сеть."""
    output = run_throwaway_ue("ue-unknown.yaml")
    amf_logs = container_logs("o5g-amf", tail=300)

    rejected = (
        "Registration reject" in amf_logs
        or "Unknown UE" in amf_logs
        or "5GMM cause" in amf_logs
        or "reject" in output.lower()
    )
    assert rejected, (
        "неизвестный абонент не получил отказа — проверьте, не пускает ли сеть "
        f"кого угодно.\nвывод UE:\n{output[-800:]}"
    )


def test_wrong_key_fails_authentication():
    """Неверный ключ SIM — отказ на этапе аутентификации, а не на этапе сессии."""
    output = run_throwaway_ue("ue-badkey.yaml")
    amf_logs = container_logs("o5g-amf", tail=300)

    failed = (
        "Authentication failure" in amf_logs
        or "MAC failure" in amf_logs
        or "authentication" in output.lower()
    )
    assert failed, (
        "абонент с неверным ключом не получил отказа аутентификации.\n"
        f"вывод UE:\n{output[-800:]}"
    )


def test_legal_subscriber_still_works_after_bad_attempts():
    """После неудачных попыток легальный абонент обязан остаться в сети."""
    def registered():
        return "RM-REGISTERED" in ue_cli("status")[1]

    assert wait_until(registered, 60), (
        f"после негативных сценариев легальный абонент {TEST_IMSI} потерял регистрацию — "
        "узел не изолирует ошибочные попытки"
    )


def test_core_survived_negative_cases():
    """Ни одна сетевая функция не должна упасть из-за некорректного абонента."""
    for container in ["o5g-amf", "o5g-ausf", "o5g-udm", "o5g-smf"]:
        code, out = run(["docker", "inspect", "-f", "{{.State.Status}}", container])
        assert out.strip() == "running", f"{container} не работает после негативных тестов"

        code, restarts = run(["docker", "inspect", "-f", "{{.RestartCount}}", container])
        assert restarts.strip() in ("0", ""), (
            f"{container} перезапускался {restarts.strip()} раз(а) — вероятно, падал"
        )
