# AQ26 Unredacted Full Website Deployment

This patch changes the unredacted area from a single test page into a complete internal review website.

## Key design

- `site_public/` remains the public/client-friendly site.
- `site_unredacted/` is generated separately for `/unredacted/`.
- The builder copies `site_public/` first, preserving menus, assets, CSS, data and site structure where available.
- It overlays an internal unredacted dashboard and evidence index.
- The workflow protects `/unredacted/` with Apache Basic Auth.

## Required secrets

- `SCC_UNREDACTED_PASSWORD`
- `HOSTINGER_PUBLIC_HTML_DIR`
- `SCCNEXUS_SSH_HOST`
- `SCCNEXUS_SSH_PORT`
- `SCCNEXUS_SSH_USERNAME`
- `SCCNEXUS_SSH_PASSWORD`

## First run

Run `AQ26 Deploy Password-Protected Unredacted Site` with:

- `remote_subdir = unredacted`
- `dry_run = true`

Check the rsync output. It should show files being uploaded directly into `/unredacted/`, including:

- `index.html`
- `evidence.html`
- `assets/aq26_unredacted.css`
- `.htaccess`
- `.htpasswd`
- `robots.txt`

Then rerun with `dry_run = false`.

## Browser

Open:

`https://sccwebdesigntest.co.uk/unredacted/`

Username: `aq26`

Password: value stored in `SCC_UNREDACTED_PASSWORD`.
