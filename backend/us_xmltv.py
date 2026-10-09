"""Small XMLTV reader for US-English guide data.

The project does not ship a TV schedule. Point TV_GUIDE_XMLTV_PATH at an XMLTV
file obtained from a source whose terms permit your intended use. XMLTV times
must carry a UTC offset so they can be normalized safely.
"""
from __future__ import annotations

import gzip
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
_TIMESTAMP_RE = re.compile(r"^\d{14}\s+[+-]\d{4}$")


def parse_xmltv_timestamp(value: str) -> datetime:
    cleaned = " ".join(value.split())
    if not _TIMESTAMP_RE.match(cleaned):
        raise ValueError(f"XMLTV timestamp must include a UTC offset: {value!r}")
    return datetime.strptime(cleaned, "%Y%m%d%H%M%S %z")


def _text(element: ET.Element | None, fallback: str = "") -> str:
    return (element.text or "").strip() if element is not None else fallback


def load_us_programmes(
    path: str | Path, *, limit_channels: int = 12,
    preferred_channel_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Read plain or gzip-compressed XMLTV and return normalized guide rows.

    If preferred_channel_ids is set, only those source IDs are retained and
    their order is used. Otherwise the first limit_channels are retained.
    This keeps multi-thousand-channel guides from overwhelming the Wii UI.
    """
    xml_path = Path(path).expanduser()
    opener = gzip.open if xml_path.suffix.lower() == ".gz" else open
    with opener(xml_path, "rb") as stream:
        root = ET.parse(stream).getroot()
    names: dict[str, str] = {}
    for channel in root.findall("channel"):
        channel_id = channel.attrib.get("id", "").strip()
        if not channel_id:
            continue
        displays = channel.findall("display-name")
        english = next((item for item in displays if item.attrib.get("lang", "").lower().startswith("en")), None)
        chosen_display = english if english is not None else (displays[0] if displays else None)
        name = _text(chosen_display, channel_id)
        if name:
            names[channel_id] = name[:80]

    if preferred_channel_ids:
        ordered_ids = [
            channel_id for channel_id in preferred_channel_ids
            if channel_id in names
        ]
    else:
        ordered_ids = list(names)[:limit_channels]
    allowed = set(ordered_ids)
    programmes: list[dict[str, Any]] = []
    for element in root.findall("programme"):
        channel_id = element.attrib.get("channel", "")
        if channel_id not in allowed:
            continue
        try:
            start = parse_xmltv_timestamp(element.attrib["start"])
            end = parse_xmltv_timestamp(element.attrib["stop"])
        except (KeyError, ValueError):
            continue
        if end <= start:
            continue
        titles = element.findall("title")
        descriptions = element.findall("desc")
        english_title = next((item for item in titles if item.attrib.get("lang", "").lower().startswith("en")), None)
        english_desc = next((item for item in descriptions if item.attrib.get("lang", "").lower().startswith("en")), None)
        chosen_title = english_title if english_title is not None else (titles[0] if titles else None)
        chosen_desc = english_desc if english_desc is not None else (descriptions[0] if descriptions else None)
        title = _text(chosen_title, "Untitled programme")
        description = _text(chosen_desc)
        programmes.append(
            {
                "channel_id": channel_id,
                "channel_name": names[channel_id],
                "start": start.isoformat(),
                "end": end.isoformat(),
                "title": title[:120],
                "description": description[:500],
                "is_demo": False,
            }
        )
    programmes.sort(key=lambda item: (item["start"], item["channel_id"]))
    return programmes


def configured_us_programmes() -> list[dict[str, Any]] | None:
    """Return imported guide data when configured; otherwise use demo fixtures."""
    path = os.environ.get("TV_GUIDE_XMLTV_PATH", "").strip()
    if not path:
        return None
    xml_path = Path(path).expanduser()
    if not xml_path.is_file():
        return None
    preferred_ids = [
        item.strip()
        for item in os.environ.get("TV_GUIDE_CHANNEL_IDS", "").split(",")
        if item.strip()
    ]
    try:
        return load_us_programmes(
            xml_path, preferred_channel_ids=preferred_ids or None
        )
    except (ET.ParseError, OSError, ValueError):
        return None
