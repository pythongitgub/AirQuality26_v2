# AQ26 White Header Full Replacement

This patch standardises AQ26 branding across the public site, unredacted review site, and static report pages.

## Branding roles

- `assets/favicon.svg` / compact icon: favicon, touch icon and browser tab only.
- `assets/air_quality_web.svg`: visible page header logo, report masthead and internal review header.

## Files

```text
scripts/aq26_apply_white_header_branding.py
.github/workflows/aq26_apply_white_header_branding.yml
.github/workflows/aq26_deploy_dual_site_sccwebdesigntest.yml
website/assets/air_quality_web.svg
website/assets/favicon.svg
website/assets/logo_web.svg
site_public/assets/air_quality_web.svg
site_public/assets/favicon.svg
site_public/assets/logo_web.svg
```

## What changes

1. Replaces dark visible headers with a white header bar.
2. Uses the full SCC Nexus Air Quality Report SVG as the visible logo.
3. Keeps the compact SVG only as the favicon/touch icon.
4. Adds a mobile hamburger menu.
5. Applies the same header to public, unredacted and report/static HTML pages.
6. Excludes `/unredacted/` from public rsync delete, so public deployment cannot wipe the protected internal site.

## Recommended run order

1. Upload/apply this patch.
2. Run `AQ26 Apply White Header Branding` with:

```text
apply_public=true
apply_unredacted=true
force_core_pages=true
commit_outputs=true
```

3. Run `AQ26 Deploy Public and Unredacted Sites` with:

```text
deploy_public=true
deploy_unredacted=true
dry_run=true
auth_debug=true
force_public_polish=true
max_index_files=1000
```

4. If clean, rerun the same deploy workflow with:

```text
dry_run=false
```

## Cache testing

After deployment, test these direct URLs in a private window or hard refresh:

```text
https://sccwebdesigntest.co.uk/assets/air_quality_web.svg?v=aq26-white-header-20260527
https://sccwebdesigntest.co.uk/assets/favicon.svg?v=aq26-white-header-20260527
https://sccwebdesigntest.co.uk/unredacted/assets/air_quality_web.svg?v=aq26-white-header-20260527
```

## Old workflows

Avoid running old similarly named deploy workflows such as:

```text
AQ26 Deploy Password-Protected Unredacted Site
```

Use only:

```text
AQ26 Deploy Public and Unredacted Sites
```
