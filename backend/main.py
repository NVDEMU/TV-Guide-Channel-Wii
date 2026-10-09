"""US-English guide API and development endpoints for the Wii channel.

The Wii-facing text protocol is project-specific, not the original Nintendo
channel protocol. Real listings are loaded from a user-configured XMLTV file;
without one, the API returns explicitly synthetic demo data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Response

from backend.us_xmltv import configured_us_programmes

APP_NAME = "TV Guide USA API"
TOKYO = ZoneInfo("Asia/Tokyo")
EASTERN = ZoneInfo("America/New_York")
MAX_WINDOW = timedelta(days=7)

app = FastAPI(
    title=APP_NAME,
    description=(
        "US-English TV guide API for the TV Guide USA Wii homebrew channel. "
        "Real schedules require a user-configured XMLTV source. Demo listings "
        "are synthetic and are never represented as live broadcast data."
    ),
    version="0.2.0",
)

REGION: dict[str, str] = {
    "id": "jp-demo",
    "name": "Japan — demo region",
    "description": "Legacy research fixture; synthetic data only.",
    "timezone": "Asia/Tokyo",
}
US_REGION: dict[str, str] = {
    "id": "us",
    "name": "United States (English)",
    "description": "US-English guide; demo fixtures unless XMLTV data is configured.",
    "timezone": "America/New_York",
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

US_CHANNELS: list[dict[str, Any]] = [
    {"id": "demo-abc", "name": "ABC (DEMO)", "name_ja": "", "broadcast_type": "terrestrial-digital", "channel_number": "ABC", "region": "us"},
    {"id": "demo-cbs", "name": "CBS (DEMO)", "name_ja": "", "broadcast_type": "terrestrial-digital", "channel_number": "CBS", "region": "us"},
    {"id": "demo-nbc", "name": "NBC (DEMO)", "name_ja": "", "broadcast_type": "terrestrial-digital", "channel_number": "NBC", "region": "us"},
    {"id": "demo-fox", "name": "FOX (DEMO)", "name_ja": "", "broadcast_type": "terrestrial-digital", "channel_number": "FOX", "region": "us"},
    {"id": "demo-pbs", "name": "PBS (DEMO)", "name_ja": "", "broadcast_type": "terrestrial-digital", "channel_number": "PBS", "region": "us"},
]

US_DEMO_TITLES = {
    "demo-abc": ("Sample National News", "Demo entertainment special"),
    "demo-cbs": ("Sample Evening News", "Demo comedy hour"),
    "demo-nbc": ("Sample Local News", "Demo game show"),
    "demo-fox": ("Sample Sports Desk", "Demo feature film"),
    "demo-pbs": ("Sample Public Affairs", "Demo science program"),
}


def _now_tokyo() -> datetime:
    return datetime.now(timezone.utc).astimezone(TOKYO).replace(microsecond=0)


def _resolve_window(
    start: datetime | None, end: datetime | None, tz: ZoneInfo = TOKYO
) -> tuple[datetime, datetime]:
    """Resolve query bounds and require explicit timezone offsets when supplied."""
    now = datetime.now(timezone.utc).astimezone(tz).replace(microsecond=0)
    if start is None and end is None:
        start, end = now, now + timedelta(hours=24)
    elif start is None:
        assert end is not None
        if end.tzinfo is None or end.utcoffset() is None:
            raise HTTPException(status_code=422, detail="'to' must include a timezone offset.")
        start = end - timedelta(hours=24)
    elif end is None:
        end = start + timedelta(hours=24)

    assert start is not None and end is not None
    if start.tzinfo is None or start.utcoffset() is None:
        raise HTTPException(status_code=422, detail="'from' must include a timezone offset.")
    if end.tzinfo is None or end.utcoffset() is None:
        raise HTTPException(status_code=422, detail="'to' must include a timezone offset.")

    start_local = start.astimezone(tz)
    end_local = end.astimezone(tz)
    if end_local <= start_local:
        raise HTTPException(status_code=422, detail="'to' must be later than 'from'.")
    if end_local - start_local > MAX_WINDOW:
        raise HTTPException(status_code=422, detail="Maximum range is 7 days.")
    return start_local, end_local


def _validate_region(region: str) -> None:
    if region not in {REGION["id"], US_REGION["id"]}:
        raise HTTPException(status_code=404, detail=f"Unknown region '{region}'.")


def _build_programmes(
    start: datetime,
    end: datetime,
    channel_id: str | None = None,
    channels: list[dict[str, Any]] | None = None,
    *,
    demo: bool = True,
) -> list[dict[str, Any]]:
    channels = channels if channels is not None else CHANNELS
    selected = channels
    if channel_id is not None:
        selected = [ch for ch in channels if ch["id"] == channel_id]
        if not selected:
            raise HTTPException(status_code=404, detail=f"Unknown channel '{channel_id}'.")

    programmes: list[dict[str, Any]] = []
    first_hour = start.replace(minute=0, second=0, microsecond=0)
    if first_hour < start:
        first_hour += timedelta(hours=1)

    for index, channel in enumerate(selected):
        current = first_hour
        while current < end:
            slot = (current.hour + index) % 24
            if channel["region"] == "us":
                choices = US_DEMO_TITLES[channel["id"]]
                title = choices[(slot // 3) % len(choices)]
            else:
                title = f"Demo programme {slot + 1:02d}"
            programmes.append(
                {
                    "id": f"{channel['id']}-{current:%Y%m%d%H}",
                    "channel_id": channel["id"],
                    "channel_name": channel["name"],
                    "start": current.isoformat(),
                    "end": (current + timedelta(hours=1)).isoformat(),
                    "title": title,
                    "title_ja": title if channel["region"] == "us" else f"サンプル番組 {slot + 1:02d}",
                    "description": (
                        "DEMO LISTING — not a real broadcast schedule."
                        if demo else ""
                    ),
                    "genre": "demo" if demo else "unknown",
                    "is_demo": demo,
                }
            )
            current += timedelta(hours=1)

    programmes.sort(key=lambda item: (item["start"], item["channel_id"]))
    return programmes


def _configured_or_demo_us(
    start: datetime, end: datetime, channel_id: str | None = None
) -> list[dict[str, Any]]:
    imported = configured_us_programmes()
    if imported is not None:
        output = []
        for programme in imported:
            programme_start = datetime.fromisoformat(programme["start"])
            programme_end = datetime.fromisoformat(programme["end"])
            if programme_end <= start or programme_start >= end:
                continue
            if channel_id is not None and programme["channel_id"] != channel_id:
                continue
            output.append({**programme, "genre": "unknown", "title_ja": programme["title"]})
        if channel_id is not None and not any(p["channel_id"] == channel_id for p in output):
            # It may simply have no programme in this requested window.
            known_ids = {p["channel_id"] for p in imported}
            if channel_id not in known_ids:
                raise HTTPException(status_code=404, detail=f"Unknown XMLTV channel '{channel_id}'.")
        output.sort(
            key=lambda item: (datetime.fromisoformat(item["start"]), item["channel_id"])
        )
        return output

    return _build_programmes(start, end, channel_id, US_CHANNELS, demo=True)


def _safe_field(value: str, max_len: int = 180) -> str:
    return (
        value.replace("|", "/")
        .replace("\\", "/")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
        .strip()[:max_len]
    )


@app.get("/health", tags=["status"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": APP_NAME, "stage": "development"}


@app.get("/api/v1/regions", tags=["guide"])
def list_regions() -> list[dict[str, str]]:
    return [REGION, US_REGION]


@app.get("/api/v1/channels", tags=["guide"])
def list_channels(
    region: str = Query(default="jp-demo", description="Guide-region identifier"),
) -> list[dict[str, Any]]:
    _validate_region(region)
    if region == "jp-demo":
        return CHANNELS
    imported = configured_us_programmes()
    if imported is None:
        return US_CHANNELS
    seen: set[str] = set()
    channels: list[dict[str, Any]] = []
    for programme in imported:
        channel_id = programme["channel_id"]
        if channel_id in seen:
            continue
        seen.add(channel_id)
        channels.append(
            {
                "id": channel_id,
                "name": programme["channel_name"],
                "name_ja": "",
                "broadcast_type": "xmltv",
                "channel_number": str(len(channels) + 1),
                "region": "us",
            }
        )
    return channels


@app.get("/api/v1/programmes", tags=["guide"])
def list_programmes(
    region: str = Query(default="jp-demo", description="Guide-region identifier"),
    start: datetime | None = Query(default=None, alias="from", description="Inclusive ISO-8601 timestamp"),
    end: datetime | None = Query(default=None, alias="to", description="Exclusive ISO-8601 timestamp"),
    channel_id: str | None = Query(default=None, description="Optional channel filter"),
) -> list[dict[str, Any]]:
    _validate_region(region)
    tz = TOKYO if region == "jp-demo" else EASTERN
    window_start, window_end = _resolve_window(start, end, tz)
    if region == "jp-demo":
        return _build_programmes(window_start, window_end, channel_id, CHANNELS, demo=True)
    return _configured_or_demo_us(window_start, window_end, channel_id)


def _xmltv_time(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.strftime("%Y%m%d%H%M%S %z")


@app.get("/api/v1/guide.xml", tags=["guide"])
def export_xmltv(
    region: str = Query(default="jp-demo", description="Guide-region identifier"),
    start: datetime | None = Query(default=None, alias="from"),
    end: datetime | None = Query(default=None, alias="to"),
) -> Response:
    _validate_region(region)
    tz = TOKYO if region == "jp-demo" else EASTERN
    window_start, window_end = _resolve_window(start, end, tz)
    channels = CHANNELS if region == "jp-demo" else list_channels(region)
    programmes = (
        _build_programmes(window_start, window_end, channels=CHANNELS)
        if region == "jp-demo"
        else _configured_or_demo_us(window_start, window_end)
    )

    root = ET.Element(
        "tv",
        {
            "source-info-name": "TV Guide USA development API",
            "generator-info-name": "tv-guide-channel-wii",
        },
    )
    for channel in channels:
        element = ET.SubElement(root, "channel", {"id": channel["id"]})
        ET.SubElement(element, "display-name", {"lang": "en"}).text = channel["name"]
        if channel.get("name_ja"):
            ET.SubElement(element, "display-name", {"lang": "ja"}).text = channel["name_ja"]

    for programme in programmes:
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
        ET.SubElement(element, "desc", {"lang": "en"}).text = programme.get("description", "")
        if programme.get("is_demo"):
            ET.SubElement(element, "category", {"lang": "en"}).text = "Demo"
    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(content=body, media_type="application/xml")


@app.get("/api/v1/wii/guide.txt", tags=["Wii channel"])
def wii_guide_text(
    region: str = Query(default="us", description="US-English guide region"),
    timezone_name: str = Query(default="America/New_York", alias="timezone"),
) -> Response:
    """Return a tiny pipe-delimited guide payload for the Wii homebrew client.

    This is a project-specific development protocol. The production feed is
    controlled via TV_GUIDE_XMLTV_PATH; otherwise every record is marked demo.
    A selected US time zone is used for display, while imported timestamps keep
    their source offsets internally.
    """
    zones = {
        "America/New_York": ZoneInfo("America/New_York"),
        "America/Chicago": ZoneInfo("America/Chicago"),
        "America/Denver": ZoneInfo("America/Denver"),
        "America/Los_Angeles": ZoneInfo("America/Los_Angeles"),
    }
    if region != "us":
        raise HTTPException(status_code=404, detail="The Wii client currently supports region 'us'.")
    if timezone_name not in zones:
        raise HTTPException(
            status_code=422,
            detail="Unsupported timezone. Choose US Eastern, Central, Mountain, or Pacific.",
        )
    selected_tz = zones[timezone_name]
    start, end = _resolve_window(None, None, selected_tz)
    end = start + timedelta(hours=6)
    programmes = _configured_or_demo_us(start, end)
    imported = configured_us_programmes() is not None
    mode = "FEED" if imported else "DEMO"
    lines = [f"TVGUIDE|1|US-EN|{timezone_name}|{mode}"]
    channels: dict[str, str] = {}
    for programme in programmes:
        channel_id = _safe_field(programme["channel_id"], 60)
        channels.setdefault(channel_id, _safe_field(programme["channel_name"], 80))
    for channel_id, name in channels.items():
        lines.append(f"CHANNEL|{channel_id}|{name}")
    per_channel: dict[str, int] = {}
    for programme in programmes:
        channel_id = _safe_field(programme["channel_id"], 60)
        per_channel[channel_id] = per_channel.get(channel_id, 0) + 1
        if per_channel[channel_id] > 4:
            continue
        start_dt = datetime.fromisoformat(programme["start"]).astimezone(selected_tz)
        end_dt = datetime.fromisoformat(programme["end"]).astimezone(selected_tz)
        lines.append(
            "PROGRAM|"
            + "|".join(
                [
                    channel_id,
                    start_dt.strftime("%I:%M %p").lstrip("0"),
                    end_dt.strftime("%I:%M %p").lstrip("0"),
                    _safe_field(programme["title"], 120),
                    _safe_field(programme.get("description", ""), 180),
                ]
            )
        )
    lines.append("END")
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; charset=utf-8")
