# Building TV Guide USA WADs

## Automated workflow

The default GitHub Actions workflow builds a DOL and a standalone prototype WAD automatically on pushes to `main` and scheduled guide refreshes. It does **not** need the user's Japanese TV no Tomo WAD, a base-WAD secret, Python on the user's Mac, or .NET on the user's Mac.

The standalone WAD is constructed with [WadPakk](https://github.com/davi-x86/WadPakk), using its own bundled generic template at `Resources/base.wad`. The WAD gets title ID `0001000154564731` (`TVG1`), channel title `TV Guide USA`, a USA TMD region and startup IOS 58.

The Nightly release includes `TV-Guide-USA.wad`, `tv-guide-usa.dol`, four timezone guide snapshots, source-status metadata and `TV-Guide-USA-Dolphin-Test-Kit.zip`.

## Test in Dolphin

1. Download [the Nightly release](https://github.com/NVDEMU/TV-Guide-Channel-Wii/releases/tag/nightly).
2. Create a separate Dolphin user/NAND profile for testing.
3. Use Dolphin's **Tools → Install WAD** menu to install `TV-Guide-USA.wad` to that test NAND.
4. Launch TV Guide USA from the emulated Wii Menu and test startup, channel/programme navigation, details and timezone switching.
5. If the installed WAD fails, record the full Dolphin log and exact version. This distinguishes a WAD/banner/loading problem from the earlier direct-DOL `Failed to init core` report.

The test-kit ZIP also contains the DOL under `sd/apps/tv-guide-channel-wii/boot.dol` with generated guide snapshots beside it. This can be tested through the Homebrew Channel using an emulated SD card. A direct DOL open follows a different boot path than an installed channel and should not be the only test.

## Local build

The script accepts a local base WAD as an optional override for experiments, but CI does not require it. Run:

```sh
bash tools/package-wad.sh
```

Requirements for local use: devkitPro/Wii SDK for a DOL build; Python 3, Git and .NET 8 for packaging. The script fetches WadPakk if needed and uses its bundled template by default.

Optional variables:

- `TV_GUIDE_DOL` — path to a prebuilt DOL.
- `TV_GUIDE_BASE_WAD` — private optional WAD template override; not needed for CI.
- `TV_GUIDE_BANNER_BIN` / `TV_GUIDE_ICON_BIN` — optional U8 archives.
- `TV_GUIDE_WAD_OUTPUT` — output path (default `build/TV-Guide-USA.wad`).
- `WADPAKK_DIR` — pre-existing WadPakk checkout.

## Important limitation: original TV no Tomo UI is not yet translated

The standalone WAD currently contains this project's homebrew DOL and uses banner/icon archives from WadPakk's generic template. It is **not** the same as the original TV no Tomo channel with English labels. Preserving the original interface means localizing/adapting the original app, its strings, graphics/layout and service protocol (or reproducing the interface in our own GX UI). That is separate from the WAD packaging task. The project docs intentionally do not claim that the modern XMLTV backend speaks the original guide protocol.

The full Nintendo TV no Tomo WAD and other proprietary title content are not included in this public repo. A future original-title patching path can download or accept a legally obtained original title during a build, and keep that input out of the public repository. There is no need to publish a full copyrighted WAD just to create a standalone prototype WAD.

## Safety

A WAD passing structural validation does not prove it boots, nor that it is safe for real hardware. Use a separate Dolphin NAND first. Do not install on physical hardware until the WAD has been tested in Dolphin. Keep a verified NAND backup and appropriate brick protection before any real-Wii installation.
