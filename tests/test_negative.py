"""Negative registration scenarios with per-attempt evidence."""

import pytest

from conftest import (
    TEST_IMSI,
    run,
    ue_cli,
    wait_until,
)

pytestmark = pytest.mark.negative


def test_legal_subscriber_still_works_after_bad_attempts():
    assert wait_until(lambda: "RM-REGISTERED" in ue_cli("status")[1], 60), (
        f"legal subscriber {TEST_IMSI} lost registration after negative scenarios"
    )


def test_core_survived_negative_cases():
    for container in ["o5g-amf", "o5g-ausf", "o5g-udm", "o5g-smf"]:
        code, out = run(["docker", "inspect", "-f", "{{.State.Status}}", container])
        assert code == 0 and out.strip() == "running", (
            f"{container} is not running after malformed registration attempts"
        )

        code, restarts = run(["docker", "inspect", "-f", "{{.RestartCount}}", container])
        assert code == 0 and restarts.strip() == "0", (
            f"{container} restarted {restarts.strip()} time(s) during negative tests"
        )
