import struct

from tools.inspect_wad import inspect_wad
from tools.normalize_wad_content_size import normalize_content_size


def make_one_content_wad(path):
    header_size = 0x20
    tmd_offset = 0x40
    body_offset = 0x140
    content_table_offset = body_offset + 0xA4
    tmd_size = content_table_offset + 36
    data_offset = (tmd_offset + tmd_size + 0x3F) & ~0x3F
    data_size = 0x40
    blob = bytearray(data_offset + data_size)
    struct.pack_into(">I", blob, 0, header_size)
    blob[4:6] = b"Is"
    struct.pack_into(">I", blob, 20, tmd_size)
    struct.pack_into(">I", blob, 24, data_size)
    tmd = memoryview(blob)[tmd_offset:tmd_offset + tmd_size]
    struct.pack_into(">I", tmd, 0, 0x00010001)
    tmd[body_offset + 0x4C:body_offset + 0x54] = bytes.fromhex("0001000154564731")
    struct.pack_into(">H", tmd, body_offset + 0x9E, 1)
    struct.pack_into(">H", tmd, body_offset + 0xA0, 0)
    record = content_table_offset
    struct.pack_into(">I", tmd, record, 7)
    struct.pack_into(">H", tmd, record + 4, 0)
    struct.pack_into(">H", tmd, record + 6, 1)
    struct.pack_into(">Q", tmd, record + 8, 16)
    path.write_bytes(blob)


def test_normalize_content_size_accounts_for_encrypted_final_block(tmp_path):
    path = tmp_path / "generated.wad"
    make_one_content_wad(path)
    result = normalize_content_size(path)
    assert result["previous_data_size"] == 0x40
    assert result["corrected_data_size"] == 0x10
    assert result["footer_offset_unchanged"] is not None
    inspected = inspect_wad(path)
    assert inspected["validated"] is True
    assert inspected["data_size"] == 0x10
