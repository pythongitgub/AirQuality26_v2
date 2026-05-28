# AQ26 Remaining Incinerator Overlay Finder V3.1

This patch updates the V3 overlay finder so repeated batch runs move forward instead of re-querying the same first facilities.

## Key behaviour

- Keeps the 46-facility broad incinerator register as the spine.
- Keeps the validated DEFRA/AURN overlay CSV as authoritative.
- Skips facilities already covered by selected V3 candidate overlays when `skip_existing_candidates=true`.
- Allows controlled re-querying with `force_requery=true`.
- Uses OpenAQ v3-compatible geospatial queries:
  - `coordinates=latitude,longitude`
  - radius capped at 25,000 metres
  - `iso=GB`
  - bbox fallback in `minLon,minLat,maxLon,maxLat` order
- Handles 429 Retry-After and backoff.
- Writes candidate rows as `candidate_needs_review`; it does not promote them to validated overlays.

## Recommended run

Use batches of 10:

```text
live_openaq=true
use_v2_cache=true
skip_existing_candidates=true
force_requery=false
max_facilities=10
radius_km=25
limit_per_query=100
min_score=35
sleep_seconds=3.0
max_retries=3
exhaustive=false
write_page=true
commit_outputs=true
```

Repeat until `no_candidate_selected_yet` rows are reduced. Then use manual review/promotion.
