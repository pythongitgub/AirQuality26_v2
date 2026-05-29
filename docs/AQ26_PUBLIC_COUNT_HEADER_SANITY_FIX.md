# AQ26 Public Count/Header Sanity Fix

This post-build workflow corrects two public-facing issues that can appear after the operational site builder merges the broad register and overlay status rows:

1. Removes the extra `SCC Nexus · AQ26` text next to the full header logo.
2. Corrects legacy duplicate-register totals such as `86 facilities in register` back to the current weekly alert count.

It should run after the focused backfill/site update workflow when the site looks visually good but legacy page fragments still show incorrect counts.

Recommended first run:

- deploy_public: true
- deploy_unredacted: false
- dry_run: true

If the dry-run rsync list is correct, rerun with dry_run=false.
