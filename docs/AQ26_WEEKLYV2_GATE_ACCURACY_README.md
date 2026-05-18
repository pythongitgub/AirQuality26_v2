# AQ26 WeeklyV2 gate accuracy patch

This patch improves the successful WeeklyV2 workflow without making it more aggressive.

Fixes:
- GDELT timeouts/429 are treated as warnings, not critical errors.
- `news_provider_warnings.json` is written.
- `openaq_safety_manifest.json` records OpenAQ request count, status codes, stop reason and safety state.
- CAMS readiness is split into:
  - `cams_key_present`
  - `cams_endpoint_configured`
  - `cams_data_ready`
- `cams_ready` is no longer used as if data were harvested.
- Drive inventory records truncation, folder count, shortcut count and followed shortcut-folder count.
- `evidence_readiness_gates.json` is corrected after redaction audit.
- Report includes OpenAQ safety, CAMS readiness, Drive truncation and news warnings.

OpenAQ remains deliberately cautious:
- max 8 requests/run
- 8 seconds between requests
- no pagination storm
- stop on 401/403/429
