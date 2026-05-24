# AQ26 WeeklyV2 SerpAPI redaction fix

The WeeklyV2 run failed because SerpAPI raw JSON included result URLs containing `token=` query parameters.

These are likely provider/search-result tracking tokens rather than your SerpAPI API key, but the redaction audit correctly treats any `token=` output as unsafe.

This patch adds:

- `scripts/aq26_weeklyv2_sanitize_outputs.py`
- workflow steps to sanitize outputs before both redaction audits
- artifact upload of `outputs/15_optional_sources/provider_sanitization_manifest.json`

The sanitizer:
- scans text-like output files
- redacts query parameters such as `token=`, `apikey=`, `api_key=`, `key=`, `access_token=`
- writes SHA256 before/after for changed files
- keeps the workflow fail-closed if redaction audit still finds leaks

This preserves the safety rule: no token-like material in logs, JSON, CSV, Markdown, PDF or final ZIP.
