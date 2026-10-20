import pytest

from openfreebuds.driver.huawei.driver.debug import FbDriverHuaweiGenericFixture
from openfreebuds.driver.huawei.handler import OfbHuaweiFitTestHandler
from openfreebuds.driver.huawei.utils import crc16_xmodem

# Frames captured live from HUAWEI FreeBuds 5i
# (freebuds evidence/spp_round9b_2026-10-20.txt, session "fit check start+exit"):
FIT_TEST_START_TX = bytes.fromhex("5a0005002b260100371f")          # 2B26 01 00 (start)
FIT_TEST_START_ANSWER = bytes.fromhex("5a0006002b26020100eb57")    # 2B26 tag 2 = 0 (play tone)
FIT_TEST_EXIT_TX = bytes.fromhex("5a0005002b260300517d")           # 2B26 03 00 (exit/reset)
FIT_TEST_RESULT_PAGE_ANSWER = bytes.fromhex("5a0006002b26020102cb15")  # 2B26 tag 2 = 2 (result page)


def _fit_notify(value: int) -> bytes:
    # NOTE: the 2B27 result notify was NEVER observed live: without the test
    # tone the measurement does not complete (REPORT.md §24, "2B27 не пришёл
    # ни разу"). The frame is rebuilt from the structure documented in
    # PROTOCOL.md §15 (notify TLV `01 01 <0..5>`) with a valid CRC16/XMODEM
    # computed by the same code the driver uses on RX.
    frame = bytes.fromhex("5a0006002b270101") + bytes([value])
    return frame + crc16_xmodem(frame)


NOTIFY_LEFT_GOOD = _fit_notify(0)      # left ear: good fit
NOTIFY_LEFT_ADJUST = _fit_notify(1)    # left ear: adjust tip size
NOTIFY_RIGHT_GOOD = _fit_notify(2)     # right ear: good fit
NOTIFY_RIGHT_ADJUST = _fit_notify(3)   # right ear: adjust tip size
NOTIFY_LEFT_NOISY = _fit_notify(4)     # left ear: too noisy
NOTIFY_RIGHT_NOISY = _fit_notify(5)    # right ear: too noisy


def _make_driver(responses: dict[bytes, list[bytes]]) -> FbDriverHuaweiGenericFixture:
    return FbDriverHuaweiGenericFixture(
        handlers=[OfbHuaweiFitTestHandler()],
        package_response_model=responses,
    )


@pytest.mark.asyncio
async def test_fit_test_start():
    driver = _make_driver({
        FIT_TEST_EXIT_TX: [FIT_TEST_RESULT_PAGE_ANSWER],
        FIT_TEST_START_TX: [FIT_TEST_START_ANSWER],
    })
    await driver.start()

    assert await driver.get_property("fit_test", "status") == "idle"

    await driver.set_property("fit_test", "control", "start")

    sent = [pkg for kind, pkg in driver.package_log if kind == "send"]
    # start = reset (03 00) first, then start (01 00)
    assert sent == [FIT_TEST_EXIT_TX, FIT_TEST_START_TX]
    assert await driver.get_property("fit_test", "status") == "testing"
    assert await driver.get_property("fit_test", "left") == ""
    assert await driver.get_property("fit_test", "right") == ""
    assert await driver.get_property("fit_test", "verdict") == "unknown"


@pytest.mark.asyncio
async def test_fit_test_start_answer_result_page():
    # Device answers the start with tag 2 = 2 ("show result page") when
    # the fit-test state was stale; no measurement runs in that case
    driver = _make_driver({
        FIT_TEST_EXIT_TX: [FIT_TEST_RESULT_PAGE_ANSWER],
        FIT_TEST_START_TX: [FIT_TEST_RESULT_PAGE_ANSWER],
    })
    await driver.start()

    await driver.set_property("fit_test", "control", "start")
    assert await driver.get_property("fit_test", "status") == "result"


@pytest.mark.asyncio
async def test_fit_test_verdict_good_fit():
    driver = _make_driver({
        FIT_TEST_EXIT_TX: [FIT_TEST_RESULT_PAGE_ANSWER],
        FIT_TEST_START_TX: [FIT_TEST_START_ANSWER],
    })
    await driver.start()
    await driver.set_property("fit_test", "control", "start")

    await driver._handle_raw_pkg(NOTIFY_LEFT_GOOD)
    assert await driver.get_property("fit_test", "left") == "0"
    # Right ear not reported yet
    assert await driver.get_property("fit_test", "verdict") == "unknown"
    assert await driver.get_property("fit_test", "status") == "testing"

    await driver._handle_raw_pkg(NOTIFY_RIGHT_GOOD)
    assert await driver.get_property("fit_test", "right") == "2"
    # "Worn correctly" rule from REPORT.md §15: left == 0 && right == 2
    assert await driver.get_property("fit_test", "verdict") == "good_fit"
    assert await driver.get_property("fit_test", "status") == "result"


@pytest.mark.asyncio
async def test_fit_test_verdict_adjust_fit():
    driver = _make_driver({
        FIT_TEST_EXIT_TX: [FIT_TEST_RESULT_PAGE_ANSWER],
        FIT_TEST_START_TX: [FIT_TEST_START_ANSWER],
    })
    await driver.start()
    await driver.set_property("fit_test", "control", "start")

    await driver._handle_raw_pkg(NOTIFY_LEFT_ADJUST)
    await driver._handle_raw_pkg(NOTIFY_RIGHT_ADJUST)
    assert await driver.get_property("fit_test", "verdict") == "adjust_fit"


@pytest.mark.asyncio
async def test_fit_test_verdict_noisy_environment():
    driver = _make_driver({
        FIT_TEST_EXIT_TX: [FIT_TEST_RESULT_PAGE_ANSWER],
        FIT_TEST_START_TX: [FIT_TEST_START_ANSWER],
    })
    await driver.start()
    await driver.set_property("fit_test", "control", "start")

    await driver._handle_raw_pkg(NOTIFY_LEFT_NOISY)
    await driver._handle_raw_pkg(NOTIFY_RIGHT_NOISY)
    assert await driver.get_property("fit_test", "verdict") == "noisy_environment"


@pytest.mark.asyncio
async def test_fit_test_start_resets_previous_results():
    driver = _make_driver({
        FIT_TEST_EXIT_TX: [FIT_TEST_RESULT_PAGE_ANSWER],
        FIT_TEST_START_TX: [FIT_TEST_START_ANSWER],
    })
    await driver.start()
    await driver.set_property("fit_test", "control", "start")
    await driver._handle_raw_pkg(NOTIFY_LEFT_GOOD)
    await driver._handle_raw_pkg(NOTIFY_RIGHT_GOOD)
    assert await driver.get_property("fit_test", "verdict") == "good_fit"

    await driver.set_property("fit_test", "control", "start")
    assert await driver.get_property("fit_test", "left") == ""
    assert await driver.get_property("fit_test", "right") == ""
    assert await driver.get_property("fit_test", "verdict") == "unknown"
    assert await driver.get_property("fit_test", "status") == "testing"


@pytest.mark.asyncio
async def test_fit_test_stop():
    driver = _make_driver({
        FIT_TEST_EXIT_TX: [FIT_TEST_RESULT_PAGE_ANSWER],
    })
    await driver.start()

    await driver.set_property("fit_test", "control", "stop")

    assert ("send", FIT_TEST_EXIT_TX) in driver.package_log
    assert await driver.get_property("fit_test", "status") == "result"
    assert await driver.get_property("fit_test", "verdict") == "unknown"


@pytest.mark.asyncio
async def test_fit_test_unknown_control_value():
    driver = _make_driver({})
    await driver.start()

    await driver.set_property("fit_test", "control", "restart")
    assert driver.package_log == []
