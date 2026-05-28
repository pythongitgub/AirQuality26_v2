# AQ26 Repository Housekeeping and Security Patch

This patch adds a non-destructive repository audit workflow and fixes a critical security pattern in the operational deployment workflow.

## Critical issue found during preflight review

`site_unredacted/.htpasswd` is currently present in the public GitHub repository. Even though it is a hash, it should not be committed. Treat the associated unredacted password as exposed and rotate `SCC_UNREDACTED_PASSWORD`.

## Added files

- `.gitignore`
- `scripts/aq26_repo_housekeeping_audit.py`
- `.github/workflows/aq26_repo_housekeeping_audit.yml`
- `.github/workflows/aq26_operational_dual_site.yml`
- `docs/AQ26_REPO_HOUSEKEEPING_SECURITY_README.md`

## Run first

Run `AQ26 Repository Housekeeping Audit` with `fail_on_critical=true` and `commit_report=true`.

## Required manual security action

Rotate `SCC_UNREDACTED_PASSWORD`. The patched operational workflow removes `.htpasswd` from tracking before commit and generates it only immediately before deployment.
