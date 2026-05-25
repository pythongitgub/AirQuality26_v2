
# AQ26 SCC Nexus Hostinger Website Patch

This patch adds a CompaniesHouse26-style SCC Nexus website layer for AirQuality26 WeeklyV2.

## What it adds

- `AQ26 WeeklyV2 SCC Nexus Website` GitHub Action.
- SCC Nexus / CompaniesHouse-style static site generator.
- Hostinger SSH/rsync deployment using your new secrets.
- Brand assets, banners, favicon/touch-icon assets.
- 52-week historical archive/backfill slots.
- Interactive Plotly charts.
- Source record tables.
- Readiness and methodology pages.
- Latest evidence ZIP/report downloads.

## Required Hostinger secrets

- `HOSTINGER_PUBLIC_HTML_DIR`
- `SCCNEXUS_SSH_HOST`
- `SCCNEXUS_SSH_PASSWORD`
- `SCCNEXUS_SSH_PORT`
- `SCCNEXUS_SSH_USERNAME`

Default deployment target:

`$HOSTINGER_PUBLIC_HTML_DIR/airquality26`

The expected public URL is usually:

`sccnexus.com/airquality26/`

Change the `remote_subdir` workflow input to publish somewhere else.

## Historical weekly data

The site maintains at least 52 weekly slots.

- Real completed weeks appear as linked evidence runs.
- Missing historical weeks appear as `not_yet_harvested` backfill slots.
- Each weekly run fetches existing `data/history` from Hostinger before rebuilding so history accumulates.

True historical pollutant backfill still needs source-specific historical backfill workflows. This patch creates the website structure and preservation mechanism now.

## Recommended first run

Actions > AQ26 WeeklyV2 SCC Nexus Website > Run workflow

Inputs:
- `lookback_days`: 14
- `history_weeks`: 52
- `deploy_to_hostinger`: true
- `remote_subdir`: airquality26
- `send_email`: true
