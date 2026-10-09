# TV Guide USA for Wii

**TV Guide USA** is a Wii homebrew channel project inspired by Nintendo's Japanese TV no Tomo / G-Guide channel. Its intended end goal is a revival-style experience with US listings, not the current text-console prototype.

> **Current status:** the DOL and standalone WAD now build automatically in GitHub Actions, with an embedded TVmaze schedule snapshot. The frontend is still a prototype and does **not** yet reproduce/translate the original TV no Tomo UI, executable or banner. The original title's data formats and service requests still need further reverse-engineering; see [protocol research](docs/PROTOCOL-RESEARCH.md).

## Components

- `backend/` — FastAPI guide API and plain/gzip XMLTV ingestion.
- `config/tv-guide-sources.json` — 35 candidate public, personal-use, account-based and commercial feed entries, with terms caveats.
- `tools/build_tvmaze_guide.py` — fetches a CC BY-SA TVmaze snapshot and generates embedded, timezone-specific guide files.
- `wii/` — native PowerPC/libogc DOL frontend.
- `tools/package-wad.sh` — packages a standalone prototype WAD using WadPakk's built-in generic template. No Japanese base WAD is needed for CI.
- `tools/inspect_wad.py` — validates a WAD's envelope and reads title/region/content metadata.
- `docs/GUIDE-SOURCES.md` — provider research.
- `docs/PROTOCOL-RESEARCH.md` — reverse-engineering research for the original channel.

## Current features

- English channel title, channel/programme browsing, programme details and timezone switching.
- Build-time TVmaze US schedule snapshot embedded in the DOL; TVmaze attribution is displayed in the UI.
- No live Python server or SD-card guide files required for the embedded snapshot.
- Optional guide text files on SD and optional backend server for development.
- Nightly DOL, standalone WAD, test-kit ZIP and four guide snapshot files published from GitHub Actions.

**Data scope:** TVmaze supplies episode-centric schedule data, not a complete per-affiliate US station grid. Other sources are catalogued in `config/tv-guide-sources.json`, but feeds with unclear or personal-use-only terms are disabled for public builds.

## Build/test without Python on your Mac

Open [Actions → Wii Channel Build](https://github.com/NVDEMU/TV-Guide-Channel-Wii/actions/workflows/wii-build.yml). Every push to `main` builds the DOL, generates the snapshot, packages a WAD, and publishes a Nightly release. The WAD uses the open-source packager's bundled generic template; the Japanese TV no Tomo WAD is **not** committed or needed for this standalone prototype.

- [Latest Nightly release (DOL + WAD + test kit + guide files)](https://github.com/NVDEMU/TV-Guide-Channel-Wii/releases/tag/nightly)
- [Latest GitHub Actions runs](https://github.com/NVDEMU/TV-Guide-Channel-Wii/actions)

### Test the WAD in Dolphin

1. Download `TV-Guide-USA.wad` from the Nightly release.
2. Create a separate Dolphin user/NAND profile for this test.
3. In Dolphin, use **Tools → Install WAD**, choose the downloaded WAD, and install it to that test NAND.
4. Open the emulated Wii Menu and launch TV Guide USA.
5. Check startup, controller navigation, embedded schedule display, programme details, and timezone switching.

For an HBC/DOL test instead, download the test kit and use its `sd/apps/tv-guide-channel-wii/boot.dol` path as an emulated SD card, then launch it through the Homebrew Channel. A bare DOL opened directly in Dolphin can follow a different launch path; the previous `Failed to init core` report is not yet diagnosed, so testing through the generated WAD and HBC will help isolate it.

The standalone WAD is a boot/test milestone, **not** the finished TV no Tomo revival. Its current banner assets come from a generic homebrew template. A true original-look version will need the original channel's graphics/layout and application flow to be localized and adapted, rather than merely placing the current DOL inside a WAD.

## Development locally

A local backend is optional. To run it, install Python 3.11 or newer, then:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Use `TV_GUIDE_XMLTV_PATH=/path/to/guide.xml.gz` for an XMLTV feed allowed by its terms; optional `TV_GUIDE_CHANNEL_IDS=id1,id2` selects preferred channel IDs. The Wii app uses plain HTTP for local-network development only—do not expose the prototype endpoint directly to the public internet.

A local DOL build requires devkitPro's Wii development packages:

```sh
make -C wii clean
make -C wii
```

A local WAD build requires Git, Python 3, and .NET 8; a Japanese base WAD is not needed:

```sh
bash tools/package-wad.sh
```

## Scope and safety

This is an independent homebrew project, not an officially licensed Nintendo product or a WiiLink project. The repository does not store the full proprietary TV no Tomo WAD, Nintendo tickets, common keys, or NAND dumps. A structurally valid WAD is not proof of emulator/hardware compatibility. Test in Dolphin first and never install an unverified WAD on a real Wii.
