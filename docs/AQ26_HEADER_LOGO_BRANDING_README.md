# AQ26 Header Logo Branding Patch

This patch separates the logo roles:

- `favicon.svg`, touch icons and Android icons remain the compact icon.
- `air_quality_web.svg` is the visible SCC Nexus Air Quality Report header logo.
- `aq26_brand_header.css/js` inject the wide header logo into public and report HTML pages.
- The script is safe to run after each site build and before deployment.

Recommended pipeline order:

```bash
python scripts/aq26_public_site_guard_build.py --site-root site_public --asset-source website/assets --force --fail-on-blank
python scripts/aq26_apply_header_logo_branding.py --site-root site_public --asset-source website/assets
python scripts/aq26_build_unredacted_site.py --repo-root . --public-site site_public --output-site site_unredacted --max-index-files 1000
python scripts/aq26_apply_header_logo_branding.py --site-root site_unredacted --asset-source website/assets --summary site_unredacted/data/unredacted/header_branding_status.json
```

Then run the dual-site deployment.

Browser favicon cache note:
Browsers cache favicons aggressively. Test these directly after deployment:

```text
https://sccwebdesigntest.co.uk/assets/air_quality_web.svg?v=aq26-header-20260527
https://sccwebdesigntest.co.uk/assets/favicon.svg?v=aq26-icon-20260527
```