# AQ26 Vibrant Public Site Rebuild

This patch replaces accumulated presentation-only fixes with a single public-site builder:

- `scripts/aq26_build_public_site_vibrant.py`
- `.github/workflows/aq26_build_public_site_vibrant.yml`
- updated `.github/workflows/aq26_deploy_dual_site_sccwebdesigntest.yml`

The builder reads existing JSON/CSV outputs from `site_public/data/`, preserves downloads and data payloads, and rebuilds all public HTML pages from one consistent template.

It restores:
- animated hero gradients;
- moving evidence ticker;
- readable content cards;
- public-safe readiness wording;
- chart payload cards and previews;
- consistent white header with `air_quality_web.svg`;
- compact favicon only for browser/touch usage.

Run:

1. `AQ26 Build Vibrant Public Site` with `commit_outputs=true`.
2. `AQ26 Deploy Public and Unredacted Sites` with `rebuild_public=true`, first `dry_run=true`, then `dry_run=false`.

The public deploy excludes `/unredacted/***` so the public rsync cannot delete the protected internal site.
