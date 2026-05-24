# AQ26 workflow map

Primary weekly workflow:

- `.github/workflows/aq26_weekly_v2.yml` — current scripts-only WeeklyV2 controlled-review evidence harvest.

Historical/experimental workflows should remain untouched until WeeklyV2 is repeatedly certified clean. Suggested future tidy approach:

1. Keep WeeklyV2 active.
2. Run `scripts/aq26_repo_tidy_audit.py` to inventory repository automation.
3. Move old experimental workflows to `.github/workflows_disabled/` only after manual review.
4. Do not mix Google Colab notebooks with GitHub-only weekly automation.
