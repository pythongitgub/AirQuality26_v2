# AQ26 Remaining Incinerator Overlay Finder V3.3

This replaces V3.2, whose skip logic was too broad and skipped all remaining facilities by reading raw candidate rows as if they were selected overlays.

## V3.3 rule

Only these count as existing candidate coverage:

- `selected_candidate_overlays_needing_review.csv`
- `selected_candidate_overlays_cumulative.csv`
- `facility_overlay_status.csv` rows with `overlay_status = candidate_overlay_needs_review`

These do **not** count as coverage:

- `candidate_monitoring_overlays.csv`
- OpenAQ diagnostics
- V2 cache raw candidates
- low-confidence raw candidates not selected for review

## Recommended run

```text
live_openaq = true
use_v2_cache = true
skip_existing_candidates = true
force_requery = false
batch_offset = 0
max_facilities = 10
radius_km = 25
limit_per_query = 100
min_score = 35
sleep_seconds = 3.0
max_retries = 3
exhaustive = false
write_page = true
commit_outputs = true
```

Expected summary after the first corrected run:

```text
workflow_version: v3.3_stateful_batching_fixed_skip
previous_selected_facilities_loaded: about 7-9
previous_candidate_facilities_skipped: about 7-9
facilities_queried_this_run: 10
rate_limited_calls: 0
```
