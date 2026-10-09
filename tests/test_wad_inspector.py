import struct

import pytest

from tools.inspect_wad import WadFormatError, inspect_wad


def make_synthetic_wad(path) -> None:
    """Create a tiny structurally valid WAD with one synthetic content record."""
    header_size = 0x20
    tmd_offset = 0x40
    body_offset = 0x140
    content_table_offset = body_offset + 0xA4
    content_size = 16
    tmd_size = content_table_offset + 36
    data_offset = (tmd_offset + tmd_size + 0x3F) & ~0x3F
    data_size = 0x40
    total_size = data_offset + data_size

    blob = bytearray(total_size)
    struct.pack_into(">I", blob, 0, header_size)
    blob[4:6] = b"Is"
    struct.pack_into(">I", blob, 20, tmd_size)
    struct.pack_into(">I", blob, 24, data_size)

    tmd = memoryview(blob)[tmd_offset : tmd_offset + tmd_size]
    struct.pack_into(">I", tmd, 0, 0x00010001)
    tmd[body_offset + 0x4C : body_offset + 0x54] = bytes.fromhex("0001000154564731")
    struct.pack_into(">H", tmd, body_offset + 0x9E, 1)
    struct.pack_into(">H", tmd, body_offset + 0xA0, 0)
    record = content_table_offset
    struct.pack_into(">I", tmd, record, 7)
    struct.pack_into(">H", tmd, record + 4, 0)
    struct.pack_into(">H", tmd, record + 6, 1)
    struct.pack_into(">Q", tmd, record + 8, content_size)
    # content data is zero-filled; signature and content hash are test fixtures.
    path.write_bytes(blob)


def test_inspect_wad_extracts_title_and_validates_lengths(tmp_path) -> None:
    path = tmp_path / "tiny.wad"
    make_synthetic_wad(path)
    result = inspect_wad(path)
    assert result["validated"] is True
    assert result["title_id"] == "0001000154564731"
    assert result["title_id_suffix"] == "TVG1"
    assert result["content_count"] == 1
    assert result["file_size"] == 0x40 + 0x140 + 0xA4 + 36 + 0x40


def test_inspect_wad_rejects_section_length_mismatch(tmp_path) -> None:
    path = tmp_path / "bad.wad"
    make_synthetic_wad(path)
    blob = bytearray(path.read_bytes())
    struct.pack_into(">I", blob, 24, 0x80)
    path.write_bytes(blob)
    with pytest.raises(WadFormatError, match="section sizes do not match"):
        inspect_wad(path)


def test_inspect_wad_rejects_truncated_tmd_content_table(tmp_path) -> None:
    path = tmp_path / "bad-tmd.wad"
    make_synthetic_wad(path)
    blob = bytearray(path.read_bytes())
    # Claim an extra TMD content without changing the TMD length.
    tmd_offset = 0x40
    struct.pack_into(">H", blob, tmd_offset + 0x140 + 0x9E, 2)
    path.write_bytes(blob)
    with pytest.raises(WadFormatError, match="TMD content table is truncated"):
        inspect_wad(path)
