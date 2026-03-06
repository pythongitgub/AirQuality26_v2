# AirQuality26 — Notebook Runbook (01 → 09)

These notebooks are designed to run in order. Each step produces:
- `outputs/<NN_stepname>/manifest.json`
- raw/processed artifacts, each hashed with SHA256 for integrity/provenance

## How to use
1. Copy the contents of this bundle into the root of your GitHub repo.
2. Ensure GitHub Secrets are set.
3. Run the workflow: **Actions → AQ26 Notebooks (01-09) → Run workflow**
4. Download the `aq26_outputs` artifact and inspect `outputs/`.

## Run order
01 Secrets
02 Config/Sites
03 News metadata
04 Ground AQ provider snapshots
05 Met Office DataHub plan (endpoint wiring next)
06 UK-AIR SOS discovery
07 S5P plan
08 Gemini neutral summary
09 Manifest index