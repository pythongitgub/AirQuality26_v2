# AQ26 Password-Protected Unredacted Site

This adds a separate restricted review portal at:

`https://sccwebdesigntest.co.uk/unredacted/`

It is intended for internal QA, evidence review and provenance inspection. The public website remains the user-friendly redacted client interface.

## Required GitHub secrets

- `SCC_UNREDACTED_PASSWORD` — password for Basic Auth user `aq26`
- `SCCNEXUS_SSH_HOST`
- `SCCNEXUS_SSH_PORT`
- `SCCNEXUS_SSH_USERNAME`
- `SCCNEXUS_SSH_PASSWORD`
- `HOSTINGER_PUBLIC_HTML_DIR`

## Run

Actions → `AQ26 Deploy Password-Protected Unredacted Site` → Run workflow.

First run:

- `remote_subdir`: `unredacted`
- `dry_run`: `true`
- `max_copy_mb`: `25`

If the dry run looks correct, rerun with `dry_run: false`.

## Security boundary

This is password-protected, noindexed and not linked from the public site by default. It is not a substitute for careful data governance. Do not publish highly sensitive personal data unless appropriate and lawful.
