import pytest

from openfreebuds.driver.huawei.driver.debug import FbDriverHuaweiGenericFixture
from openfreebuds.driver.huawei.handler import OfbHuaweiActionFindMyBudsHandler

# Frames captured live from HUAWEI FreeBuds 5i
# (freebuds evidence/spp_round9b_2026-10-20.txt, REPORT.md §"Поиск наушника")
FIND_START_LEFT_TX = bytes.fromhex("5a0007002b5d010200006f63")  # [side=0, state=0]
FIND_STOP_LEFT_TX = bytes.fromhex("5a0007002b5d010200017f42")  # [side=0, state=1]
FIND_START_RIGHT_TX = bytes.fromhex("5a0007002b5d010201005c52")  # [side=1, state=0]
FIND_STOP_RIGHT_TX = bytes.fromhex("5a0007002b5d010201014c73")  # [side=1, state=1]
FIND_ACK = bytes.fromhex("5a0007002b5d02020000f4bf")  # ACK 2B5D tag 2 = [side, state]
FIND_STATE_PUSH = bytes.fromhex("5a0007002b5e020200001a6d")  # notify 2B5E tag 2


@pytest.mark.asyncio
async def test_find_my_buds_start_stop():
    driver = FbDriverHuaweiGenericFixture(
        handlers=[
            OfbHuaweiActionFindMyBudsHandler()
        ],
        package_response_model={
            FIND_START_LEFT_TX: [FIND_ACK],
            FIND_STOP_LEFT_TX: [FIND_ACK],
            FIND_START_RIGHT_TX: [FIND_ACK],
            FIND_STOP_RIGHT_TX: [FIND_ACK],
        }
    )

    await driver.start()

    await driver.set_property("action", "find_my_buds", "left_start")
    assert ("send", FIND_START_LEFT_TX) in driver.package_log

    await driver.set_property("action", "find_my_buds", "left_stop")
    assert ("send", FIND_STOP_LEFT_TX) in driver.package_log

    await driver.set_property("action", "find_my_buds", "right_start")
    assert ("send", FIND_START_RIGHT_TX) in driver.package_log

    await driver.set_property("action", "find_my_buds", "right_stop")
    assert ("send", FIND_STOP_RIGHT_TX) in driver.package_log


@pytest.mark.asyncio
async def test_find_my_buds_state_push_ignored():
    # Device pushes the ringing state via 2B5E; stateless handler must
    # swallow it without errors and without touching the store
    driver = FbDriverHuaweiGenericFixture(
        handlers=[
            OfbHuaweiActionFindMyBudsHandler()
        ],
        package_response_model={}
    )

    await driver.start()
    await driver._handle_raw_pkg(FIND_STATE_PUSH)
    assert await driver.get_property("action", "find_my_buds") is None


@pytest.mark.asyncio
async def test_find_my_buds_unknown_value():
    driver = FbDriverHuaweiGenericFixture(
        handlers=[
            OfbHuaweiActionFindMyBudsHandler()
        ],
        package_response_model={}
    )

    await driver.start()
    await driver.set_property("action", "find_my_buds", "center_start")
    assert driver.package_log == []
