import struct

from tools.inspect_wad import inspect_wad
from tools.normalize_wad_content_size import normalize_content_size
from tests.test_wad_inspector import make_synthetic_wad


def test_normalize_content_size_accounts_for_encrypted_final_block(tmp_path):
    path = tmp_path / "generated.wad"
    make_synthetic_wad(path)
    blob = bytearray(path.read_bytes())
    # Simulate libWiiSharp's header bug: plaintext final size is 16 here,
    # but the test writer declares 64 bytes of padding in the data section.
    struct.pack_into(">I", blob, 24, 0x40)
    path.write_bytes(blob)

    result = normalize_content_size(path)
    assert result["previous_data_size"] == 0x40
    assert result["corrected_data_size"] == 0x10
    assert result["footer_offset_unchanged"] is not None
    inspected = inspect_wad(path)
    assert inspected["validated"] is True
    assert inspected["data_size"] == 0x10
