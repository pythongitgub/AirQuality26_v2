# AQ26 Public Polish Full Core Pages Fix

This patch fixes the public polish workflow by creating/repairing every core public page before validation.

Run:

1. `AQ26 Public Site Polish and No-Blank Guard`
   - `force_public_pages=true`
   - `commit_outputs=true`

2. `AQ26 Deploy Public and Unredacted Sites`
   - `deploy_public=true`
   - `deploy_unredacted=true`
   - `dry_run=true`, then `dry_run=false`

The guard prevents blank client-facing pages while the WeeklyV2 backfill and integrated evidence workflows populate real chart payloads.
