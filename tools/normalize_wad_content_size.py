#!/usr/bin/env python3
"""Normalize WadPakk/libWiiSharp's encrypted data-size header field.

libWiiSharp calculates WAD contentSize using plaintext size for the final
content, while AES-CBC storage rounds that content up to a 16-byte block.
This adjusts only the WAD header's data-size field, after verifying the
section layout and proving that the aligned footer offset remains unchanged.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Executing this script by path sets sys.path[0] to tools/, so add the repo
# root explicitly before importing the shared WAD parser.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inspect_wad import (
    CONTENT_ALIGNMENT,
    HEADER_SIZE,
    WAD_ALIGNMENT,
    TMD_SIGNATURE_BODY_OFFSETS,
    _align,
    _u16,
    _u32,
    _u64,
)


def normalize_content_size(path: str | Path) -> dict[str, int | str]:
    wad_path = Path(path)
    blob = bytearray(wad_path.read_bytes())
    if len(blob) < HEADER_SIZE:
        raise ValueError("WAD too short.")
    header_size = _u32(blob, 0, "header_size")
    if header_size != HEADER_SIZE or blob[4:6] not in (b"Is", b"ib"):
        raise ValueError("Unsupported WAD header.")
    cert_size = _u32(blob, 8, "cert_size")
    crl_size = _u32(blob, 12, "crl_size")
    ticket_size = _u32(blob, 16, "ticket_size")
    tmd_size = _u32(blob, 20, "tmd_size")
    current_data_size = _u32(blob, 24, "data_size")
    footer_size = _u32(blob, 28, "footer_size")

    cursor = _align(header_size, WAD_ALIGNMENT)
    cursor = _align(cursor + cert_size, WAD_ALIGNMENT)
    cursor = _align(cursor + crl_size, WAD_ALIGNMENT)
    cursor = _align(cursor + ticket_size, WAD_ALIGNMENT)
    tmd_offset = _align(cursor, WAD_ALIGNMENT)
    data_offset = _align(tmd_offset + tmd_size, WAD_ALIGNMENT)
    tmd = bytes(blob[tmd_offset:tmd_offset + tmd_size])
    if not tmd:
        raise ValueError("Empty TMD.")
    sig_type = _u32(tmd, 0, "tmd.signature_type")
    body_offset = TMD_SIGNATURE_BODY_OFFSETS.get(sig_type)
    if body_offset is None:
        raise ValueError(f"Unsupported TMD signature type 0x{sig_type:08X}.")
    count = _u16(tmd, body_offset + 0x9E, "tmd.content_count")
    table_offset = body_offset + 0xA4
    if table_offset + count * 36 > len(tmd):
        raise ValueError("TMD content table truncated.")

    records: list[tuple[int, int]] = []
    seen: set[int] = set()
    for i in range(count):
        off = table_offset + i * 36
        index = _u16(tmd, off + 4, f"content[{i}].index")
        size = _u64(tmd, off + 8, f"content[{i}].size")
        if index in seen:
            raise ValueError(f"Duplicate content index: {index}.")
        seen.add(index)
        records.append((index, _align(size, CONTENT_ALIGNMENT)))
    records.sort(key=lambda row: row[0])

    if not records:
        raise ValueError("No content records.")
    expected = 0
    for pos, (_, encrypted_size) in enumerate(records):
        if pos < len(records) - 1:
            expected += _align(encrypted_size, WAD_ALIGNMENT)
        else:
            expected += encrypted_size

    old_footer_offset = _align(data_offset + current_data_size, WAD_ALIGNMENT)
    new_footer_offset = _align(data_offset + expected, WAD_ALIGNMENT)
    if old_footer_offset != new_footer_offset:
        raise ValueError(
            "Correcting encrypted content length would move the footer; refusing to rewrite."
        )
    if new_footer_offset + footer_size > len(blob):
        raise ValueError("Computed footer position exceeds the WAD file.")
    if current_data_size > len(blob) or expected <= 0:
        raise ValueError("Invalid data size.")

    blob[24:28] = expected.to_bytes(4, "big")
    wad_path.write_bytes(blob)
    return {
        "file": wad_path.name,
        "previous_data_size": current_data_size,
        "corrected_data_size": expected,
        "size_delta": expected - current_data_size,
        "footer_offset_unchanged": new_footer_offset,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wad", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(normalize_content_size(args.wad), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
