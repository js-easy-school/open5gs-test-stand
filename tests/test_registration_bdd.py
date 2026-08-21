"""Executable Gherkin scenarios for the registration feature."""

import re
import time

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from conftest import container_logs, run_throwaway_ue, ue_cli

scenarios("../features/registration.feature")
pytestmark = pytest.mark.bdd


@pytest.fixture
def attempt():
    return {"started": None, "output": "", "imsi": ""}


@given(parsers.parse('subscriber "{imsi}" exists in Open5GS'))
def subscriber_exists(subscribers, imsi):
    assert subscribers.find_one({"imsi": imsi}) is not None


@given(parsers.parse('subscriber "{imsi}" is absent from Open5GS'))
def subscriber_absent(subscribers, imsi):
    assert subscribers.find_one({"imsi": imsi}) is None


@when("the provisioned UE requests registration", target_fixture="ue_observation")
def provisioned_ue_requests_registration():
    status = ue_cli("status")
    sessions = ue_cli("ps-list")
    return {"status": status, "sessions": sessions}


@when(parsers.parse('a temporary UE requests registration with "{config_name}"'))
def temporary_ue_requests_registration(config_name, attempt):
    attempt["started"] = time.time() - 1
    attempt["output"] = run_throwaway_ue(
        config_name,
        "o5g-bdd-" + config_name.removesuffix(".yaml").replace("_", "-"),
    )


@then(parsers.parse('the UE reaches state "{state}"'))
def ue_reaches_state(ue_observation, state):
    code, output = ue_observation["status"]
    assert code == 0 and state in output


@then(parsers.parse('an "{dnn}" PDU session is active'))
def pdu_session_is_active(ue_observation, dnn):
    code, output = ue_observation["sessions"]
    assert code == 0 and "PS-ACTIVE" in output and dnn in output


@then(parsers.parse('the AMF rejects IMSI "{imsi}"'))
def amf_rejects_imsi(attempt, imsi):
    logs = container_logs("o5g-amf", tail=500, since=attempt["started"])
    evidence = logs + attempt["output"]
    assert imsi in evidence
    assert re.search(r"Registration reject|Unknown UE|5GMM cause|reject", evidence, re.I)


@then(parsers.parse('authentication fails for IMSI "{imsi}"'))
def authentication_fails(attempt, imsi):
    logs = container_logs("o5g-amf", tail=500, since=attempt["started"])
    evidence = logs + attempt["output"]
    assert imsi in evidence
    assert re.search(r"Authentication failure|MAC failure|authentication.*(fail|reject)", evidence, re.I)
