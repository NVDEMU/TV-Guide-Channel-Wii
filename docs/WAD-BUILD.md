# Building an installable TV Guide USA WAD

A Wii DOL is executable homebrew, but the Wii Menu expects a channel package with a valid title structure, boot content, metadata, and banner application. The local package script uses your base WAD, extracts its current banner/icon archives when custom assets are not supplied, replaces the boot contents with TV Guide USA, and changes the channel metadata/title region to USA.

## The supplied Japanese base WAD

The supplied `TV no Toma (Japan) (Channel).wad` has already been checked locally. The structural summary is in [BASE-WAD-ANALYSIS.md](BASE-WAD-ANALYSIS.md). The package script looks for a file with that name in the repo root or `~/Wii`; otherwise set `TV_GUIDE_BASE_WAD` to its full path. The binary itself must remain local and is ignored by Git.

## Prerequisites

- A built `wii/tv-guide-usa.dol` (or download it from a successful [Nightly release](https://github.com/NVDEMU/TV-Guide-Channel-Wii/releases/tag/nightly)).
- Your local Japanese base WAD (or another compatible WAD that has a readable `BannerApp`).
- Python 3 and Git.
- .NET 8 SDK. The script clones [WadPakk](https://github.com/davi-x86/WadPakk) into ignored local tooling and removes its Windows-only runtime pin for macOS/Linux builds.

Do not upload a base WAD, Wii keys, tickets, certificates, NAND backup, or proprietary channel executable to this public repository.

## Build the DOL

```sh
make -C wii clean
make -C wii
```

## Build the WAD

Put your file named `TV no Toma (Japan) (Channel).wad` in the repo root or `~/Wii`, or pass an explicit full path:

```sh
TV_GUIDE_BASE_WAD="$HOME/Wii/TV no Toma (Japan) (Channel).wad" \
  bash tools/package-wad.sh
```

No custom banner files are required for a first packaging attempt. The helper extracts the existing `banner.bin` and `icon.bin` from your base WAD and reuses them. That preserves a valid banner structure, but its images may still contain Japanese branding/text. For a fully polished English presentation, create US-English archives with a Wii banner editor and supply them:

```sh
TV_GUIDE_BASE_WAD="$HOME/Wii/TV no Toma (Japan) (Channel).wad" \
TV_GUIDE_BANNER_BIN="$PWD/channel-assets/banner.bin" \
TV_GUIDE_ICON_BIN="$PWD/channel-assets/icon.bin" \
  bash tools/package-wad.sh
```

Environment variables:
- `TV_GUIDE_DOL` — alternative DOL path.
- `TV_GUIDE_BASE_WAD` — local base WAD.
- `TV_GUIDE_BANNER_BIN` — custom banner U8 archive (optional).
- `TV_GUIDE_ICON_BIN` — custom Wii Menu icon U8 archive (optional).
- `TV_GUIDE_WAD_OUTPUT` — output path (default `build/TV-Guide-USA.wad`).
- `WADPAKK_DIR` — existing WadPakk checkout, if available.

The output title ID is `0001000154564731` (`TVG1`), channel title is `TV Guide USA`, TMD region is set to USA, and startup IOS is 58. The pack script validates the WAD envelope after generating it. This structural check does not verify signatures or prove that it will boot.

## Testing and installation

1. Test the DOL in Dolphin or via the Homebrew Channel.
2. Test the WAD in a separate Dolphin user profile/NAND and confirm the displayed title, banner behavior, network connection and guide UI.
3. Only after successful emulation tests should you consider a real Wii.

A malformed WAD can brick a console. Keep a verified NAND backup and brick-protection setup before installing. CI builds the DOL and checks the packaging tools; it does not publish a WAD because the base WAD is local user content.

## Important scope distinction

This package replaces the original title's boot contents with our own US-English homebrew frontend and backend. It is **not** a byte-for-byte translation patch of the original Nintendo TV no Tomo executable. It will reuse the base WAD's current banner/icon artwork unless custom English U8 archives are supplied.
