# Building an installable TV Guide USA WAD

A Wii DOL is executable homebrew, but the Wii Menu expects a channel package with a valid title structure, boot content, metadata, and banner application. This guide explains the local WAD path without placing Wii keys or proprietary WAD files in the public repository.

## Prerequisites

- Build `wii/tv-guide-usa.dol` with devkitPro (or download the DOL from a successful Wii Channel Build workflow).
- A compatible base channel WAD you are authorized to use. It must contain a replaceable `BannerApp`.
- Valid U8 channel banner/icon archives: `channel-assets/banner.bin` and `channel-assets/icon.bin`. See [channel-assets/README.md](../channel-assets/README.md).
- .NET 8 SDK and Git. The script clones [WadPakk](https://github.com/davi-x86/WadPakk) into ignored local tooling directory `.tools/WadPakk`.

Do not upload a personal base WAD, Wii keys, ticket, NAND backup, or proprietary channel files to this public repository. The package script does not download or guess a base WAD on your behalf.

## Build the DOL

```sh
make -C wii clean
make -C wii
```

You can run the DOL in Dolphin or from the Homebrew Channel before creating an installed channel.

## Supply local base and banner assets

Export the valid U8 banner/icon archives from a banner editor. Then point the script at your own compatible base WAD:

```sh
TV_GUIDE_BASE_WAD="$HOME/Wii/authorized-base.wad" \
  TV_GUIDE_BANNER_BIN="$PWD/channel-assets/banner.bin" \
  TV_GUIDE_ICON_BIN="$PWD/channel-assets/icon.bin" \
  bash tools/package-wad.sh
```

Optional environment variables:

- `TV_GUIDE_DOL` — alternative input DOL path.
- `TV_GUIDE_BASE_WAD` — base WAD file.
- `TV_GUIDE_BANNER_BIN` — banner U8 archive.
- `TV_GUIDE_ICON_BIN` — icon U8 archive.
- `TV_GUIDE_WAD_OUTPUT` — output path (default: `build/TV-Guide-USA.wad`).
- `WADPAKK_DIR` — an existing WadPakk source checkout if you already have one.

The packer assigns the title ID `00010001-54564731` (four-character ID `TVG1`), channel name `TV Guide USA`, and startup IOS 58. The resulting file is local and ignored by Git.

## Testing and installation

1. Inspect the packer's output and make sure the WAD file is non-empty.
2. Test the DOL in Dolphin.
3. Test the WAD in a separate Dolphin user profile/NAND.
4. Only then consider installing on a physical Wii.

Malformed WADs can brick a console. Keep a verified NAND backup and brick-protection setup before installing. A build passing CI does not establish that an installed channel behaves correctly on a physical Wii.

## What CI does not do

CI builds and publishes the DOL only. It cannot create a branded WAD until the project owner supplies valid local banner/icon archives and a compatible base WAD. That is intentional: these are user-supplied binary inputs, and the repository must not publish private Wii keys or redistribute proprietary channel content.
