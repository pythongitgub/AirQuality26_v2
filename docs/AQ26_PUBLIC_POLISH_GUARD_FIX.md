# AQ26 Public Polish Workflow Guard Fix

This patch fixes the standalone `AQ26 Public Site Polish and No-Blank Guard` workflow.

The failed workflow was running the polish validator against an absent/incomplete `site_public` folder. The replacement workflow now runs `scripts/aq26_public_site_guard_build.py` first, which creates a professional public-site shell before the polish validator runs.

Run order:

1. Apply this patch.
2. Run `AQ26 Public Site Polish and No-Blank Guard` with `force_public_pages=true` and `commit_outputs=true`.
3. Run `AQ26 Deploy Public and Unredacted Sites` dry-run, then real deploy.
4. Run WeeklyV2/Stage2 backfill to replace fallback panels with real charts/data.
