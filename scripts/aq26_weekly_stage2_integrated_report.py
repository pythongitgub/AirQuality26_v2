#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
import yaml
from aq26_common_evidence import mkdir, write_json, read_json, now_utc, file_manifest, source_record

def load_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}

def load_df(path):
    path=Path(path)
    if not path.exists(): return pd.DataFrame()
    try:
        if path.suffix==".json":
            data=json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "pair_summaries" in data: return pd.DataFrame(data["pair_summaries"])
            if isinstance(data, list): return pd.DataFrame(data)
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--config", default="configs/aq26_weekly_stage2_report.yml")
    args=ap.parse_args()
    repo=Path(args.repo_root).resolve(); cfg=load_yaml(repo/args.config)
    out=repo/cfg.get("outputs",{}).get("root","outputs/36_weekly_stage2_integrated")
    site=repo/cfg.get("outputs",{}).get("site_root","site_public/data/providers/integrated_weekly_stage2")
    mkdir(out); mkdir(site); mkdir(out/"charts")
    weekly_index=read_json(repo/"site_public/data/weekly_index.json", {})
    v331_validation=read_json(repo/"outputs/99_integrity/AQ26_WEEKLYV2_SCIENCE_V33_VALIDATION.json", {})
    earth=read_json(repo/"outputs/34_earthdata_stage2/earthdata_stage2_summary.json", {})
    laqn=read_json(repo/"outputs/35_laqn_backfill/laqn_backfill_summary.json", {})
    # charts
    chart_paths=[]
    try:
        import matplotlib.pyplot as plt
        # LAQN numeric values by pair
        ps=pd.DataFrame(laqn.get("pair_summaries",[]))
        if len(ps):
            plt.figure(figsize=(10,5)); plt.bar(ps["site_code"].astype(str)+"/"+ps["species_code"].astype(str), ps["numeric_value_count"])
            plt.xticks(rotation=45, ha="right"); plt.ylabel("Numeric readings"); plt.title("LAQN controlled backfill numeric readings")
            p=out/"charts/laqn_numeric_readings_by_pair.png"; plt.tight_layout(); plt.savefig(p,dpi=160); plt.close(); chart_paths.append(str(p))
        tc=pd.DataFrame(earth.get("top_candidates",[]))
        if len(tc) and "aq26_relevance_score" in tc.columns:
            top=tc.head(10)
            plt.figure(figsize=(10,5)); plt.barh(top["short_name"].astype(str), top["aq26_relevance_score"]); plt.gca().invert_yaxis()
            plt.xlabel("AQ26 relevance score"); plt.title("NASA Earthdata CMR candidate scorecard")
            p=out/"charts/earthdata_candidate_scorecard.png"; plt.tight_layout(); plt.savefig(p,dpi=160); plt.close(); chart_paths.append(str(p))
    except Exception as e:
        write_json(out/"chart_warning.json", {"warning":repr(e)})
    records=[
        source_record("AQ26 WeeklyV2 Science Backfill V3.3.1 carried forward","AQ26 WeeklyV2","ok" if weekly_index else "warning", len(weekly_index.get("weeks",[]) if isinstance(weekly_index,dict) else []), "site_public/data/weekly_index.json", "Prior weekly science backfill state consumed by Stage2 follow-on."),
        source_record("NASA Earthdata Stage2 scorecard carried forward","NASA Earthdata CMR", earth.get("status","warning"), earth.get("collections_scored",0), "outputs/34_earthdata_stage2/earthdata_stage2_summary.json", "Satellite/reanalysis discovery context."),
        source_record("LAQN controlled backfill carried forward","London Air Quality Network", laqn.get("status","warning"), laqn.get("rows",0), "outputs/35_laqn_backfill/laqn_backfill_summary.json", "Validated ground-monitoring comparator sample/backfill."),
    ]
    summary={"provider":"aq26_weekly_stage2_integrated","status":"ok" if earth.get("status")=="ok" or laqn.get("status")=="ok" else "warning",
             "generated_utc":now_utc(),"follows_on_from":"AQ26 WeeklyV2 Science Backfill V3.3.1",
             "weekly_index_present":bool(weekly_index),"v331_validation_present":bool(v331_validation),
             "earthdata_stage2":earth,"laqn_backfill":laqn,"charts":chart_paths,
             "evidence_position":{"ground_monitoring":"LAQN controlled samples/backfill; expand pair coverage before full claims.",
                                  "satellite_reanalysis":"NASA CMR scorecard/discovery; not observation evidence until subset extraction validated.",
                                  "integrity":"manifests/checksums generated per provider and carried forward."},
             "institutional_caveat":"AQ26 uses WHO/UNEP/EEA/C40-style evidence discipline as an analytical frame; it does not imply endorsement by those organisations or named experts."}
    write_json(out/"weekly_stage2_integrated_summary.json", summary); write_json(out/"weekly_stage2_source_records.json", records); write_json(out/"manifest.json", {"generated_utc":now_utc(),"files":file_manifest(out,"weekly_stage2")})
    # simple HTML
    html=f"""<!doctype html><meta charset='utf-8'><title>AQ26 Weekly Stage2 Integrated Evidence</title>
<h1>AQ26 Weekly Stage2 Integrated Evidence</h1>
<p>Generated UTC: {summary['generated_utc']}</p>
<h2>Status</h2><pre>{json.dumps({'status':summary['status'],'weekly_index_present':summary['weekly_index_present'],'earthdata':earth.get('status'),'laqn':laqn.get('status')}, indent=2)}</pre>
<h2>Caveat</h2><p>{summary['institutional_caveat']}</p>"""
    (out/"weekly_stage2_integrated_report.html").write_text(html, encoding="utf-8")
    write_json(site/"summary.json", summary); write_json(site/"source_records.json", records)
    print(json.dumps(summary, indent=2, default=str)[:8000])
if __name__=="__main__":
    main()
