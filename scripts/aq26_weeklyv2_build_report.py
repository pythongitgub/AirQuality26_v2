#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, zipfile
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
except Exception:
    SimpleDocTemplate = None

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def ledger(root: Path):
    p = root / "99_integrity" / "AQ26_SHA256_LEDGER.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() == ".zip" or f.name in {"AQ26_SHA256_LEDGER.csv", "AQ26_FINAL_ZIP_LEDGER.csv", "LATEST_ZIP.txt"}:
            continue
        rows.append({"path": str(f), "size_bytes": f.stat().st_size, "sha256": sha(f)})
    with p.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["path", "size_bytes", "sha256"])
        w.writeheader()
        w.writerows(rows)
    return p

def pdf(md: Path, out: Path):
    if SimpleDocTemplate is None:
        out.write_bytes(b"%PDF-1.4\n% reportlab unavailable\n")
        return
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story = []
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            story += [Paragraph(line[2:], styles["Title"]), Spacer(1, 8)]
        elif line.startswith("## "):
            story += [Paragraph(line[3:], styles["Heading2"]), Spacer(1, 6)]
        elif line.startswith("- "):
            story.append(Paragraph("• " + line[2:], styles["BodyText"]))
        elif line.strip():
            story += [Paragraph(line, styles["BodyText"]), Spacer(1, 4)]
        else:
            story.append(Spacer(1, 4))
    doc.build(story)

def final_zip_ledger(zip_path: Path, root: Path):
    p = root / "99_integrity" / "AQ26_FINAL_ZIP_LEDGER.csv"
    rows = []
    with zipfile.ZipFile(zip_path, "r") as z:
        for info in z.infolist():
            if info.is_dir() or info.filename.endswith("AQ26_FINAL_ZIP_LEDGER.csv"):
                continue
            data = z.read(info.filename)
            rows.append({"zip_entry": info.filename, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    with p.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["zip_entry", "size_bytes", "sha256"])
        w.writeheader()
        w.writerows(rows)
    return p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", default="outputs")
    args = ap.parse_args()
    root = Path(args.output_root)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rdir = root / "weeklyv2_reports" / f"AQ26_WEEKLYV2_{ts}"
    rdir.mkdir(parents=True, exist_ok=True)

    latest = load(root / "00_weeklyv2" / "LATEST_WEEKLYV2.json")
    gates = load(root / "12_scoring" / "evidence_readiness_gates.json")
    red = load(root / "99_integrity" / "redaction_audit.json")
    official = load(root / "06_official_filings" / "official_priority_summary.json")
    sat = load(root / "07_satellite_cdse" / "satellite_catalogue_metadata.json")
    drive = load(root / "08_gdrive_snapshot" / "gdrive_recursive_inventory.json")
    openaq = load(root / "04_ground_aq_providers" / "openaq_safety_manifest.json")
    cams = load(root / "09_cams" / "cams_readiness.json")
    warnings = load(root / "03_news_context" / "news_provider_warnings.json")
    cdse = load(root / "15_optional_sources" / "cdse_auth_readiness.json")

    md = rdir / f"AQ26_WEEKLYV2_REPORT_{ts}.md"
    md.write_text("\n".join([
        "# AQ26 WeeklyV2 Evidence Report",
        "",
        "## Controlled-use boundary",
        "Controlled-review evidence harvester. No WHO/UNEP/EEA/C40 or expert endorsement claimed. No causal attribution unless gates pass.",
        "",
        "## Executive status",
        f"- Source records: `{latest.get('source_record_count', 0)}`",
        f"- OK: `{latest.get('ok_count', 0)}`",
        f"- Errors: `{latest.get('error_count', 0)}`",
        f"- Warnings: `{latest.get('warning_count', 0)}`",
        f"- Skipped: `{latest.get('skipped_count', 0)}`",
        f"- Redaction leaks: `{red.get('leak_count', 'not yet scanned')}`",
        f"- Google Drive files inventoried: `{drive.get('file_count', 'not scanned')}`",
        f"- Drive inventory truncated: `{drive.get('drive_inventory_truncated', 'not scanned')}`",
        f"- Satellite catalogue products: `{sat.get('product_count', 0)}`",
        f"- High-priority official filings: `{len(official.get('high', []))}`",
        f"- Medium-priority official filings: `{len(official.get('medium', []))}`",
        "",
        "## OpenAQ low-rate safety",
        f"- OpenAQ enabled: `{openaq.get('enabled')}`",
        f"- OpenAQ request count: `{openaq.get('request_count')}`",
        f"- OpenAQ max requests/run: `{openaq.get('max_requests_per_run')}`",
        f"- OpenAQ stopped reason: `{openaq.get('stopped_reason')}`",
        f"- OpenAQ rate limit seen: `{openaq.get('rate_limit_seen')}`",
        f"- OpenAQ auth error seen: `{openaq.get('auth_error_seen')}`",
        "",
        "## CAMS readiness",
        f"- CAMS key present: `{cams.get('cams_key_present')}`",
        f"- CAMS endpoint configured: `{cams.get('cams_endpoint_configured')}`",
        f"- CAMS data ready: `{cams.get('cams_data_ready')}`",
        "",
        "## CDSE readiness",
        f"- CDSE catalogue ready: `{gates.get('cdse_catalogue_ready')}`",
        f"- CDSE OData username/password ready: `{gates.get('cdse_odata_username_password_ready')}`",
        f"- CDSE Sentinel Hub client credentials ready: `{gates.get('cdse_sentinelhub_client_credentials_ready')}`",
        f"- CDSE download ready: `{gates.get('cdse_download_ready')}`",
        f"- CDSE auth recommendation: `{cdse.get('recommendation', '')}`",
        "",
        "## News provider warnings",
        f"- News warning count: `{warnings.get('warning_count', 0)}`",
        "",
        "## Evidence gates",
        f"- Redaction ready: `{gates.get('redaction_ready')}`",
        f"- Met Office ready: `{gates.get('metoffice_ready')}`",
        f"- Ground AQ ready: `{gates.get('ground_aq_ready')}`",
        f"- OpenAQ ready: `{gates.get('openaq_ready')}`",
        f"- OpenAQ safety ready: `{gates.get('openaq_safety_ready')}`",
        f"- CAMS key present: `{gates.get('cams_key_present')}`",
        f"- CAMS endpoint configured: `{gates.get('cams_endpoint_configured')}`",
        f"- CAMS data ready: `{gates.get('cams_data_ready')}`",
        f"- Satellite catalogue ready: `{gates.get('satellite_catalogue_ready')}`",
        f"- Satellite extraction ready: `{gates.get('satellite_extraction_ready')}`",
        f"- Official filings ready: `{gates.get('official_filings_ready')}`",
        f"- Drive ready: `{gates.get('drive_ready')}`",
        f"- External submission ready: `{gates.get('external_submission_ready')}`",
        "",
        "## Methods alignment",
        "- Dominici: causal language remains guarded; exposure/confounder readiness is tracked.",
        "- Martin: satellite catalogue supports remote sensing context; extraction/fusion remains next stage.",
        "- Brauer: multi-source exposure screening is structured; health burden attribution is not claimed.",
        "- Anenberg: trace-gas/emissions-relevant product families are prioritised.",
        "- Damoulas: target/control sites, gaps and metadata inventory prepare digital-twin style modelling.",
    ]), encoding="utf-8")

    pdf_path = rdir / f"AQ26_WEEKLYV2_REPORT_{ts}.pdf"
    pdf(md, pdf_path)
    led = ledger(root)
    manifest = {"run_ts": ts, "report_md": str(md), "report_pdf": str(pdf_path), "sha256_ledger": str(led), "latest": str(root / "00_weeklyv2" / "LATEST_WEEKLYV2.json"), "redaction_audit": str(root / "99_integrity" / "redaction_audit.json"), "cdse_auth_readiness": str(root / "15_optional_sources" / "cdse_auth_readiness.json")}
    (rdir / f"AQ26_WEEKLYV2_MASTER_MANIFEST_{ts}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    led = ledger(root)

    zip_path = root / "weeklyv2_reports" / f"AQ26_WEEKLYV2_EVIDENCE_{ts}.zip"
    include = [
        root / "00_weeklyv2", root / "00_live_harvest", root / "03_news_context",
        root / "04_ground_aq_providers", root / "05_weather", root / "05_metoffice_datahub_weather",
        root / "06_official_filings", root / "07_satellite_cdse", root / "08_gdrive_snapshot",
        root / "09_cams", root / "11_backfill", root / "12_scoring", root / "15_optional_sources",
        root / "99_integrity", root / "source_history", rdir
    ]

    def build_zip():
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for b in include:
                if b.exists():
                    for p in sorted(b.rglob("*")):
                        if p.is_file() and p != zip_path:
                            z.write(p, arcname=str(p.relative_to(root.parent)))

    build_zip()
    fzl = final_zip_ledger(zip_path, root)
    build_zip()
    (root / "weeklyv2_reports" / "LATEST_ZIP.txt").write_text(str(zip_path), encoding="utf-8")
    print(json.dumps({"zip": str(zip_path), "zip_sha256": sha(zip_path), "pdf": str(pdf_path), "final_zip_ledger": str(fzl)}, indent=2))

if __name__ == "__main__":
    main()
