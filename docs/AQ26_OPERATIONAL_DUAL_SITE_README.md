# AQ26 Operational Dual Site

This patch builds a complete facility-led AQ26 website using the incinerator overlay outputs.

## Public redacted site

Generated under `site_public/`:

- `index.html` — moving banner public observatory landing page
- `incinerators.html` — full 46-facility register table
- `newhaven.html` — validated Newhaven proof-of-quality case study
- `overlays.html` — validated/candidate/unresolved overlay status
- `comparisons.html` — interactive Chart.js charts
- `methodology.html` — legal/scientific methodology and AI/ML caveats
- `downloads.html` — redacted public downloads

## Unredacted site

Generated under `site_unredacted/`:

- `index.html` — internal dashboard
- `candidates.html` — candidate review table
- `diagnostics.html` — OpenAQ/API diagnostics
- `evidence.html` — links to full generated evidence
- `.htaccess` — basic auth stub; deployment workflow writes `.htpasswd` from `SCC_UNREDACTED_PASSWORD`

## Legal safety

The public pages avoid causal claims, breach findings, health advice, regulatory determinations and raw internal diagnostics. Candidate overlays are described as review-only.

## AI / ML

The AI/ML elements are transparent triage signals based on overlay status, score bands, candidate class and review priority. They are not regulatory or causal conclusions.

## Run

Use workflow:

`AQ26 Operational Dual Site Build and Deploy`

First run with:

- `deploy_public=false`
- `deploy_unredacted=false`

Then deploy dry-run:

- `deploy_public=true`
- `deploy_unredacted=true`
- `dry_run=true`

Then live:

- `dry_run=false`

