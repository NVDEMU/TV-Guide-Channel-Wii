# Supplied Japanese base WAD inspection

The user-supplied file `TV no Toma (Japan) (Channel).wad` was inspected locally and is not committed to this repository.

Observed metadata:
- WAD type marker: `Is` (installable title package).
- WAD size: 31,034,240 bytes.
- Title ID: `0001000148424E4A`, suffix `HBNJ`.
- TMD content records: 14.
- TMD boot index: 13.
- TMD region code: `0` (`Japan`).
- Declared WAD section sizes and padded content table fit the complete file length.

The title ID suffix identifies the supplied Japanese TV no Tomo channel, and the actual TMD region field at offset `0x19C` is `0` (Japan). The adjacent field at `0x19E` is reserved, not the region code.

This validates the file's outer structure and clear metadata only. It does not decrypt or inspect each executable, verify Nintendo signatures, prove the WAD is unmodified, or guarantee that reusing it is safe. Use it only as a local packaging input. Do not commit the WAD, ticket, certificates, NAND dump, or console keys to the public repository.

Use `python tools/inspect_wad.py "/path/to/TV no Toma (Japan) (Channel).wad"` to run the same structural inspector on your copy.
