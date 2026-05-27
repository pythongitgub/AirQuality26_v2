# AQ26 Remaining Incinerator Overlay Finder V2

This replacement fixes the previous 422-prone OpenAQ overlay discovery workflow.

## Key fixes

- OpenAQ point radius is capped at 25,000 metres.
- Coordinates are queried as `latitude,longitude` for OpenAQ v3.
- `sort=distance` and `order_by=distance` are removed.
- `iso=GB` is used instead of `countries_id=GB`.
- BBox fallback uses `minLon,minLat,maxLon,maxLat` and is never mixed with coordinates/radius.
- The exact URL and HTTP response body are saved for every failed query.
- New matches are `candidate_needs_review`, never auto-validated.

## Recommended run sequence

First smoke test:

- `live_openaq=true`
- `max_facilities=5`
- `radius_km=25`
- `limit_per_query=100`
- `commit_outputs=true`

Then all remaining facilities:

- `max_facilities=0`

## Outputs

- `site_public/data/focus/overlays_v2/incinerator_overlay_summary.json`
- `site_public/data/focus/overlays_v2/remaining_overlay_queue.csv`
- `site_public/data/focus/overlays_v2/openaq_query_diagnostics.csv`
- `site_public/data/focus/overlays_v2/candidate_monitoring_overlays.csv`
- `site_public/data/focus/overlays_v2/selected_candidate_overlays_needing_review.csv`
- `site_public/incinerator-overlays.html`

## Interpretation

Candidate overlays should be reviewed against DEFRA/AURN/UK-AIR station metadata before being promoted into the validated overlay CSV.
