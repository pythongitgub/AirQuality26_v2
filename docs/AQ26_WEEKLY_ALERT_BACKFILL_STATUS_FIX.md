# AQ26 weekly alert backfill-status fix

This patch fixes the workflow/script mismatch where `.github/workflows/aq26_weekly_monday_backfill_alerts.yml` calls:

```bash
python scripts/aq26_build_weekly_alert_pages.py --backfill-status site_public/data/weekly/backfill_status.json
```

but the script did not previously accept `--backfill-status`.

## Files replaced

- `scripts/aq26_build_weekly_alert_pages.py`
- `.github/workflows/aq26_weekly_monday_backfill_alerts.yml`
- `.github/workflows/aq26_operational_dual_site.yml`

## Behaviour

- Creates `site_public/data/weekly/` and `site_unredacted/data/weekly/` safely.
- Accepts `--backfill-status` and uses that JSON as the first source of backfill status.
- Builds `weekly-update.html` for public and unredacted sites.
- Injects a weekly alert into both homepages.
- Preserves legal-safe public language.
- Applies WEBM banners after the operational site build so they are not overwritten.
- Validates banner hooks and key assets before deployment.

## Recommended run

First run with deployment disabled:

- `run_backfill = true`
- `backfill_windows = 1`
- `build_operational_site = true`
- `apply_alerts = true`
- `deploy_public = false`
- `deploy_unredacted = false`
- `dry_run = true`

Then run with deployment dry-run, then live.
