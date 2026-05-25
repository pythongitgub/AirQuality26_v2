# AQ26 Hostinger retry/root deployment patch

This patch is a follow-up to the root deployment/two-year history patch.

## What the latest logs showed

The AQ26 site build and validation succeeded, including the SCC Nexus pages and cookie/footer structure.

The failure was at Hostinger SSH deployment:

`ssh: connect to host *** port ***: Connection timed out`

This is not a Python, evidence-harvest, report-build or website-generation failure. It is a network/SSH connection failure to Hostinger from the GitHub runner.

## Changes

- Keeps default root deployment:
  - `remote_subdir = .`
  - `public_base_url = https://sccwebdesigntest.co.uk`
- Keeps 104-week / 2026-05-25 two-year history defaults.
- Makes Hostinger history restore non-fatal and retry-safe.
- Adds a pre-deploy artifact upload so the valid built site is preserved even if Hostinger SSH times out.
- Adds six retry attempts for SSH mkdir and rsync deploy.
- Uses longer SSH/rsync timeouts.

## Run settings

Use:

- `remote_subdir`: `.`
- `public_base_url`: `https://sccwebdesigntest.co.uk`
- `history_weeks`: `104`
- `history_end_date`: `2026-05-25`
- `deploy_to_hostinger`: `true`

## If it still times out

Check these secrets carefully:

- `SCCNEXUS_SSH_HOST`
- `SCCNEXUS_SSH_PORT`
- `SCCNEXUS_SSH_USERNAME`
- `SCCNEXUS_SSH_PASSWORD`
- `HOSTINGER_PUBLIC_HTML_DIR`

Also check whether Hostinger is temporarily blocking GitHub-hosted runner IP ranges or whether SSH access is disabled/rate-limited.
