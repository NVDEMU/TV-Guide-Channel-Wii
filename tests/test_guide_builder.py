from datetime import datetime
from zoneinfo import ZoneInfo

from tools.build_tvmaze_guide import format_guide, normalize_episodes, render_c_include


def sample_episode():
    return {
        "id": 101,
        "name": "Pilot",
        "airdate": "2026-10-09",
        "airtime": "11:00",
        "airstamp": "2026-10-09T15:00:00+00:00",
        "runtime": 30,
        "summary": "<p>A <b>sample</b> episode.</p>",
        "show": {
            "name": "Example Show",
            "network": {
                "name": "ABC",
                "country": {"code": "US", "timezone": "America/New_York"},
            },
        },
    }


def test_normalize_tvmaze_episode_with_timezone_and_html_summary():
    now = datetime(2026, 10, 9, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    rows = normalize_episodes([sample_episode()], now)
    assert len(rows) == 1
    assert rows[0]["channel_id"] == "abc"
    assert rows[0]["channel_name"] == "ABC"
    assert rows[0]["title"] == "Pilot"
    assert rows[0]["description"] == "A sample episode."
    assert rows[0]["start"].isoformat().startswith("2026-10-09T15:00:00+00:00")


def test_snapshot_formats_each_timezone_and_has_tvmaze_mode():
    now = datetime(2026, 10, 9, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    events = normalize_episodes([sample_episode()], now)
    east = format_guide(events, "America/New_York", now)
    central = format_guide(events, "America/Chicago", now)
    assert east.startswith("TVGUIDE|1|US-EN|America/New_York|TVMAZE")
    assert central.startswith("TVGUIDE|1|US-EN|America/Chicago|TVMAZE")
    assert "CHANNEL|abc|ABC" in east
    assert "PROGRAM|abc|11:00 AM|11:30 AM|Pilot|A sample episode." in east
    assert "PROGRAM|abc|10:00 AM|10:30 AM|Pilot|A sample episode." in central


def test_snapshot_falls_back_to_explicit_demo_when_no_source_entries():
    now = datetime(2026, 10, 9, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    payload = format_guide([], "America/New_York", now)
    assert payload.startswith("TVGUIDE|1|US-EN|America/New_York|DEMO")
    assert "Synthetic offline fallback" in payload
    assert "TVMAZE" not in payload


def test_c_include_escapes_quotes_backslashes_and_newlines():
    source = render_c_include({
        "eastern": 'TVGUIDE|1|"test"\\line\nEND\n',
        "central": "c\n",
        "mountain": "m\n",
        "pacific": "p\n",
    })
    assert "static char guide_eastern[]" in source
    assert '\\"test\\"' in source
    assert "\\n" in source
