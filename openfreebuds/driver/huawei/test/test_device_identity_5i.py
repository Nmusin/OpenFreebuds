import pytest

from openfreebuds.driver.huawei.constants import CMD_DEVICE_IDENTITY
from openfreebuds.driver.huawei.driver.debug import FbDriverHuaweiGenericFixture
from openfreebuds.driver.huawei.handler import OfbHuaweiDeviceIdentityHandler
from openfreebuds.driver.huawei.package import HuaweiSppPackage


# Live capture, HUAWEI FreeBuds 5i, 2026-10-20 (evidence round 10)
RQ = bytes.fromhex("5a0009002b0a010002000300714e")
RESP = bytes.fromhex(
    "5a003a002b0a011035505554513234383236303035343933"
    "020c54303031342f54303031344c"
    "0303303832040330303105045a4141440605312e302e308e63"
)


@pytest.mark.asyncio
async def test_device_identity_5i():
    # Handler must build the exact request frame observed live
    assert HuaweiSppPackage.read_rq(CMD_DEVICE_IDENTITY, [1, 2, 3]).to_bytes() == RQ

    driver = FbDriverHuaweiGenericFixture(
        handlers=[
            OfbHuaweiDeviceIdentityHandler()
        ],
        package_response_model={
            RQ: [RESP],
        }
    )

    await driver.start()

    assert await driver.get_property("info", "model_name") == "T0014/T0014L"
    assert await driver.get_property("info", "region") == "082"
    assert await driver.get_property("info", "revision") == "001"
    assert await driver.get_property("info", "sub_model") == "ZAAD"
    assert await driver.get_property("info", "firmware_version") == "1.0.0"

    # Serial (tag 1) is not stored by this handler: device_info (0107)
    # already exposes the same value as info/serial_number
    assert await driver.get_property("info", "serial_number") is None
