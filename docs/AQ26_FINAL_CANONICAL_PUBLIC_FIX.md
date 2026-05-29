# AQ26 Final Canonical Public Fix

Run this after the public count/header sanity fixes if old generated page fragments still show:

- `86 facilities`
- `43 fallback cases`
- duplicated fallback rows in the facility table.

The script deduplicates the overlay status CSV by facility key, prefers validated/candidate rows over stale fallback rows, rebuilds the public facility tables, rewrites visible counts, and validates that the legacy counts no longer appear on the main public pages.
