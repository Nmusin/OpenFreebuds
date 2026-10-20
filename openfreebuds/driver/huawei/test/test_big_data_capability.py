import pytest

from openfreebuds.driver.huawei.driver.debug import FbDriverHuaweiGenericFixture
from openfreebuds.driver.huawei.package import HuaweiSppPackage

# Real device frames (HUAWEI FreeBuds 5i, spp_readonly_2026-10-20 logs):
# device asks about big-data capability right after connection
CAPABILITY_PUSH = bytes.fromhex("5a0006000a0e010100a26f")
# Expected answer from host side
CAPABILITY_ANSWER = bytes.fromhex("5a0006000a0e020100fb3f")


@pytest.mark.asyncio
async def test_big_data_capability():
    driver = FbDriverHuaweiGenericFixture(
        handlers=[],
        package_response_model={},
    )

    await driver.start()

    # Handler must be auto-registered for all Huawei models
    assert "config_big_data_capability" in [h.handler_id for h in driver.handlers]

    # Reference frames must checksum-validate
    push_pkg = HuaweiSppPackage.from_bytes(CAPABILITY_PUSH, validate_checksum=True)
    assert push_pkg.find_param(1) == b"\x00"

    # Deliver capability request push, expect exactly one answer per push
    await driver._handle_raw_pkg(CAPABILITY_PUSH)
    assert driver.package_log == [
        ("send", CAPABILITY_ANSWER),
        ("recv", CAPABILITY_PUSH),
    ]

    # Repeated push must be answered again
    await driver._handle_raw_pkg(CAPABILITY_PUSH)
    assert driver.package_log == [
        ("send", CAPABILITY_ANSWER),
        ("recv", CAPABILITY_PUSH),
        ("send", CAPABILITY_ANSWER),
        ("recv", CAPABILITY_PUSH),
    ]
