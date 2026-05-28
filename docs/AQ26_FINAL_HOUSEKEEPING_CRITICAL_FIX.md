# AQ26 final housekeeping critical fix

This patch addresses the three remaining critical audit findings reported on
2026-05-28:

1. `scripts/aq26_build_unredacted_site.py` had invalid Python syntax.
2. The weekly workflow could create `.htpasswd` before committing generated site files.
3. The operational workflow still matched the audit's risky `git add site_public site_unredacted` pattern.

After applying this patch:

- `.htpasswd` files are removed before build/commit.
- `.htpasswd` is created only immediately before unredacted deployment.
- workflow commits use safer path syntax and reset `.htpasswd` defensively.
- the legacy unredacted builder is a valid compatibility wrapper.

Run the housekeeping audit next with:
- Fail critical issues: checked
- Commit housekeeping report: checked

If the audit passes, proceed to focused backfill and deployment dry-run.
