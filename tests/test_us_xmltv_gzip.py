import gzip

from backend.us_xmltv import load_us_programmes


def test_load_gzip_xmltv_and_prioritize_explicit_channel_ids(tmp_path):
    content = b"""<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="random"><display-name lang="en">Random channel</display-name></channel>
  <channel id="ny.abc"><display-name lang="en">ABC New York</display-name></channel>
  <programme start="20261009150000 +0000" stop="20261009153000 +0000" channel="random">
    <title lang="en">Random listing</title>
  </programme>
  <programme start="20261009150000 +0000" stop="20261009153000 +0000" channel="ny.abc">
    <title lang="en">NY listing</title>
    <desc lang="en">A test programme.</desc>
  </programme>
</tv>"""
    path = tmp_path / "guide.xml.gz"
    with gzip.open(path, "wb") as stream:
        stream.write(content)

    programmes = load_us_programmes(path, preferred_channel_ids=["ny.abc"])
    assert len(programmes) == 1
    assert programmes[0]["channel_id"] == "ny.abc"
    assert programmes[0]["channel_name"] == "ABC New York"
    assert programmes[0]["title"] == "NY listing"
