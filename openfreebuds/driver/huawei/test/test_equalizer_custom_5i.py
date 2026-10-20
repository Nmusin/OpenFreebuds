import json
import pytest

from openfreebuds.driver.huawei.driver.debug import FbDriverHuaweiGenericFixture
from openfreebuds.driver.huawei.handler import OfbHuaweiEqualizerPresetHandler
from openfreebuds.driver.huawei.handler.config_equalizer import _build_payload
from openfreebuds.driver.huawei.package import HuaweiSppPackage

# Frames captured live from HUAWEI FreeBuds 5i
# (freebuds SET_COMMANDS.md §2, evidence/spp_persist*_2026-10-20.txt)
READ_2B4A_RQ = bytes.fromhex("5a0013002b4a01000200030004000500060007000800e90c")
EQ_ACK_OK = bytes.fromhex("5a0009002b497f04000186a0b3c6")  # 7F 04 000186A0 = success
SELECT_SLOT_100 = bytes.fromhex("5a0006002b490101641319")  # TLV 01 01 64 (plugin frame)
SELECT_DEFAULT = bytes.fromhex("5a0006002b490101012f1a")  # TLV 01 01 01 (plugin frame)
HARMAN_UPDATE_TX = bytes.fromhex(
    "5a0020002b4901016402010a050101030a0ff6f6f6001914e241f604064861726d616e59ec")
CUSTOM_24B_NAME_TX = bytes.fromhex(
    "5a0032002b4901016502010a050101030afb141e0a0000e7f60a000418"
    "4d7920437573746f6d2045512032342062797465732121214aad")


def _read_resp(current_id: int) -> bytes:
    """
    Real 2B4A response structure of 5i: tags 1/2/3/4 only, custom slot list
    (tags 6/7/8) is never returned by this firmware. CRC is auto-computed.
    """
    return HuaweiSppPackage(cmd=b"\x2b\x4a", parameters=[
        (1, 1), (2, current_id), (3, bytes([1, 2, 3, 9])), (4, 1),
    ]).to_bytes()


assert _read_resp(1).hex() == "5a0012002b4a010101020101030401020309040101f8d7"
assert _read_resp(100).hex() == "5a0012002b4a01010102016403040102030904010171b0"


def _eq_tx(mode_id: int, name: str, rows: list[int]) -> bytes:
    data = b"".join(x.to_bytes(1, signed=True, byteorder="big") for x in rows)
    return HuaweiSppPackage.change_rq(
        b"\x2b\x49", _build_payload(mode_id, name, data, 1, (1, 2, 5, 3, 4))
    ).to_bytes()


@pytest.mark.asyncio
async def test_custom_eq_create_update_select():
    driver = FbDriverHuaweiGenericFixture(
        handlers=[
            OfbHuaweiEqualizerPresetHandler(w_presets={
                1: "default",
                2: "hardbass",
                3: "treble",
                9: "voices",
            }, w_custom=True, w_custom_local=True),
        ],
        package_response_model={
            READ_2B4A_RQ: [_read_resp(1)],
            _eq_tx(100, "Harman", [0] * 10): [EQ_ACK_OK],
            HARMAN_UPDATE_TX: [EQ_ACK_OK],
            SELECT_DEFAULT: [EQ_ACK_OK],
            SELECT_SLOT_100: [EQ_ACK_OK],
        }
    )

    await driver.start()
    assert await driver.get_property("sound", "equalizer_preset") == "equalizer_preset_default"

    # Create custom preset in slot 100 (device switches current mode to it)
    driver.package_response_model[READ_2B4A_RQ] = [_read_resp(100)]
    await driver.set_property("sound", "equalizer_preset", "Harman")
    assert ("send", _eq_tx(100, "Harman", [0] * 10)) in driver.package_log
    assert await driver.get_property("sound", "equalizer_preset") == "Harman"

    # Update rows: wire frame must match the live-captured one byte-for-byte
    # (slot 100, tag order 01 02 05 03 04, 10 signed int8 values)
    harman_rows = [15, -10, -10, -10, 0, 25, 20, -30, 65, -10]
    await driver.set_property("sound", "equalizer_rows", json.dumps(harman_rows))
    assert ("send", HARMAN_UPDATE_TX) in driver.package_log
    assert json.loads(await driver.get_property("sound", "equalizer_rows")) == harman_rows

    # Switch to a built-in preset and back: re-select of an existing
    # client-side slot goes as a bare id frame `01 01 64`
    driver.package_response_model[READ_2B4A_RQ] = [_read_resp(1)]
    await driver.set_property("sound", "equalizer_preset", "equalizer_preset_default")
    assert await driver.get_property("sound", "equalizer_preset") == "equalizer_preset_default"

    driver.package_response_model[READ_2B4A_RQ] = [_read_resp(100)]
    await driver.set_property("sound", "equalizer_preset", "Harman")
    assert ("send", SELECT_SLOT_100) in driver.package_log
    assert await driver.get_property("sound", "equalizer_preset") == "Harman"
    assert json.loads(await driver.get_property("sound", "equalizer_rows")) == harman_rows


@pytest.mark.asyncio
async def test_custom_eq_24_byte_name_and_truncation():
    driver = FbDriverHuaweiGenericFixture(
        handlers=[
            OfbHuaweiEqualizerPresetHandler(w_presets={
                1: "default",
                2: "hardbass",
                3: "treble",
                9: "voices",
            }, w_custom=True, w_custom_local=True),
        ],
        package_response_model={
            READ_2B4A_RQ: [_read_resp(1)],
            _eq_tx(100, "Harman", [0] * 10): [EQ_ACK_OK],
            _eq_tx(101, "My Custom EQ 24 bytes!!!", [0] * 10): [EQ_ACK_OK],
            CUSTOM_24B_NAME_TX: [EQ_ACK_OK],
            _eq_tx(102, "Х" * 12, [0] * 10): [EQ_ACK_OK],
        }
    )

    await driver.start()

    # Occupy slot 100 first so the next preset lands in slot 101
    driver.package_response_model[READ_2B4A_RQ] = [_read_resp(100)]
    await driver.set_property("sound", "equalizer_preset", "Harman")

    # Preset #2 in slot 101, name of exactly 24 UTF-8 bytes, Rock params:
    # wire frame must match the reference one byte-for-byte
    driver.package_response_model[READ_2B4A_RQ] = [_read_resp(101)]
    await driver.set_property("sound", "equalizer_preset", "My Custom EQ 24 bytes!!!")
    rock_rows = [-5, 20, 30, 10, 0, 0, -25, -10, 10, 0]
    await driver.set_property("sound", "equalizer_rows", json.dumps(rock_rows))
    assert ("send", CUSTOM_24B_NAME_TX) in driver.package_log

    # Preset #3 in slot 102: 20-char Cyrillic name is 40 bytes UTF-8, wire
    # name must be truncated to 24 bytes on a character boundary
    driver.package_response_model[READ_2B4A_RQ] = [_read_resp(102)]
    await driver.set_property("sound", "equalizer_preset", "Х" * 20)
    sent_pkgs = [HuaweiSppPackage.from_bytes(pkg) for action, pkg in driver.package_log
                 if action == "send" and pkg[4:6] == b"\x2b\x49"]
    wire_name = sent_pkgs[-1].find_param(4)
    assert wire_name == ("Х" * 12).encode()
    assert len(wire_name) == 24
    # UI label is kept intact, only the wire name is capped
    assert await driver.get_property("sound", "equalizer_preset") == "Х" * 20


def test_wire_name_limit():
    handler = OfbHuaweiEqualizerPresetHandler(w_presets={1: "default"},
                                              w_custom=True, w_custom_local=True)
    # Exactly 24 bytes stays untouched
    assert handler._wire_name("My Custom EQ 24 bytes!!!") == "My Custom EQ 24 bytes!!!"
    # Multi-byte characters are cut on a character boundary, not mid-codepoint
    assert len(handler._wire_name("Х" * 20).encode("utf8")) == 24
