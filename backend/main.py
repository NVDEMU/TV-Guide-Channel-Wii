"""Development guide API for the TV Guide Channel Wii revival.

The channel and programme records generated here are intentionally synthetic.
This API is not the original channel's network protocol.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Response

APP_NAME = "TV Guide Channel Wii API"
TOKYO = ZoneInfo("Asia/Tokyo")
MAX_WINDOW = timedelta(days=7)

app = FastAPI(
    title=APP_NAME,
    description=(
        "A development API for guide-data experiments. All current channel and "
        "programme listings are synthetic placeholders, not live TV data and "
        "not a verified implementation of the original Wii protocol."
    ),
    version="0.1.0",
)

REGION: dict[str, str] = {
    "id": "jp-demo",
    "name": "Japan — demo region",
    "description": (
        "Placeholder region for API tests only; it does not represent a real "
        "prefecture, lineup, or broadcaster."
    ),
    "timezone": "Asia/Tokyo",
}

CHANNELS: list[dict[str, Any]] = [
    {
        "id": "jp-demo-terrestrial-01",
        "name": "Demo Terrestrial 1",
        "name_ja": "サンプル地上波 1",
        "broadcast_type": "terrestrial-digital",
        "channel_number": "1",
        "region": "jp-demo",
    },
    {
        "id": "jp-demo-terrestrial-02",
        "name": "Demo Terrestrial 2",
        "name_ja": "サンプル地上波 2",
        "broadcast_type": "terrestrial-digital",
        "channel_number": "2",
        "region": "jp-demo",
    },
    {
        "id": "jp-demo-satellite-01",
        "name": "Demo Satellite 1",
        "name_ja": "サンプル衛星放送 1",
        "broadcast_type": "satellite-digital",
        "channel_number": "BS1",
        "region": "jp-demo",
    },
]


def _now_tokyo() -> datetime:
    return datetime.now(timezone.utc).astimezone(TOKYO).replace(microsecond=0)


def _resolve_window(
    start: datetime | None, end: datetime | None
) -> tuple[datetime, datetime]:
    """Resolve optional query bounds and require explicit timezone offsets."""
    now = _now_tokyo()
    if start is None and end is None:
        start, end = now, now + timedelta(hours=24)
    elif start is None:
        assert end is not None
        if end.tzinfo is None or end.utcoffset() is None:
            raise HTTPException(
                status_code=422,
                detail="The 'to' timestamp must include a timezone offset.",
            )
        start = end - timedelta(hours=24)
    elif end is None:
        end = start + timedelta(hours=24)

    assert start is not None and end is not None
    if start.tzinfo is None or start.utcoffset() is None:
        raise HTTPException(
            status_code=422,
            detail="The 'from' timestamp must include a timezone offset.",
        )
    if end.tzinfo is None or end.utcoffset() is None:
        raise HTTPException(
            status_code=422,
            detail="The 'to' timestamp must include a timezone offset.",
        )

    start_local = start.astimezone(TOKYO)
    end_local = end.astimezone(TOKYO)
    if end_local <= start_local:
        raise HTTPException(status_code=422, detail="'to' must be later than 'from'.")
    if end_local - start_local > MAX_WINDOW:
        raise HTTPException(
            status_code=422,
            detail="Requested window is too large; maximum range is 7 days.",
        )
    return start_local, end_local


def _validate_region(region: str) -> None:
    if region != REGION["id"]:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown region '{region}'. Only the jp-demo fixture exists.",
        )


def _build_programmes(
    start: datetime,
    end: datetime,
    channel_id: str | None = None,
) -> list[dict[str, Any]]:
    selected_channels = CHANNELS
    if channel_id is not None:
        selected_channels = [ch for ch in CHANNELS if ch["id"] == channel_id]
        if not selected_channels:
            raise HTTPException(
                status_code=404, detail=f"Unknown demo channel '{channel_id}'."
            )

    programmes: list[dict[str, Any]] = []
    first_hour = start.replace(minute=0, second=0, microsecond=0)
    if first_hour < start:
        first_hour += timedelta(hours=1)

    for channel_index, channel in enumerate(selected_channels):
        current = first_hour
        while current < end:
            slot = (current.hour + channel_index) % 24
            programme_start = current
            programme_end = current + timedelta(hours=1)
            programmes.append(
                {
                    "id": f"{channel['id']}-{programme_start:%Y%m%d%H}",
                    "channel_id": channel["id"],
                    "channel_name": channel["name"],
                    "start": programme_start.isoformat(),
                    "end": programme_end.isoformat(),
                    "title": f"Demo programme {slot + 1:02d}",
                    "title_ja": f"サンプル番組 {slot + 1:02d}",
                    "description": (
                        "Synthetic placeholder schedule for development only. "
                        "This is not real broadcast information."
                    ),
                    "genre": "demo",
                    "is_demo": True,
                }
            )
            current += timedelta(hours=1)

    programmes.sort(key=lambda item: (item["start"], item["channel_id"]))
    return programmes


@app.get("/health", tags=["status"])
def health() -> dict[str, str]:
    """Return a simple readiness result."""
    return {"status": "ok", "service": APP_NAME, "stage": "development"}


@app.get("/api/v1/regions", tags=["guide"])
def list_regions() -> list[dict[str, str]]:
    """List currently configured guide regions."""
    return [REGION]


@app.get("/api/v1/channels", tags=["guide"])
def list_channels(
    region: str = Query(default="jp-demo", description="Guide-region identifier"),
) -> list[dict[str, Any]]:
    """List synthetic channels for a configured region."""
    _validate_region(region)
    return CHANNELS


@app.get("/api/v1/programmes", tags=["guide"])
def list_programmes(
    region: str = Query(default="jp-demo", description="Guide-region identifier"),
    start: datetime | None = Query(
        default=None, alias="from", description="Inclusive ISO-8601 timestamp"
    ),
    end: datetime | None = Query(
        default=None, alias="to", description="Exclusive ISO-8601 timestamp"
    ),
    channel_id: str | None = Query(default=None, description="Optional channel filter"),
) -> list[dict[str, Any]]:
    """Return synthetic programme slots for an ISO-8601 time window.

    When omitted, the window is the next 24 hours. Query timestamps must include
    timezone offsets; the API returns times normalized to Japan Standard Time.
    """
    _validate_region(region)
    window_start, window_end = _resolve_window(start, end)
    return _build_programmes(window_start, window_end, channel_id)


def _xmltv_time(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.strftime("%Y%m%d%H%M%S %z")


@app.get("/api/v1/guide.xml", tags=["guide"])
def export_xmltv(
    region: str = Query(default="jp-demo", description="Guide-region identifier"),
    start: datetime | None = Query(default=None, alias="from"),
    end: datetime | None = Query(default=None, alias="to"),
) -> Response:
    """Export synthetic sample listings as XMLTV for integration testing."""
    _validate_region(region)
    window_start, window_end = _resolve_window(start, end)

    root = ET.Element(
        "tv",
        {
            "source-info-name": "TV Guide Channel Wii development fixture",
            "generator-info-name": "tv-guide-channel-wii",
        },
    )
    for channel in CHANNELS:
        element = ET.SubElement(root, "channel", {"id": channel["id"]})
        ET.SubElement(element, "display-name", {"lang": "en"}).text = channel["name"]
        ET.SubElement(element, "display-name", {"lang": "ja"}).text = channel["name_ja"]

    for programme in _build_programmes(window_start, window_end):
        element = ET.SubElement(
            root,
            "programme",
            {
                "channel": programme["channel_id"],
                "start": _xmltv_time(programme["start"]),
                "stop": _xmltv_time(programme["end"]),
            },
        )
        ET.SubElement(element, "title", {"lang": "en"}).text = programme["title"]
        ET.SubElement(element, "title", {"lang": "ja"}).text = programme["title_ja"]
        ET.SubElement(element, "desc", {"lang": "en"}).text = programme["description"]
        ET.SubElement(element, "category", {"lang": "en"}).text = "Demo"

    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(content=body, media_type="application/xml")
