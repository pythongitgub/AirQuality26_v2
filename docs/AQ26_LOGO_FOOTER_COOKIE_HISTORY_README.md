# AQ26 logo, footer, cookies and history patch

This patch updates the SCC Nexus AQ26 website.

## Changes

- Uses `website/assets/brand/air_quality_web.svg` as the main page/header logo.
- Keeps the AQ logo as favicon, web manifest icon and subtle watermark.
- Adds SCC Nexus-style footer navigation.
- Generates these footer pages:
  - `about.html`
  - `privacy.html`
  - `cookies.html`
  - `accessibility.html`
  - `terms.html`
  - `contact.html`
- Adds a cookie banner.
- Collates completed historical weekly summaries from:
  - Hostinger `data/history/`
  - Hostinger `data/weekly_index.json`
  - `outputs/10_historical_backfill/history`
  - `outputs/10_historical_backfill/site_history`
  - `outputs/historical_site/history`

## Historical data note

This patch collates and displays every completed historical weekly summary it can find. It does not invent missing source records. Weeks without harvested evidence remain labelled `not_yet_harvested` until controlled historical backfill workflows create real records and manifests.
