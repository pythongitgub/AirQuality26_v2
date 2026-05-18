# AQ26 WeeklyV2 GitHub workflow

Adds `.github/workflows/aq26_weekly_v2.yml`, a separate test workflow.

## New keys
- `OPENAQ_API_KEY`
- `CAMS_API_KEY`
- optional `CAMS_BASE_URL`

## OpenAQ safety
Because your OpenAQ keys have been blocked before, WeeklyV2 is deliberately conservative:
- 8 requests per run by default
- 8 seconds minimum spacing
- no pagination loops
- stop immediately on 401, 403, or 429
- no key values in logs or outputs
- redacted URLs

## CAMS
If `CAMS_API_KEY` is present but `CAMS_BASE_URL` is absent, WeeklyV2 records readiness and does not guess an endpoint.

## Run
Actions → AQ26 WeeklyV2 Evidence Harvest → Run workflow
