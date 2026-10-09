# Wii channel banner and icon assets

The WAD packager expects two **U8 archives**, not PNG/JPEG files:

- `banner.bin` — channel banner archive
- `icon.bin` — Wii Menu channel icon archive

Put them in this folder using those exact names, or set `TV_GUIDE_BANNER_BIN`
and `TV_GUIDE_ICON_BIN` to your local paths. They are ignored by Git because
channel art archives may contain assets you do not have permission to redistribute.

## Creating the archives

Use a Wii channel banner editor such as CustomizeMii with a channel/base WAD
you are authorized to modify. Create a US-English banner and icon branded
**TV Guide USA**, then export the `banner.bin` and `icon.bin` U8 archives.

Keep these display strings in English:

- Channel title: `TV Guide USA`
- Subtitle: `United States TV Listings`
- Description: `TV schedules and programme information`

The frontend is a clean homebrew implementation and does not reuse Nintendo's
original TV no Tomo banner graphics or Japanese proprietary channel executable.
A PNG or SVG logo alone cannot be used as a Wii banner archive; it must be
placed into valid Wii banner/icon layouts by the banner editor.

## Base WAD and safety

Set `TV_GUIDE_BASE_WAD` to a compatible base WAD you are legally entitled to
use and whose banner application can be replaced by WadPakk. Do not commit any
base WAD, Wii keys, tickets, NAND backups, or proprietary channel binaries to
the public repository. Verify the finished channel in Dolphin first. On a
physical Wii, use a NAND backup and brick-protection setup and install only
after the DOL has been tested.
