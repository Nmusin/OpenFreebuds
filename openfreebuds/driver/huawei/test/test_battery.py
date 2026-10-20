import pytest

from openfreebuds.driver.huawei.driver.debug import FbDriverHuaweiGenericFixture
from openfreebuds.driver.huawei.handler import OfbHuaweiBatteryHandler
from openfreebuds.driver.huawei.package import HuaweiSppPackage

GET_BATTERY_RQ = bytes.fromhex("5a0009000108010002000300fbb9")
GET_BATTERY_RESP_BASE = bytes.fromhex("5a0014000108010140020310203003030001000402140a1461")
GET_BATTERY_RESP_LEGACY = bytes.fromhex("5a0009000108010140030100ed2e")

# Real FreeBuds 5i frames from CRC-verified device logs (freebuds/evidence).
# 0108 response with the right bud docked: tag 2 = `64 00 4B`, the 0x00 byte
# means "not reported / in case", not 0% (REPORT.md §18.6: "R=нет данных").
GET_BATTERY_RESP_RIGHT_IN_CASE = bytes.fromhex("5a0014000108010164020364004b03030000000402140a507c")
# Real spontaneous push 0127, tags 1-4 only, right bud docked
# (spp_readonly_sweep_2026-10-20.txt, also spp_misc_2026-10-20.txt).
PUSH_BATTERY_RIGHT_IN_CASE = bytes.fromhex("5a0014000127010155020355004b03030000000402140a83fe")
# Synthetic frame: the real push above plus tag 5 `05 02 00 01` (inBoxFlags,
# 1 = in case) built per freebuds PROTOCOL.md §11.4. No tag-5 frame was
# captured live yet, so tag 5 is constructed from the documented structure.
PUSH_BATTERY_IN_BOX_FLAGS = bytes.fromhex("5a0018000127010155020355004b03030000000402140a0502000177a0")


async def create_driver(resp):
    driver = FbDriverHuaweiGenericFixture(
        handlers=[
            OfbHuaweiBatteryHandler()
        ],
        package_response_model={
            GET_BATTERY_RQ: [resp]
        }
    )

    await driver.start()
    await driver.send_package(HuaweiSppPackage.from_bytes(GET_BATTERY_RQ))

    assert driver.package_log[0] == ("send", GET_BATTERY_RQ)
    assert driver.package_log[1] == ("recv", resp)

    return driver


@pytest.mark.asyncio
async def test_battery_base():
    driver = await create_driver(GET_BATTERY_RESP_BASE)
    props = await driver.get_property("battery", None)

    assert props["left"] == 0x10
    assert props["right"] == 0x20
    assert props["case"] == 0x30
    assert props["global"] == 0x40
    assert props["is_charging"] == "true"


@pytest.mark.asyncio
async def test_battery_legacy():
    driver = await create_driver(GET_BATTERY_RESP_LEGACY)
    props = await driver.get_property("battery", None)

    assert "left" not in props
    assert props["global"] == 0x40
    assert props["is_charging"] == "false"


@pytest.mark.asyncio
async def test_battery_zero_level_is_unreported():
    # Real 0108 frame with the right bud in the case: 0x00 must not surface
    # as a 0% battery property.
    driver = await create_driver(GET_BATTERY_RESP_RIGHT_IN_CASE)
    props = await driver.get_property("battery", None)

    assert props["global"] == 0x64
    assert props["left"] == 0x64
    assert "right" not in props
    assert props["case"] == 0x4B
    assert props["is_charging"] == "false"


@pytest.mark.asyncio
async def test_battery_push_0127_right_in_case():
    # Real spontaneous push 0127 from device logs: tags 1-4, no tag 5.
    driver = await create_driver(GET_BATTERY_RESP_BASE)
    await driver._handle_raw_pkg(PUSH_BATTERY_RIGHT_IN_CASE)
    props = await driver.get_property("battery", None)

    assert props["left"] == 0x55
    assert "right" not in props
    assert props["case"] == 0x4B
    assert props["is_charging"] == "false"
    assert "in_box" not in props


@pytest.mark.asyncio
async def test_battery_push_0127_in_box_flags():
    # Synthetic push 0127 with tag 5 = 00 01 (right bud in the case).
    driver = await create_driver(GET_BATTERY_RESP_BASE)
    await driver._handle_raw_pkg(PUSH_BATTERY_IN_BOX_FLAGS)
    props = await driver.get_property("battery", None)

    assert props["in_box"] == "true"
    assert props["left"] == 0x55
    assert "right" not in props
    assert props["case"] == 0x4B
