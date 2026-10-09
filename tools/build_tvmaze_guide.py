#!/usr/bin/env python3
"""Fetch TVmaze US schedules and generate a compact guide snapshot for the Wii.

TVmaze's public API is licensed CC BY-SA. The resulting UI therefore displays
an attribution line; preserve that attribution and the ShareAlike requirement
when distributing derived guide data. Other providers are catalogued separately
because their data-use permissions are not consistently clear.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

API_ROOT = "https://api.tvmaze.com/schedule"
ET = ZoneInfo("America/New_York")
TIMEZONES = {
    "eastern": "America/New_York",
    "central": "America/Chicago",
    "mountain": "America/Denver",
    "pacific": "America/Los_Angeles",
}
MAX_CHANNELS = 16
PROGRAMMES_PER_CHANNEL = 4
HORIZON_HOURS = 24
USER_AGENT = "TV-Guide-USA/0.3 (TVmaze CC BY-SA attribution: https://www.tvmaze.com/api)"
PRIORITY = {
    "abc": 0, "cbs": 1, "nbc": 2, "fox": 3, "pbs": 4, "the cw": 5,
    "cw": 5, "ion": 6, "univision": 7, "telemundo": 8, "espn": 9,
    "espn2": 10, "cnn": 11, "fox news": 12, "msnbc": 13, "tnt": 14, "tbs": 15,
}
DEMO_ROWS = [
    ("demo-abc", "ABC (DEMO)", "Sample National News", "Demo Entertainment"),
    ("demo-cbs", "CBS (DEMO)", "Sample Evening News", "Demo Comedy Hour"),
    ("demo-nbc", "NBC (DEMO)", "Sample Local News", "Demo Game Show"),
    ("demo-fox", "FOX (DEMO)", "Sample Sports Desk", "Demo Feature Film"),
    ("demo-pbs", "PBS (DEMO)", "Sample Public Affairs", "Demo Science"),
]


def _clean(value: Any, max_chars: int = 160) -> str:
    """Convert API HTML/plain text to the Wii's pipe-delimited field safely."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.replace("|", "/").replace("\\", "/").strip()[:max_chars]


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return result[:48] or "unknown-network"


def _timezone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "America/New_York")
    except (ZoneInfoNotFoundError, ValueError):
        return ET


def fetch_date(day: date) -> list[dict[str, Any]]:
    query = urlencode({"country": "US", "date": day.isoformat()})
    request = Request(
        f"{API_ROOT}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urlopen(request, timeout=20) as response:
        if getattr(response, "status", 200) != 200:
            raise RuntimeError(f"TVmaze returned HTTP {response.status}")
        payload = json.load(response)
    if not isinstance(payload, list):
        raise RuntimeError("TVmaze returned an unexpected schedule payload.")
    return payload


def normalize_episodes(
    episodes: list[dict[str, Any]], now: datetime
) -> list[dict[str, Any]]:
    """Normalise TVmaze episodes to timezone-aware network/programme records."""
    now_et = now.astimezone(ET)
    horizon_end = now_et + timedelta(hours=HORIZON_HOURS)
    normalised: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for episode in episodes:
        if not isinstance(episode, dict):
            continue
        show = episode.get("show") or {}
        network = show.get("network") or show.get("webChannel") or {}
        channel_name = _clean(network.get("name") or "", 60)
        if not channel_name:
            continue
        country = network.get("country") or {}
        channel_tz = _timezone(country.get("timezone"))
        raw_stamp = episode.get("airstamp")
        start: datetime | None = None
        if isinstance(raw_stamp, str) and raw_stamp:
            try:
                start = datetime.fromisoformat(raw_stamp.replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=channel_tz)
            except ValueError:
                start = None

        if start is None:
            airdate = episode.get("airdate")
            airtime = episode.get("airtime")
            if not airdate or not airtime:
                continue
            try:
                start = datetime.strptime(
                    f"{airdate} {airtime}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=channel_tz)
            except ValueError:
                continue

        runtime = episode.get("runtime") or show.get("averageRuntime") or 30
        try:
            runtime_minutes = max(1, min(int(runtime), 360))
        except (TypeError, ValueError):
            runtime_minutes = 30
        end = start + timedelta(minutes=runtime_minutes)
        start_et = start.astimezone(ET)
        end_et = end.astimezone(ET)
        if end_et <= now_et - timedelta(minutes=30) or start_et >= horizon_end:
            continue

        channel_id = _slug(channel_name)
        title = _clean(episode.get("name") or show.get("name") or "Untitled programme", 120)
        summary = _clean(episode.get("summary") or show.get("summary") or "", 160)
        if not summary:
            summary = "Episode schedule data provided by TVmaze."
        key = (channel_id, start.isoformat(), title)
        if key in seen:
            continue
        seen.add(key)
        normalised.append({
            "channel_id": channel_id,
            "channel_name": channel_name,
            "start": start,
            "end": end,
            "title": title,
            "description": summary,
        })

    normalised.sort(key=lambda item: item["start"].astimezone(ET))
    return normalised


def _demo_guide(timezone_name: str) -> str:
    lines = [f"TVGUIDE|1|US-EN|{timezone_name}|DEMO"]
    for channel_id, name, title1, title2 in DEMO_ROWS:
        lines.append(f"CHANNEL|{channel_id}|{name}")
        lines.append(
            f"PROGRAM|{channel_id}|NOW|1 HOUR|{title1}|Synthetic offline fallback, not a real TV listing."
        )
        lines.append(
            f"PROGRAM|{channel_id}|NEXT|LATER|{title2}|Synthetic offline fallback, not a real TV listing."
        )
    lines.append("END")
    return "\n".join(lines) + "\n"


def format_guide(
    events: list[dict[str, Any]], timezone_name: str, now: datetime
) -> str:
    """Render up to 16 channels/four entries each in the Wii text protocol."""
    target_tz = ZoneInfo(timezone_name)
    now_et = now.astimezone(ET)
    horizon_end = now_et + timedelta(hours=HORIZON_HOURS)
    by_channel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    names: dict[str, str] = {}

    for item in events:
        start = item["start"]
        end = item["end"]
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            continue
        if end.astimezone(ET) <= now_et - timedelta(minutes=30):
            continue
        if start.astimezone(ET) >= horizon_end:
            continue
        channel_id = str(item["channel_id"])
        names[channel_id] = _clean(item["channel_name"], 60)
        by_channel[channel_id].append(item)

    for channel_id in by_channel:
        by_channel[channel_id].sort(key=lambda item: item["start"].astimezone(ET))

    channel_ids = sorted(
        by_channel,
        key=lambda channel_id: (
            PRIORITY.get(names[channel_id].casefold(), 100),
            names[channel_id].casefold(),
            channel_id,
        ),
    )[:MAX_CHANNELS]
    if not channel_ids:
        return _demo_guide(timezone_name)

    lines = [f"TVGUIDE|1|US-EN|{timezone_name}|TVMAZE"]
    for channel_id in channel_ids:
        lines.append(f"CHANNEL|{channel_id}|{names[channel_id]}")
    programme_total = 0
    for channel_id in channel_ids:
        rows = by_channel[channel_id][:PROGRAMMES_PER_CHANNEL]
        for item in rows:
            start_local = item["start"].astimezone(target_tz)
            end_local = item["end"].astimezone(target_tz)
            start_label = start_local.strftime("%I:%M %p").lstrip("0")
            end_label = end_local.strftime("%I:%M %p").lstrip("0")
            title = _clean(item["title"], 120)
            description = _clean(item.get("description", ""), 150)
            lines.append(
                f"PROGRAM|{channel_id}|{start_label}|{end_label}|{title}|{description}"
            )
            programme_total += 1
            if programme_total >= MAX_CHANNELS * PROGRAMMES_PER_CHANNEL:
                break
        if programme_total >= MAX_CHANNELS * PROGRAMMES_PER_CHANNEL:
            break
    lines.append("END")
    return "\n".join(lines) + "\n"


def _c_string(data: bytes) -> str:
    parts: list[str] = []
    for byte in data:
        if byte == 0x22:
            parts.append('\\\"')
        elif byte == 0x5C:
            parts.append('\\\\')
        elif byte == 0x0A:
            parts.append('\\n')
        elif byte == 0x0D:
            parts.append('\\r')
        elif byte == 0x09:
            parts.append('\\t')
        elif 0x20 <= byte <= 0x7E:
            parts.append(chr(byte))
        else:
            parts.append(f"\\{byte:03o}")
    return '"' + "".join(parts) + '"'


def render_c_include(guides: dict[str, str]) -> str:
    """Render C literals as octal-escaped UTF-8 bytes, safe for arbitrary titles."""
    lines = ["/* Generated by tools/build_tvmaze_guide.py; do not edit by hand. */"]
    for short_name in TIMEZONES:
        payload = guides[short_name].encode("utf-8")
        escaped_parts: list[str] = []
        chunk: list[bytes] = []
        chunk_len = 0
        for byte in payload:
            rendered = _c_string(bytes([byte]))[1:-1]
            if chunk and chunk_len + len(rendered) > 90:
                escaped_parts.append('"' + "".join(_c_string(b)[1:-1] for b in chunk) + '"')
                chunk, chunk_len = [], 0
            chunk.append(bytes([byte]))
            chunk_len += len(rendered)
        if chunk:
            escaped_parts.append('"' + "".join(_c_string(b)[1:-1] for b in chunk) + '"')
        lines.append(f"static char guide_{short_name}[] =")
        lines.extend(f"    {part}" for part in escaped_parts)
        lines.append("    ;")
    return "\n".join(lines) + "\n"


def build_snapshot(
    output_dir: Path,
    c_output: Path,
    *,
    now: datetime | None = None,
    fetcher=fetch_date,
) -> dict[str, Any]:
    moment = (now or datetime.now(timezone.utc)).astimezone(ET)
    days = [moment.date(), (moment + timedelta(days=1)).date()]
    episodes: list[dict[str, Any]] = []
    fetch_errors: list[str] = []
    for day in days:
        try:
            episodes.extend(fetcher(day))
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
            fetch_errors.append(f"{day.isoformat()}: {type(exc).__name__}: {exc}")

    events = normalize_episodes(episodes, moment)
    guides: dict[str, str] = {}
    for short_name, timezone_name in TIMEZONES.items():
        guides[short_name] = format_guide(events, timezone_name, moment)

    output_dir.mkdir(parents=True, exist_ok=True)
    c_output.parent.mkdir(parents=True, exist_ok=True)
    for short_name, payload in guides.items():
        (output_dir / f"guide-{short_name}.txt").write_text(payload, encoding="utf-8")

    status = {
        "provider": "TVmaze public US schedule API",
        "source_url": API_ROOT,
        "license": "CC BY-SA; attribute TVmaze and comply with ShareAlike",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "window_start_et": moment.isoformat(),
        "horizon_hours": HORIZON_HOURS,
        "channels": len({event["channel_id"] for event in events}),
        "programmes": len(events),
        "used_demo_fallback": not bool(events),
        "fetch_errors": fetch_errors,
    }
    (output_dir / "source-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    c_output.write_text(render_c_include(guides), encoding="ascii")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/guide"),
        help="directory for the four timezone-specific guide text files",
    )
    parser.add_argument(
        "--c-output", type=Path,
        default=Path("wii/source/embedded_guide_data.inc"),
        help="generated C include compiled into the Wii DOL",
    )
    parser.add_argument(
        "--offline-demo", action="store_true",
        help="generate only clearly marked synthetic listings (for tests)",
    )
    args = parser.parse_args()
    if args.offline_demo:
        guides = {
            short_name: _demo_guide(zone_name)
            for short_name, zone_name in TIMEZONES.items()
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.c_output.parent.mkdir(parents=True, exist_ok=True)
        for short_name, payload in guides.items():
            (args.output_dir / f"guide-{short_name}.txt").write_text(payload, encoding="utf-8")
        args.c_output.write_text(render_c_include(guides), encoding="ascii")
        status = {
            "provider": "offline synthetic fallback",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "used_demo_fallback": True,
            "channels": len(DEMO_ROWS),
            "programmes": len(DEMO_ROWS) * 2,
            "fetch_errors": [],
        }
        (args.output_dir / "source-status.json").write_text(
            json.dumps(status, indent=2) + "\n", encoding="utf-8"
        )
    else:
        status = build_snapshot(args.output_dir, args.c_output)
    print(json.dumps(status, indent=2))
    # A provider outage must not prevent building; the UI explicitly labels demo data.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
