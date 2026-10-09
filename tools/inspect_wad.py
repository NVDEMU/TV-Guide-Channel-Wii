#!/usr/bin/env python3
"""Inspect a Wii WAD envelope and its clear TMD metadata without modifying it.

This validates section sizes/offsets and content records. It does not decrypt
content, verify signatures, or prove that a WAD is safe to install.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HEADER_SIZE = 0x20
WAD_ALIGNMENT = 0x40
CONTENT_ALIGNMENT = 0x10
TMD_SIGNATURE_BODY_OFFSETS = {
    0x00010000: 0x240,  # RSA-4096
    0x00010001: 0x140,  # RSA-2048
    0x00010002: 0x080,  # ECDSA
}


class WadFormatError(ValueError):
    """Raised when a WAD envelope or TMD content table is inconsistent."""


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def _u16(data: bytes, offset: int, label: str) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise WadFormatError(f"{label} is outside the input.")
    return int.from_bytes(data[offset : offset + 2], "big")


def _u32(data: bytes, offset: int, label: str) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise WadFormatError(f"{label} is outside the input.")
    return int.from_bytes(data[offset : offset + 4], "big")


def _u64(data: bytes, offset: int, label: str) -> int:
    if offset < 0 or offset + 8 > len(data):
        raise WadFormatError(f"{label} is outside the input.")
    return int.from_bytes(data[offset : offset + 8], "big")


def inspect_wad(path: str | Path) -> dict[str, Any]:
    """Return validated WAD header/TMD metadata for a local file."""
    wad_path = Path(path)
    data = wad_path.read_bytes()
    if len(data) < HEADER_SIZE:
        raise WadFormatError("File is too short to contain a WAD header.")

    header_size = _u32(data, 0, "header_size")
    wad_type_bytes = data[4:6]
    cert_size = _u32(data, 8, "cert_chain_size")
    crl_size = _u32(data, 12, "crl_size")
    ticket_size = _u32(data, 16, "ticket_size")
    tmd_size = _u32(data, 20, "tmd_size")
    data_size = _u32(data, 24, "data_size")
    footer_size = _u32(data, 28, "footer_size")

    if header_size != HEADER_SIZE:
        raise WadFormatError(f"Unexpected WAD header size: {header_size}.")
    if wad_type_bytes not in (b"Is", b"ib"):
        raise WadFormatError(
            f"Unexpected WAD type marker {wad_type_bytes!r}; expected b'Is' or b'ib'."
        )

    cursor = _align(header_size, WAD_ALIGNMENT)
    cert_offset = cursor
    cursor = _align(cursor + cert_size, WAD_ALIGNMENT)
    crl_offset = cursor
    cursor = _align(cursor + crl_size, WAD_ALIGNMENT)
    ticket_offset = cursor
    cursor = _align(cursor + ticket_size, WAD_ALIGNMENT)
    tmd_offset = cursor
    cursor = _align(cursor + tmd_size, WAD_ALIGNMENT)
    data_offset = cursor
    data_end = data_offset + data_size
    footer_offset = _align(data_end, WAD_ALIGNMENT)
    expected_file_size = footer_offset + footer_size

    if expected_file_size != len(data):
        raise WadFormatError(
            "WAD section sizes do not match file length: "
            f"expected {expected_file_size} bytes, found {len(data)}."
        )
    if tmd_size == 0 or tmd_offset + tmd_size > len(data):
        raise WadFormatError("TMD section is empty or truncated.")

    tmd = data[tmd_offset : tmd_offset + tmd_size]
    signature_type = _u32(tmd, 0, "tmd.signature_type")
    try:
        body_offset = TMD_SIGNATURE_BODY_OFFSETS[signature_type]
    except KeyError as exc:
        raise WadFormatError(
            f"Unsupported TMD signature type 0x{signature_type:08X}."
        ) from exc

    title_id_offset = body_offset + 0x4C
    content_count_offset = body_offset + 0x9E
    boot_index_offset = body_offset + 0xA0
    content_table_offset = body_offset + 0xA4
    if title_id_offset + 8 > len(tmd):
        raise WadFormatError("TMD title ID is truncated.")

    title_id = tmd[title_id_offset : title_id_offset + 8]
    region_code = _u16(tmd, body_offset + 0x5C, "tmd.region")
    region_names = {0: "Japan", 1: "USA", 2: "Europe", 3: "Free"}
    content_count = _u16(tmd, content_count_offset, "tmd.content_count")
    boot_index = _u16(tmd, boot_index_offset, "tmd.boot_index")
    table_end = content_table_offset + content_count * 36
    if table_end > len(tmd):
        raise WadFormatError("TMD content table is truncated.")

    contents: list[dict[str, Any]] = []
    content_cursor = data_offset
    for index in range(content_count):
        record_offset = content_table_offset + index * 36
        content_id = _u32(tmd, record_offset, f"content[{index}].id")
        content_index = _u16(tmd, record_offset + 4, f"content[{index}].index")
        content_type = _u16(tmd, record_offset + 6, f"content[{index}].type")
        content_length = _u64(tmd, record_offset + 8, f"content[{index}].size")
        encrypted_length = _align(content_length, CONTENT_ALIGNMENT)
        content_end = content_cursor + encrypted_length
        if content_end > data_end:
            raise WadFormatError(
                f"Content record {index} extends beyond the WAD data section."
            )
        contents.append(
            {
                "content_id": content_id,
                "index": content_index,
                "type": f"0x{content_type:04X}",
                "plain_size": content_length,
                "stored_size": encrypted_length,
                "data_offset": content_cursor,
            }
        )
        content_cursor = _align(content_end, WAD_ALIGNMENT)

    if content_cursor > data_end:
        raise WadFormatError("Padded content records exceed the WAD data section.")

    return {
        "file": wad_path.name,
        "file_size": len(data),
        "wad_type": wad_type_bytes.decode("ascii"),
        "validated": True,
        "title_id": title_id.hex().upper(),
        "title_id_suffix": title_id[4:].decode("ascii", errors="replace"),
        "tmd_signature_type": f"0x{signature_type:08X}",
        "content_count": content_count,
        "boot_index": boot_index,
        "region_code": region_code,
        "region_name": region_names.get(region_code, f"Unknown ({region_code})"),
        "data_size": data_size,
        "section_offsets": {
            "cert": cert_offset,
            "crl": crl_offset,
            "ticket": ticket_offset,
            "tmd": tmd_offset,
            "data": data_offset,
            "footer": footer_offset,
        },
        "contents": contents,
        "notes": [
            "This is structural validation only; it does not decrypt content or verify signatures.",
            "The TMD region field is read at the TMD body's region field offset; nearby reserved bytes must not be interpreted as region metadata.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wad", type=Path, help="local WAD file to inspect")
    args = parser.parse_args()
    try:
        result = inspect_wad(args.wad)
    except (OSError, WadFormatError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
