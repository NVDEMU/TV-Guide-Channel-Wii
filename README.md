# TV Guide Channel Wii

An open-source revival project for the Japanese **TV no Tomo Channel: G-Guide for Wii**.

> **Current status: research and backend scaffold.** The service in this repository is a working development API with clearly marked synthetic demo listings. It is **not yet compatible with the original Wii channel's network protocol**, and its demo schedules are not real TV listings.

## Project plan

1. Provide a local guide-data API that can be tested independently from a Wii.
2. identify and document the original channel's requests, payload formats, region identifiers, and update flow.
3. Add a licensed schedule-data importer for a verified source.
4. Implement the adapter/serializer required by the original channel once its protocol is confirmed.
5. Test in Dolphin, then on a Wii, before calling the revival functional.

## Current backend features

- `GET /health` — health check.
- `GET /api/v1/regions` — available guide regions (currently a demo region).
- `GET /api/v1/channels?region=jp-demo` — synthetic demo channels.
- `GET /api/v1/programmes?region=jp-demo&from=...&to=...` — synthetic programmes over an ISO-8601 time range.
- `GET /api/v1/guide.xml?region=jp-demo` — XMLTV-formatted demo output for testing integrations.
- Input validation and automated API tests.
- Docker image for local/server deployment.

These endpoints are **our development API**, not claims about the endpoints or file formats expected by the original channel.

## Run locally

Requires Python 3.11+.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the interactive API documentation.

Examples:

```sh
curl http://127.0.0.1:8000/health
curl 'http://127.0.0.1:8000/api/v1/regions'
curl 'http://127.0.0.1:8000/api/v1/channels?region=jp-demo'
curl 'http://127.0.0.1:8000/api/v1/guide.xml?region=jp-demo'
```

Run tests with:

```sh
python -m pytest -q
```

## Docker

```sh
docker build -t tv-guide-channel-wii .
docker run --rm -p 8000:8000 tv-guide-channel-wii
```

## Data and licensing

The sample schedule is generated dynamically and explicitly labeled as demo content. It must not be presented as a real broadcast schedule. Before adding real listings, confirm the data source permits retrieval, transformation, and redistribution. See [data/README.md](data/README.md).

## Protocol research

See [docs/PROTOCOL-RESEARCH.md](docs/PROTOCOL-RESEARCH.md). Existing community research worth reviewing includes:

- [WiiLink24/tv-epg](https://github.com/WiiLink24/tv-epg) — guide-data acquisition utilities.
- [WiiLink24/kaitais](https://github.com/WiiLink24/kaitais) — includes a Kaitai definition for the Terebi no Tomo `header.bin`.
- [Wii-Kaitai](https://github.com/quatric/Wii-Kaitai) — consolidated Wii file-format definitions, including Terebi no Tomo formats.

Those projects are references, not evidence that this repository already implements the original channel's protocol.

## Scope

The goal is to restore the original channel experience where technically practical, without distributing proprietary channel binaries or claiming that an unverified protocol works. Keep test captures free of passwords, device identifiers, personal information, and other secrets.
