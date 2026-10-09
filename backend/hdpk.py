"""Bounds-checked reader for the known TV no Tomo EPG HDPK 001B layout.

This is a structural inspection tool, not a full channel implementation. The
layout follows the public Wii-Kaitai definition, and should still be verified
against an authentic, legally obtained sample before being used for production
data generation.
"""
from __future__ import annotations

import struct
from typing import Any

BASE_OFFSET = 0x20
EPG_HEADER_SIZE = 0x4C
PROGRAM_RECORD_SIZE = 0x18


class HDPKError(ValueError):
    """Raised when an HDPK EPG package is malformed or truncated."""


def _u16(data: memoryview, offset: int, field: str) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise HDPKError(f"{field} is outside the input file.")
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: memoryview, offset: int, field: str) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise HDPKError(f"{field} is outside the input file.")
    return struct.unpack_from(">I", data, offset)[0]


def _table_start(
    data: memoryview, relative_offset: int, count: int, item_size: int, field: str
) -> int:
    """Validate a table whose offsets are relative to byte 0x20."""
    if count < 0 or relative_offset < 0:
        raise HDPKError(f"{field} has a negative count or offset.")
    absolute = BASE_OFFSET + relative_offset
    size = count * item_size
    if count and (absolute < EPG_HEADER_SIZE or absolute + size > len(data)):
        raise HDPKError(
            f"{field} range 0x{absolute:X}..0x{absolute + size:X} "
            f"does not fit in a {len(data)}-byte file."
        )
    return absolute


def parse_epg(data: bytes | bytearray | memoryview) -> dict[str, Any]:
    """Read EPG channels and program records from an HDPK 001B package.

    Offset/count bounds are checked before reading. Program text is referenced
    by offsets into a companion string package, so this parser returns those
    offsets instead of pretending it can decode the missing strings.
    """
    view = memoryview(data)
    if len(view) < EPG_HEADER_SIZE:
        raise HDPKError(
            f"EPG header is truncated: need at least {EPG_HEADER_SIZE} bytes."
        )
    if bytes(view[0:4]) != b"HDPK":
        raise HDPKError("Invalid HDPK magic; expected b'HDPK'.")
    if bytes(view[4:8]) != b"001B":
        raise HDPKError("Unsupported HDPK type; expected b'001B'.")

    declared_length = _u32(view, 8, "file_length")
    if declared_length != len(view):
        raise HDPKError(
            f"Declared file length ({declared_length}) does not match "
            f"actual length ({len(view)})."
        )

    pointer_table_offset = _u32(view, 12, "pointer_table_offset")
    pointer_table_size = _u32(view, 16, "pointer_table_size")
    footer_size = _u32(view, 24, "footer_size")
    region_code = _u16(view, 56, "region_code")
    number_of_channels = _u32(view, 60, "number_of_channels")
    channel_table_offset = _u32(view, 64, "channel_table_offset")
    number_of_aux = _u32(view, 68, "number_of_aux")
    aux_table_offset = _u32(view, 72, "aux_table_offset")

    if footer_size > len(view):
        raise HDPKError("footer_size exceeds the complete file length.")

    pointer_start = _table_start(
        view, pointer_table_offset, pointer_table_size, 4, "pointer_table"
    )
    channel_start = _table_start(
        view, channel_table_offset, number_of_channels, 12, "channel_table"
    )
    aux_start = _table_start(view, aux_table_offset, number_of_aux, 16, "aux_table")

    common_pointers: list[dict[str, int]] = []
    for index in range(pointer_table_size):
        value = _u32(view, pointer_start + index * 4, "pointer_table.value")
        target = BASE_OFFSET + value
        resolved = _u32(view, target, "pointer_table.target")
        common_pointers.append({"offset": value, "value_at_target": resolved})

    channels: list[dict[str, Any]] = []
    for index in range(number_of_channels):
        offset = channel_start + index * 12
        broadcast_type = _u16(view, offset, "channel.broadcast_type")
        channel_number = _u16(view, offset + 2, "channel.channel_number")
        program_count = _u32(view, offset + 4, "channel.program_data_count")
        program_offset = _u32(view, offset + 8, "channel.program_pointer_offset")
        program_start = _table_start(
            view, program_offset, program_count, 8, f"channel[{index}].program_pointers"
        )

        programmes: list[dict[str, int]] = []
        for program_index in range(program_count):
            pointer_pos = program_start + program_index * 8
            program_id = _u32(view, pointer_pos, "program_pointer.program_id")
            record_offset = _u32(view, pointer_pos + 4, "program_pointer.offset")
            record_start = BASE_OFFSET + record_offset
            if record_start < EPG_HEADER_SIZE or record_start + PROGRAM_RECORD_SIZE > len(view):
                raise HDPKError(
                    f"Program record {program_index} for channel {index} is out of bounds."
                )
            programmes.append(
                {
                    "id": program_id,
                    "start_timestamp": _u32(view, record_start, "program.start_timestamp"),
                    "end_timestamp": _u32(view, record_start + 4, "program.end_timestamp"),
                    "text_offset": _u32(view, record_start + 8, "program.text_offset"),
                    "genre": _u16(view, record_start + 12, "program.genre"),
                    "audio_type": _u16(view, record_start + 14, "program.audio_type"),
                    "resolution": _u32(view, record_start + 16, "program.resolution"),
                    "position": _u32(view, record_start + 20, "program.position"),
                }
            )
        channels.append(
            {
                "broadcast_type": broadcast_type,
                "channel_number": channel_number,
                "program_count": program_count,
                "programmes": programmes,
            }
        )

    auxiliary_entries: list[dict[str, Any]] = []
    for index in range(number_of_aux):
        offset = aux_start + index * 16
        start_timestamp = _u32(view, offset, "aux.start_timestamp")
        end_timestamp = _u32(view, offset + 4, "aux.end_timestamp")
        nested_count = _u32(view, offset + 8, "aux.nested_count")
        nested_offset = _u32(view, offset + 12, "aux.nested_offset")
        nested_start = _table_start(
            view, nested_offset, nested_count, 16, f"aux[{index}].nested_records"
        )
        nested_records = [
            {
                "value_1": _u32(view, nested_start + child * 16, "aux.value_1"),
                "value_2": _u32(view, nested_start + child * 16 + 4, "aux.value_2"),
                "value_3": _u32(view, nested_start + child * 16 + 8, "aux.value_3"),
                "value_4": _u32(view, nested_start + child * 16 + 12, "aux.value_4"),
            }
            for child in range(nested_count)
        ]
        auxiliary_entries.append(
            {
                "start_timestamp": start_timestamp,
                "end_timestamp": end_timestamp,
                "nested_records": nested_records,
            }
        )

    return {
        "format": "HDPK",
        "type": "001B",
        "file_length": declared_length,
        "footer_size": footer_size,
        "region_code": region_code,
        "common_pointers": common_pointers,
        "channels": channels,
        "auxiliary_entries": auxiliary_entries,
    }
