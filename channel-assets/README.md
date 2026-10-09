# Wii channel banner and icon assets

The packager accepts two valid U8 archive files:

- `banner.bin` — the full-screen selected-channel banner
- `icon.bin` — the Wii Menu channel icon

## Default behavior

If you do not supply custom archives, `tools/package-wad.sh` extracts `banner.bin` and `icon.bin` from your local base WAD using libWiiSharp and reuses them. This makes an initial packaging test possible without hand-building new U8 archives, but **the resulting artwork may still be the original Japanese imagery**. The channel name and native homebrew UI are English; that does not automatically translate text baked into pictures.

## Create fully US-English artwork

Use a Wii channel banner editor such as CustomizeMii with assets you own or are authorized to modify. Create a new US-English banner and icon branded **TV Guide USA**, then export the `banner.bin` and `icon.bin` U8 archives.

Recommended strings:

- Channel title: `TV Guide USA`
- Subtitle: `United States TV Listings`
- Description: `TV schedules and programme information`

Set `TV_GUIDE_BANNER_BIN` and `TV_GUIDE_ICON_BIN` to the exported paths when building the WAD. A PNG or SVG alone cannot replace these Wii archive files; it must be placed in a valid banner/icon layout with correctly referenced textures/animations.

Do not commit binary banner files unless you have the rights to redistribute every included asset. A PNG/JPEG artwork export does not need to be committed; the build can reference local archives.

## Base WAD and safety

Keep the local base WAD, tickets, Wii keys, certificates and NAND backups out of the public repository. Verify the DOL in Dolphin and test the generated WAD in a separate Dolphin profile before physical installation.
