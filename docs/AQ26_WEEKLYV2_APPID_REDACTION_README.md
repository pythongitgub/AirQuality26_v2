# AQ26 WeeklyV2 OpenWeather appid redaction patch

The 2026-05-24 WeeklyV2 bundle passed the old redaction audit, but manual inspection found
OpenWeather URLs containing `appid=<key>` in LATEST_WEEKLYV2/source-history outputs.

This patch updates:

- `scripts/aq26_weeklyv2_sanitize_outputs.py`
- `scripts/aq26_weeklyv2_redaction_audit.py`

New coverage:
- `appid=`
- `app_id=`
- `access_token=`
- subscription key variants
- JSON fields with token/key/appid names

The workflow already runs the sanitizer before both redaction audits, so after this patch the next run should:
- sanitize OpenWeather `appid` in all output files
- fail closed if any unredacted appid remains
- record changed files in `provider_sanitization_manifest.json`
