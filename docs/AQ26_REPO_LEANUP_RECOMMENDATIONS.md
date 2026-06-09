# AQ26 repository cleanup recommendations

## Keep active in GitHub

These are required for the lean weekly production model:

- `.github/workflows/weekly-production.yml`
- `.github/workflows/aq26-hostinger-ssh-preflight.yml` only while Hostinger debugging is needed
- `scripts/`
- `configs/`
- `site_public/`
- `site_unredacted/`
- `site_test/`
- `docs/`
- `requirements.txt`
- `README.md`
- `.gitignore`

## Disable or move after the new workflow passes

Move older experiment/polish/probe workflows out of `.github/workflows/` so GitHub Actions stops showing/running them. Good destination:

`docs/disabled_workflows/<old-workflow>.yml.txt`

Candidates visible in the uploaded repo include:

- branding-only workflows such as `aq26_apply_*`, `aq26_enforce_*`, `aq26_final_*`, `aq26_restore_*`
- phase smoke tests such as `aq26_phase40.yml`, `aq26_phase50.yml`, `aq26_phase70_national_screening.yml`, `aq26_phase80_historical.yml`, `aq26_phase88_94_geospatial.yml`, `aq26_phase95.yml`
- one-off probe workflows such as `aq26_earthdata_*`, `aq26_laqn_probe.yml`, `aq26_ukair_sos_probe.yml`, `newhaven-radius-forensics.yml`, `satellite-opportunity-scan.yml`, `s5p-07b.yml`
- old/deprecated weekly variants such as `aq26_weekly_v2.yml`, `aq26-weekly-production-compatible.yml`, `aq26-weekly-production.yml`, and any `.txt` duplicate can stay disabled or move to docs
- separate deploy bridge workflows such as `download_drive_upload_hostinger.yml` unless you still use the two-repo Drive-to-Hostinger bridge

Do **not** permanently delete these immediately. Move them to docs first, confirm production remains stable for at least one full Monday run, then delete later.

## Remove from Git tracking if present

These should not live in Git history because they bloat clones and can break pushes:

- `outputs/`
- `downloads/`
- `exports/`
- `reports/`
- `evidence/`
- `artifacts/`
- `logs/`
- `*.zip`
- `*.parquet`
- generated PDFs/XLSX files
- old `public_html` backups
- notebook execution outputs if they are large

Keep those in Google Drive, GitHub Actions artifacts, or Hostinger, not permanently in the repo.

## Lean website target

The public website should publish:

- HTML pages
- small JSON feeds
- current PDF/report summary if small
- hashes/ledgers/manifests
- links to Google Drive evidence bundles

The public website should not repeatedly publish 50-100 MB evidence ZIPs. The workflow now prunes files larger than 25 MB from public publish folders and writes a notice file instead.

## Useful commands

Audit current repository:

```bash
python scripts/aq26_repo_lean_suggestions.py
```

Disable extra workflows on Linux/macOS/GitHub Codespaces:

```bash
bash scripts/disable_extra_workflows.sh
git status
git commit -am "Disable duplicate AQ26 workflows"
git push
```

Disable extra workflows in PowerShell:

```powershell
./scripts/disable_extra_workflows.ps1
git status
git commit -am "Disable duplicate AQ26 workflows"
git push
```
