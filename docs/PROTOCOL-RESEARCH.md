# Original channel protocol research

## What is known

TV no Tomo was the Japanese TV guide channel for Wii. Existing community research includes Kaitai Struct definitions for several of the channel's data files. In particular, [Wii-Kaitai's Terebi no Tomo definitions](https://github.com/quatric/Wii-Kaitai/tree/main/channels/terebi_no_tomo) describe:

- `tv_header.ksy`: region and channel selections plus genre/audio/resolution lookup tables.
- `tv_epg.ksy`: an HDPK `001B` guide package containing channel directories, program pointers, timestamps and metadata.
- `tv_str.ksy`: string-index tables whose full string encoding/semantics are still described as partially unknown.

The documented EPG and header layouts use big-endian fields and offsets relative to byte `0x20`. These definitions give us useful file-format research, but do not by themselves establish the original live-service request URLs, authentication, update flow, or every required field.

Reference projects:
- [WiiLink24/tv-epg](https://github.com/WiiLink24/tv-epg) — EPG acquisition/utilities. Its README says pre-made guides are no longer provided and describes running guide downloads yourself.
- [WiiLink24/kaitais](https://github.com/WiiLink24/kaitais) — original community format definitions.
- [Wii-Kaitai](https://github.com/quatric/Wii-Kaitai) — consolidated format definitions.

## Next reverse-engineering milestones

1. Obtain lawful test material: files from a channel installation you own, sample data published by the community, or captures made on your own console. Do not commit proprietary WADs, tickets, keys, NAND dumps, personal identifiers, or credentials.
2. Compare valid `header.bin`, EPG, and string-package samples against the Kaitai definitions. Record observed fields separately from guesses.
3. Identify the original channel's server requests and expected responses. A PCAP/HTTP trace should be redacted before sharing; never share account credentials or device-specific secrets.
4. Write golden tests for parsing existing sample files before attempting to generate replacements.
5. Implement an EPG package serializer only after each relevant field, offset, size, encoding, timestamp epoch, and footer rule has evidence.
6. Determine which remote features rely on hardware infrared functions and which are service-dependent.
7. Test in Dolphin first, then on real hardware. Record exact channel version, region, request, response status, and visible result.

## Do not confuse the development API with the Wii protocol

The endpoints implemented in `backend/main.py` are a modern JSON/XMLTV API created for this project. They intentionally do not claim to speak the Wii channel's original network protocol. An adapter will be needed once the protocol is established.
