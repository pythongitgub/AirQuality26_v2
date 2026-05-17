#!/usr/bin/env python3
import argparse, json, re, datetime as dt
from pathlib import Path
PATS=[r"(?i)apiKey=[A-Za-z0-9_\-.]{8,}",r"(?i)apikey=[A-Za-z0-9_\-.]{8,}",r"(?i)api_key=[A-Za-z0-9_\-.]{8,}",r"(?i)token=[A-Za-z0-9_\-.]{8,}",r"(?i)password=[^&\s\"']{6,}",r"(?i)client_secret=[^&\s\"']{6,}",r"(?i)Bearer\s+[A-Za-z0-9_\-.]{12,}"]
EXT={".json",".jsonl",".csv",".txt",".md",".html",".xml",".yml",".yaml",".log"}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",default="outputs"); ap.add_argument("--fail-on-leak",default="true"); args=ap.parse_args()
    root=Path(args.root); leaks=[]; scanned=0
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in EXT: continue
        scanned+=1; text=p.read_text(encoding="utf-8",errors="ignore")
        for pat in PATS:
            m=re.search(pat,text)
            if m: leaks.append({"path":str(p),"pattern":pat,"match_preview":m.group(0)[:16]+"***"}); break
    out=root/"99_integrity/redaction_audit.json"; out.parent.mkdir(parents=True,exist_ok=True)
    res={"created_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"files_scanned":scanned,"leak_count":len(leaks),"leaks":leaks}
    out.write_text(json.dumps(res,indent=2),encoding="utf-8"); print(json.dumps(res,indent=2))
    if leaks and args.fail_on_leak.lower() in ("1","true","yes","y"): raise SystemExit("Redaction audit failed")
if __name__=="__main__": main()
