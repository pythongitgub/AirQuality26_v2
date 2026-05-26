# AQ26 WeeklyV2 Backfill + Interactive Site V3 patch

This patch adds a conservative historical backfill/index/chart layer for the AirQuality26_v2 weekly site.

## Files

- `scripts/aq26_weeklyv2_history_v3.py` — canonical weekly index, controlled backfill runner, chart JSON builder, validator.
- `.github/workflows/aq26_weeklyv2_backfill_v3.yml` — manual GitHub Action for historical batches.
- `notebooks/AQ26_60A_Backfill_Interactive_Site_V3.ipynb` — Colab installer/runner.

## Local / Colab quick run

```bash
python scripts/aq26_weeklyv2_history_v3.py --repo-root . --output-root outputs --site-root site_public --history-weeks 104 --history-end-date 2026-05-25 build-site-data
```

## GitHub Actions batch run

Open Actions → `AQ26 WeeklyV2 Historical Backfill V3` → Run workflow.
Start with 4 windows. Increase only when stable.

## What this does not do

It does not fabricate historical evidence. It only marks a week as harvested when the existing AQ26 weekly scripts or evidence summaries create real non-zero source records.
