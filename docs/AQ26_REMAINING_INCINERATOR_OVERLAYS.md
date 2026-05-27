# AQ26 Remaining Incinerator Overlay Finder

This workflow restores the incinerator/control-site register as the evidence spine and finds monitoring overlay candidates for the facilities that do not yet have validated DEFRA/AURN overlays.

## Inputs

- `UK_Incinerators_with_Controls_Full_v3.csv` — broad 46-facility register.
- `UK_Incinerators_with_DEFRA_Sites_v3_validated_Full.csv` — existing 8 validated DEFRA/AURN overlays.

## Outputs

Written to `site_public/data/focus/overlays/`:

- `incinerator_overlay_summary.json`
- `validated_defra_overlays.json/csv`
- `remaining_overlay_queue.json/csv`
- `candidate_monitoring_overlays.json/csv`
- `selected_candidate_overlays_needing_review.json/csv`
- `overlay_discovery_errors.json`

Optional public page:

- `site_public/incinerator-overlays.html`

## Important interpretation

Only the 8 rows in the validated DEFRA/AURN overlay CSV are treated as validated. Live OpenAQ results are candidates and must be reviewed before becoming accepted overlays.

## Recommended run

Run `AQ26 Remaining Incinerator Overlay Finder` with:

- `live_openaq = true`
- `max_facilities = 0`
- `radius_km = 50`
- `limit_per_query = 50`
- `write_page = true`
- `commit_outputs = true`

Then review `selected_candidate_overlays_needing_review.csv` and promote accepted overlays into the validated overlay CSV.
