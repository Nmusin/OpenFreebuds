from openfreebuds.driver.huawei.constants import CMD_WIND_SUPPRESSION_READ, CMD_WIND_SUPPRESSION_WRITE
from openfreebuds.driver.huawei.driver.generic import OfbDriverHandlerHuawei
from openfreebuds.driver.huawei.package import HuaweiSppPackage


class OfbHuaweiConfigWindSuppressionHandler(OfbDriverHandlerHuawei):
    """
    Wind suppression (wind reduction) toggle handler.

    WARNING: on the wire the polarity is INVERTED compared to the logical
    property: the device accepts 0 = suppression ON, 1 = suppression OFF.
    This was live-confirmed on a FreeBuds 5i (2026-10-20, SET 2B94 with
    b=0 enabled wind reduction, b=1 disabled it; the official plugin sends
    "!enabled", NoiseImpl.java:853). Read command 2B95 reports the same
    inverted encoding: val=0 means suppression is ON, val=1 means OFF.
    Evidence: REPORT.md §18.5, evidence/spp_misc_2026-10-20.txt.
    """

    handler_id = "wind_suppression"
    commands = [CMD_WIND_SUPPRESSION_READ, CMD_WIND_SUPPRESSION_WRITE]
    properties = [
        ("config", "wind_suppression"),
    ]

    async def on_init(self):
        resp = await self.driver.send_package(HuaweiSppPackage.read_rq(CMD_WIND_SUPPRESSION_READ, [1]))
        await self.on_package(resp)

    async def on_package(self, package: HuaweiSppPackage):
        data = package.find_param(1)
        if len(data) == 1:
            # Inverted polarity: wire 0 = suppression ON, 1 = OFF
            await self.driver.put_property("config", "wind_suppression",
                                           "true" if data[0] == 0 else "false")

    async def set_property(self, group: str, prop: str, value):
        # Inverted polarity: property "true" (suppression ON) goes on the
        # wire as 0, property "false" goes as 1
        resp = await self.driver.send_package(HuaweiSppPackage.change_rq(CMD_WIND_SUPPRESSION_WRITE, [
            (1, 0 if value == "true" else 1)
        ]))
        data = resp.find_param(2)
        if len(data) == 1 and data[0] == 0:
            await self.driver.put_property(group, prop, value)
