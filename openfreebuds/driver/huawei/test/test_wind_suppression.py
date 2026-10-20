import pytest

from openfreebuds.driver.huawei.driver.debug import FbDriverHuaweiGenericFixture
from openfreebuds.driver.huawei.handler import OfbHuaweiConfigWindSuppressionHandler


@pytest.mark.asyncio
async def test_wind_suppression():
    # All frames captured live from HUAWEI FreeBuds 5i
    # (freebuds evidence/spp_misc_2026-10-20.txt, REPORT.md §18.5).
    # Wire polarity is inverted: 0 = suppression ON, 1 = suppression OFF.
    get_wind_rq = bytes.fromhex("5a0005002b95010090b0")
    get_wind_resp_off = bytes.fromhex("5a0006002b95010101c82b")  # wire 1 = OFF
    get_wind_resp_on = bytes.fromhex("5a0006002b95010100d80a")  # wire 0 = ON
    set_wind_on_rq = bytes.fromhex("5a0006002b94010100aebe")  # wire 0 = ON
    set_wind_off_rq = bytes.fromhex("5a0006002b94010101be9f")  # wire 1 = OFF
    set_wind_ack = bytes.fromhex("5a0006002b94020100f7ee")  # tag 02 val 00 = success

    driver = FbDriverHuaweiGenericFixture(
        handlers=[
            OfbHuaweiConfigWindSuppressionHandler()
        ],
        package_response_model={
            get_wind_rq: [get_wind_resp_off],
            set_wind_on_rq: [set_wind_ack],
            set_wind_off_rq: [set_wind_ack],
        }
    )

    await driver.start()

    # Read: device reports wire val=1 -> suppression OFF
    assert await driver.get_property("config", "wind_suppression") == "false"

    # Write "true" (ON) -> wire byte 0, exactly the captured SET-ON frame
    await driver.set_property("config", "wind_suppression", "true")
    assert ("send", set_wind_on_rq) in driver.package_log
    assert await driver.get_property("config", "wind_suppression") == "true"

    # Write "false" (OFF) -> wire byte 1, exactly the captured SET-OFF frame
    await driver.set_property("config", "wind_suppression", "false")
    assert ("send", set_wind_off_rq) in driver.package_log
    assert await driver.get_property("config", "wind_suppression") == "false"


@pytest.mark.asyncio
async def test_wind_suppression_state_push():
    # Device pushes 2B95 state after a SET; wire val=0 must map to "true"
    push_on = bytes.fromhex("5a0006002b95010100d80a")

    driver = FbDriverHuaweiGenericFixture(
        handlers=[
            OfbHuaweiConfigWindSuppressionHandler()
        ],
        package_response_model={}
    )

    await driver.start()
    await driver._handle_raw_pkg(push_on)
    assert await driver.get_property("config", "wind_suppression") == "true"
