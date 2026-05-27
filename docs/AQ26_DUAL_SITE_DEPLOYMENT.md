# AQ26 dual-site deployment

This patch deploys two separate client interfaces from the same repository:

- Public client site: `https://www.sccwebdesigntest.co.uk/`
- Password-protected internal review site: `https://sccwebdesigntest.co.uk/unredacted/`

The public site remains the user-friendly front end. The unredacted site is a full internal review site with index pages, CSS, menus, evidence index JSON and Basic Auth.

Required GitHub secrets:

- `SCCNEXUS_SSH_HOST`
- `SCCNEXUS_SSH_PORT`
- `SCCNEXUS_SSH_USERNAME`
- `SCCNEXUS_SSH_PASSWORD`
- `HOSTINGER_PUBLIC_HTML_DIR`
- `SCC_UNREDACTED_PASSWORD`

Run workflow:

`AQ26 Deploy Public and Unredacted Sites`

First run with `dry_run=true`. If the file list is correct, rerun with `dry_run=false`.
