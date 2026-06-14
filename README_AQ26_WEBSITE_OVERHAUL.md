# AQ26 Website Overhaul Pack

This pack replaces the fragmented AQ26 website surface with a consistent public site and a protected unredacted site.

## What it fixes

- Adds missing `newhaven.html` to the public and unredacted site.
- Adds uniform header, burger menu, footer and page directory across all pages.
- Adds Privacy, Terms, Cookies, Accessibility, Contact and 404 pages.
- Adds canonical URLs, Open Graph, Twitter card metadata and JSON-LD.
- Adds sitemap and robots rules.
- Keeps `/unredacted/` noindex/nofollow and protected by the existing `.htaccess` / `.htpasswd` files.
- Adds optional analytics via the `GA_MEASUREMENT_ID` GitHub secret.
- Adds optional Google Search Console verification via the `GOOGLE_SITE_VERIFICATION` GitHub secret.
- Adds a deploy workflow that uploads public and unredacted builds to Hostinger over SSH.

## Required GitHub secrets

Existing deployment secrets:

```text
SCCAIRQUALITY_SSH_HOST
SCCAIRQUALITY_SSH_PORT
SCCAIRQUALITY_SSH_USERNAME
SCCAIRQUALITY_SSH_PASSWORD
SCC_UNREDACTED_PASSWORD
AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR
AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR
```

Recommended values:

```text
AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR=/home/u288464186/domains/sccairquality.com/public_html
AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR=/home/u288464186/domains/sccairquality.com/public_html/unredacted
```

Optional SEO/analytics secrets:

```text
GA_MEASUREMENT_ID=G-XXXXXXXXXX
GOOGLE_SITE_VERIFICATION=your-google-search-console-token
```

## Files to copy into the repository

Copy all folders from this ZIP into the root of `AirQuality26_v2`:

```text
.github/workflows/aq26-site-overhaul-build-deploy.yml
.github/workflows/aq26-site-quality-gate.yml
config/aq26_site_config.json
scripts/aq26_build_overhauled_site.py
scripts/aq26_site_quality_gate.py
scripts/aq26_deploy_hostinger_dual.py
requirements.txt
site_public/
site_unredacted/
```

Then run the GitHub Action:

```text
AQ26 Website Overhaul Build and Deploy
```

## Important auth note

The deploy script intentionally does not replace `.htaccess` or `.htpasswd` in `/unredacted/`. Your working auth workflow has already fixed those files. This avoids breaking password protection.

## Award-level next steps after this baseline

1. Replace placeholder explanatory cards with generated weekly evidence cards.
2. Add Newhaven timeline, facility context map and monitoring-station map.
3. Add visual evidence explorer: date, source, status, confidence, redaction state.
4. Add public plain-English summaries and protected reviewer notes.
5. Add Lighthouse checks, accessibility checks and HTML validation to CI.
6. Add Search Console sitemap submission and analytics dashboard review.
