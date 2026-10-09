# TV Guide USA for Wii

**TV Guide USA** is a US-English Wii homebrew channel project inspired by the idea of Nintendo's Japanese TV no Tomo / G-Guide channel. It aims to offer a familiar programme-guide experience with US TV listings, channel navigation, programme details, and an installable Wii channel package.

> **Status: early, testable prototype.** The repository builds a new homebrew frontend; it does not patch or translate Nintendo's original proprietary channel executable. The Wii frontend can fetch this project's guide endpoint over a local network. When no XMLTV feed is configured it clearly labels the content as synthetic demo listings. Full internet-safe transport, polished banner/icon archives, Dolphin verification, and real-Wii testing are still required before calling this a finished public release.

## Project components

- `backend/` — FastAPI guide API, plain/gzip XMLTV ingestion, and a Wii-friendly text endpoint.
- `config/tv-guide-sources.json` — catalogue of public, account-based, personal-use, and commercial guide-source candidates, including known usage caveats.
- `tools/build_tvmaze_guide.py` — pulls the attributed TVmaze US schedule and generates compact timezone guide snapshots for the DOL and SD card.
- `wii/` — native PowerPC/libogc channel frontend, built as a Wii DOL.
- `tests/` — API and parser tests.
- `channel-assets/` — instructions for creating US-English Wii banner and icon U8 archives.
- `tools/inspect_wad.py` — validates the local WAD envelope and reads title/region/content metadata.
- `tools/package-wad.sh` — local WAD packaging script using the supplied Japanese base WAD, automatic banner/icon extraction fallback, and WadPakk.
- `tools/wad-assets/` — helper to extract the banner/icon archives from the base WAD.
- `docs/PROTOCOL-RESEARCH.md` — research into TV no Tomo's original guide-file formats.

## Features in this prototype

- US-English channel UI: `TV GUIDE USA`.
- Channel selection, programme listing, programme details, and refresh control.
- US Eastern, Central, Mountain, and Pacific time-zone switching.
- Backend supports user-provided XMLTV files for guide schedules.
- Synthetic demo schedule when no real source snapshot is available, clearly labelled `DEMO`.
- A compact TVmaze US schedule snapshot embedded in development builds, with TVmaze CC BY-SA attribution displayed in the channel. TVmaze data is episode-centric, not a complete local-affiliate lineup.
- Offline snapshot and optional SD-card guide loading, so the DOL can be tested in Dolphin without a local Python server.
- A growing provider catalogue: US-EPG, USA Locals, EPGTalk, EPGShare, Open-EPG, epg.pw, IPTV-EPG.org, iptv-org, i.mjh.nz FAST-channel feeds, Schedules Direct, TV Media and Gracenote.
- Wii frontend can read its backend IPv4 address/port and default time zone from SD-card configuration.
- GitHub Actions workflow builds the native Wii DOL and uploads it as an Actions artifact.
- Local WAD package script uses title ID `TVG1` and channel title `TV Guide USA`.

## 1. Run the backend on a computer

Requires Python 3.11 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for API documentation.

Important endpoints:

- `GET /health` — service status.
- `GET /api/v1/regions` — configured guide regions.
- `GET /api/v1/channels?region=us` — configured US guide channels.
- `GET /api/v1/programmes?region=us` — programme data.
- `GET /api/v1/guide.xml?region=us` — XMLTV export.
- `GET /api/v1/wii/guide.txt?region=us&timezone=America/New_York` — Wii frontend text protocol.

The Wii text protocol is custom to this project. It has **not** been confirmed as compatible with the original TV no Tomo channel's protocol.

## 2. Add real US guide schedules

The default build uses TVmaze's public US schedule API under its documented CC BY-SA licence. It is a compact build-time snapshot rather than a full local affiliate grid. For a different provider, obtain data whose terms permit your use and set `TV_GUIDE_XMLTV_PATH` to a plain or gzip-compressed XMLTV file before starting the API:

```sh
TV_GUIDE_XMLTV_PATH="/absolute/path/to/us-guide.xml" \
  uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

The importer reads English display names/titles where available, supports `.xml` and `.xml.gz`, validates offset-aware XMLTV timestamps, and skips malformed programme entries. Set optional `TV_GUIDE_CHANNEL_IDS` to a comma-separated list of channel IDs from your chosen feed to select the desired stations; otherwise the importer takes the first 12 channels. If no source is configured or it cannot be read, the API deliberately falls back to synthetic demo listings.

## 3. Build the native Wii frontend

Install devkitPro with the Wii development packages (`wii-dev` and the libogc/libfat libraries), then run:

```sh
make -C wii clean
make -C wii
```

The build produces `wii/tv-guide-usa.dol` (and the ELF/map files). Every push and pull request also runs the Wii build workflow; open the repository's **Actions** tab to download the development build artifact.

To let the frontend reach your backend, copy `wii/config.ini.example` to:

```
sd:/apps/tv-guide-channel-wii/config.ini
```

Change `server=` to the computer's LAN IPv4 address, for example `192.168.1.25`. The default port is `8000`. The channel currently uses **plain HTTP for local-network development only**; do not expose this endpoint directly to the public internet. HTTPS/TLS support is a requirement before a public hosted service is considered ready.

Controls: D-pad Up/Down selects channels; Left/Right selects programmes; A opens programme details; 1 refreshes; Plus cycles US time zones; HOME returns to the Wii Menu. The channel prefers a configured server, then a matching guide file on the SD card, then the built-in snapshot. The offline snapshot means Dolphin testing does not require you to run Python locally.

## 4. Package a WAD

A DOL executable is not by itself an installable Wii Menu channel. The packaging script can use your local `TV no Toma (Japan) (Channel).wad` as the base, validate it, and extract its existing U8 banner/icon archives when custom English archives are not supplied. This repo deliberately does not store Nintendo channel binaries, Wii common keys, tickets, NAND backups, or a base WAD.

See [docs/WAD-BUILD.md](docs/WAD-BUILD.md) and [channel-assets/README.md](channel-assets/README.md). The packaging script needs:

- A built `wii/tv-guide-usa.dol`.
- Your local base WAD, passed as `TV_GUIDE_BASE_WAD` or named `TV no Toma (Japan) (Channel).wad` in the repo root or `~/Wii`.
- Python 3, Git, and the .NET 8 SDK. The script extracts the base WAD's current banner/icon files by default; custom English archives can be supplied through `TV_GUIDE_BANNER_BIN` and `TV_GUIDE_ICON_BIN`.

Example:

```sh
TV_GUIDE_BASE_WAD="$HOME/Wii/TV no Toma (Japan) (Channel).wad" \
  bash tools/package-wad.sh
```

The output channel gets the `TVG1` title ID and USA TMD region. Without custom English banner/icon files, the WAD's menu artwork remains the original artwork even though the channel title and homebrew UI are English.

Override the banner/icon paths with `TV_GUIDE_BANNER_BIN` and `TV_GUIDE_ICON_BIN` if necessary. The output is `build/TV-Guide-USA.wad`. The base WAD and exported binary assets remain local/ignored rather than being committed. The regular workflow publishes the DOL and its timezone snapshot files. To package a WAD without installing Python or .NET on your Mac, use the GitHub Actions route below.

**Safety:** first test the DOL in Dolphin or via Homebrew Channel, then test the WAD in Dolphin. Installing malformed WADs can brick a Wii. Keep a verified NAND backup and brick-protection setup before installing a WAD on physical hardware. A successful compile is not proof of real-console functionality.

## Build the WAD using GitHub Actions (no local Python required)

1. Put a direct download URL for your own base WAD in the repository's **Settings → Secrets and variables → Actions → New repository secret**, named `TV_GUIDE_BASE_WAD_URL`. Use a private or short-lived URL that will remain valid for the workflow run; do not put the WAD itself in the public repo or commit a permanent public link.
2. Open **Actions → Wii Channel Build → Run workflow**.
3. Check **package_wad**, then run the workflow. It builds the DOL, fetches a TVmaze snapshot, downloads and validates your base WAD inside the runner, and packages the WAD there.
4. Download the `tv-guide-usa-wad-<commit>` artifact from the workflow run. It contains `TV-Guide-USA.wad` and `TV-Guide-USA-Dolphin-Test-Kit.zip`.

The test kit includes a DOL and four timezone-specific snapshot files for the SD path `sd:/apps/tv-guide-channel-wii/`. It is fine to test the WAD in Dolphin first; the WAD build is not automatically proof that it boots. The workflow does not expose the base WAD as a release asset.

If you do not set the base-WAD URL secret, leave `package_wad` unchecked; the normal DOL build still succeeds and publishes the snapshot files.

## 5. Tests

```sh
python -m pytest -q
python -m compileall -q backend tests
```

## Protocol research

See [docs/PROTOCOL-RESEARCH.md](docs/PROTOCOL-RESEARCH.md). Useful existing format references include [WiiLink24/tv-epg](https://github.com/WiiLink24/tv-epg), [WiiLink24/kaitais](https://github.com/WiiLink24/kaitais), and [Wii-Kaitai's Terebi no Tomo definitions](https://github.com/quatric/Wii-Kaitai/tree/main/channels/terebi_no_tomo).

## Scope and naming

The project is an independent US-English homebrew implementation, not an officially licensed Nintendo product. It uses the original channel as historical inspiration, while building a new frontend and backend rather than redistributing the original executable or banner art.
