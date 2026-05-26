# AQ26 NASA Earthdata Auth Smoke Test

This patch adds a GitHub Actions workflow that verifies the repository can access these secrets at runtime:

- `EARTHDATA_USERNAME`
- `EARTHDATA_PASSWORD`
- `EARTHDATA_TOKEN`

It does not print or persist secret values.

## Run

Actions → **AQ26 NASA Earthdata Auth Smoke Test** → Run workflow

Recommended first run:

- `fail_on_auth_warning`: `true`
- `commit_outputs`: `true`

## Success means

- GitHub Actions can see non-empty Earthdata secrets.
- CMR public collection/granule discovery works from the runner.
- `earthaccess.login(strategy="environment")` succeeds using `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD`.

## Outputs

- `outputs/34_earthdata_auth/earthdata_auth_smoke_summary.json`
- `outputs/34_earthdata_auth/earthdata_auth_source_records.json`
- `site_public/data/providers/earthdata/auth_smoke_summary.json`
- `site_public/data/providers/earthdata/auth_smoke_source_records.json`

## Important

A warning on the token-profile probe does not necessarily mean your Earthdata credentials are wrong. The username/password `earthaccess` login is the main authentication smoke test. Token permissions can vary by Earthdata application/token configuration.
