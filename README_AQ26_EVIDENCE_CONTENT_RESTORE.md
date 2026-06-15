# AQ26 evidence content restore pack

This fixes the post-overhaul placeholder problem by rebuilding the protected AQ26 site with real evidence content from the existing AQ26 data files.

## What it restores

- `site_unredacted/index.html` evidence reviewer console
- `site_unredacted/newhaven.html` Newhaven ERF evidence hub
- `site_unredacted/evidence.html` evidence library with priorities, downloads and source indexes
- `site_unredacted/source-records.html` traceable source records and SHA256 fields
- `site_unredacted/weekly-update.html` weekly readiness/backfill status
- `site_unredacted/candidates.html` candidate overlay review table
- `site_unredacted/diagnostics.html` protected diagnostic tables
- `site_unredacted/history.html` evidence build history
- public `index.html`, `newhaven.html`, and `source-records.html` links back to the protected evidence area

## Install

Upload the contents of this ZIP to the repository root, preserving paths.

Then run manually:

`Actions -> AQ26 Evidence Content Restore and Deploy -> Run workflow`

The workflow is manual-only to avoid workflow spam.

## Notes

- The repo already uses `configs/`, so this workflow normalises to `config/` only if needed.
- The protected pages are marked `noindex,nofollow`.
- The deploy step uses your existing `scripts/aq26_deploy_hostinger_dual.py`, so the working `.htaccess`/`.htpasswd` protection should remain untouched if that deploy script preserves auth files as in the earlier successful run.
- Large bundles such as `AQ26_WEEKLY_EVIDENCE_BUNDLE.zip` are linked if present on the server/repo. This pack includes data and the small weekly report, but not the 55MB legacy evidence ZIP.
