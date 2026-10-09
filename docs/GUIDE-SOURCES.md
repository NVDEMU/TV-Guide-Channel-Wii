# US TV-guide sources

This project catalogues candidate providers in the machine-readable file [config/tv-guide-sources.json](../config/tv-guide-sources.json). It distinguishes a feed being technically accessible from permission to publish its schedule data. A software repository's licence does not automatically license the third-party TV listings it downloads.

## Default source for public builds: TVmaze

The GitHub Actions build queries the [TVmaze public US schedule API](https://www.tvmaze.com/api) for today and tomorrow. TVmaze says its public API is licensed under **CC BY-SA**, so the Wii interface displays a TVmaze attribution line; use and redistribution must follow its ShareAlike terms. The API returns known episodes for US broadcast and web channels; it is **not** a complete grid of every local affiliate, cable channel, news programme, or live sports event. The compact snapshot is embedded in the DOL, allowing the UI to be tested in Dolphin without a locally running Python server. It is a build-time snapshot, not continuous live data.

The snapshot is regenerated on pushes and scheduled builds. Pressing 1 attempts the configured guide API server first; if there is no server, the built-in snapshot remains available. If the provider is unreachable or has no matching items, the fallback is clearly labelled `DEMO`.

## Additional XMLTV candidates

These can broaden coverage; availability, source freshness and channel identifiers vary by provider.

| Source | Coverage / purpose | Integration note |
| --- | --- | --- |
| [US-EPG](https://github.com/vcicio/US-EPG) | Merged US national, local and sports guides | Aggregates other feeds; verify underlying data reuse terms. |
| [USA Locals](https://github.com/usa-local-epg/usa-locals) | ABC, CBS, FOX and NBC US affiliates | Repository says free for personal use; don't publish its data without permission. |
| [EPGTalk](https://github.com/acidjesuz/EPGTalk) | US, local markets, sports and free streaming channels | Separate US, US-local, sports, Free TV and lite feeds; review current terms. |
| [EPGShare](https://epgshare01.online/) | US national, local-affiliate and sports feeds | Useful as a backup candidate; data terms need checking. |
| [Open-EPG](https://www.open-epg.com/) | Eleven split US XMLTV files | Not one single complete US feed; combine only required channel groups. |
| [epg.pw](https://epg.pw/) | Large US XMLTV feed | Large download; validate freshness and channel IDs. |
| [IPTV-EPG.org](https://iptv-epg.org/guides) | Large US guide plus international guides | Filter the feed to the desired market before sending data to the Wii. |
| [iptv-org EPG](https://github.com/iptv-org/epg) | Many source sites, including US listings from TVTV, TV Guide and other providers | Check each underlying source's terms; software licence is not a data licence. |
| [i.mjh.nz](https://i.mjh.nz/) | Pluto TV, Samsung TV Plus and Plex US free-streaming channels | Supplementary streaming lineup, not a local broadcast replacement. |
| [Schedules Direct](https://schedulesdirect.org/) | US/Canadian listings by configured lineup | Account-based; use the official [XMLTV grabbers](https://github.com/XMLTV/xmltv). Don't redistribute member data without permission. |
| [TV Media](https://www.tvmedia.ca/) | Commercially licensed schedule and metadata data | Ask about a supported API and licensing costs. |
| [Gracenote](https://www.gracenote.com/) | Commercial TV listings and programme metadata | Contact the provider for API access and a distribution licence. |
| [TVmaze](https://www.tvmaze.com/api) | Public US TV and web/streaming episode schedules | CC BY-SA; attribution and ShareAlike apply. Coverage is episode-centric rather than a complete station grid. |

## Catalogue of candidate files

The JSON registry includes direct candidate URLs for:

- US-EPG merged feed: `merged_epg.xml.gz`
- USA Locals: `usalocals.xml.gz`
- EPGTalk: `US_guide.xml.gz`, `US_local_guide.xml.gz`, `Sports_guide.xml.gz`, `FreeTV_guide.xml.gz`, and `US_lite.xml.gz`
- EPGShare: `epg_ripper_US2.xml.gz`, `epg_ripper_US_LOCALS1.xml.gz`, and `epg_ripper_US_SPORTS1.xml.gz`
- Open-EPG: `unitedstates1.xml.gz` through `unitedstates11.xml.gz`
- epg.pw: `epg_US.xml.gz`
- IPTV-EPG.org: `epg-us.xml.gz`
- i.mjh.nz: Pluto TV US, Samsung TV Plus US and Plex US
- iptv-org generated TVTV / TV Guide sources, including a New York guide

These are **candidate inputs**, not all enabled sources. Several community feeds describe themselves as personal-use or have no clear explicit data licence. Public automated builds use TVmaze's documented CC BY-SA public API by default; unverified feeds should be used only in a private build after reviewing their terms.

## Using another XMLTV feed

For a local/private backend, set `TV_GUIDE_XMLTV_PATH` to an XMLTV file whose terms permit your use, then restart the API. XMLTV may be plain `.xml` or gzip-compressed `.xml.gz`. A multi-source merge should be filtered to the user's actual market and Wii-sized channel/programme limits rather than sending a 500 MB guide directly to the console.

Schedules can contain local-time conventions, source-specific channel IDs and duplicates. Keep original channel IDs during a merge, deduplicate by channel/start/title, reject malformed timestamps and indicate source/freshness. No provider can guarantee correct lineup matches for every US ZIP code without an explicit lineup or market setting.
