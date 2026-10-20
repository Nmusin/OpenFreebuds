from openfreebuds.driver.huawei.constants import CMD_FIT_TEST_RESULT, CMD_FIT_TEST_WRITE
from openfreebuds.driver.huawei.driver.generic import OfbDriverHandlerHuawei
from openfreebuds.driver.huawei.package import HuaweiSppPackage
from openfreebuds.utils.logger import create_logger

log = create_logger("OfbHuaweiFitTestHandler")


class OfbHuaweiFitTestHandler(OfbDriverHandlerHuawei):
    """
    Ear fit test (проверка посадки) handler for HUAWEI FreeBuds 5i.

    Protocol (live-confirmed 2026-10-20, freebuds REPORT.md §13/§23/§24,
    PROTOCOL.md §15, evidence/spp_round9b_2026-10-20.txt):

    - Control command 2B26, TLV `01 00` = start, `03 00` = exit/reset.
      The device answers on the same command with tag 2:
      `0` = "play the test tone" (measurement started),
      `2` = "show result page" (no measurement runs).
      Answers are parsed synchronously from send_package.
      Live frames: start `5a0005002b260100371f` -> `5a0006002b26020100eb57`,
      exit `5a0005002b260300517d` -> `5a0006002b26020102cb15`.
    - Result arrives as a spontaneous notify 2B27, TLV `01 01 <0..5>`:
      0 = left ear good fit, 1 = left ear adjust tip size,
      2 = right ear good fit, 3 = right ear adjust tip size,
      4 = left ear measurement noisy, 5 = right ear measurement noisy.
    - "Worn correctly" verdict: left == 0 AND right == 2 -> "good_fit";
      left == 4 or right == 5 -> "noisy_environment" (retry in a quiet
      place); anything else -> "adjust_fit" (try other tip size).
      A single 2B27 notify carries one value only, so left/right results
      accumulate across notifies until both sides are known.

    IMPORTANT LIMITATION (live-proven, REPORT.md §24): the app-side test
    tone (detect_music.ogg, resource pack 000145_07) CANNOT be played by
    a headless SPP process: the tone must be routed to the earbuds over
    A2DP, which our process can't do (AudioManager sees no BT outputs,
    MediaPlayer raises SecurityException on Termux uid). Without the tone
    the measurement never completes and 2B27 never arrives. Therefore
    this handler only starts/stops the test and collects 2B27 results:
    after set_property(..., "start") answers tag 2 = 0, the CLIENT is
    responsible for playing the test tone itself (any player, A2DP).

    Preconditions enforced by the official app, recommended for clients
    (REPORT.md §24): turn ANC/Awareness off, raise volume, quiet room.
    The app also gates the test on wear status 2B25 first (TLV
    `01 00 02 00` -> tag 1 = left worn, tag 2 = right worn, live frame
    `5a0009002b25010101020100acde`); this handler does not read 2B25,
    gating is left to the client.

    Note: `2B26 01 00` without a prior `2B26 03 00` is answered with
    tag 2 = 2 and no measurement runs (live-proven), so "start" always
    sends the exit/reset frame first.
    """

    handler_id = "fit_test"
    commands = [CMD_FIT_TEST_RESULT]
    properties = [
        ("fit_test", "status"),
        ("fit_test", "left"),
        ("fit_test", "right"),
        ("fit_test", "verdict"),
        ("fit_test", "control"),
    ]

    # 0/1/4 are reported for the left ear, 2/3/5 for the right one
    _LEFT_CODES = (0, 1, 4)
    _RIGHT_CODES = (2, 3, 5)

    def __init__(self):
        self._left: int | None = None
        self._right: int | None = None

    async def on_init(self):
        self._left = None
        self._right = None
        await self.driver.put_property("fit_test", "status", "idle")
        await self.driver.put_property("fit_test", "left", "")
        await self.driver.put_property("fit_test", "right", "")
        await self.driver.put_property("fit_test", "verdict", "unknown")

    async def on_package(self, package: HuaweiSppPackage):
        # 2B27 result notify, TLV `01 01 <0..5>`
        value = package.find_param(1)
        if len(value) != 1:
            log.warning(f"Unexpected fit test result notify: {package}")
            return

        code = value[0]
        if code in self._LEFT_CODES:
            self._left = code
            side = "left"
        elif code in self._RIGHT_CODES:
            self._right = code
            side = "right"
        else:
            log.warning(f"Unknown fit test result code {code}, ignoring")
            return

        await self.driver.put_property("fit_test", side, str(code))
        await self.driver.put_property("fit_test", "verdict", self._verdict())

        if self._left is not None and self._right is not None:
            # Both ears reported, the measurement is complete
            await self.driver.put_property("fit_test", "status", "result")

    def _verdict(self) -> str:
        if self._left is None or self._right is None:
            return "unknown"
        if self._left == 0 and self._right == 2:
            # REPORT.md §15: "правильно надето" iff left==0 && right==2
            return "good_fit"
        if self._left == 4 or self._right == 5:
            # "Too noisy" - measurement is inconclusive
            return "noisy_environment"
        return "adjust_fit"

    async def set_property(self, group: str, prop: str, value: str):
        if value == "start":
            await self._start_test()
        elif value == "stop":
            await self._stop_test()
        else:
            log.warning(f"Unknown fit_test control value {value}, ignoring")

    async def _start_test(self):
        # 1. Leave any stale fit-test business state first, otherwise the
        #    device skips the measurement and answers with tag 2 = 2
        await self.driver.send_package(HuaweiSppPackage.change_rq(
            CMD_FIT_TEST_WRITE, [(3, b"")],
        ))

        # 2. Start the test, expect tag 2 answer
        resp = await self.driver.send_package(HuaweiSppPackage.change_rq(
            CMD_FIT_TEST_WRITE, [(1, b"")],
        ))

        # Fresh results
        self._left = None
        self._right = None
        await self.driver.put_property("fit_test", "left", "")
        await self.driver.put_property("fit_test", "right", "")
        await self.driver.put_property("fit_test", "verdict", "unknown")

        data = resp.find_param(2) if resp is not None else b""
        if len(data) == 1 and data[0] == 0:
            # "Play the test tone": client must play the tone now (A2DP),
            # see the docstring limitation
            await self.driver.put_property("fit_test", "status", "testing")
        elif len(data) == 1 and data[0] == 2:
            log.warning("Fit test start answered 'show result page', "
                        "no measurement runs (stale device state?)")
            await self.driver.put_property("fit_test", "status", "result")
        else:
            log.warning(f"Fit test start got no parsable answer: {resp}")
            await self.driver.put_property("fit_test", "status", "idle")

    async def _stop_test(self):
        await self.driver.send_package(HuaweiSppPackage.change_rq(
            CMD_FIT_TEST_WRITE, [(3, b"")],
        ))
        # The device answers tag 2 = 2 ("show result page", live-confirmed)
        await self.driver.put_property("fit_test", "status", "result")
