# AQ26 public site no-blank + mobile + deployment consolidation patch

## Why this patch exists

The public `comparisons.html` page was effectively blank/empty, which is unprofessional for a client-facing site. The website must never expose empty pages even when the data pipeline is still warming up.

This patch makes the public site behave like a polished user interface:

- mobile hamburger navigation;
- favicon/touch-icon references;
- no-blank fallback content for Comparisons, Downloads and Weekly Archive;
- old URL aliases such as `historical-comparisons.html`;
- stable download aliases for public/redacted evidence bundles;
- improved dual-site deployment workflow;
- larger unredacted index default.

## Apply

Unzip into the repository root.

## Run order

1. Run `AQ26 Public Site Polish and No-Blank Guard`
   - `force_public_pages=true`
   - `commit_outputs=true`

2. Run `AQ26 Deploy Public and Unredacted Sites`
   - first dry run:
     - `deploy_public=true`
     - `deploy_unredacted=true`
     - `dry_run=true`
     - `auth_debug=true`
     - `max_index_files=1000`
   - then real run:
     - `dry_run=false`

3. Stop using the old workflow:
   - `AQ26 Deploy Password-Protected Unredacted Site`

## Backfill position

Yes, keep running the backfill, but the website should not wait for perfect backfill before being professional. Missing charts should display a clear “awaiting validated data” panel, not a blank page.

Recommended next backfill:
- run one clean monthly/weekly batch;
- regenerate `site_public/data/charts/*.json`;
- rerun this polish workflow;
- deploy.

## Public download policy

The public site should offer only redacted evidence:
- `downloads/latest-evidence.zip`
- `downloads/latest-report.pdf`

Unredacted/full review files remain behind `/unredacted/`.
