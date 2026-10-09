import struct

import pytest

from backend.hdpk import HDPKError, parse_epg


def make_synthetic_epg() -> bytes:
    """Make a deliberately small fixture based on the public EPG layout."""
    data = bytearray(0x98)  # 152 bytes; one 24-byte programme record at 0x80
    data[0:4] = b"HDPK"
    data[4:8] = b"001B"
    struct.pack_into(">I", data, 0x08, len(data))   # complete file length
    struct.pack_into(">I", data, 0x0C, 0)           # common pointer table offset
    struct.pack_into(">I", data, 0x10, 0)           # common pointer count
    struct.pack_into(">I", data, 0x18, 0)           # footer size
    struct.pack_into(">H", data, 0x38, 123)         # region code fixture
    struct.pack_into(">I", data, 0x3C, 1)            # channel count
    struct.pack_into(">I", data, 0x40, 48)           # channel table at 0x50
    struct.pack_into(">I", data, 0x44, 0)            # auxiliary count
    struct.pack_into(">I", data, 0x48, 0)            # auxiliary table offset

    # Channel: digital terrestrial, channel 7, one program pointer at 0x60.
    struct.pack_into(">HHII", data, 0x50, 9, 7, 1, 64)
    struct.pack_into(">II", data, 0x60, 9001, 96)
    # Fixed 0x18-byte program record at 0x80.
    struct.pack_into(">IIIHHII", data, 0x80, 100, 160, 0x20, 4, 1, 2, 3)
    return bytes(data)


def test_parse_synthetic_epg_header_channel_and_programme() -> None:
    parsed = parse_epg(make_synthetic_epg())
    assert parsed["format"] == "HDPK"
    assert parsed["type"] == "001B"
    assert parsed["region_code"] == 123
    assert len(parsed["channels"]) == 1

    channel = parsed["channels"][0]
    assert channel["broadcast_type"] == 9
    assert channel["channel_number"] == 7
    assert channel["programmes"][0] == {
        "id": 9001,
        "start_timestamp": 100,
        "end_timestamp": 160,
        "text_offset": 0x20,
        "genre": 4,
        "audio_type": 1,
        "resolution": 2,
        "position": 3,
    }


def test_reject_invalid_magic() -> None:
    data = bytearray(make_synthetic_epg())
    data[0:4] = b"NOPE"
    with pytest.raises(HDPKError, match="magic"):
        parse_epg(data)


def test_reject_declared_length_mismatch() -> None:
    data = bytearray(make_synthetic_epg())
    struct.pack_into(">I", data, 8, len(data) - 1)
    with pytest.raises(HDPKError, match="Declared file length"):
        parse_epg(data)


def test_reject_channel_table_outside_file() -> None:
    data = bytearray(make_synthetic_epg())
    struct.pack_into(">I", data, 0x40, 120)
    with pytest.raises(HDPKError, match="channel_table"):
        parse_epg(data)


def test_reject_programme_record_outside_file() -> None:
    data = bytearray(make_synthetic_epg())
    struct.pack_into(">I", data, 0x64, 0xFFFFFFF0)
    with pytest.raises(HDPKError, match="Program record"):
        parse_epg(data)
