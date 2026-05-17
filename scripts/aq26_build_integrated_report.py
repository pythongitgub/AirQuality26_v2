#!/usr/bin/env python3
import argparse, csv, datetime as dt, hashlib, json, zipfile
from pathlib import Path
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
except Exception:
    SimpleDocTemplate=None
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def load(p):
    p=Path(p); return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def ledger(root):
    out=root/"99_integrity/AQ26_SHA256_LEDGER.csv"; out.parent.mkdir(parents=True,exist_ok=True)
    rows=[]
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix!=".zip": rows.append({"path":str(p),"size_bytes":p.stat().st_size,"sha256":sha(p)})
    with out.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["path","size_bytes","sha256"]); w.writeheader(); w.writerows(rows)
    return out
def pdf_from_lines(lines,pdf):
    if SimpleDocTemplate is None:
        pdf.write_bytes(b"%PDF-1.4\n% placeholder\n"); return
    styles=getSampleStyleSheet(); doc=SimpleDocTemplate(str(pdf),pagesize=A4); story=[]
    for line in lines:
        if line.startswith("# "): story += [Paragraph(line[2:],styles["Title"]), Spacer(1,8)]
        elif line.startswith("## "): story += [Paragraph(line[3:],styles["Heading2"]), Spacer(1,6)]
        elif line.strip(): story.append(Paragraph(line,styles["BodyText"]))
        else: story.append(Spacer(1,4))
    doc.build(story)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output-root",default="outputs"); args=ap.parse_args()
    root=Path(args.output_root); ts=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rep=root/"weekly_reports"/f"AQ26_WEEKLY_{ts}"; rep.mkdir(parents=True,exist_ok=True)
    latest=load(root/"00_live_harvest/LATEST_HARVEST.json"); alerts=load(root/"10_anomaly_alerts/anomaly_alerts.json"); filings=load(root/"06_official_filings/official_filing_index.json"); sat=load(root/"07_satellite_cdse/satellite_catalogue_metadata.json")
    lines=["# AQ26 Weekly Integrated Evidence Report","","## Controlled-use boundary","Automated controlled-review evidence harvest. No endorsement claimed by WHO, UNEP, EEA, C40 Cities or named experts. No causal attribution unless evidence gates support it.","","## Executive status",f"- Source records: {latest.get('source_record_count',0)}",f"- OK records: {latest.get('ok_count',0)}",f"- Error records: {latest.get('error_count',0)}",f"- Official filing candidates: {filings.get('filing_count',0)}",f"- Satellite catalogue products: {sat.get('product_count',0)}",f"- Attention/anomaly alerts: {alerts.get('alert_count',0)}","","## Readiness","Controlled-review beta. External submission is not recommended until official relevance, weather/wind, ground AQ QA and satellite extraction gates pass."]
    md=rep/f"AQ26_WEEKLY_INTEGRATED_REPORT_{ts}.md"; md.write_text("\n".join(lines),encoding="utf-8")
    pdf=rep/f"AQ26_WEEKLY_INTEGRATED_REPORT_{ts}.pdf"; pdf_from_lines(lines,pdf)
    led=ledger(root)
    manifest={"run_ts":ts,"report_md":str(md),"report_pdf":str(pdf),"sha256_ledger":str(led),"latest_harvest":str(root/"00_live_harvest/LATEST_HARVEST.json"),"source_history":str(root/"source_history/source_index.jsonl"),"controlled_use_boundary":"No endorsement claimed; no causal attribution unless evidence gates support it."}
    (rep/f"AQ26_WEEKLY_MASTER_MANIFEST_{ts}.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    led=ledger(root)
    z=root/"weekly_reports"/f"AQ26_WEEKLY_INTEGRATED_EVIDENCE_{ts}.zip"
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as zz:
        for p in root.rglob("*"):
            if p.is_file() and p!=z: zz.write(p,arcname=str(p.relative_to(root.parent)))
    (root/"weekly_reports/LATEST_ZIP.txt").write_text(str(z),encoding="utf-8")
    print(json.dumps({"zip":str(z),"sha256":sha(z),"pdf":str(pdf)},indent=2))
if __name__=="__main__": main()
