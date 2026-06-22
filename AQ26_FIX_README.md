# AQ26 canonical website fix patch

This patch replaces the accumulated patch-on-patch AQ26 static output with a single canonical build/audit/deploy path.

## Files included

- `configs/aq26_canonical_site.yml` — single source of truth for public/protected pages and SEO metadata.
- `scripts/aq26_build_canonical_site.py` — rebuilds `site_public`, `site_unredacted`, and `site_test` from scratch.
- `scripts/aq26_site_full_audit.py` — fails on missing SEO, broken local assets, public ZIP leaks, `.htpasswd`, `git-test`, stale repo/source leaks, missing sitemap/robots, or unredacted pages lacking `noindex`.
- `scripts/aq26_deploy_canonical_hostinger.py` — deploys the clean output, removes stale `git-test`, `.git`, `/test`, old root files, and keeps unredacted protected.
- `.github/workflows/aq26-canonical-site-deploy.yml` — one clean workflow to build, audit, and deploy.
- `.gitignore` additions — prevents `.htpasswd`, secrets and large evidence ZIPs being committed.

## What this fixes

1. Removes the mixed-template site problem.
2. Removes accidental deployed `git-test/` repo copy.
3. Stops public publication of full evidence ZIP bundles unless explicitly named public.
4. Ensures all public pages have title, description, canonical, Open Graph, Twitter card, JSON-LD, manifest, favicon and sitemap coverage.
5. Ensures unredacted pages are `noindex,nofollow,noarchive` and blocked by `robots.txt`.
6. Fixes missing `/unredacted/assets/...` references by rebuilding protected assets correctly.
7. Replaces stale tiny sitemap with a complete generated sitemap.
8. Cleans the Hostinger target before upload so old files do not survive forever.

## How to install

Copy these files into the root of the GitHub repo, preserving folders.

Then run:

```bash
python scripts/aq26_build_canonical_site.py
python scripts/aq26_site_full_audit.py
```

In GitHub Actions, run:

`AQ26 Canonical Site Build, Audit and Deploy`

Use `deploy_to_hostinger=true`, `dry_run=false` when ready.

## Secrets expected

Required for deployment:

- `SCCAIRQUALITY_SSH_HOST`
- `SCCAIRQUALITY_SSH_PORT`
- `SCCAIRQUALITY_SSH_USERNAME`
- `SCCAIRQUALITY_SSH_PASSWORD`
- `AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR`

Recommended:

- `GA_MEASUREMENT_ID`
- `GOOGLE_SITE_VERIFICATION`
- `SCC_UNREDACTED_USERNAME` — defaults to `aq26` if missing
- `SCC_UNREDACTED_PASSWORD` — used to create `/home/u288464186/.aq26_auth/.htpasswd` outside web root

## Important

This patch deliberately does not rely on the many older AQ26 patch workflows. Once this workflow succeeds, disable the old one-off branding/auth/patch workflows to avoid them overwriting the clean site again.
