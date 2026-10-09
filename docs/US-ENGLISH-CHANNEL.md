# US-English channel design

The repository is building a **new US-English homebrew guide frontend** inspired by the old TV no Tomo channel. It is not a binary translation patch of Nintendo's original channel. Translating the original executable itself would require the original channel's code/data, its asset formats, and a precise understanding of its obsolete service dependencies; this project does not redistribute that proprietary binary.

## User experience

- Display name: **TV Guide USA**
- Language/locale: English (United States)
- Guide market: United States
- Time-zone choices: Eastern, Central, Mountain, Pacific
- Channel/program selection via Wii Remote D-pad
- A opens the selected programme's details
- 1 refreshes data
- Plus cycles US time zones
- HOME returns to the Wii Menu

The current user interface uses libogc's text console to establish reliable controls and guide loading first. A custom GX-rendered grid and polished Wii Menu banner are follow-up visual work after backend/data compatibility is stable.

## Configure the US backend

Run FastAPI on a computer reachable from the Wii over the same trusted LAN, then set `server=` and `port=` in `sd:/apps/tv-guide-channel-wii/config.ini`. For an actual schedule, configure `TV_GUIDE_XMLTV_PATH` to a US-English XMLTV guide source you are allowed to use.

The Wii client currently uses plain HTTP and numeric IPv4 addresses. That is suitable only for local-network prototyping. A public Internet service needs HTTPS/TLS support (or another secure, validated transport) before public deployment. Do not expose the prototype endpoint directly to the Internet.

## Data caveats

- Built-in ABC/CBS/NBC/FOX/PBS entries are placeholders labelled `DEMO`.
- Imported XMLTV content is marked `FEED`, not guaranteed to be current/live just because a file is present.
- The schedule provider determines actual channel lineups and coverage. No national or local US listing availability is claimed until a permitted feed is configured and refreshed.
