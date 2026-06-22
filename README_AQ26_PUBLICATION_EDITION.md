# AQ26 publication edition patch

This patch turns AQ26 from a mixed historical build into one publication-grade website system.

## What it changes

- Replaces the canonical site builder with a richer environmental-forensic evidence portal.
- Adds public pages for official filings, monitoring / meteorology, and satellite / CAMS / Earthdata status.
- Keeps full evidence ZIP bundles out of the public downloads folder.
- Keeps `/unredacted/` noindex and protected by an external `.htpasswd` path.
- Adds stricter audit rules for SEO, sitemap, local assets, public ZIP leaks, dangerous phrases, protected noindex and forensic caveat wording.
- Adds an optional workflow to retire old one-off workflows after the canonical deploy is proven.

## Run order

1. Upload these files into the root of `AirQuality26_v2`.
2. Run `AQ26 Canonical Site Build, Audit and Deploy` with `deploy_to_hostinger=true` and `dry_run=false`.
3. Check the public site and `/unredacted/` gate.
4. Only after confirming the site is correct, run `AQ26 Retire Superseded Workflows` and type `RETIRE`.

## Required secrets

- `SCCAIRQUALITY_SSH_HOST`
- `SCCAIRQUALITY_SSH_PORT`
- `SCCAIRQUALITY_SSH_USERNAME`
- `SCCAIRQUALITY_SSH_PASSWORD`
- `AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR`
- `SCC_UNREDACTED_USERNAME` = `aq26`
- `SCC_UNREDACTED_PASSWORD`
- `GA_MEASUREMENT_ID`
- optional: `GOOGLE_SITE_VERIFICATION`

## Publication boundary

AQ26 is suitable for publication as a redacted evidence observatory when it uses cautious wording, visible caveats, source provenance and readiness gates. It should not claim causal attribution, breach findings or health impacts unless the relevant scientific and review gates pass.
