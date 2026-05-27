#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, time, os
from pathlib import Path
from typing import Any, Dict, List
import requests, yaml
import pandas as pd
from aq26_common_evidence import mkdir, write_json, now_utc, sha256_text, source_record, file_manifest

def load_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}

def flatten_payload(data: Any) -> List[Dict[str,Any]]:
    rows=[]
    def rec(x):
        if isinstance(x, list):
            for v in x: rec(v)
        elif isinstance(x, dict):
            # LAQN RawAQData/Data wrapper usually contains a list of hourly rows under Data or RawAQData.
            if any(k in x for k in ["@MeasurementDateGMT","@Value","@SiteCode","@SpeciesCode"]):
                rows.append(x)
            for v in x.values():
                if isinstance(v,(list,dict)): rec(v)
    rec(data)
    return rows

def fetch_laqn(base, site, species, start, end, ua, timeout=60):
    url=f"{base.rstrip('/')}/Data/SiteSpecies/SiteCode={site}/SpeciesCode={species}/StartDate={start}/EndDate={end}/Json"
    r=requests.get(url, headers={"User-Agent":ua,"Accept":"application/json"}, timeout=timeout)
    meta={"url":r.url,"http_status":r.status_code,"bytes":len(r.content),"content_type":r.headers.get("content-type",""),"sha256":sha256_text(r.text)}
    try: data=r.json()
    except Exception: data={"_error":r.text[:1000]}
    return meta,data,flatten_payload(data)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--config", default="configs/aq26_laqn_backfill.yml")
    ap.add_argument("--max-pairs", type=int, default=None)
    args=ap.parse_args()
    repo=Path(args.repo_root).resolve(); cfg=load_yaml(repo/args.config)
    out=repo/cfg.get("outputs",{}).get("root","outputs/35_laqn_backfill")
    site_root=repo/cfg.get("outputs",{}).get("site_root","site_public/data/providers/laqn/backfill")
    raw=mkdir(out/"raw"); norm=mkdir(out/"normalised"); chart=mkdir(out/"chart_safe"); mkdir(site_root)
    base=cfg.get("base_url","https://api.erg.ic.ac.uk/AirQuality")
    ua=os.getenv("AQ26_USER_AGENT", cfg.get("user_agent","AQ26 LAQN controlled backfill"))
    pairs=cfg.get("pairs",[])
    if args.max_pairs is not None: pairs=pairs[:args.max_pairs]
    all_rows=[]; recs=[]; pair_summaries=[]
    for p in pairs:
        site_code=str(p["site_code"]); species=str(p["species_code"]); start=str(p["start_date"]); end=str(p["end_date"])
        stem=f"{site_code}_{species}_{start}_{end}".replace("/","_")
        meta,data,rows=fetch_laqn(base, site_code, species, start, end, ua)
        write_json(raw/f"{stem}.json", {"_meta":meta,"payload":data})
        df=pd.DataFrame(rows)
        # remove wrapper rows without a measurement timestamp/value
        if not df.empty:
            for col in ["@Value","@MeasurementDateGMT","@MeasurementDateBST","@SiteCode","@SpeciesCode"]:
                if col not in df.columns: df[col]=""
            df["@Value_numeric"]=pd.to_numeric(df["@Value"], errors="coerce")
            df["site_code"]=site_code; df["species_code"]=species
            df["backfill_start_date"]=start; df["backfill_end_date"]=end
        csv_path=norm/f"laqn_{stem}.csv"; json_path=chart/f"laqn_{stem}.json"
        df.to_csv(csv_path,index=False); write_json(json_path, df.to_dict("records"))
        numeric=int(df["@Value_numeric"].notna().sum()) if "@Value_numeric" in df.columns else 0
        status="ok" if meta["http_status"]==200 and len(df)>0 and numeric>0 else "warning"
        rel=f"outputs/35_laqn_backfill/normalised/laqn_{stem}.csv"
        recs.append(source_record(f"LAQN controlled backfill {site_code}/{species}", "London Air Quality Network", status, len(df), rel,
                                  "Controlled evidence-lake historical harvest; value-bearing status depends on numeric_value_count.",
                                  site_code=site_code, species_code=species, observed_start=start, observed_end=end, http_status=meta["http_status"],
                                  numeric_value_count=numeric, blank_value_count=int(len(df)-numeric)))
        pair_summaries.append({"site_code":site_code,"species_code":species,"start_date":start,"end_date":end,
                               "rows":int(len(df)),"numeric_value_count":numeric,"status":status,
                               "normalised_path":str(csv_path),"chart_safe_path":str(json_path)})
        if len(df): all_rows.append(df)
        time.sleep(float(cfg.get("min_seconds_between_requests",1.0)))
    combined=pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    combined_csv=norm/"laqn_backfill_combined.csv"; combined_parq=norm/"laqn_backfill_combined.parquet"
    combined.to_csv(combined_csv,index=False)
    try:
        combined.to_parquet(combined_parq,index=False)
    except Exception as e:
        write_json(out/"parquet_warning.json", {"warning":repr(e)})
    write_json(chart/"laqn_backfill_combined.json", combined.head(int(cfg.get("chart_safe_row_limit",5000))).to_dict("records") if len(combined) else [])
    summary={"provider":"laqn_controlled_backfill","status":"ok" if any(x["numeric_value_count"]>0 for x in pair_summaries) else "warning",
             "retrieved_at_utc":now_utc(),"pairs_attempted":len(pair_summaries),"rows":int(len(combined)),
             "numeric_value_count":int(pd.to_numeric(combined.get("@Value",pd.Series(dtype=str)), errors="coerce").notna().sum()) if len(combined) else 0,
             "pair_summaries":pair_summaries,
             "follows_on_from":["AQ26 LAQN Provider Probe v3.6","AQ26 WeeklyV2 Science Backfill V3.3.1"],
             "caveat":"Controlled LAQN sample/backfill. Not full LAQN archive unless configured/pair coverage is expanded."}
    write_json(out/"laqn_backfill_source_records.json", recs); write_json(out/"laqn_backfill_summary.json", summary); write_json(out/"manifest.json", {"generated_utc":now_utc(),"files":file_manifest(out,"laqn_backfill")})
    write_json(site_root/"summary.json", summary); write_json(site_root/"source_records.json", recs); write_json(site_root/"laqn_backfill_combined.json", combined.head(5000).to_dict("records") if len(combined) else [])
    print(json.dumps(summary, indent=2)[:8000])
if __name__=="__main__":
    main()
