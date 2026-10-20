from openfreebuds.driver.huawei.driver.generic import OfbDriverHandlerHuawei
from openfreebuds.driver.huawei.package import HuaweiSppPackage
from openfreebuds.utils.logger import create_logger

log = create_logger("OfbHuaweiBigDataCapabilityHandler")


class OfbHuaweiBigDataCapabilityHandler(OfbDriverHandlerHuawei):
    """
    Big-data capability exchange handler

    Right after connection, some devices (e.g. FreeBuds 5i) send a 0A0E
    push asking whether host supports big-data transfer. If there is no
    answer, device considers connection broken and disconnects.
    """
    handler_id = "config_big_data_capability"
    commands = [b"\x0a\x0e"]

    async def on_package(self, package: HuaweiSppPackage):
        if package.find_param(1) != b"\x00":
            log.warn(f"Unexpected big-data capability push\n{str(package)}")
            return

        log.debug("Answer big-data capability request")
        pkg = HuaweiSppPackage.change_rq(b"\x0a\x0e", [(2, b"\x00")])
        # Device never answers this request, so don't wait for response
        pkg.response_id = b""
        await self.driver.send_package(pkg)
