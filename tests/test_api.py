from datetime import datetime
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_demo_region_and_channels_are_explicitly_demo() -> None:
    regions = client.get("/api/v1/regions")
    channels = client.get("/api/v1/channels?region=jp-demo")
    assert regions.status_code == 200
    assert regions.json()[0]["id"] == "jp-demo"
    assert channels.status_code == 200
    assert len(channels.json()) >= 1
    assert all("Demo" in item["name"] for item in channels.json())


def test_programmes_respect_window_and_are_marked_demo() -> None:
    response = client.get(
        "/api/v1/programmes",
        params={
            "region": "jp-demo",
            "from": "2026-10-09T09:00:00+09:00",
            "to": "2026-10-09T12:00:00+09:00",
            "channel_id": "jp-demo-terrestrial-01",
        },
    )
    assert response.status_code == 200
    programmes = response.json()
    assert programmes
    assert all(item["is_demo"] is True for item in programmes)
    assert all(item["channel_id"] == "jp-demo-terrestrial-01" for item in programmes)
    start = datetime.fromisoformat("2026-10-09T09:00:00+09:00")
    end = datetime.fromisoformat("2026-10-09T12:00:00+09:00")
    assert all(start <= datetime.fromisoformat(item["start"]) < end for item in programmes)


def test_unknown_region_returns_404() -> None:
    response = client.get("/api/v1/channels?region=unknown")
    assert response.status_code == 404


def test_oversized_programme_window_is_rejected() -> None:
    response = client.get(
        "/api/v1/programmes",
        params={
            "from": "2026-10-01T00:00:00+09:00",
            "to": "2026-10-10T00:00:00+09:00",
        },
    )
    assert response.status_code == 422


def test_xmltv_export_is_well_formed_and_labels_demo_content() -> None:
    response = client.get(
        "/api/v1/guide.xml",
        params={
            "from": "2026-10-09T09:00:00+09:00",
            "to": "2026-10-09T11:00:00+09:00",
        },
    )
    assert response.status_code == 200
    root = ET.fromstring(response.content)
    assert root.tag == "tv"
    assert root.findall("channel")
    programmes = root.findall("programme")
    assert programmes
    assert all(p.findtext("category") == "Demo" for p in programmes)
