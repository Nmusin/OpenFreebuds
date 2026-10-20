import json

from openfreebuds.driver.huawei.constants import CMD_BATTERY_READ, CMD_BATTERY_NOTIFY
from openfreebuds.driver.huawei.driver.generic import OfbDriverHandlerHuawei
from openfreebuds.driver.huawei.package import HuaweiSppPackage


class OfbHuaweiBatteryHandler(OfbDriverHandlerHuawei):
    """
    Battery read handler
    """

    handler_id = "battery"
    commands = [CMD_BATTERY_READ, CMD_BATTERY_NOTIFY]

    def __init__(self, w_tws: bool = True):
        self.w_tws = w_tws

    async def on_init(self):
        resp = await self.driver.send_package(HuaweiSppPackage.read_rq(CMD_BATTERY_READ, [1, 2, 3]))
        await self.on_package(resp)

    async def on_package(self, package: HuaweiSppPackage):
        out = {}
        # A 0x00 level byte means "component did not report / is in the case",
        # not a 0% charge. Confirmed on device: captured frames carry tag 2 as
        # `55 00 4B` with the right bud docked (freebuds/evidence/
        # spp_readonly_sweep_2026-10-20.txt), and the official plugin decodes
        # that same frame as "R=нет данных" (freebuds REPORT.md §18.6,
        # PROTOCOL.md §11.4: levels [left, right, case], 0x00 = нет данных).
        # Such bytes are skipped instead of exposing a fake 0%.
        if 1 in package.parameters and len(package.parameters[1]) == 1 \
                and package.parameters[1][0] != 0:
            out["global"] = int(package.parameters[1][0])
        if 2 in package.parameters and len(package.parameters[2]) == 3 and self.w_tws:
            level = package.parameters[2]
            if level[0] != 0:
                out["left"] = int(level[0])
            if level[1] != 0:
                out["right"] = int(level[1])
            if level[2] != 0:
                out["case"] = int(level[2])
        if 3 in package.parameters and len(package.parameters[3]) > 0:
            out["is_charging"] = json.dumps(b"\x01" in package.parameters[3])
        # Push 0127 tag 5 = inBoxFlags (freebuds PROTOCOL.md §11.4 /
        # PUSH_HANDLERS.md: 2 flag bytes, 1 = component in the case). Exposed
        # in the same json.dumps(bool) style as is_charging above. No captured
        # frame carries tag 5 yet (caught pushes hold tags 1-4 only), so this
        # follows the structure documented from the plugin reverse.
        if 5 in package.parameters and len(package.parameters[5]) > 0:
            out["in_box"] = json.dumps(b"\x01" in package.parameters[5])
        await self.driver.put_property("battery", None, out)
