# AQ26 Drive Forensic Evidence Audit

This patch adds a read-only Google Drive inventory and evidence-quality audit for AQ26.

It does **not** claim to prove emissions impact. Its purpose is to classify, validate and risk-screen the evidence archive so the website can make accurate, defensible statements about what evidence exists and what still requires QA or controlled review.

## Files added

```text
scripts/aq26_drive_forensic_evidence_audit.py
.github/workflows/aq26-drive-forensic-evidence-audit.yml
README_AQ26_DRIVE_FORENSIC_AUDIT.md
```

## Required GitHub secrets

```text
GDRIVE_FOLDER_ID
GDRIVE_SERVICE_ACCOUNT
```

`GDRIVE_SERVICE_ACCOUNT` should contain the full JSON service account credential. The root AQ26 Drive folder must be shared with that service account email.

## What it produces

```text
outputs/drive_forensic_audit/aq26_drive_inventory.csv
outputs/drive_forensic_audit/aq26_drive_inventory_public.csv
outputs/drive_forensic_audit/aq26_drive_forensic_summary_public.json
outputs/drive_forensic_audit/aq26_drive_forensic_review_private.json
site_public/data/drive_forensic_summary.json
site_unredacted/data/drive_forensic_review.json
```

The public summary is safe to publish. The private review contains path-level triage and should remain unredacted/protected.

## Evidence classes

The audit classifies files into groups including:

- Newhaven official annual/performance evidence
- Newhaven regulatory documents
- satellite/remote-sensing material
- ground air-quality monitoring
- meteorology/model context
- QA/readiness/validation material
- workflow/run-history material
- raw/structured data
- reports/dossiers

## Release classes

The script assigns publication controls:

- `public_citable_after_manual_source_check`
- `public_summary_ok_controlled_detail`
- `context_only_until_qa_gate_passes`
- `controlled_review_only`
- `never_publish_raw`
- `inventory_only`

## Scientific boundary

This audit supports provenance and review triage only. It does not by itself support claims of:

- proven emissions impact;
- source attribution;
- health outcome attribution;
- permit breach;
- regulatory non-compliance.

Those require separate QA, wind-sector, comparator, measurement-unit and independent-review gates.
