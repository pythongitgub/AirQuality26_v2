# AQ26 brand/icon and unredacted console upgrade

This patch fixes three issues:

1. The browser favicon/touch icon could remain stale or incorrect.
2. The public header logo was too small/unclear after the no-blank fallback rebuild.
3. The password-protected unredacted site had a working index but not enough useful review structure.

## Run order

1. Apply this patch.
2. Run `AQ26 Deploy Public and Unredacted Sites` with:
   - `deploy_public=true`
   - `deploy_unredacted=true`
   - `dry_run=true`
   - `auth_debug=true`
   - `force_public_polish=true`
   - `max_index_files=1000`
3. If clean, rerun with `dry_run=false`.
4. Clear browser cache or open in a private window to verify favicon changes.

## Notes

The public rsync now excludes `/unredacted/`, so a public deploy will not delete the protected internal site if the unredacted deploy fails later.
