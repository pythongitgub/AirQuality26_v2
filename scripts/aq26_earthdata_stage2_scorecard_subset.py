#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, time, json, math
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse
import requests, yaml
import pandas as pd
from aq26_common_evidence import mkdir, write_json, write_csv, now_utc, sha256_text, source_record, file_manifest

CMR = "https://cmr.earthdata.nasa.gov/search"

def load_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}

def get_json(url, params, user_agent, timeout=60):
    h={"Accept":"application/json","User-Agent":user_agent}
    r=requests.get(url, params=params, headers=h, timeout=timeout)
    meta={"url":r.url,"http_status":r.status_code,"content_type":r.headers.get("content-type",""),"bytes":len(r.content),"sha256":sha256_text(r.text)}
    try: data=r.json()
    except Exception: data={"_error":r.text[:1000]}
    data["_meta"]=meta
    return data

def collection_rows(payload, keyword):
    rows=[]
    for e in payload.get("feed",{}).get("entry",[]):
        rows.append({
            "concept_id":e.get("id"), "short_name":e.get("short_name"), "version_id":e.get("version_id"),
            "title":e.get("title"), "data_center":e.get("data_center"), "time_start":e.get("time_start"),
            "time_end":e.get("time_end"), "summary":(e.get("summary") or "")[:1000], "matched_keyword":keyword,
            "has_granules":e.get("has_granules"), "links_json":json.dumps(e.get("links",[]), default=str),
        })
    return rows

def granule_rows(payload, coll):
    rows=[]
    for e in payload.get("feed",{}).get("entry",[]):
        hrefs=[l.get("href") for l in e.get("links",[]) if isinstance(l,dict) and l.get("href")]
        opendap=[h for h in hrefs if "opendap" in h.lower() or ".dap" in h.lower() or "/dap" in h.lower()]
        download=[h for h in hrefs if h.lower().startswith("http")]
        rows.append({
            "collection_concept_id":coll.get("concept_id"), "collection_short_name":coll.get("short_name"),
            "collection_title":coll.get("title"), "granule_id":e.get("id"), "producer_granule_id":e.get("producer_granule_id"),
            "title":e.get("title"), "time_start":e.get("time_start"), "time_end":e.get("time_end"), "updated":e.get("updated"),
            "links_count":len(hrefs), "opendap_count":len(opendap), "download_count":len(download),
            "opendap_links_json":json.dumps(opendap[:10]), "download_links_json":json.dumps(download[:10]),
        })
    return rows

def score_collection(row, gr_count=0, opendap_count=0):
    text=(" ".join(str(row.get(k,"")) for k in ["short_name","title","summary","matched_keyword"])).lower()
    score=0; reasons=[]
    rules=[("merra",35),("m2t1nxaer",45),("aerosol",25),("pm2.5",20),("pm25",20),("particulate",20),
           ("sulfur dioxide",20),("sulphur dioxide",20),("so2",20),("nitrogen dioxide",20),("no2",20),
           ("carbon monoxide",15),("co ",10),("ozone",12),("o3",12),("omi",12),("modis",12),("viirs",12),
           ("tempo",10),("gpm",3)]
    for term, pts in rules:
        if term in text:
            score += pts; reasons.append(term)
    if "GES_DISC" in str(row.get("data_center","")) or "GES DISC" in str(row.get("data_center","")):
        score += 10; reasons.append("ges_disc")
    if gr_count: score += 10; reasons.append("has_granules")
    if opendap_count: score += 20; reasons.append("has_opendap")
    if "Low-Cost-Sensors" in str(row.get("short_name","")):
        score -= 20; reasons.append("probably_not_uk")
    return max(score,0), ";".join(reasons)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--config", default="configs/aq26_earthdata_stage2.yml")
    ap.add_argument("--enable-tiny-download", action="store_true")
    args=ap.parse_args()
    repo=Path(args.repo_root).resolve()
    cfg=load_yaml(repo/args.config)
    out=repo/cfg.get("outputs",{}).get("root","outputs/34_earthdata_stage2")
    site=repo/cfg.get("outputs",{}).get("site_root","site_public/data/providers/earthdata/stage2")
    mkdir(out); mkdir(site)
    user_agent=os.getenv("AQ26_USER_AGENT", cfg.get("user_agent","AQ26 Earthdata Stage2"))
    search=cfg.get("search",{})
    bbox=search.get("bounding_box","-1.1,50.6,0.7,51.8")
    temporal=search.get("temporal","2024-01-01T00:00:00Z,2026-05-26T23:59:59Z")
    keywords=search.get("keywords",["MERRA-2 aerosol","M2T1NXAER","sulfur dioxide Level 4","nitrogen dioxide tropospheric column","aerosol optical depth MODIS"])
    max_col=int(search.get("max_collections_per_keyword",8)); max_total=int(search.get("max_total_collections",25))
    max_gran=int(search.get("max_granules_per_collection",3))
    collections=[]; seen=set(); raw_meta=[]
    for kw in keywords:
        payload=get_json(f"{CMR}/collections.json", {"keyword":kw,"bounding_box":bbox,"temporal":temporal,"page_size":max_col,"has_granules":"true","sort_key":"-score"}, user_agent)
        write_json(out/f"raw_collections_{kw.replace(' ','_').replace('/','_')}.json", payload)
        raw_meta.append(payload.get("_meta",{}))
        for r in collection_rows(payload, kw):
            if r.get("concept_id") and r["concept_id"] not in seen:
                seen.add(r["concept_id"]); collections.append(r)
        time.sleep(0.2)
    collections=collections[:max_total]
    granules=[]
    for coll in collections:
        payload=get_json(f"{CMR}/granules.json", {"collection_concept_id":coll["concept_id"],"bounding_box":bbox,"temporal":temporal,"page_size":max_gran,"sort_key":"-start_date"}, user_agent)
        write_json(out/f"raw_granules_{coll['concept_id']}.json", payload)
        granules += granule_rows(payload, coll)
        time.sleep(0.2)
    gr_df=pd.DataFrame(granules)
    rows=[]
    for c in collections:
        if gr_df.empty:
            gr_count=op_count=0
        else:
            g=gr_df[gr_df["collection_concept_id"].eq(c["concept_id"])]
            gr_count=len(g); op_count=int(g["opendap_count"].sum()) if len(g) else 0
        score, reasons=score_collection(c, gr_count, op_count)
        rows.append({**c, "aq26_relevance_score":score, "score_reasons":reasons,
                     "sample_granules":gr_count, "sample_opendap_links":op_count,
                     "aq26_recommended_next_step":"tiny_opendap_or_earthaccess_subset" if op_count else "inspect_daac_links"})
    score_df=pd.DataFrame(rows).sort_values("aq26_relevance_score", ascending=False) if rows else pd.DataFrame()
    score_csv=out/"cmr_candidate_scorecard.csv"; score_json=out/"cmr_candidate_scorecard.json"
    score_df.to_csv(score_csv,index=False); write_json(score_json, score_df.to_dict("records"))
    if not gr_df.empty: gr_df.to_csv(out/"cmr_granule_link_manifest.csv", index=False)
    write_json(out/"cmr_granule_link_manifest.json", gr_df.to_dict("records") if not gr_df.empty else [])
    # safe auth readiness only; no secret values
    auth={"earthdata_username_present":bool(os.getenv("EARTHDATA_USERNAME")),
          "earthdata_password_present":bool(os.getenv("EARTHDATA_PASSWORD")),
          "earthdata_token_present":bool(os.getenv("EARTHDATA_TOKEN")),
          "earthdata_api_key_alias_present":bool(os.getenv("EARTH_DATA_API_KEY"))}
    tiny={"enabled":bool(args.enable_tiny_download), "attempted":False, "status":"not_attempted", "notes":"Generic large/science download disabled. Build product-specific subset provider after scorecard review."}
    records=[
        source_record("NASA Earthdata CMR Stage2 candidate scorecard","NASA Earthdata CMR","ok" if len(score_df) else "warning",len(score_df),"outputs/34_earthdata_stage2/cmr_candidate_scorecard.csv","Catalogue discovery/scoring only; not observational evidence."),
        source_record("NASA Earthdata CMR Stage2 granule link manifest","NASA Earthdata CMR","ok" if len(gr_df) else "warning",len(gr_df),"outputs/34_earthdata_stage2/cmr_granule_link_manifest.csv","Granule/link probe only; no bulk download."),
    ]
    summary={"provider":"nasa_earthdata_stage2","status":"ok" if len(score_df) else "warning","retrieved_at_utc":now_utc(),
             "collections_scored":int(len(score_df)),"granules_sampled":int(len(gr_df)),"bounding_box":bbox,"temporal":temporal,
             "top_candidates":score_df.head(10).to_dict("records") if len(score_df) else [],"auth_readiness":auth,"tiny_download":tiny,
             "follows_on_from":["AQ26 Earthdata Auth Smoke Test","AQ26 NASA Earthdata CMR Probe","AQ26 WeeklyV2 Science Backfill V3.3.1"],
             "caveat":"Discovery/scorecard only. NASA data becomes evidence only after tiny subset extraction, validation, geospatial alignment and provenance checks."}
    write_json(out/"earthdata_stage2_summary.json", summary); write_json(out/"earthdata_stage2_source_records.json", records)
    write_json(site/"summary.json", summary); write_json(site/"cmr_candidate_scorecard.json", score_df.head(50).to_dict("records") if len(score_df) else [])
    write_json(out/"manifest.json", {"generated_utc":now_utc(),"files":file_manifest(out,"earthdata_stage2")})
    print(json.dumps(summary, indent=2)[:8000])
if __name__=="__main__":
    main()
