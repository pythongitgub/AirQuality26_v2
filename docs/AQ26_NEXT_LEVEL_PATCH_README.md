# AQ26 next-level website and workflow consolidation patch

This patch is designed to be copied into the root of `AirQuality26_v2`.

## What it adds/replaces

- One main production workflow: `.github/workflows/weekly-production.yml`
- A lean interactive public website layer:
  - `dashboard.html`
  - `data-catalog.html`
  - `weekly-archive.html`
  - `assets/aq26_nextlevel.css`
  - `assets/aq26_dashboard.js`
  - `data/weekly/dashboard_summary.json`
  - `data/weekly/facility_status.json`
  - `data/weekly/coverage_trend.json`
- SEO files:
  - `sitemap.xml`
  - `robots.txt`
  - canonical tags and page descriptions on new/rewritten pages
- QA scripts:
  - public/unredacted split check
  - sitemap/robots check
  - oversized public file pruning
  - workflow consolidation warning
- Housekeeping helpers:
  - `scripts/disable_extra_workflows.sh`
  - `scripts/disable_extra_workflows.ps1`
  - `scripts/aq26_repo_lean_suggestions.py`

## Recommended use

1. Unzip this patch into the repository root.
2. Commit the patch.
3. Run the production workflow manually first with:
   - `deploy_to_hostinger`: `false`
   - `dry_run`: `true`
   - `upload_to_drive`: `false`
   - `send_email`: `false`
4. If the build passes, run again with:
   - `deploy_to_hostinger`: `true`
   - `dry_run`: `false`
   - `upload_to_drive`: `true`
   - `send_email`: optional.

## Important

This patch does **not** delete your old workflows automatically. That is deliberate. First confirm the new production workflow passes. Then run one of the disable scripts to move old active `.yml`/`.yaml` workflows into `docs/disabled_workflows/` as `.txt` files.
