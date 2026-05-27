# AQ26 consistent public site rebuild

This patch replaces the mixed/partially styled public pages with one clean, readable template.

It intentionally rebuilds the public HTML shell from the data already in `site_public/data` and `site_public/downloads`, so users do not see raw unstyled fallback pages while backfill catches up.

## Main files

- `scripts/aq26_rebuild_public_site_consistent.py`
- `.github/workflows/aq26_rebuild_public_consistent_site.yml`
- `.github/workflows/aq26_deploy_dual_site_sccwebdesigntest.yml`
- `website/assets/air_quality_web.svg`
- `website/assets/favicon.svg`

## Run order

1. Run `AQ26 Rebuild Public Site Consistently` with `commit_outputs=true`.
2. Run `AQ26 Deploy Public and Unredacted Sites` with `dry_run=true`.
3. If clean, rerun `AQ26 Deploy Public and Unredacted Sites` with `dry_run=false`.
4. Run the WeeklyV2/backfill workflow to populate richer chart payloads.
5. Redeploy.

## Design rules

- Full SCC Nexus Air Quality Report SVG is used for visible headers.
- Compact favicon is used only for browser/touch icons.
- Public deploy excludes `/unredacted/***` so it does not wipe the protected area.
- Core pages are generated with readable text, white content cards, high-contrast hero text and a mobile hamburger menu.
