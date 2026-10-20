from openfreebuds.driver.huawei.constants import CMD_DEVICE_IDENTITY
from openfreebuds.driver.huawei.driver.generic import OfbDriverHandlerHuawei
from openfreebuds.driver.huawei.package import HuaweiSppPackage


class OfbHuaweiDeviceIdentityHandler(OfbDriverHandlerHuawei):
    """
    Device identity handler (2B0A, live capture on FreeBuds 5i, 2026-10-20).

    Response TLV tags:
        1: serial number ("5PUTQ24826005493")
        2: model names ("T0014/T0014L")
        3: region ("082")
        4: revision ("001")
        5: sub-model ("ZAAD")
        6: firmware version ("1.0.0")

    Tag 1 is intentionally not stored: the device_info (0107) handler
    already exposes it as info/serial_number, and both live captures carry
    the same value. Only fields missing from 0107 are stored.
    """

    handler_id = "device_identity"
    commands = [CMD_DEVICE_IDENTITY]
    properties = [
        ("info", "model_name"),
        ("info", "region"),
        ("info", "revision"),
        ("info", "sub_model"),
        ("info", "firmware_version"),
    ]

    descriptor = {
        2: "model_name",
        3: "region",
        4: "revision",
        5: "sub_model",
        6: "firmware_version",
    }

    async def on_init(self):
        # A 1,2,3 read request makes the device answer with tags 1-6
        resp = await self.driver.send_package(
            HuaweiSppPackage.read_rq(CMD_DEVICE_IDENTITY, [1, 2, 3])
        )
        await self.on_package(resp)

    async def on_package(self, package: HuaweiSppPackage):
        if package.command_id != CMD_DEVICE_IDENTITY:
            return

        for tag, prop in self.descriptor.items():
            data = package.find_param(tag)
            if not data:
                continue
            try:
                value = data.decode("ascii")
            except UnicodeDecodeError:
                value = data.hex()
            await self.driver.put_property("info", prop, value)
