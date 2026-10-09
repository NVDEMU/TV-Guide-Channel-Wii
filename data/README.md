# Guide data

The current backend generates synthetic guide entries at request time. These are placeholders for development and testing only; they are not real television listings.

Before importing real programme data:

1. Identify a source that covers the desired Japanese region and station lineup.
2. Review the provider's licence and terms, including caching and redistribution permissions.
3. Convert that source to an internal model with explicit timezone-aware start/end values.
4. Preserve source attribution and update timestamps.
5. Add tests for Japanese text encoding, missing descriptions, midnight boundaries, and overlapping/duplicate programme records.

XMLTV is a useful interchange format for the local development API, but it has **not** been confirmed as the original Wii channel's wire format.
