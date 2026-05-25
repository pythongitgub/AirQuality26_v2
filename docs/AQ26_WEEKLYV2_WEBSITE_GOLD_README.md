# AQ26 WeeklyV2 Website Gold Patch

Adds a website-ready publishing layer on top of the validated WeeklyV2 evidence pipeline.

New workflow: `.github/workflows/aq26_weekly_v2_website.yml`.

Outputs a static site in `public_site/` with overview metrics, interactive Plotly charts, tables, methods/gates and a clickable 52-week archive/backfill scaffold. The workflow can publish to `gh-pages` and email the final evidence ZIP.

The dashboard remains controlled-review only. No external endorsement or causal attribution is claimed. True historical backfill still needs source-specific historical harvesters, but the site structure and weekly comparison links are created immediately.
