# AQ26 WeeklyV2 V3.2 Backfill Hardening Patch

This patch is a small hardening update after the successful V3.1 date-bound backfill proof.

## Main corrections

1. **NewsAPI disabled by default during historical backfill**
   - Prevents avoidable `HTTP 429 rateLimited` errors from contaminating harvested historical weeks.
   - Can be re-enabled from the workflow input `newsapi_enabled=true`.

2. **GDELT throttled and reduced for backfill**
   - Uses `AQ26_GDELT_MIN_SECONDS=6` and limits backfill queries to 3 by default.
   - GDELT remains contextual evidence only and warnings are non-blocking.

3. **Gemini optional and non-blocking during backfill**
   - Disabled by default in historical backfill.
   - Uses `gemini-3.5-flash` as the default model when enabled.
   - Supports both `AQ26_GEMINI_MODEL` and `GEMINI_MODEL`.

4. **Drive roll-up improved**
   - Historical summaries now derive `drive_file_count` from `gdrive` source-record counts.

5. **Latest live and latest backfill summaries separated**
   - `site_public/data/latest_live_summary.json`
   - `site_public/data/latest_backfill_summary.json`
   - This avoids confusing the live observatory state with historical backfill batches.

## Files included

```text
scripts/aq26_weeklyv2_collect.py
scripts/aq26_weeklyv2_history_v3.py
.github/workflows/aq26_weeklyv2_backfill_v3.yml
.github/workflows/aq26_weekly_v2_sccnexus_website.yml
configs/aq26_weeklyv2_history_v3.yml
requirements.txt
README_AQ26_V32_BACKFILL_HARDENING_PATCH.md
```

## Recommended first run

Use GitHub Actions:

```text
Actions → AQ26 WeeklyV2 Historical Backfill V3.2 → Run workflow
```

Recommended inputs:

```text
backfill_start_date: 2024-06-24
backfill_end_date: 2026-05-25
backfill_limit_windows: 4
history_weeks: 104
strict_validation: true
force: false
newsapi_enabled: false
gdelt_enabled: true
gemini_enabled: false
```

This should process:

```text
2024-06-24 → 2024-07-01
2024-07-01 → 2024-07-08
2024-07-08 → 2024-07-15
2024-07-15 → 2024-07-22
```

## Gemini note

If you want to test Gemini, set either GitHub secret:

```text
AQ26_GEMINI_MODEL=gemini-3.5-flash
```

or:

```text
GEMINI_MODEL=gemini-3.5-flash
```

Then run one small batch with:

```text
gemini_enabled: true
backfill_limit_windows: 1
```

Gemini remains narrative/metadata-only and should not determine external submission readiness.
