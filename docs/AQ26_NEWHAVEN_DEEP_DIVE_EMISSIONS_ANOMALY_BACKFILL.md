# AQ26 Newhaven Deep-Dive Emissions and Anomaly Backfill

This patch adds the next content-depth layer after the public canonical count fix.

## What it does

- Creates `site_public/newhaven-deep-dive.html`.
- Builds public-safe evidence inventory summaries.
- Builds unredacted local/Drive evidence inventory tables.
- Attempts to extract structured emissions/measurement/ELV/throughput/exceedance records from CSV evidence already in the repository.
- Generates statistical anomaly review prompts where enough numeric evidence exists.
- Does **not** make regulatory, health, legal, breach or causal claims.

## Important limitation

The current public site already has overlay/candidate charts. It does **not** yet have robust public emissions-value charts unless the relevant row-level emissions/measurement CSVs are present in the repository or reachable through the configured Drive service account.

Your Drive evidence suggests these data exist in the wider AirQuality26 Drive project, especially the Newhaven 35R2 dossier and 35PB row-level QA outputs. This workflow is the bridge that starts wiring those evidence layers into the website.

## Recommended first run

Run:

`AQ26 Newhaven Deep-Dive Emissions and Anomaly Backfill`

Use:

- `drive_fetch = false`
- `max_rows_per_file = 50000`
- `deploy_public = false`
- `deploy_unredacted = false`
- `dry_run = true`

Review the artifact.

## Recommended Drive-enabled run

Only after the first run succeeds and the service account has access to the AirQuality26 Drive folder:

- `drive_fetch = true`
- `deploy_public = false`
- `deploy_unredacted = false`
- `dry_run = true`

## Deployment

If the artifact is clean:

- `deploy_public = true`
- `deploy_unredacted = false`
- `dry_run = true`

Then live:

- `dry_run = false`

For unredacted deployment, rotate/confirm `SCC_UNREDACTED_PASSWORD` and use `deploy_unredacted = true`.

## Safety language

Public outputs must keep the notice that AQ26 does not make regulatory determinations, health advice, legal conclusions, breach findings or causal attribution.
