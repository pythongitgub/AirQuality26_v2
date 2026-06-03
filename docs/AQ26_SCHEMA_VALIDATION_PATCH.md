# AQ26 schema validation hardening patch

This patch fixes the next production workflow failure after the stale redaction leak was removed.

Observed failure:

```text
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

Cause: the production validator was parsing every `*.json` file under `site_public`, `site_unredacted`
and `outputs`. Older AQ26 site/deploy workflows can leave zero-byte or partial JSON files in the site
folders. Those stale files are not current production evidence, but they can break final validation.

Changes:

- Keeps current `outputs/aq26_production/<run_ts>/*.json` as a hard validation gate.
- Quarantines invalid legacy JSON found under `site_public` or `site_unredacted` into the run output folder.
- Writes `AQ26_VALIDATION_QUARANTINE_SUMMARY.json` when stale site JSON is quarantined.
- Writes `AQ26_VALIDATION_FAILURE_SUMMARY.json` if current production JSON/CSV validation fails.
- Adds a workflow artifact upload for safe validation failure summaries.

This does not weaken the redaction gate. It only prevents old, stale, invalid site JSON from blocking a clean
production build after it has been safely quarantined.
