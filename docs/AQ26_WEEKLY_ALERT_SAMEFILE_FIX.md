# AQ26 weekly alert SameFile fix

This patch fixes the workflow failure:

```text
shutil.SameFileError: ... desktop_banner_5.webm and ... desktop_banner_5.webm are the same file
```

The cause was the weekly alert builder copying banner assets from `site_public/assets/banners` back into the same folder.

## Replacements

- `scripts/aq26_build_weekly_alert_pages.py`
- `.github/workflows/aq26_weekly_monday_backfill_alerts.yml`

## Fixes

- Adds `safe_copy()` to skip same-file copies.
- Keeps `--backfill-status` support.
- Re-copies weekly backfill status after operational site rebuild.
- Injects public and unredacted weekly alerts.
- Keeps WEBM banner hooks and validates them.
- Keeps public/unredacted deploy separation.

## Recommended run

First run without deployment:

```text
run_backfill=true
backfill_windows=1
build_operational_site=true
apply_alerts=true
deploy_public=false
deploy_unredacted=false
dry_run=true
```

Then deploy dry-run, then live if clean.
