#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import zipfile
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
except Exception:
    SimpleDocTemplate = None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_ledger(root: Path) -> Path:
    out = root / "99_integrity" / "AQ26_SHA256_LEDGER.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"AQ26_SHA256_LEDGER.csv", "AQ26_FINAL_ZIP_LEDGER.csv", "LATEST_ZIP.txt"}:
            continue
        if path.suffix.lower() == ".zip":
            continue
        rows.append({
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "size_bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)

    return out


def build_pdf(markdown_path: Path, pdf_path: Path) -> None:
    if SimpleDocTemplate is None:
        # Valid minimal placeholder bytes if reportlab is unavailable.
        pdf_path.write_bytes(b"%PDF-1.4\n% reportlab unavailable\n")
        return

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
    story = []

    for line in markdown_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            story.extend([Paragraph(line[2:], styles["Title"]), Spacer(1, 8)])
        elif line.startswith("## "):
            story.extend([Paragraph(line[3:], styles["Heading2"]), Spacer(1, 6)])
        elif line.startswith("- "):
            story.append(Paragraph("• " + line[2:], styles["BodyText"]))
        elif line.strip():
            story.extend([Paragraph(line, styles["BodyText"]), Spacer(1, 4)])
        else:
            story.append(Spacer(1, 4))

    doc.build(story)


def write_final_zip_ledger(zip_path: Path, root: Path) -> Path:
    ledger_path = root / "99_integrity" / "AQ26_FINAL_ZIP_LEDGER.csv"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            # Avoid the final ledger hashing itself.
            if info.filename.endswith("AQ26_FINAL_ZIP_LEDGER.csv"):
                continue
            data = archive.read(info.filename)
            rows.append({
                "zip_entry": info.filename,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })

    with ledger_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["zip_entry", "size_bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)

    return ledger_path


def write_markdown_report(root: Path, report_dir: Path, ts: str) -> Path:
    latest = load_json(root / "00_live_harvest" / "LATEST_HARVEST.json")
    alerts = load_json(root / "10_anomaly_alerts" / "anomaly_alerts.json")
    filings = load_json(root / "06_official_filings" / "official_filing_index.json")
    satellite = load_json(root / "07_satellite_cdse" / "satellite_catalogue_metadata.json")
    redaction = load_json(root / "99_integrity" / "redaction_audit.json")
    scoring = load_json(root / "12_scoring" / "evidence_priority_scores.json")
    readiness = load_json(root / "12_scoring" / "evidence_readiness_gates.json")
    backfill = load_json(root / "11_backfill" / "missing_date_backfill_plan.json")
    drive = load_json(root / "08_gdrive_snapshot" / "gdrive_recursive_inventory.json")

    markdown = report_dir / f"AQ26_WEEKLY_INTEGRATED_REPORT_{ts}.md"

    lines = [
        "# AQ26 Weekly Integrated Evidence Report",
        "",
        "## Controlled-use boundary",
        (
            "Automated controlled-review evidence harvest. No endorsement claimed by WHO, UNEP, EEA, "
            "C40 Cities or named experts. No causal attribution unless evidence gates support it."
        ),
        "",
        "## Executive status",
        f"- Source records: `{latest.get('source_record_count', 0)}`",
        f"- OK records: `{latest.get('ok_count', 0)}`",
        f"- Error records: `{latest.get('error_count', 0)}`",
        f"- Official filing candidates: `{filings.get('filing_count', 0)}`",
        f"- High-priority filings: `{len(scoring.get('high_priority_filings', []))}`",
        f"- Medium-priority filings: `{len(scoring.get('medium_priority_filings', []))}`",
        f"- Satellite catalogue products: `{satellite.get('product_count', 0)}`",
        f"- Alerts: `{alerts.get('alert_count', 0)}`",
        f"- Redaction leaks: `{redaction.get('leak_count', 'not yet scanned')}`",
        f"- Recursive Drive files inventoried: `{drive.get('file_count', 'not scanned')}`",
        f"- Backfill missing stream/date rows: `{backfill.get('missing_count', 'not planned')}`",
        "",
        "## Evidence gates",
        f"- Automation ready: `{readiness.get('automation_ready')}`",
        f"- Provenance ready: `{readiness.get('provenance_ready')}`",
        f"- Redaction ready: `{readiness.get('redaction_ready')}`",
        f"- Met Office ready: `{readiness.get('metoffice_ready')}`",
        f"- Ground AQ ready: `{readiness.get('ground_aq_ready')}`",
        f"- Satellite catalogue ready: `{readiness.get('satellite_catalogue_ready')}`",
        f"- Satellite extraction ready: `{readiness.get('satellite_extraction_ready')}`",
        f"- Official filings ready: `{readiness.get('official_filings_ready')}`",
        f"- External submission ready: `{readiness.get('external_submission_ready')}`",
        "",
        "## Specialist-method alignment",
        (
            "- Dominici-style causal epidemiology: guarded causal language, confounder notes and future "
            "exposure-response readiness."
        ),
        (
            "- Martin-style satellite/ground fusion: Sentinel catalogue retained with target/control context; "
            "extraction remains next stage."
        ),
        (
            "- Brauer/GBD-style integration: multi-source exposure-screening registry, not health-burden "
            "attribution yet."
        ),
        (
            "- Anenberg-style NO2/emissions-health logic: NO2/SO2/CO/HCHO/O3/CH4/AER_AI families are prioritised."
        ),
        (
            "- Damoulas-style digital twin readiness: target/control graph, completeness and scoring files "
            "prepare future spatiotemporal modelling."
        ),
        "",
        "## Readiness",
        (
            "Controlled-review beta. Not external-submission ready until satellite extraction, official relevance "
            "review, ground AQ QA and weather/wind alignment gates pass."
        ),
    ]

    blocking = readiness.get("blocking_reasons", [])
    if blocking:
        lines.extend(["", "## Blocking reasons"])
        for reason in blocking:
            lines.append(f"- {reason}")

    markdown.write_text("\n".join(lines), encoding="utf-8")
    return markdown


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="outputs")
    args = parser.parse_args()

    root = Path(args.output_root)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir = root / "weekly_reports" / f"AQ26_WEEKLY_{ts}"
    report_dir.mkdir(parents=True, exist_ok=True)

    markdown = write_markdown_report(root, report_dir, ts)
    pdf = report_dir / f"AQ26_WEEKLY_INTEGRATED_REPORT_{ts}.pdf"
    build_pdf(markdown, pdf)

    ledger_path = build_ledger(root)

    manifest = {
        "run_ts": ts,
        "report_md": str(markdown),
        "report_pdf": str(pdf),
        "sha256_ledger": str(ledger_path),
        "redaction_audit": str(root / "99_integrity" / "redaction_audit.json"),
        "latest_harvest": str(root / "00_live_harvest" / "LATEST_HARVEST.json"),
        "source_history": str(root / "source_history" / "source_index.jsonl"),
        "scoring": str(root / "12_scoring" / "evidence_priority_scores.json"),
        "backfill_plan": str(root / "11_backfill" / "missing_date_backfill_plan.json"),
        "recursive_drive_inventory": str(root / "08_gdrive_snapshot" / "gdrive_recursive_inventory.json"),
        "controlled_use_boundary": "No endorsement claimed; no causal attribution unless evidence gates support it.",
    }
    manifest_path = report_dir / f"AQ26_WEEKLY_MASTER_MANIFEST_{ts}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Rebuild ledger after manifest/report exist, still excluding ledger/ZIP self-references.
    ledger_path = build_ledger(root)

    zip_path = root / "weekly_reports" / f"AQ26_WEEKLY_INTEGRATED_EVIDENCE_{ts}.zip"
    include_roots = [
        root / "00_live_harvest",
        root / "03_news_context",
        root / "04_ground_aq_providers",
        root / "05_weather",
        root / "05_metoffice_datahub_weather",
        root / "06_official_filings",
        root / "07_satellite_cdse",
        root / "08_gdrive_snapshot",
        root / "10_anomaly_alerts",
        root / "11_backfill",
        root / "12_scoring",
        root / "99_integrity",
        root / "source_history",
        report_dir,
    ]

    def build_zip() -> None:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for base in include_roots:
                if not base.exists():
                    continue
                for path in sorted(base.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, arcname=str(path.relative_to(root.parent)))

    build_zip()
    final_zip_ledger = write_final_zip_ledger(zip_path, root)
    build_zip()

    (root / "weekly_reports" / "LATEST_ZIP.txt").write_text(str(zip_path), encoding="utf-8")

    print(json.dumps({
        "zip": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
        "pdf": str(pdf),
        "final_zip_ledger": str(final_zip_ledger),
    }, indent=2))


if __name__ == "__main__":
    main()
