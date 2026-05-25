
# AQ26 active workflow map

## Recommended production workflow

`aq26_weekly_v2_sccnexus_website.yml`

Purpose:
- WeeklyV2 evidence harvest
- Redaction/integrity packaging
- CDSE auth verification
- SCC Nexus styled website build
- Hostinger deployment
- email notification

## Keep for diagnostics

`aq26_weekly_v2.yml`

Evidence-only workflow for debugging.

`smoketest.yml`

Manual-only secret smoke test after changing secrets.

## Recommendation

Make older scheduled workflows manual-only or archive them to prevent duplicate API usage, duplicate emails and noisy Actions history.
