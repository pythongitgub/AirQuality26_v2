# AQ26 Housekeeping Critical Cleanup

Run this once before further site/backfill deployment.

It removes deployment-only `.htpasswd` files from the repository, adds `.gitignore`, and keeps `.htaccess`/robots templates safe for deployment.

After this completes, rotate `SCC_UNREDACTED_PASSWORD` in GitHub Actions secrets because an old `.htpasswd` hash was previously committed.

Recommended sequence:

1. Apply this patch.
2. Run `AQ26 Housekeeping Critical Cleanup` with `commit_cleanup=true`.
3. Rotate `SCC_UNREDACTED_PASSWORD`.
4. Run `AQ26 Repository Housekeeping Audit` with `fail_on_critical=false` to inspect remaining warnings.
5. Only run deploy/backfill after the report is acceptable.
