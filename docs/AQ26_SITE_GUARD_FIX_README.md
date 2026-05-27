# AQ26 site guard fix

This patch fixes the dual-site deploy failure where `site_public` was missing required pages such as `index.html`, `source-records.html`, `readiness.html`, and `methodology.html`.

It adds a guard builder:

```bash
python scripts/aq26_public_site_guard_build.py --site-root site_public --asset-source website/assets --force --fail-on-blank
```

The deploy workflow now runs that guard before deployment, so public pages are created/repaired before the no-blank check.

## Recommended run

Run **AQ26 Deploy Public and Unredacted Sites** with:

- `deploy_public=true`
- `deploy_unredacted=true`
- `dry_run=true`
- `auth_debug=true`
- `force_public_polish=true`
- `max_index_files=1000`

If clean, rerun with `dry_run=false`.

## Backfill

This is not a replacement for backfill. It prevents blank pages while backfill and chart payloads are rebuilt. After deployment is stable, run the WeeklyV2 backfill or Stage2 follow-on workflow, then rerun this deployment.
