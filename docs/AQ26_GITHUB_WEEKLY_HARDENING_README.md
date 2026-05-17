# AQ26 GitHub weekly hardening patch

This patch applies the next targeted fixes:

1. Met Office coordinate precision
   - Uses `lat` and `lon`
   - Rounds Met Office coordinates to 2 decimal places, as required by the DataHub endpoint

2. GDELT throttling
   - Uses 7-second spacing
   - Retries once after HTTP 429

3. Provenance bundle hardening
   - Keeps redaction audit in the final ZIP
   - Excludes SHA256 ledgers from hashing themselves
   - Adds `AQ26_FINAL_ZIP_LEDGER.csv` with hashes of final ZIP entries

Apply to the GitHub repository root, commit, then run:
- AQ26 Secret Smoke Test
- AQ26 Weekly Integrated Evidence Harvest
