"""Small XMLTV reader for US-English guide data.

The project does not ship a TV schedule. Point TV_GUIDE_XMLTV_PATH at an XMLTV
file obtained from a source whose terms permit your intended use. XMLTV times
must carry a UTC offset so they can be normalized safely.
"""
from __future__ import annotations

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


def load_us_programmes(path: str | Path, *, limit_channels: int = 12) -> list[dict[str, Any]]:
    """Read XMLTV channel/programme data and return normalized US-English rows.

    This intentionally preserves only useful guide fields. Schedule-source
    selection and licence verification remain the deployer's responsibility.
    """
    root = ET.parse(path).getroot()
    names: dict[str, str] = {}
    for channel in root.findall("channel"):
        channel_id = channel.attrib.get("id", "").strip()
        if not channel_id:
            continue
        displays = channel.findall("display-name")
        english = next((item for item in displays if item.attrib.get("lang", "").lower().startswith("en")), None)
        name = _text(english or (displays[0] if displays else None), channel_id)
        if name:
            names[channel_id] = name[:80]

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
        title = _text(english_title or (titles[0] if titles else None), "Untitled programme")
        description = _text(english_desc or (descriptions[0] if descriptions else None))
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
    try:
        return load_us_programmes(xml_path)
    except (ET.ParseError, OSError, ValueError):
        return None
