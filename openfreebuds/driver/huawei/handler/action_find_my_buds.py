from openfreebuds.driver.huawei.constants import CMD_FIND_MY_BUDS_WRITE, CMD_FIND_MY_BUDS_STATE
from openfreebuds.driver.huawei.driver.generic import OfbDriverHandlerHuawei
from openfreebuds.driver.huawei.package import HuaweiSppPackage
from openfreebuds.utils.logger import create_logger

log = create_logger("OfbHuaweiActionFindMyBudsHandler")


class OfbHuaweiActionFindMyBudsHandler(OfbDriverHandlerHuawei):
    """
    "Find my earbuds" ringing sound action handler.

    Stateless action: sends 2B5D with TLV tag 1 = [side, state], where
    side is 0=left / 1=right and state is 0=ringing start / 1=ringing
    stop. Live-confirmed on FreeBuds 5i (REPORT.md, evidence/
    spp_round9b_2026-10-20.txt: start left `5a0007002b5d010200006f63`,
    stop left `5a0007002b5d010200017f42`). The device ACKs on 2B5D
    (tag 2 = [side, state]) and pushes the ringing state via 2B5E
    (tag 2 = [side, state]); this handler is write-only, those pushes
    are intentionally ignored (2B5E read semantics are not confirmed).
    """

    handler_id = "find_my_buds"
    commands = [CMD_FIND_MY_BUDS_WRITE]
    ignore_commands = [CMD_FIND_MY_BUDS_STATE]
    properties = [
        ("action", "find_my_buds"),
    ]

    # Property value -> wire [side, state] bytes
    _values = {
        "left_start": bytes([0, 0]),
        "left_stop": bytes([0, 1]),
        "right_start": bytes([1, 0]),
        "right_stop": bytes([1, 1]),
    }

    async def set_property(self, group: str, prop: str, value: str):
        data = self._values.get(value)
        if data is None:
            log.warning(f"Unknown find_my_buds value {value}, ignoring")
            return

        await self.driver.send_package(HuaweiSppPackage.change_rq(CMD_FIND_MY_BUDS_WRITE, [
            (1, data),
        ]))
