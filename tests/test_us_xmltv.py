from pathlib import Path

import pytest

from backend.us_xmltv import load_us_programmes, parse_xmltv_timestamp


def test_xmltv_timestamp_requires_and_respects_offset() -> None:
    parsed = parse_xmltv_timestamp("20261009190000 -0400")
    assert parsed.isoformat() == "2026-10-09T19:00:00-04:00"
    with pytest.raises(ValueError):
        parse_xmltv_timestamp("20261009190000")


def test_parse_us_xmltv_and_skip_invalid_programmes(tmp_path: Path) -> None:
    xml = tmp_path / "guide.xml"
    xml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="abc.us"><display-name>ABC</display-name></channel>
  <channel id="pbs.us"><display-name>PBS</display-name></channel>
  <programme start="20261009190000 -0400" stop="20261009200000 -0400" channel="abc.us">
    <title>Evening News</title><desc>Local and national headlines.</desc>
  </programme>
  <programme start="bad-time" stop="also-bad" channel="abc.us">
    <title>Bad entry</title>
  </programme>
  <programme start="20261009200000 -0400" stop="20261009210000 -0400" channel="other.us">
    <title>Ignored channel</title>
  </programme>
</tv>""",
        encoding="utf-8",
    )
    programmes = load_us_programmes(xml)
    assert len(programmes) == 1
    assert programmes[0]["channel_name"] == "ABC"
    assert programmes[0]["title"] == "Evening News"
    assert programmes[0]["is_demo"] is False
