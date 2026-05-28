# AQ26 Weekly Monday Backfill Alerts

Adds a Monday 07:00 UK update layer for the public redacted site and the protected unredacted review site.

## Adds

- `.github/workflows/aq26_weekly_monday_backfill_alerts.yml`
- `scripts/aq26_build_weekly_alert_pages.py`
- `site_public/weekly-update.html`
- `site_unredacted/weekly-update.html`
- front-page alert injection on both index pages
- redacted public alert JSON
- unredacted alert JSON with backfill script status
- moving ticker and WEBM banner support when `assets/banners/*.webm` is present

## First run

Use:

- `run_backfill`: true
- `backfill_windows`: 1
- `build_operational_site`: true
- `apply_alerts`: true
- `deploy_public`: false
- `deploy_unredacted`: false
- `dry_run`: true

Inspect artifact, then deploy dry-run, then live.

## Weekly schedule

GitHub cron is UTC. The workflow schedules both 06:00 and 07:00 UTC Monday, then a Python Europe/London gate only allows the one matching Monday 07:00 UK time to proceed.

## Legal/public safety

The public alert is deliberately cautious: no regulatory determination, legal conclusion, health advice or causal attribution. Candidate overlays remain review-only. Full diagnostics stay in `/unredacted/`.
