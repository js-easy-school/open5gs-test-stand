"""Проверка данных абонента в базе: ядро обязано отвечать тем, что лежит в UDR.

Классический дефект интеграции — API говорит одно, база хранит другое.
"""

import pytest

from conftest import TEST_IMSI

pytestmark = pytest.mark.subscriber


def test_subscriber_exists(subscribers):
    doc = subscribers.find_one({"imsi": TEST_IMSI})
    assert doc is not None, (
        f"абонент {TEST_IMSI} отсутствует в базе — выполните scripts/add-subscriber.sh"
    )


def test_subscriber_has_security_keys(subscribers):
    doc = subscribers.find_one({"imsi": TEST_IMSI})
    security = doc.get("security", {})
    assert security.get("k"), "у абонента не задан ключ K"
    assert security.get("opc") or security.get("op"), "у абонента не задан OPc/OP"
    assert security.get("amf"), "у абонента не задан AMF-параметр аутентификации"


def test_subscriber_slice_matches_core_config(subscribers):
    """Слайс абонента должен совпадать с тем, что поддерживает AMF (sst 1)."""
    doc = subscribers.find_one({"imsi": TEST_IMSI})
    slices = doc.get("slice", [])
    assert slices, "у абонента не настроен ни один слайс"
    assert any(s.get("sst") == 1 for s in slices), (
        f"слайс абонента не совпадает с поддерживаемым в ядре: {slices}"
    )


def test_subscriber_has_internet_dnn(subscribers):
    doc = subscribers.find_one({"imsi": TEST_IMSI})
    dnns = [
        session.get("name")
        for slice_ in doc.get("slice", [])
        for session in slice_.get("session", [])
    ]
    assert "internet" in dnns, f"нет точки доступа internet, найдены: {dnns}"


def test_ambr_limits_are_set(subscribers):
    """Ограничения скорости — часть профиля: их отсутствие ломает политику PCF."""
    doc = subscribers.find_one({"imsi": TEST_IMSI})
    ambr = doc.get("ambr", {})
    assert ambr.get("downlink", {}).get("value"), "не задано ограничение скорости вниз"
    assert ambr.get("uplink", {}).get("value"), "не задано ограничение скорости вверх"


def test_no_duplicate_subscribers(subscribers):
    """Дубликат IMSI в базе — источник плавающих отказов аутентификации."""
    count = subscribers.count_documents({"imsi": TEST_IMSI})
    assert count == 1, f"в базе {count} записей с IMSI {TEST_IMSI}, должна быть одна"
