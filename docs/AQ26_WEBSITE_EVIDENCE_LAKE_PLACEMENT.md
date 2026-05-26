# AQ26 website evidence-lake placement patch

This patch places the Google Drive evidence-lake status card automatically into the generated AQ26 home page.

## Why this location

The card is inserted on `index.html` immediately after **Latest evidence status** and before **Interactive comparison charts**. That is the safest and clearest placement because it explains storage/provenance before visitors see charts.

## Important

Do not manually edit `site_public/index.html` as the main fix. The weekly website builder regenerates that file. The durable fix is in:

`scripts/aq26_weeklyv2_build_sccnexus_site.py`

The builder now writes the evidence-lake container automatically and includes:

```html
<script src="assets/aq26_evidence_lake.js"></script>
```

The visible container is:

```html
<div id="aq26-evidence-lake" data-index="data/providers/laqn/evidence_lake/latest_index.json"></div>
```

## Run order

1. Commit this patch.
2. Run `AQ26 LAQN Provider Probe V3.5` with the tiny historical probe checked.
3. Run `AQ26 Evidence Lake Package` for provider `laqn`.
4. Run `AQ26 WeeklyV2 SCC Nexus Website` with deployment enabled, or run the standalone Hostinger deploy workflow.

## What the public site shows

If the evidence-lake package has not run yet, the card shows a safe pending message rather than crashing.

If the compact index exists, the card shows provider, file count, total indexed size, site-ready file count, raw file count and manifest pointer.
