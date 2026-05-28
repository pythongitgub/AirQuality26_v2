# AQ26 Remaining Incinerator Overlay Finder V3

This workflow is the production-grade follow-up to the V2 overlay finder.

## Why V3 exists

V2 proved that the earlier OpenAQ failures were caused by malformed request patterns. It also found useful candidates, but the full run hit OpenAQ rate limiting and re-queued some already validated facilities because facility names did not match exactly.

V3 fixes this by:

- aliasing facility names such as `Tyseley EfW` / `Tyseley ERF`, `Riverside RR ERF` / `Riverside Resource Recovery`, and `Runcorn EfW` / `Runcorn TPS`;
- using OpenAQ-safe point and bounding-box queries;
- respecting 429 rate limits with retries and sleep intervals;
- optionally importing V2 candidates so the API is not hammered repeatedly;
- classifying candidates before any validation promotion.

## Recommended runs

### Smoke test

Run `AQ26 Remaining Incinerator Overlay Finder V3` with:

- `live_openaq = true`
- `use_v2_cache = true`
- `max_facilities = 5`
- `sleep_seconds = 3.0`
- `max_retries = 3`
- `exhaustive = false`
- `commit_outputs = true`

### Controlled batch

Use `max_facilities = 10` until rate limiting is stable.

### Full run

Only use `max_facilities = 0` after batch runs show few/no 429 responses. Keep `sleep_seconds` at 3–5 seconds.

## Outputs

- `site_public/data/focus/overlays_v3/incinerator_overlay_summary.json`
- `site_public/data/focus/overlays_v3/facility_overlay_status.csv`
- `site_public/data/focus/overlays_v3/candidate_monitoring_overlays.csv`
- `site_public/data/focus/overlays_v3/selected_candidate_overlays_needing_review.csv`
- `site_public/data/focus/overlays_v3/openaq_query_diagnostics.csv`
- `site_public/incinerator-overlays.html`

## Validation rule

All new matches are candidates. Do not promote them into the validated DEFRA/AURN overlay file until reviewed against source provenance, distance, pollutant coverage, geography, and facility/control-site logic.
