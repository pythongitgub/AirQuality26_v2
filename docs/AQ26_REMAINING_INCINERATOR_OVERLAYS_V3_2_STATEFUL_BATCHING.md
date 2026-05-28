# AQ26 Remaining Incinerator Overlays V3.2 — Stateful Batching

This patch replaces the V3 overlay finder with a stateful batching version.

## Why

V3 fixed the OpenAQ query format and rate limiting, but repeated runs could re-query the first facilities again. V3.2 reads previous overlay outputs and skips facilities already covered by either:

- an existing validated DEFRA/AURN overlay; or
- a cumulative candidate overlay awaiting review.

## Main outputs

- `site_public/data/focus/overlays_v3/incinerator_overlay_summary.json`
- `site_public/data/focus/overlays_v3/remaining_overlay_queue.csv`
- `site_public/data/focus/overlays_v3/candidate_monitoring_overlays_this_run.csv`
- `site_public/data/focus/overlays_v3/selected_candidate_overlays_this_run.csv`
- `site_public/data/focus/overlays_v3/selected_candidate_overlays_cumulative.csv`
- `site_public/data/focus/overlays_v3/selected_candidate_overlays_needing_review.csv`
- `site_public/data/focus/overlays_v3/facility_overlay_status.csv`
- `site_public/data/focus/overlays_v3/openaq_query_diagnostics.csv`
- `site_public/incinerator-overlays.html`

## Recommended run settings

Use the workflow `AQ26 Remaining Incinerator Overlay Finder V3` with:

- `live_openaq=true`
- `use_v2_cache=true`
- `skip_existing_candidates=true`
- `force_requery=false`
- `batch_offset=0`
- `max_facilities=10`
- `radius_km=25`
- `limit_per_query=100`
- `min_score=35`
- `sleep_seconds=3.0`
- `max_retries=3`
- `exhaustive=false`
- `write_page=true`
- `commit_outputs=true`

## Expected success signs

- `previous_candidate_facilities_skipped` should be greater than zero after the first successful V3/V3.2 batch.
- `queried_facilities` should move to the next unresolved facilities instead of repeating the first batch.
- `rate_limited_calls` should remain zero or low.

## Integrity note

The workflow does not promote candidates to validated overlays. Candidate rows remain review-only until manually checked for source quality, distance, site type, pollutant coverage and appropriateness as facility-near/control/background evidence.
