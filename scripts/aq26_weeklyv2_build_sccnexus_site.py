#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, html, json, os, shutil, zipfile
from pathlib import Path
from typing import Any

MAIN_NAV=[("index.html","Observatory"),("archive.html","Weekly Archive"),("comparisons.html","Comparisons"),("source-records.html","Source Records"),("readiness.html","Readiness"),("methodology.html","Methodology"),("downloads.html","Downloads")]
FOOTER_NAV=[("about.html","About"),("privacy.html","Privacy"),("cookies.html","Cookies"),("accessibility.html","Accessibility"),("terms.html","Terms"),("contact.html","Contact")]

def esc(x:Any)->str: return html.escape("" if x is None else str(x))
def n(x:Any)->int:
    try: return int(float(x or 0))
    except Exception: return 0
def j(path:Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace")) if path.exists() else {}
    except Exception: return {}
def wj(path:Path,obj:Any):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def latest_zip(root:Path):
    p=root/"weeklyv2_reports"/"LATEST_ZIP.txt"
    if p.exists():
        z=Path(p.read_text(encoding="utf-8").strip())
        if z.exists(): return z
    zs=sorted((root/"weeklyv2_reports").glob("AQ26_WEEKLYV2_EVIDENCE_*.zip"))
    return zs[-1] if zs else None

def zip_status(z):
    if not z: return {"zip_present":False}
    with zipfile.ZipFile(z) as zz:
        names=zz.namelist(); led=[x for x in names if x.endswith("AQ26_FINAL_ZIP_LEDGER.csv")]
        rows=0
        if led:
            rows=max(0,len(zz.read(led[-1]).decode("utf-8","replace").splitlines())-1)
    return {"zip_present":True,"zip_name":z.name,"zip_sha256":sha(z),"zip_entry_count":len(names),"ledger_rows":rows,"ledger_present":bool(led)}

def summary(root:Path, remote_subdir:str):
    latest=j(root/"00_weeklyv2"/"LATEST_WEEKLYV2.json") or j(root/"00_live_harvest"/"LATEST_HARVEST.json")
    gates=j(root/"12_scoring"/"evidence_readiness_gates.json"); red=j(root/"99_integrity"/"redaction_audit.json")
    sat=j(root/"07_satellite_cdse"/"satellite_catalogue_metadata.json"); drv=j(root/"08_gdrive_snapshot"/"gdrive_recursive_inventory.json")
    off=j(root/"06_official_filings"/"official_priority_summary.json"); oq=j(root/"04_ground_aq_providers"/"openaq_safety_manifest.json")
    cams=j(root/"09_cams"/"cams_readiness.json"); cdse=j(root/"15_optional_sources"/"cdse_auth_readiness.json")
    san=j(root/"15_optional_sources"/"provider_sanitization_manifest.json"); warn=j(root/"03_news_context"/"news_provider_warnings.json")
    z=latest_zip(root); zs=zip_status(z); run=latest.get("run_ts") or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {"run_ts":run,"created_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"date_window":latest.get("date_window") or {},
    "source_record_count":n(latest.get("source_record_count")),"ok_count":n(latest.get("ok_count")),"warning_count":n(latest.get("warning_count")),"error_count":n(latest.get("error_count")),"skipped_count":n(latest.get("skipped_count")),
    "redaction_leak_count":n(red.get("leak_count")),"redaction_ready":bool(gates.get("redaction_ready")),"external_submission_ready":bool(gates.get("external_submission_ready")),
    "metoffice_ready":bool(gates.get("metoffice_ready")),"ground_aq_ready":bool(gates.get("ground_aq_ready")),"openaq_ready":bool(gates.get("openaq_ready")),"openaq_safety_ready":bool(gates.get("openaq_safety_ready")),
    "satellite_catalogue_ready":bool(gates.get("satellite_catalogue_ready")),"satellite_extraction_ready":bool(gates.get("satellite_extraction_ready")),"satellite_product_count":n(sat.get("product_count")),
    "drive_ready":bool(gates.get("drive_ready")),"drive_file_count":n(drv.get("file_count")),"drive_inventory_truncated":bool(drv.get("drive_inventory_truncated")),"drive_folder_count":n(drv.get("folder_count")),
    "high_priority_filings":len(off.get("high",[]) or []),"medium_priority_filings":len(off.get("medium",[]) or []),"openaq_request_count":n(oq.get("request_count")),"openaq_rate_limit_seen":bool(oq.get("rate_limit_seen")),
    "cams_key_present":bool(cams.get("cams_key_present")),"cams_endpoint_configured":bool(cams.get("cams_endpoint_configured")),"cams_data_ready":bool(cams.get("cams_data_ready")),
    "cdse_download_ready":bool(cdse.get("cdse_download_ready") or gates.get("cdse_download_ready")),"cdse_sentinelhub_ready":bool(cdse.get("cdse_sentinelhub_ready") or gates.get("cdse_sentinelhub_client_credentials_ready")),
    "gemini_summary_ready":bool(gates.get("gemini_summary_ready")),"provider_sanitized_files":n(san.get("files_changed")),"news_warning_count":n(warn.get("warning_count")),
    "final_zip_name":z.name if z else "","final_zip_sha256":zs.get("zip_sha256",""),"final_zip_relpath":f"downloads/{z.name}" if z else "","final_zip_status":zs,
    "github_repository":os.getenv("GITHUB_REPOSITORY_VALUE",os.getenv("GITHUB_REPOSITORY","")),"github_run_id":os.getenv("GITHUB_RUN_ID_VALUE",os.getenv("GITHUB_RUN_ID","")),"github_sha":os.getenv("GITHUB_SHA_VALUE",os.getenv("GITHUB_SHA","")),"remote_subdir":remote_subdir}

def records(root:Path):
    r=(j(root/"00_weeklyv2"/"LATEST_WEEKLYV2.json").get("source_records") or [])
    return r if isinstance(r,list) else []

def existing_history(root:Path):
    rows=[]
    for folder in [root/"website_history",root/"10_historical_backfill"/"history",root/"10_historical_backfill"/"site_history",root/"historical_site"/"history",root/"website_history"/"two_year_validated"]:
        if folder.exists():
            for p in folder.glob("*.json"):
                if p.name.startswith("weekly_index"): continue
                o=j(p)
                if o.get("run_ts"): o.setdefault("backfill_status","historical_summary_loaded"); rows.append(o)
            prev=j(folder/"weekly_index.previous.json")
            if isinstance(prev.get("weeks"),list): rows += [x for x in prev["weeks"] if isinstance(x,dict) and x.get("run_ts")]
    d={str(x.get("run_ts")):x for x in rows}
    return list(d.values())

def history(cur, old, weeks):
    by={str(x.get("run_ts")):x for x in old if x.get("run_ts")}; by[str(cur["run_ts"])]=cur
    today=dt.date.fromisoformat(getattr(history, "end_date", "") or dt.datetime.now(dt.timezone.utc).date().isoformat()); bywin={}
    for r in by.values():
        win=r.get("date_window") or {}
        if win.get("start") and win.get("end"): bywin[(win["start"],win["end"])]=r
    rows=[]
    for i in range(weeks):
        end=today-dt.timedelta(days=i*7); start=end-dt.timedelta(days=7); key=(start.isoformat(),end.isoformat())
        rows.append(bywin.get(key,{"run_ts":f"BACKFILL_SLOT_{key[0]}_{key[1]}","date_window":{"start":key[0],"end":key[1]},"backfill_status":"not_yet_harvested","source_record_count":0,"ok_count":0,"warning_count":0,"error_count":0,"satellite_product_count":0,"drive_file_count":0,"high_priority_filings":0,"medium_priority_filings":0,"external_submission_ready":False,"final_zip_relpath":""}))
    seen={x.get("run_ts") for x in rows}
    rows += [x for x in by.values() if x.get("run_ts") not in seen]
    return sorted(rows,key=lambda x:(str((x.get("date_window") or {}).get("end","")),str(x.get("run_ts",""))),reverse=True)

def copy_assets(asset_root:Path, site:Path):
    target=site/"assets"
    if target.exists(): shutil.rmtree(target)
    target.mkdir(parents=True,exist_ok=True)
    if asset_root.exists(): shutil.copytree(asset_root,target,dirs_exist_ok=True)
    (target/"site.css").write_text(css(),encoding="utf-8"); (target/"site.js").write_text(js(),encoding="utf-8")
    (target/"site.webmanifest").write_text(json.dumps({"name":"AQ26 Environmental Intelligence Observatory","short_name":"AQ26","start_url":"./index.html","display":"standalone","background_color":"#eef7fb","theme_color":"#0b2245","icons":[{"src":"brand/air_quality_web.svg","sizes":"any","type":"image/svg+xml"}]},indent=2),encoding="utf-8")
    icon=target/"brand"/"air_quality_web.svg"
    if icon.exists(): shutil.copy2(icon,target/"favicon.svg")

def copy_downloads(root:Path, site:Path):
    d=site/"downloads"; d.mkdir(parents=True,exist_ok=True); out=[]
    z=latest_zip(root)
    if z:
        dst=d/z.name; shutil.copy2(z,dst); out.append({"name":z.name,"path":f"downloads/{z.name}","bytes":dst.stat().st_size,"sha256":sha(dst),"type":"evidence_zip"})
    for p in sorted((root/"weeklyv2_reports").rglob("AQ26_WEEKLYV2_REPORT_*.*"))[-8:]:
        if p.is_file() and p.suffix.lower() in {".pdf",".md"}:
            dst=d/p.name; shutil.copy2(p,dst); out.append({"name":p.name,"path":f"downloads/{p.name}","bytes":dst.stat().st_size,"sha256":sha(dst),"type":"report"})
    return out

def topbar(s):
    w=s.get("date_window") or {}
    return f"<div class='topbar'><div class='topbar-inner'><span>SCC Nexus · AQ26 controlled-review environmental intelligence</span><span>Run {esc(s.get('run_ts'))} · Window {esc(w.get('start'))} to {esc(w.get('end'))}</span></div></div>"
def header(active):
    links="".join(f"<a class=\"{'active' if h==active else ''}\" href=\"{h}\">{l}</a>" for h,l in MAIN_NAV)
    return f"<header class='header'><div class='header-inner'><a class='brand-link' href='index.html'><img class='logo aq-logo' src='assets/brand/air_quality_web.svg' alt='AQ26 Air Quality'></a><nav class='nav'>{links}</nav></div></header>"
def footer(s):
    links="".join(f"<a href='{h}'>{l}</a>" for h,l in FOOTER_NAV)
    return f"<footer class='footer'><div class='footer-inner'><div><strong>AQ26 WeeklyV2</strong><p>Controlled-review evidence dashboard prepared for expert and institutional review; no endorsement, representation, regulatory determination or causal attribution is claimed.</p></div><nav class='footer-nav'>{links}</nav><div class='footer-meta'><span>External submission ready: {esc(s.get('external_submission_ready'))}</span><span>© SCC Nexus / AQ26</span></div></div></footer><div id='cookie-banner' class='cookie-banner' role='dialog'><div><strong>Cookies on AQ26</strong><p>We use essential local-storage preferences for this banner and may load Plotly from CDN for interactive charts. No advertising cookies are intentionally set by this static site.</p></div><div><button class='btn small' onclick='AQ26.acceptCookies()'>Accept</button><a class='btn small ghost-dark' href='cookies.html'>Cookie details</a></div></div>"
def layout(title, active, body, s):
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='robots' content='index,follow'><title>{esc(title)} · AQ26</title><link rel='icon' href='assets/favicon.svg' type='image/svg+xml'><link rel='manifest' href='assets/site.webmanifest'><link rel='stylesheet' href='assets/site.css'><script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script></head><body>{topbar(s)}{header(active)}{body}{footer(s)}<script src='assets/site.js'></script></body></html>"

def metric(t,v,note="",cls=""): return f"<div class='metric'><span>{esc(t)}</span><strong class='{cls}'>{esc(v)}</strong><small>{esc(note)}</small></div>"
def gate(t,v,invert=False):
    truth=bool(v); cls="danger" if (truth and invert) or ((not truth) and not invert) else "ok"
    return f"<div class='card'><h3>{esc(t)}</h3><p class='{cls}'><strong>{esc(v)}</strong></p></div>"
def download_card(d): return f"<a class='report-card' href='{esc(d.get('path'))}'><strong>{esc(d.get('name'))}</strong><span>{esc(d.get('type'))} · {n(d.get('bytes')):,} bytes</span><code>{esc(str(d.get('sha256',''))[:16])}...</code></a>"

def hero(s):
    return f"<section class='hero'><video class='hero-video' autoplay muted loop playsinline poster='assets/banners/desktop_banner_1_web.svg'><source src='assets/banners/desktop_banner_2.webm' type='video/webm'></video><div class='hero-inner'><div><p class='kicker'>AQ26 Environmental Intelligence Observatory</p><h1>Weekly evidence, provenance and target-control air-quality intelligence.</h1><p>Website-ready monitoring around Newhaven Energy Recovery Facility and contextual control sites, with source records, integrity ledgers, readiness gates and historical comparison slots.</p><a class='btn primary' href='archive.html'>View weekly archive</a><a class='btn ghost' href='{esc(s.get('final_zip_relpath') or '#')}'>Download evidence ZIP</a></div><div class='banner-card'><div class='slide active'><h3>Controlled review</h3><p>Prepared for controlled expert and institutional review. No WHO, UNEP, EEA, C40 Cities or named-expert endorsement, representation or causal attribution is claimed. Evidence gates make limitations visible.</p></div><div class='slide'><h3>Integrity ledgers</h3><p>Final ZIP entries, redaction status and source records are bundled for audit-ready weekly review.</p></div><div class='slide'><h3>Historical trajectory</h3><p>Weekly slots and charts support comparison and source-specific historical backfill.</p></div><div class='dots'><span class='dot active'></span><span class='dot'></span><span class='dot'></span></div></div></div></section>"

def render_index(site,s,weeks,downloads):
    cards=[metric("Source records",s["source_record_count"],"All source classes"),metric("OK records",s["ok_count"],"Successful harvests","ok"),metric("Warnings",s["warning_count"],"Provider warnings","warn"),metric("Errors",s["error_count"],"Should remain zero","danger" if s["error_count"] else "ok"),metric("Satellite products",s["satellite_product_count"],"Catalogue records"),metric("Drive files",s["drive_file_count"],"Recursive metadata inventory"),metric("Redaction leaks",s["redaction_leak_count"],"Fail-closed audit","danger" if s["redaction_leak_count"] else "ok"),metric("High filings",s["high_priority_filings"],"Official relevance queue")]
    data=esc(json.dumps({"summary":s,"weeks":weeks},ensure_ascii=False))
    body=hero(s)+f"<main><section class='section'><div class='section-title'><h2>Latest evidence status</h2><p>Current GitHub weekly run, source coverage and readiness state.</p></div><div class='grid grid-4'>{''.join(cards)}</div></section><section class='section'><div class='section-title'><h2>Interactive comparison charts</h2><p>Weekly record counts, satellite coverage and filings.</p></div><div class='grid grid-2'><div class='viz-card'><div id='records-chart'></div></div><div class='viz-card'><div id='coverage-chart'></div></div></div></section><section class='section'><div class='section-title'><h2>Evidence gates</h2><p>External submission remains false until science gates pass.</p></div><div class='grid grid-3'>{gate('Redaction ready',s['redaction_ready'])}{gate('CDSE download ready',s['cdse_download_ready'])}{gate('CAMS data ready',s['cams_data_ready'])}{gate('Satellite extraction ready',s['satellite_extraction_ready'])}{gate('Drive inventory truncated',s['drive_inventory_truncated'],True)}{gate('External submission ready',s['external_submission_ready'],True)}</div></section><section class='section'><div class='section-title'><h2>Latest downloads</h2><p>Evidence bundles and report files generated by the latest run.</p></div><div class='report-list'>{''.join(download_card(d) for d in downloads)}</div></section></main><script id='aq26-data' type='application/json'>{data}</script>"
    (site/"index.html").write_text(layout("AQ26 Environmental Intelligence Observatory","index.html",body,s),encoding="utf-8")

def render_archive(site,s,weeks):
    rows=""
    for w in weeks:
        win=w.get("date_window") or {}; status=w.get("backfill_status") or ("harvested" if n(w.get("source_record_count")) else "not_yet_harvested"); link=w.get("final_zip_relpath") or "#"
        rows += f"<tr><td>{esc(win.get('start'))}</td><td>{esc(win.get('end'))}</td><td><span class='tag'>{esc(status)}</span></td><td>{n(w.get('source_record_count'))}</td><td>{n(w.get('ok_count'))}</td><td>{n(w.get('warning_count'))}</td><td>{n(w.get('error_count'))}</td><td>{n(w.get('satellite_product_count'))}</td><td>{n(w.get('high_priority_filings'))}</td><td><a href='{esc(link)}'>Open</a></td></tr>"
    body=f"<main><section class='section'><div class='section-title'><h2>Weekly archive and historical backfill slots</h2><p>Completed weekly summaries are collated from Hostinger history and local backfill folders. Empty slots remain clearly marked until source-specific historical backfill runs create real evidence records.</p></div><input class='filter' placeholder='Filter by date/status...' oninput=\"AQ26.filterTable('weekly-table',this.value)\"><div class='table-wrap'><table id='weekly-table'><thead><tr><th>Start</th><th>End</th><th>Status</th><th>Records</th><th>OK</th><th>Warnings</th><th>Errors</th><th>Satellite</th><th>High filings</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table></div></section></main>"
    (site/"archive.html").write_text(layout("Weekly Archive","archive.html",body,s),encoding="utf-8")

def render_comparisons(site,s,weeks):
    data=esc(json.dumps({"summary":s,"weeks":weeks},ensure_ascii=False))
    body=f"<main><section class='section'><div class='section-title'><h2>Comparison charts</h2><p>Interactive weekly comparisons across source coverage, readiness and filings.</p></div><div class='grid grid-2'><div class='viz-card'><div id='records-chart'></div></div><div class='viz-card'><div id='coverage-chart'></div></div><div class='viz-card'><div id='filings-chart'></div></div><div class='viz-card'><div id='readiness-chart'></div></div></div></section></main><script id='aq26-data' type='application/json'>{data}</script>"
    (site/"comparisons.html").write_text(layout("Comparisons","comparisons.html",body,s),encoding="utf-8")
def render_source_records(site,s,recs):
    rows="".join(f"<tr><td>{esc(r.get('source_name'))}</td><td>{esc(r.get('source_type'))}</td><td>{esc(r.get('status'))}</td><td>{esc(r.get('http_status'))}</td><td>{esc(r.get('record_count'))}</td><td>{esc(r.get('retrieved_at_uk'))}</td><td>{esc(r.get('query'))}</td></tr>" for r in recs)
    body=f"<main><section class='section'><div class='section-title'><h2>Source records</h2><p>Redacted provenance records generated by the latest WeeklyV2 run.</p></div><input class='filter' placeholder='Filter source records...' oninput=\"AQ26.filterTable('source-table',this.value)\"><div class='table-wrap'><table id='source-table'><thead><tr><th>Source</th><th>Type</th><th>Status</th><th>HTTP</th><th>Records</th><th>Retrieved UK</th><th>Query/site</th></tr></thead><tbody>{rows}</tbody></table></div></section></main>"
    (site/"source-records.html").write_text(layout("Source Records","source-records.html",body,s),encoding="utf-8")
def render_readiness(site,s):
    body=f"<main><section class='section'><div class='section-title'><h2>Readiness and governance gates</h2><p>These gates prevent overclaiming and separate evidence harvesting from scientific attribution.</p></div><div class='grid grid-3'>{gate('Redaction ready',s['redaction_ready'])}{gate('Ground AQ ready',s['ground_aq_ready'])}{gate('Met Office ready',s['metoffice_ready'])}{gate('OpenAQ safety ready',s['openaq_safety_ready'])}{gate('Satellite catalogue ready',s['satellite_catalogue_ready'])}{gate('Satellite extraction ready',s['satellite_extraction_ready'])}{gate('CDSE download ready',s['cdse_download_ready'])}{gate('CAMS data ready',s['cams_data_ready'])}{gate('Drive inventory truncated',s['drive_inventory_truncated'],True)}{gate('External submission ready',s['external_submission_ready'],True)}</div></section><section class='section'><div class='callout'><strong>Current boundary:</strong> controlled-review evidence, not regulatory proof, not health-burden attribution, and not causal facility attribution.</div></section></main>"
    (site/"readiness.html").write_text(layout("Readiness","readiness.html",body,s),encoding="utf-8")
def render_methodology(site,s):
    items=[("Maria Neira / WHO framing","Health-protective guideline context and cautious public-health language."),("Frank Kelly-style QA","Station quality, representativeness, averaging periods and traffic/background confounding."),("Helen ApSimon-style source-receptor logic","Wind, dispersion, emissions inventory and uncertainty before attribution."),("Prashant Kumar-style sensor governance","Low-cost sensor provenance, siting, calibration and spatial representativeness."),("Dominici-style causal epidemiology","No causal health inference without confounder control, exposure windows and uncertainty."),("Randall Martin-style satellite fusion","Remote-sensing context requires extraction, QA and ground validation."),("Michael Brauer / GBD integration","Exposure screening is separated from health-burden calculation."),("Susan Anenberg-style emissions-health modelling","Trace-gas and emissions-related indicators are prioritised for screening."),("Theo Damoulas-style digital twin readiness","Weekly historical structure and target/control sites support future spatiotemporal models.")]
    body="<main><section class='section'><div class='section-title'><h2>Methodology alignment</h2><p>Scientific and policy frameworks used as design benchmarks for controlled review, not endorsements or representation.</p></div><div class='grid grid-3'>"+ "".join(f"<div class='card'><h3>{esc(t)}</h3><p>{esc(d)}</p></div>" for t,d in items)+"</div></section></main>"
    (site/"methodology.html").write_text(layout("Methodology","methodology.html",body,s),encoding="utf-8")
def render_downloads(site,s,downloads):
    body=f"<main><section class='section'><div class='section-title'><h2>Downloads</h2><p>Latest evidence bundles, reports and machine-readable indexes.</p></div><div class='report-list'>{''.join(download_card(d) for d in downloads)}<a class='report-card' href='data/latest_summary.json'><strong>latest_summary.json</strong><span>machine-readable latest run summary</span></a><a class='report-card' href='data/weekly_index.json'><strong>weekly_index.json</strong><span>weekly historical index and backfill slots</span></a></div></section></main>"
    (site/"downloads.html").write_text(layout("Downloads","downloads.html",body,s),encoding="utf-8")
def legal_page(site,fn,title,content,s):
    body=f"<main><section class='section legal'><div class='section-title'><h2>{esc(title)}</h2><p>SCC Nexus / AQ26 website information.</p></div><div class='card legal-card'>{content}</div></section></main>"
    (site/fn).write_text(layout(title,fn,body,s),encoding="utf-8")
def render_footer_pages(site,s):
    legal_page(site,"about.html","About AQ26","<p>AQ26 is a controlled-review environmental evidence dashboard for weekly air-quality, weather, satellite-catalogue, official filing and provenance monitoring. It is designed for evidence triage and transparent review, not unsupported causal attribution.</p>",s)
    legal_page(site,"privacy.html","Privacy","<p>This static website publishes redacted, non-secret evidence summaries. It does not intentionally collect personal data from visitors. Server logs may be created by the hosting provider. Evidence bundles must pass redaction audit before publication.</p><p>No API keys, passwords, tokens or raw secret values should appear in website files.</p>",s)
    legal_page(site,"cookies.html","Cookies","<p>This site uses an essential local-storage preference to remember whether the cookie banner has been accepted. Interactive charts may load Plotly from a CDN. No advertising cookies are intentionally set by this static site.</p><p>You can clear your browser site data to reset the banner preference.</p>",s)
    legal_page(site,"accessibility.html","Accessibility","<p>The site aims to use readable contrast, semantic headings, keyboard-friendly links and responsive layouts. If any chart or table is inaccessible, the linked JSON data files and downloads provide alternative machine-readable formats.</p>",s)
    legal_page(site,"terms.html","Terms","<p>AQ26 outputs are controlled-review materials for evidence triage, provenance review and research-development. They should not be represented as regulatory determinations, health-burden attribution or external endorsement.</p>",s)
    legal_page(site,"contact.html","Contact","<p>For project contact, use the SCC Nexus / AQ26 project contact route configured by the site owner. Do not send API keys, passwords or private tokens through public channels.</p>",s)

def write_data(site,s,weeks,recs):
    data=site/"data"; hist=data/"history"; hist.mkdir(parents=True,exist_ok=True)
    wj(data/"latest_summary.json",s); wj(data/"weekly_index.json",{"created_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"weeks":weeks})
    wj(data/"source_records_latest.json",{"run_ts":s.get("run_ts"),"records":recs}); wj(hist/f"{s['run_ts']}.json",s)

def css():
    return """:root{--navy:#0b2245;--navy2:#123d73;--cyan:#20b5aa;--gold:#c79533;--ink:#132238;--muted:#607083;--line:#d9e3ec;--ok:#217a50;--warn:#b7791f;--danger:#b83232;--shadow:0 12px 30px rgba(13,43,87,.08);--radius:18px}*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#e9f0f6 0,#f8fafc 360px,#fff);color:var(--ink);font-family:Aptos,Segoe UI,Roboto,Arial,sans-serif;line-height:1.55;position:relative}body:before{content:"";position:fixed;right:-110px;bottom:4vh;width:min(46vw,620px);aspect-ratio:1;background:url("brand/air_quality_web.svg") center/contain no-repeat;opacity:.035;pointer-events:none;z-index:0}.topbar,.header,.hero,main,.footer{position:relative;z-index:1}.topbar{background:#06172e;color:#d9e8f6;font-size:13px;padding:8px 22px}.topbar-inner{max-width:1380px;margin:0 auto;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.header{background:rgba(255,255,255,.97);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:50;box-shadow:0 4px 20px rgba(10,28,55,.08)}.header-inner{max-width:1380px;margin:0 auto;padding:10px 22px;display:flex;align-items:center;justify-content:space-between;gap:18px}.logo.aq-logo{width:260px;height:96px;display:block;object-fit:contain;filter:drop-shadow(0 8px 18px rgba(11,34,69,.08))}.nav{display:flex;gap:7px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.nav a{text-decoration:none;color:var(--navy);font-size:12.5px;font-weight:800;padding:8px 10px;border-radius:999px;white-space:nowrap}.nav a.active,.nav a:hover{background:#e8f1fb}.hero{background:linear-gradient(135deg,rgba(6,23,46,.96),rgba(9,47,84,.86) 52%,rgba(8,127,121,.78)),url("banners/desktop_banner_1_web.svg");background-size:cover;background-position:center;color:#fff;position:relative;overflow:hidden}.hero-video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.12;filter:saturate(.85) contrast(1.05)}.hero-inner{max-width:1380px;margin:0 auto;padding:48px 22px 54px;position:relative;z-index:1;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(320px,.75fr);gap:30px;align-items:center}.kicker{text-transform:uppercase;letter-spacing:.13em;font-size:12px;font-weight:900;color:#bcebe7}.hero h1{font-size:clamp(34px,4.0vw,56px);line-height:1.06;margin:12px 0 16px;max-width:900px;text-wrap:balance}.hero p{font-size:clamp(16px,1.6vw,19px);color:#e5f1fb}.btn{display:inline-block;padding:11px 16px;border-radius:10px;text-decoration:none;font-weight:900;border:1px solid rgba(255,255,255,.28);margin:6px 8px 0 0}.btn.primary{background:#fff;color:var(--navy);box-shadow:0 14px 34px rgba(0,0,0,.18)}.btn.ghost{color:#fff;background:rgba(255,255,255,.08)}.btn.small{font-size:13px;padding:8px 10px}.ghost-dark{background:#e9f0f6;color:var(--navy);border:1px solid var(--line)}.banner-card{background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.27);border-radius:22px;padding:24px}.slide{display:none}.slide.active{display:block}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:rgba(255,255,255,.38);margin-right:8px}.dot.active{background:#fff}main{max-width:1380px;margin:0 auto;padding:30px 22px 58px}.section{margin:0 0 28px}.section-title{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-bottom:14px}.section-title h2{font-size:clamp(23px,2.4vw,30px);margin:0;color:var(--navy)}.section-title p{margin:0;color:var(--muted);max-width:720px}.grid{display:grid;gap:16px}.grid-4{grid-template-columns:repeat(4,minmax(0,1fr))}.grid-3{grid-template-columns:repeat(3,minmax(0,1fr))}.grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}.card,.metric,.callout,.viz-card{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow)}.metric span{display:block;text-transform:uppercase;letter-spacing:.08em;font-size:12px;color:var(--muted);font-weight:900}.metric strong{display:block;font-size:clamp(30px,4vw,46px);color:var(--navy);line-height:1.05;margin:8px 0}.ok{color:var(--ok)!important}.warn{color:var(--warn)!important}.danger{color:var(--danger)!important}.tag{display:inline-block;border-radius:999px;background:#e8f1fb;color:var(--navy);font-weight:900;font-size:12px;padding:3px 8px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);background:#fff}table{border-collapse:collapse;width:100%;min-width:860px}th,td{padding:11px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:14px}th{background:#f0f5fa;color:var(--navy);position:sticky;top:0}.filter{width:100%;padding:13px 14px;border:1px solid var(--line);border-radius:12px;margin:0 0 12px;font-size:15px}.viz-card{min-height:420px}.report-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.report-card{display:block;text-decoration:none;background:#fff;border:1px solid var(--line);border-radius:16px;padding:16px;box-shadow:var(--shadow)}.report-card strong{display:block;color:var(--navy);margin-bottom:6px}.report-card span{display:block;color:var(--muted);font-size:13px}.report-card code{display:block;margin-top:8px;color:#456;font-size:12px}.callout{border-left:5px solid var(--gold);background:#fffaf0}.footer{background:#06172e;color:#d9e8f6;padding:28px 22px}.footer-inner{max-width:1380px;margin:0 auto;display:grid;grid-template-columns:1.3fr 1fr 1fr;gap:18px}.footer p{color:#9eb6cf}.footer-nav{display:flex;flex-wrap:wrap;gap:10px}.footer-nav a{color:#d9e8f6;text-decoration:none;font-weight:700}.footer-meta{display:flex;flex-direction:column;gap:6px;color:#9eb6cf}.cookie-banner{position:fixed;left:18px;right:18px;bottom:18px;z-index:100;background:#fff;border:1px solid var(--line);box-shadow:0 18px 60px rgba(0,0,0,.22);border-radius:18px;padding:16px;display:none;grid-template-columns:1fr auto;gap:16px;align-items:center}.cookie-banner.show{display:grid}@media(max-width:980px){.hero-inner,.grid-4,.grid-3,.grid-2,.footer-inner,.cookie-banner{grid-template-columns:1fr}.header-inner{align-items:center;flex-direction:column;padding:8px 16px 12px}.logo.aq-logo{width:230px;height:82px}.nav{width:100%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.nav a{text-align:center;font-size:13px;padding:10px 6px;background:#f7fbff;border:1px solid #e2edf7}.nav a.active{background:#e8f1fb}.hero-inner{padding:44px 22px 52px}.hero h1{font-size:clamp(36px,9.5vw,46px);line-height:1.08}.hero p{font-size:18px;line-height:1.55}.kicker{font-size:12px;letter-spacing:.18em}.banner-card{display:none}.section-title{display:block}.cookie-banner{left:12px;right:12px;bottom:12px}}"""

def js():
    return """const AQ26={};AQ26.filterTable=function(id,q){q=(q||'').toLowerCase();document.querySelectorAll('#'+id+' tbody tr').forEach(tr=>{tr.style.display=tr.innerText.toLowerCase().includes(q)?'':'none';});};AQ26.acceptCookies=function(){localStorage.setItem('aq26_cookie_ok','1');const b=document.getElementById('cookie-banner');if(b)b.classList.remove('show');};(function(){function initCookie(){const b=document.getElementById('cookie-banner');if(b&&localStorage.getItem('aq26_cookie_ok')!=='1')b.classList.add('show');}function initSlider(){const slides=[...document.querySelectorAll('.slide')],dots=[...document.querySelectorAll('.dot')];if(!slides.length)return;let i=0;function show(n){i=n%slides.length;slides.forEach((x,j)=>x.classList.toggle('active',j===i));dots.forEach((x,j)=>x.classList.toggle('active',j===i));}dots.forEach((x,j)=>x.addEventListener('click',()=>show(j)));setInterval(()=>show(i+1),5600);}function data(){const el=document.getElementById('aq26-data');if(!el)return null;try{return JSON.parse(el.textContent);}catch(e){return null;}}function labels(w){return w.slice().reverse().map(x=>((x.date_window||{}).end||x.run_ts||'').slice(0,10));}function arr(w,k){return w.slice().reverse().map(x=>Number(x[k]||0));}function plot(){const d=data();if(!d||typeof Plotly==='undefined')return;const w=d.weeks||[],l=labels(w),layout={paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:'#132238'},xaxis:{gridcolor:'#d9e3ec'},yaxis:{gridcolor:'#d9e3ec'},margin:{t:50,l:52,r:24,b:48}};if(document.getElementById('records-chart'))Plotly.newPlot('records-chart',[{x:l,y:arr(w,'source_record_count'),type:'scatter',mode:'lines+markers',name:'Records'},{x:l,y:arr(w,'ok_count'),type:'scatter',mode:'lines+markers',name:'OK'},{x:l,y:arr(w,'warning_count'),type:'scatter',mode:'lines+markers',name:'Warnings'},{x:l,y:arr(w,'error_count'),type:'scatter',mode:'lines+markers',name:'Errors'}],{...layout,title:'Weekly evidence records'},{responsive:true});if(document.getElementById('coverage-chart'))Plotly.newPlot('coverage-chart',[{x:l,y:arr(w,'satellite_product_count'),type:'bar',name:'Satellite products'},{x:l,y:arr(w,'drive_file_count'),type:'bar',name:'Drive files'},{x:l,y:arr(w,'high_priority_filings'),type:'bar',name:'High filings'}],{...layout,barmode:'group',title:'Evidence coverage'},{responsive:true});if(document.getElementById('filings-chart'))Plotly.newPlot('filings-chart',[{x:l,y:arr(w,'high_priority_filings'),type:'bar',name:'High priority'},{x:l,y:arr(w,'medium_priority_filings'),type:'bar',name:'Medium priority'}],{...layout,barmode:'stack',title:'Official filing queue'},{responsive:true});if(document.getElementById('readiness-chart'))Plotly.newPlot('readiness-chart',[{labels:['External ready','Needs validation'],values:[d.summary.external_submission_ready?1:0,d.summary.external_submission_ready?0:1],type:'pie',hole:.58}],{...layout,title:'External submission gate'},{responsive:true});}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{initCookie();initSlider();plot();});else{initCookie();initSlider();plot();}})();"""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output-root",default="outputs"); ap.add_argument("--site-root",default="site_public"); ap.add_argument("--history-weeks",default="104"); ap.add_argument("--history-end-date",default="2026-05-25"); ap.add_argument("--asset-root",default="website/assets"); ap.add_argument("--remote-subdir",default=".")
    a=ap.parse_args(); root=Path(a.output_root); site=Path(a.site_root)
    if site.exists(): shutil.rmtree(site)
    site.mkdir(parents=True,exist_ok=True)
    copy_assets(Path(a.asset_root),site)
    s=summary(root,a.remote_subdir); history.end_date=a.history_end_date; weeks=history(s,existing_history(root),int(a.history_weeks)); dl=copy_downloads(root,site); recs=records(root)
    write_data(site,s,weeks,recs)
    render_index(site,s,weeks,dl); render_archive(site,s,weeks); render_comparisons(site,s,weeks); render_source_records(site,s,recs); render_readiness(site,s); render_methodology(site,s); render_downloads(site,s,dl); render_footer_pages(site,s)
    (site/"robots.txt").write_text("User-agent: *\nAllow: /\n",encoding="utf-8")
    (site/"sitemap.txt").write_text("\n".join([x[0] for x in MAIN_NAV+FOOTER_NAV]+["data/latest_summary.json","data/weekly_index.json"]),encoding="utf-8")
    print(json.dumps({"site_root":str(site),"pages":[x[0] for x in MAIN_NAV+FOOTER_NAV],"history_weeks":len(weeks),"latest_run_ts":s.get("run_ts"),"downloads":len(dl)},indent=2))
if __name__=="__main__": main()
