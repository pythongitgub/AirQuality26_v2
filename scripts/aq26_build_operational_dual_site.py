#!/usr/bin/env python3
"""
AQ26 operational dual-site builder.
Builds a public redacted incinerator observatory and a separate unredacted review site.
Inputs are existing AQ26 evidence outputs already committed by workflows:
  - site_public/data/focus/overlays_v3/facility_overlay_status.csv
  - site_public/data/focus/overlays_v3/incinerator_overlay_summary.json
  - site_public/data/focus/overlays_v3/selected_candidate_overlays_cumulative.csv
  - configs/aq26_incinerator_register/*.csv
The public site is public-safe and avoids raw diagnostics/internal paths.
The unredacted site includes raw review tables and diagnostics for password-protected review.
"""
from __future__ import annotations

import argparse, csv, html, json, math, os, re, shutil, statistics, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PUBLIC_SAFE_NOTICE = (
    "AQ26 is an evidence and provenance observatory. It does not make regulatory determinations, "
    "health advice, legal conclusions, or causal attribution. Candidate overlays are exploratory until reviewed."
)

STATUS_LABELS = {
    "validated_existing_overlay": "Validated overlay",
    "candidate_overlay_needs_review": "Candidate under review",
    "no_candidate_selected_yet": "Fallback discovery needed",
}

STATUS_ORDER = ["validated_existing_overlay", "candidate_overlay_needs_review", "no_candidate_selected_yet"]

HIGH_CONF = "high_confidence_official_candidate"
LOCAL = "local_or_official_candidate_needs_review"
PLAUSIBLE = "plausible_candidate_needs_review"
SUPPORT = "supporting_context_community_sensor"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys = []
        for r in rows:
            for k in r.keys():
                if k not in keys:
                    keys.append(k)
        fieldnames = keys or ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def esc(x: Any) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def slugify(x: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (x or "").lower()).strip("-")
    return s or "item"


def safe_int(x: Any, default: int = 0) -> int:
    try:
        if x in (None, ""):
            return default
        return int(float(str(x).strip()))
    except Exception:
        return default


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x in (None, ""):
            return default
        return float(str(x).strip())
    except Exception:
        return default


def normalise_key(x: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (x or "").lower())


def detect_columns(rows: List[Dict[str, str]]) -> Dict[str, str]:
    if not rows:
        return {}
    cols = list(rows[0].keys())
    lower = {c.lower().strip(): c for c in cols}
    def find(*names: str) -> str:
        for n in names:
            if n in lower:
                return lower[n]
        for c in cols:
            lc = c.lower()
            if any(n in lc for n in names):
                return c
        return ""
    return {
        "facility": find("facility", "incinerator", "site name"),
        "operator": find("operator", "company"),
        "location": find("location", "authority", "county"),
        "postcode": find("postcode", "post code"),
        "lat": find("latitude", "lat"),
        "lon": find("longitude", "lon", "lng"),
        "control": find("control", "control site"),
    }


def load_broad_register(repo: Path) -> List[Dict[str, Any]]:
    candidates = [
        repo / "configs/aq26_incinerator_register/UK_Incinerators_with_Controls_Full_v3.csv",
        repo / "site_public/data/focus/incinerator_facility_register.csv",
        repo / "UK_Incinerators_with_Controls_Full_v3.csv",
    ]
    rows: List[Dict[str, str]] = []
    for p in candidates:
        rows = read_csv(p)
        if rows:
            break
    if not rows:
        return []
    col = detect_columns(rows)
    out = []
    for r in rows:
        fac = r.get(col.get("facility", ""), "") or r.get("facility", "")
        if not fac:
            continue
        out.append({
            "facility": fac,
            "facility_key": normalise_key(fac),
            "operator": r.get(col.get("operator", ""), ""),
            "location": r.get(col.get("location", ""), ""),
            "postcode": r.get(col.get("postcode", ""), ""),
            "latitude": r.get(col.get("lat", ""), ""),
            "longitude": r.get(col.get("lon", ""), ""),
            "control_site": r.get(col.get("control", ""), ""),
        })
    return out


def merge_register_status(register: List[Dict[str, Any]], status_rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    status_by_key = {r.get("facility_key") or normalise_key(r.get("facility", "")): r for r in status_rows}
    merged = []
    seen = set()
    for r in register:
        key = r.get("facility_key") or normalise_key(r.get("facility", ""))
        s = status_by_key.get(key, {})
        merged.append({**r, **{
            "overlay_status": s.get("overlay_status", "no_candidate_selected_yet"),
            "best_candidate_site": s.get("best_candidate_site", ""),
            "best_candidate_score": safe_int(s.get("best_candidate_score"), 0),
            "best_candidate_class": s.get("best_candidate_class", ""),
            "suggested_action": s.get("suggested_action", ""),
        }})
        seen.add(key)
    for key, s in status_by_key.items():
        if key not in seen:
            merged.append({
                "facility": s.get("facility", key),
                "facility_key": key,
                "operator": "",
                "location": "",
                "postcode": "",
                "latitude": "",
                "longitude": "",
                "control_site": "",
                "overlay_status": s.get("overlay_status", "no_candidate_selected_yet"),
                "best_candidate_site": s.get("best_candidate_site", ""),
                "best_candidate_score": safe_int(s.get("best_candidate_score"), 0),
                "best_candidate_class": s.get("best_candidate_class", ""),
                "suggested_action": s.get("suggested_action", ""),
            })
    return merged


def band(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score > 0:
        return "D"
    return "Pending"


def role_from_class(cls: str, site: str = "") -> str:
    s = (cls + " " + site).lower()
    if "community" in s or "airgradient" in s:
        return "supporting_only"
    if "roadside" in s:
        return "roadside_context"
    if "high_confidence" in s:
        return "review_for_validated_overlay"
    if "local_or_official" in s:
        return "local_official_review"
    if "plausible" in s:
        return "regional_context_review"
    return "manual_review"


def compute_summary(facilities: List[Dict[str, Any]], overlay_summary: Dict[str, Any]) -> Dict[str, Any]:
    counts = Counter(f.get("overlay_status", "no_candidate_selected_yet") for f in facilities)
    scores = [safe_int(f.get("best_candidate_score"), 0) for f in facilities if f.get("overlay_status") == "candidate_overlay_needs_review" and safe_int(f.get("best_candidate_score"), 0) > 0]
    high = sum(1 for f in facilities if f.get("best_candidate_class") == HIGH_CONF)
    unresolved = [f["facility"] for f in facilities if f.get("overlay_status") == "no_candidate_selected_yet"]
    return {
        "generated_utc": now_utc(),
        "source_overlay_generated_utc": overlay_summary.get("generated_utc"),
        "total_facilities": len(facilities) or safe_int(overlay_summary.get("broad_facilities"), 46),
        "validated_overlays": counts.get("validated_existing_overlay", safe_int(overlay_summary.get("validated_overlays"), 8)),
        "candidate_overlays": counts.get("candidate_overlay_needs_review", safe_int(overlay_summary.get("candidate_facilities_cumulative"), 35)),
        "unresolved_facilities": counts.get("no_candidate_selected_yet", safe_int(overlay_summary.get("no_candidate_selected_yet"), 3)),
        "high_confidence_candidates": high,
        "median_candidate_score": round(statistics.median(scores), 1) if scores else None,
        "unresolved_names": unresolved,
        "legal_notice": PUBLIC_SAFE_NOTICE,
        "ml_notice": "AI/ML signals are transparent triage scores based on coverage, candidate class, overlay status and review priority. They are not regulatory conclusions.",
    }


def ensure_assets(public: Path, unredacted: Path, repo: Path) -> None:
    for site in [public, unredacted]:
        (site / "assets").mkdir(parents=True, exist_ok=True)
    asset_sources = [repo / "website/assets/air_quality_web.svg", repo / "site_public/assets/air_quality_web.svg", Path("/mnt/data/air_quality_web.svg")]
    logo = next((p for p in asset_sources if p.exists()), None)
    for site in [public, unredacted]:
        if logo:
            shutil.copyfile(logo, site / "assets/air_quality_web.svg")
        fav_src = repo / "website/assets/favicon.svg"
        if fav_src.exists():
            shutil.copyfile(fav_src, site / "assets/favicon.svg")
        else:
            (site / "assets/favicon.svg").write_text("""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 128 128'><rect width='128' height='128' rx='28' fill='#0b1f3a'/><path d='M28 86c18-37 52-47 76-37-22 2-40 18-49 37h49v14H28z' fill='white'/></svg>""", encoding="utf-8")
        # Placeholders for touch icons if no png is present; browsers will still use svg favicon.
        for name in ["apple-touch-icon.png", "android-chrome-192x192.png", "android-chrome-512x512.png"]:
            if not (site / "assets" / name).exists():
                # intentionally omit binary placeholder; manifest points to svg fallback
                pass
        (site / "site.webmanifest").write_text(json.dumps({
            "name": "AQ26 Incinerator Evidence Observatory",
            "short_name": "AQ26",
            "icons": [{"src": "assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"}],
            "theme_color": "#0b1f3a",
            "background_color": "#f4f8fb",
            "display": "standalone",
        }, indent=2), encoding="utf-8")


def css() -> str:
    return r'''
:root{--navy:#071a30;--blue:#0b4d83;--aqua:#00a69c;--green:#177245;--red:#c93232;--gold:#f2b84b;--ink:#142033;--muted:#5b687a;--paper:#f5f8fc;--card:#ffffff;--line:#d9e4ef;--shadow:0 18px 45px rgba(7,26,48,.12);--radius:22px}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);background:linear-gradient(180deg,#f7fbff 0%,#eef5fb 60%,#f7fbff 100%)}a{color:#075e86;text-decoration:none}a:hover{text-decoration:underline}.top-strip{background:linear-gradient(90deg,#071a30,#0b4d83,#006c67);color:#fff;font-size:.82rem;padding:.45rem 1rem}.top-strip .wrap,.header .wrap,.main,.footer .wrap{max-width:1240px;margin:auto}.top-strip .wrap{display:flex;gap:1rem;justify-content:space-between;align-items:center}.header{background:rgba(255,255,255,.96);backdrop-filter:blur(14px);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10}.header .wrap{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.85rem 1rem}.brand{display:flex;align-items:center;gap:.9rem;min-width:0}.brand img{height:64px;width:auto;display:block}.brand small{display:block;color:var(--muted);font-weight:700;letter-spacing:.06em;text-transform:uppercase}.nav{display:flex;gap:.45rem;flex-wrap:wrap;justify-content:flex-end}.nav a{padding:.65rem .85rem;border-radius:999px;color:#10233c;font-weight:750;background:#f2f6fb;border:1px solid #dfe9f4}.nav a:hover{background:#e7f4ff;text-decoration:none}.hamb{display:none;border:1px solid var(--line);background:#fff;border-radius:14px;padding:.65rem .8rem;font-weight:900}.main{padding:1.2rem 1rem 3rem}.hero{position:relative;overflow:hidden;border-radius:32px;margin:1.2rem 0 1rem;color:#fff;background:linear-gradient(120deg,#06172b 0%,#0a4a7d 45%,#008577 78%,#c43b3b 125%);box-shadow:var(--shadow);min-height:390px}.hero:before{content:"";position:absolute;inset:-45%;background:radial-gradient(circle at 20% 30%,rgba(255,255,255,.22),transparent 20%),radial-gradient(circle at 74% 25%,rgba(0,255,220,.17),transparent 22%),radial-gradient(circle at 75% 85%,rgba(255,210,80,.24),transparent 20%);animation:floatBg 18s ease-in-out infinite alternate}.hero:after{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.08) 1px,transparent 1px);background-size:48px 48px;mask-image:linear-gradient(180deg,black,transparent 92%)}@keyframes floatBg{from{transform:translate3d(-2%,1%,0) rotate(0)}to{transform:translate3d(4%,-3%,0) rotate(7deg)}}.hero-inner{position:relative;z-index:1;padding:3rem 2.2rem;max-width:900px}.eyebrow{letter-spacing:.2em;text-transform:uppercase;font-weight:900;font-size:.8rem;color:#bffcf5}.hero h1{font-size:clamp(2.2rem,6vw,5.3rem);line-height:.93;margin:.45rem 0 .9rem}.hero p{font-size:1.22rem;line-height:1.6;max-width:760px;color:#eefbff}.actions{display:flex;gap:.8rem;flex-wrap:wrap;margin-top:1.3rem}.btn{display:inline-flex;align-items:center;gap:.45rem;border-radius:999px;padding:.86rem 1.1rem;font-weight:900;border:1px solid rgba(255,255,255,.25);background:#fff;color:#0b1f3a;box-shadow:0 10px 30px rgba(0,0,0,.12)}.btn.alt{background:rgba(255,255,255,.12);color:#fff}.btn:hover{text-decoration:none;transform:translateY(-1px)}.ticker{overflow:hidden;background:#081a2d;color:white;border-radius:18px;margin:1rem 0;box-shadow:var(--shadow);white-space:nowrap}.ticker-track{display:inline-block;padding:.9rem 0;animation:ticker 38s linear infinite}.ticker span{display:inline-block;margin:0 2rem;color:#e9fbff;font-weight:850}.ticker b{color:#f9d16b}@keyframes ticker{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}.grid{display:grid;gap:1rem}.stats{grid-template-columns:repeat(4,minmax(0,1fr));margin:1rem 0}.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:1.2rem;box-shadow:var(--shadow)}.card h2,.card h3{margin:.2rem 0 .6rem;color:#0d2038}.stat .label{font-size:.77rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:900}.stat .value{font-size:2.25rem;font-weight:950;margin:.35rem 0;color:#09213a}.stat .note{color:var(--muted);font-size:.92rem}.section{margin:1.4rem 0}.section-title{display:flex;align-items:flex-end;justify-content:space-between;gap:1rem;margin:1.2rem 0 .8rem}.section-title h2{font-size:2rem;margin:0;color:#091b31}.pill{display:inline-flex;border-radius:999px;padding:.35rem .65rem;background:#edf7ff;border:1px solid #cde5fa;font-weight:850;font-size:.8rem;color:#0d4068}.pill.validated{background:#e7f8ee;border-color:#bfe8cc;color:#116238}.pill.candidate{background:#fff4d8;border-color:#f3d27d;color:#7b5200}.pill.missing{background:#ffecec;border-color:#f5b6b6;color:#9b2222}.table-wrap{overflow:auto;border-radius:18px;border:1px solid var(--line);background:#fff}table{width:100%;border-collapse:collapse;font-size:.92rem}th,td{padding:.75rem .85rem;border-bottom:1px solid #edf2f7;text-align:left;vertical-align:top}th{background:#f5f9fd;color:#21364f;font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;position:sticky;top:0}tr:hover td{background:#fbfdff}.charts{grid-template-columns:repeat(2,minmax(0,1fr))}.chart-card{min-height:360px}.chart-card canvas{width:100%;max-height:285px}.insights{grid-template-columns:2fr 1fr}.insight-list{display:grid;gap:.75rem}.insight{border-left:5px solid var(--aqua);background:#f7fcff;padding:.85rem;border-radius:14px}.insight.warn{border-left-color:var(--gold);background:#fffaf0}.insight.good{border-left-color:var(--green);background:#f0fbf4}.legal{background:#fff7ec;border:1px solid #f1d3a5;border-radius:18px;padding:1rem;color:#4b3618}.footer{background:#071a30;color:#dbe9f6;margin-top:2rem}.footer .wrap{padding:2rem 1rem}.footer a{color:#fff}.watermark{position:fixed;right:2vw;bottom:2vh;opacity:.035;pointer-events:none;z-index:0}.watermark img{width:360px}.filters{display:flex;gap:.7rem;flex-wrap:wrap;margin:.7rem 0}.filters input,.filters select{border:1px solid var(--line);border-radius:14px;padding:.75rem .85rem;background:#fff;min-width:220px}.map{min-height:340px;background:radial-gradient(circle at 40% 35%,rgba(0,166,156,.15),transparent 25%),linear-gradient(135deg,#eef8ff,#fff);border-radius:22px;border:1px solid var(--line);position:relative;overflow:hidden}.map .dot{position:absolute;width:12px;height:12px;border-radius:50%;background:var(--red);box-shadow:0 0 0 8px rgba(201,50,50,.13);transform:translate(-50%,-50%)}.map .dot.validated{background:var(--green);box-shadow:0 0 0 8px rgba(23,114,69,.13)}.map .dot.candidate{background:var(--gold);box-shadow:0 0 0 8px rgba(242,184,75,.18)}@media(max-width:860px){.brand img{height:48px}.hamb{display:block}.nav{display:none;position:absolute;left:1rem;right:1rem;top:82px;background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:.8rem;flex-direction:column}.nav.open{display:flex}.stats,.charts,.insights{grid-template-columns:1fr}.hero-inner{padding:2rem 1.2rem}.top-strip .wrap{display:block}.section-title{display:block}.watermark{display:none}}
'''


def js() -> str:
    return r'''
(function(){
  const $=(s,root=document)=>root.querySelector(s); const $$=(s,root=document)=>Array.from(root.querySelectorAll(s));
  const nav=$('#nav'); const btn=$('#hamb'); if(btn&&nav){btn.addEventListener('click',()=>nav.classList.toggle('open'));}
  function tryCharts(){ if(!window.Chart || !window.AQ26_DATA) return; const d=window.AQ26_DATA; 
    const counts=d.counts||{}; const dough=$('#chartStatus'); if(dough){new Chart(dough,{type:'doughnut',data:{labels:['Validated','Candidate review','Fallback needed'],datasets:[{data:[counts.validated||0,counts.candidate||0,counts.missing||0]}]},options:{plugins:{legend:{position:'bottom'}}}});} 
    const score=$('#chartScores'); if(score){const bands=d.scoreBands||{};new Chart(score,{type:'bar',data:{labels:Object.keys(bands),datasets:[{label:'Facilities',data:Object.values(bands)}]},options:{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0}}}}});}
    const classChart=$('#chartClasses'); if(classChart){const c=d.classCounts||{};new Chart(classChart,{type:'bar',data:{labels:Object.keys(c),datasets:[{label:'Candidates',data:Object.values(c)}]},options:{indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,ticks:{precision:0}}}}});}
    const progress=$('#chartProgress'); if(progress){const p=[counts.validated||0,(counts.validated||0)+(counts.candidate||0),d.total||0];new Chart(progress,{type:'line',data:{labels:['Validated','Overlay path','Register'],datasets:[{label:'Coverage progression',data:p,tension:.35,fill:false}]},options:{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0}}}}});}
  }
  function filterTable(){const q=($('#q')?.value||'').toLowerCase();const st=$('#statusFilter')?.value||'';$$('[data-facility-row]').forEach(tr=>{const text=tr.innerText.toLowerCase();const okq=!q||text.includes(q);const oks=!st||tr.dataset.status===st;tr.style.display=(okq&&oks)?'':'none';});}
  $('#q')?.addEventListener('input',filterTable); $('#statusFilter')?.addEventListener('change',filterTable);
  function aiPanel(){const el=$('#aiNarrative'); if(!el||!window.AQ26_DATA) return; const d=window.AQ26_DATA, c=d.counts||{}; const pct=Math.round(((c.validated||0)+(c.candidate||0))*100/(d.total||1)); const unresolved=(c.missing||0); let risk='stable'; if(unresolved>8) risk='needs discovery'; else if(unresolved>0) risk='near-complete'; el.innerHTML='<b>AI-assisted triage:</b> The register currently has an overlay path for '+pct+'% of facilities. Status: <b>'+risk+'</b>. Candidate overlays remain review-only until station role, geography and provenance are confirmed.'; }
  tryCharts(); aiPanel();
})();
'''


def page_template(title: str, body: str, active: str = "", unredacted: bool = False, data_js: Optional[Dict[str, Any]] = None) -> str:
    nav_items = [
        ("index.html", "Home"), ("incinerators.html", "Incinerators"), ("newhaven.html", "Newhaven"),
        ("overlays.html", "Overlays"), ("comparisons.html", "Charts"), ("methodology.html", "Methodology"), ("downloads.html", "Downloads"),
    ]
    if unredacted:
        nav_items = [("index.html", "Dashboard"), ("evidence.html", "Evidence"), ("candidates.html", "Candidates"), ("diagnostics.html", "Diagnostics"), ("../index.html", "Public site")]
    nav = "".join(f"<a href='{esc(h)}' class='{'active' if active==h else ''}'>{esc(t)}</a>" for h,t in nav_items)
    data_block = f"<script>window.AQ26_DATA={json.dumps(data_js, ensure_ascii=False)};</script>" if data_js is not None else ""
    noindex = "<meta name='robots' content='noindex,nofollow'>" if unredacted else ""
    area = "Unredacted internal review" if unredacted else "Public redacted observatory"
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>{noindex}<title>{esc(title)} · AQ26</title><link rel='icon' href='assets/favicon.svg?v=operational'><link rel='manifest' href='site.webmanifest'><link rel='stylesheet' href='assets/aq26_operational.css?v=operational'><script src='https://cdn.jsdelivr.net/npm/chart.js'></script></head><body><div class='top-strip'><div class='wrap'><span>Evidence-led incinerator and air-quality intelligence</span><span>{esc(area)} · Generated {esc(now_utc())}</span></div></div><header class='header'><div class='wrap'><a class='brand' href='index.html' aria-label='AQ26 home'><img src='assets/air_quality_web.svg' alt='SCC Nexus Air Quality Report'><span><small>SCC Nexus · AQ26</small></span></a><button id='hamb' class='hamb'>Menu ☰</button><nav id='nav' class='nav'>{nav}</nav></div></header><main class='main'>{body}</main><div class='watermark'><img src='assets/air_quality_web.svg' alt=''></div><footer class='footer'><div class='wrap'><b>AQ26 WeeklyV2</b><p>{esc(PUBLIC_SAFE_NOTICE)}</p><p><a href='methodology.html'>Methodology</a> · <a href='downloads.html'>Downloads</a> · <a href='legal.html'>Legal and safety notice</a></p></div></footer>{data_block}<script src='assets/aq26_operational.js?v=operational'></script></body></html>"""


def hero(title: str, subtitle: str, eyebrow: str = "AQ26 incinerator observatory", actions: str = "") -> str:
    return f"""<section class='hero'><div class='hero-inner'><div class='eyebrow'>{esc(eyebrow)}</div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p><div class='actions'>{actions}</div></div></section>"""


def ticker(summary: Dict[str, Any]) -> str:
    items = [
        f"<b>{summary['total_facilities']}</b> facilities in register",
        f"<b>{summary['validated_overlays']}</b> validated overlays",
        f"<b>{summary['candidate_overlays']}</b> candidate overlays under review",
        f"<b>{summary['unresolved_facilities']}</b> fallback discovery cases",
        "Newhaven remains the high-confidence reference case",
        "AI/ML triage is exploratory and review-only",
    ]
    return "<div class='ticker'><div class='ticker-track'>" + "".join(f"<span>{x}</span>" for x in items*2) + "</div></div>"


def stats_cards(summary: Dict[str, Any]) -> str:
    cards = [
        ("Facilities", summary["total_facilities"], "England/Wales incinerator and EfW register"),
        ("Validated overlays", summary["validated_overlays"], "Confirmed baseline monitoring overlays"),
        ("Candidates", summary["candidate_overlays"], "Monitoring overlays under review"),
        ("Fallback cases", summary["unresolved_facilities"], "Need non-OpenAQ/manual discovery"),
    ]
    return "<section class='grid stats'>" + "".join(f"<div class='card stat'><div class='label'>{esc(l)}</div><div class='value'>{esc(v)}</div><div class='note'>{esc(n)}</div></div>" for l,v,n in cards) + "</section>"


def status_pill(status: str) -> str:
    cls = "validated" if status == "validated_existing_overlay" else "candidate" if status == "candidate_overlay_needs_review" else "missing"
    return f"<span class='pill {cls}'>{esc(STATUS_LABELS.get(status,status))}</span>"


def facility_table(facilities: List[Dict[str, Any]], public: bool = True, limit: Optional[int] = None) -> str:
    rows = facilities[:limit] if limit else facilities
    trs = []
    for f in rows:
        status = f.get("overlay_status", "")
        score = safe_int(f.get("best_candidate_score"), 0)
        trs.append(f"""<tr data-facility-row data-status='{esc(status)}'><td><b>{esc(f.get('facility'))}</b><br><small>{esc(f.get('location') or f.get('postcode') or '')}</small></td><td>{status_pill(status)}</td><td>{esc(f.get('best_candidate_site') or '—')}</td><td>{esc(score if score else '—')}</td><td>{esc(f.get('best_candidate_class') or '—')}</td><td>{esc(role_from_class(f.get('best_candidate_class',''), f.get('best_candidate_site','')))}</td></tr>""")
    return """<div class='filters'><input id='q' placeholder='Search facilities, stations or status'><select id='statusFilter'><option value=''>All statuses</option><option value='validated_existing_overlay'>Validated</option><option value='candidate_overlay_needs_review'>Candidate review</option><option value='no_candidate_selected_yet'>Fallback needed</option></select></div><div class='table-wrap'><table><thead><tr><th>Facility</th><th>Status</th><th>Best overlay / candidate</th><th>Score</th><th>Evidence class</th><th>Suggested role</th></tr></thead><tbody>""" + "".join(trs) + "</tbody></table></div>"


def chart_data(facilities: List[Dict[str, Any]], summary: Dict[str, Any]) -> Dict[str, Any]:
    counts = {
        "validated": sum(1 for f in facilities if f.get("overlay_status") == "validated_existing_overlay"),
        "candidate": sum(1 for f in facilities if f.get("overlay_status") == "candidate_overlay_needs_review"),
        "missing": sum(1 for f in facilities if f.get("overlay_status") == "no_candidate_selected_yet"),
    }
    bands = Counter(band(safe_int(f.get("best_candidate_score"), 0)) for f in facilities if f.get("overlay_status") == "candidate_overlay_needs_review")
    class_counts = Counter(f.get("best_candidate_class") or "unknown" for f in facilities if f.get("overlay_status") == "candidate_overlay_needs_review")
    return {"total": summary["total_facilities"], "counts": counts, "scoreBands": dict(bands), "classCounts": dict(class_counts)}


def map_panel(facilities: List[Dict[str, Any]]) -> str:
    dots = []
    # Approximate normalisation over UK bbox; non-critical visual, not analytic.
    minlat, maxlat, minlon, maxlon = 49.8, 55.9, -6.0, 2.0
    for f in facilities:
        lat, lon = safe_float(f.get("latitude"), None), safe_float(f.get("longitude"), None)
        if lat is None or lon is None or lat == 0 or lon == 0:
            continue
        x = max(4, min(96, (lon-minlon)/(maxlon-minlon)*100))
        y = max(4, min(96, (maxlat-lat)/(maxlat-minlat)*100))
        st = f.get("overlay_status")
        cls = "validated" if st == "validated_existing_overlay" else "candidate" if st == "candidate_overlay_needs_review" else ""
        dots.append(f"<span class='dot {cls}' style='left:{x:.1f}%;top:{y:.1f}%' title='{esc(f.get('facility'))}'></span>")
    return "<div class='map'>" + "".join(dots) + "</div>"


def build_public(public: Path, facilities: List[Dict[str, Any]], summary: Dict[str, Any], candidates: List[Dict[str, str]]) -> None:
    data = chart_data(facilities, summary)
    actions = "<a class='btn' href='incinerators.html'>Explore facility register</a><a class='btn alt' href='newhaven.html'>Open Newhaven case study</a>"
    body = hero("AQ26 Environmental Intelligence Observatory", "A redacted, public-safe view of England and Wales incinerator evidence, monitoring overlays, control-site context and transparent AI-assisted review signals.", actions=actions)
    body += ticker(summary) + stats_cards(summary)
    body += """<section class='grid insights section'><div class='card'><h2>What this platform now shows</h2><p>AQ26 is now facility-led. Each incinerator is linked to validated or candidate monitoring overlays, with candidate status kept separate from validated status. Public pages show redacted summaries; the protected site retains raw diagnostics and review files.</p><div id='aiNarrative' class='insight good'></div></div><div class='card legal'><h3>Legally safe wording</h3><p>No regulatory determination, causal attribution, breach finding or health advice is made. Candidate monitoring overlays remain exploratory until reviewed.</p></div></section>"""
    body += "<section class='grid charts section'><div class='card chart-card'><h3>Overlay coverage</h3><canvas id='chartStatus'></canvas></div><div class='card chart-card'><h3>Candidate score bands</h3><canvas id='chartScores'></canvas></div></section>"
    body += "<section class='section'><div class='section-title'><h2>Facility overlay status</h2><span class='pill'>Searchable public table</span></div>" + facility_table(facilities, public=True, limit=18) + "<p><a class='btn' href='incinerators.html'>View full register</a></p></section>"
    public.joinpath("index.html").write_text(page_template("AQ26 Environmental Intelligence Observatory", body, "index.html", False, data), encoding="utf-8")

    body = hero("Incinerator register", "A national facility-led register with overlay status, review class and public-safe monitoring context.", "England and Wales register", "<a class='btn' href='overlays.html'>Overlay review</a><a class='btn alt' href='comparisons.html'>View charts</a>")
    body += ticker(summary) + stats_cards(summary)
    body += "<section class='section'><div class='section-title'><h2>All facilities</h2><span class='pill'>Validated, candidate, or fallback</span></div>" + facility_table(facilities) + "</section>"
    public.joinpath("incinerators.html").write_text(page_template("Incinerator register", body, "incinerators.html", False, data), encoding="utf-8")

    newhaven = next((f for f in facilities if "newhaven" in f.get("facility_key", "")), None)
    nh_text = "Newhaven ERF remains the high-confidence reference case with a validated overlay. It is used as the model for how future facility pages should separate official evidence, monitoring context, candidate status and public limitations."
    body = hero("Newhaven focus", nh_text, "Gold-standard reference case", "<a class='btn' href='overlays.html'>Compare overlay status</a><a class='btn alt' href='methodology.html'>Read method</a>")
    body += ticker(summary)
    if newhaven:
        body += f"<section class='grid stats'><div class='card stat'><div class='label'>Facility</div><div class='value' style='font-size:1.5rem'>{esc(newhaven.get('facility'))}</div><div class='note'>{esc(newhaven.get('location') or '')}</div></div><div class='card stat'><div class='label'>Overlay status</div><div class='value' style='font-size:1.3rem'>{status_pill(newhaven.get('overlay_status'))}</div><div class='note'>Validated baseline overlay retained</div></div><div class='card stat'><div class='label'>Control context</div><div class='value' style='font-size:1.2rem'>{esc(newhaven.get('control_site') or 'Control site retained in register')}</div><div class='note'>Control/receptor context requires public-safe explanation</div></div></section>"
    body += "<section class='card section'><h2>Public-safe interpretation</h2><p>Newhaven is not used to claim causation. It is used to demonstrate the evidence workflow: facility register, monitoring overlay, source provenance, pollutant context, and transparent limitations.</p></section>"
    public.joinpath("newhaven.html").write_text(page_template("Newhaven focus", body, "newhaven.html", False, data), encoding="utf-8")

    body = hero("Overlay status", "Validated overlays, candidate monitoring sites and remaining fallback-discovery cases across the incinerator register.", "Monitoring overlay intelligence", "<a class='btn' href='incinerators.html'>View register</a><a class='btn alt' href='downloads.html'>Download public data</a>")
    body += ticker(summary) + "<section class='grid charts section'><div class='card chart-card'><h3>Validated vs candidate vs unresolved</h3><canvas id='chartStatus'></canvas></div><div class='card chart-card'><h3>Candidate classes</h3><canvas id='chartClasses'></canvas></div></section>"
    body += "<section class='section'><div class='section-title'><h2>Overlay table</h2><span class='pill'>Candidate does not mean validated</span></div>" + facility_table(facilities) + "</section>"
    public.joinpath("overlays.html").write_text(page_template("Overlay status", body, "overlays.html", False, data), encoding="utf-8")

    body = hero("Interactive comparison charts", "Public-safe charts generated from the incinerator overlay status, candidate score bands and review classes.", "Charts and evidence signals", "<a class='btn' href='overlays.html'>Overlay status</a><a class='btn alt' href='downloads.html'>Downloads</a>")
    body += "<section class='grid charts section'><div class='card chart-card'><h3>Coverage progression</h3><canvas id='chartProgress'></canvas></div><div class='card chart-card'><h3>Candidate score bands</h3><canvas id='chartScores'></canvas></div><div class='card chart-card'><h3>Overlay status</h3><canvas id='chartStatus'></canvas></div><div class='card chart-card'><h3>Candidate classes</h3><canvas id='chartClasses'></canvas></div></section>"
    public.joinpath("comparisons.html").write_text(page_template("Comparison charts", body, "comparisons.html", False, data), encoding="utf-8")

    method = hero("Methodology", "How AQ26 separates validated evidence, candidate overlays, supporting context and unredacted review material.", "Scientific and legal caution")
    method += """<section class='grid insights section'><div class='card'><h2>Evidence classes</h2><p><b>Validated overlay</b>: retained from the validated DEFRA/AURN overlay register. <b>Candidate under review</b>: monitoring candidate discovered by evidence workflow and not yet promoted. <b>Fallback needed</b>: OpenAQ discovery did not produce a suitable candidate; manual/alternative-source review is required.</p></div><div class='card'><h2>AI/ML use</h2><p>AI/ML features are transparent triage aids: score bands, candidate classes and review priority. They do not make legal, health, causal or regulatory findings.</p></div></section><section class='card legal'><h2>Legal and public safety notice</h2><p>All content is informational, provisional and evidence-led. The site avoids claims of breach, causation or health impact. Unreviewed data stays in the protected review site.</p></section>"""
    public.joinpath("methodology.html").write_text(page_template("Methodology", method, "methodology.html", False, data), encoding="utf-8")

    downloads = hero("Downloads", "Public redacted downloads and chart-ready data. Full diagnostics are restricted to the unredacted review area.", "Redacted data access")
    downloads += """<section class='grid stats'><div class='card'><h3>Public overlay summary</h3><p><a class='btn' href='data/focus/operational/public_overlay_summary.json'>Open JSON</a></p></div><div class='card'><h3>Facility status CSV</h3><p><a class='btn' href='data/focus/operational/public_facility_overlay_status.csv'>Download CSV</a></p></div><div class='card'><h3>Latest evidence bundle</h3><p><a class='btn' href='downloads/latest-evidence.zip'>Download if available</a></p></div></section>"""
    public.joinpath("downloads.html").write_text(page_template("Downloads", downloads, "downloads.html", False, data), encoding="utf-8")

    legal = hero("Legal and safety notice", PUBLIC_SAFE_NOTICE, "Public safety") + "<section class='card'><h2>Limitations</h2><p>Monitoring overlays can be influenced by distance, station type, road traffic, local sources, meteorology and data availability. Candidate status is not validation.</p></section>"
    public.joinpath("legal.html").write_text(page_template("Legal notice", legal, "legal.html", False, data), encoding="utf-8")
    # aliases
    for alias, target in {"historical-comparisons.html":"comparisons.html", "incinerator-overlays.html":"overlays.html", "source-records.html":"incinerators.html", "readiness.html":"overlays.html", "archive.html":"incinerators.html", "about.html":"methodology.html", "privacy.html":"legal.html", "cookies.html":"legal.html", "accessibility.html":"legal.html", "terms.html":"legal.html", "contact.html":"legal.html"}.items():
        public.joinpath(alias).write_text(f"<!doctype html><meta charset='utf-8'><meta http-equiv='refresh' content='0; url={target}'><link rel='canonical' href='{target}'><a href='{target}'>Continue to {target}</a>", encoding="utf-8")


def build_unredacted(unredacted: Path, facilities: List[Dict[str, Any]], summary: Dict[str, Any], candidates: List[Dict[str, str]], diagnostics: List[Dict[str, str]], errors: List[Dict[str, str]]) -> None:
    data = chart_data(facilities, summary)
    body = hero("AQ26 Unredacted Evidence Review", "Password-protected QA area for candidate overlays, diagnostics, review decisions and provenance. Do not share externally.", "Restricted internal review", "<a class='btn' href='candidates.html'>Review candidates</a><a class='btn alt' href='../index.html'>Public site</a>")
    body += ticker(summary) + stats_cards(summary)
    body += "<section class='grid charts section'><div class='card chart-card'><h3>Overlay status</h3><canvas id='chartStatus'></canvas></div><div class='card chart-card'><h3>Candidate classes</h3><canvas id='chartClasses'></canvas></div></section>"
    body += "<section class='section'><div class='section-title'><h2>Full status table</h2><span class='pill'>Unredacted review</span></div>" + facility_table(facilities, public=False) + "</section>"
    unredacted.joinpath("index.html").write_text(page_template("Unredacted review", body, "index.html", True, data), encoding="utf-8")

    # candidates table
    rows = []
    for c in candidates[:2000]:
        fac = c.get("facility") or c.get("facility_name") or ""
        site = c.get("candidate_site") or c.get("candidate_monitoring_site") or c.get("location_name") or c.get("name") or ""
        score = c.get("score") or c.get("candidate_score") or c.get("best_score") or ""
        cls = c.get("candidate_class") or ""
        dist = c.get("distance_km") or c.get("facility_distance_km") or c.get("distance") or ""
        pol = c.get("pollutants") or c.get("parameters") or ""
        rows.append(f"<tr><td>{esc(fac)}</td><td>{esc(site)}</td><td>{esc(score)}</td><td>{esc(dist)}</td><td>{esc(pol)}</td><td>{esc(cls)}</td><td>{esc(role_from_class(cls,site))}</td></tr>")
    body = hero("Candidate overlay review", "Review table for promotion decisions. Strong candidates still require human review before they become validated overlays.", "Review queue")
    body += "<section class='table-wrap'><table><thead><tr><th>Facility</th><th>Candidate site</th><th>Score</th><th>Distance</th><th>Pollutants</th><th>Class</th><th>Recommended role</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></section>"
    unredacted.joinpath("candidates.html").write_text(page_template("Candidate review", body, "candidates.html", True, data), encoding="utf-8")

    # diagnostics summary
    diag_rows = "".join(f"<tr><td>{esc(d.get('method') or d.get('query_method') or '')}</td><td>{esc(d.get('http_status') or d.get('status') or '')}</td><td>{esc(d.get('facility') or '')}</td><td>{esc(d.get('url') or '')[:250]}</td></tr>" for d in diagnostics[:1000])
    body = hero("Diagnostics", "OpenAQ/API diagnostics, errors and internal review metadata. Restricted from public pages.", "Internal provenance")
    body += f"<section class='grid stats'><div class='card stat'><div class='label'>Diagnostics rows</div><div class='value'>{len(diagnostics)}</div></div><div class='card stat'><div class='label'>Error rows</div><div class='value'>{len(errors)}</div></div></section>"
    body += "<section class='table-wrap'><table><thead><tr><th>Method</th><th>Status</th><th>Facility</th><th>URL</th></tr></thead><tbody>" + diag_rows + "</tbody></table></section>"
    unredacted.joinpath("diagnostics.html").write_text(page_template("Diagnostics", body, "diagnostics.html", True, data), encoding="utf-8")

    evidence = hero("Evidence index", "Links to unredacted generated files. Keep this area password protected.", "Unredacted output catalogue")
    evidence += "<section class='grid stats'><div class='card'><h3>Overlay data</h3><p><a class='btn' href='../data/focus/overlays_v3/facility_overlay_status.csv'>Facility status</a></p><p><a class='btn' href='../data/focus/overlays_v3/selected_candidate_overlays_cumulative.csv'>Selected candidates</a></p><p><a class='btn' href='../data/focus/overlays_v3/openaq_query_diagnostics.csv'>OpenAQ diagnostics</a></p></div><div class='card'><h3>Review outputs</h3><p><a class='btn' href='data/review/UK_Incinerator_Overlay_Candidate_Review.csv'>Candidate review CSV</a></p></div></section>"
    unredacted.joinpath("evidence.html").write_text(page_template("Evidence index", evidence, "evidence.html", True, data), encoding="utf-8")


def build_review_csv(repo: Path, unredacted: Path, facilities: List[Dict[str, Any]], candidates: List[Dict[str, str]]) -> None:
    review_rows = []
    by_fac = defaultdict(list)
    for c in candidates:
        fac = c.get("facility") or c.get("facility_name") or ""
        by_fac[normalise_key(fac)].append(c)
    for f in facilities:
        if f.get("overlay_status") != "candidate_overlay_needs_review":
            continue
        key = f.get("facility_key") or normalise_key(f.get("facility", ""))
        site = f.get("best_candidate_site", "")
        cls = f.get("best_candidate_class", "")
        review_rows.append({
            "facility": f.get("facility", ""),
            "candidate_monitoring_site": site,
            "score": f.get("best_candidate_score", ""),
            "candidate_class": cls,
            "recommended_role": role_from_class(cls, site),
            "review_decision": "pending_review",
            "review_notes": "Check station type, geography, pollutant coverage, provider and suitability before public validation.",
            "promote_to_validated": "no",
        })
    out1 = repo / "configs/aq26_incinerator_register/UK_Incinerator_Overlay_Candidate_Review.csv"
    out2 = unredacted / "data/review/UK_Incinerator_Overlay_Candidate_Review.csv"
    fields = ["facility","candidate_monitoring_site","score","candidate_class","recommended_role","review_decision","review_notes","promote_to_validated"]
    write_csv(out1, review_rows, fields)
    write_csv(out2, review_rows, fields)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--public-site", default="site_public")
    ap.add_argument("--unredacted-site", default="site_unredacted")
    ap.add_argument("--max-public-rows", type=int, default=200)
    args = ap.parse_args()
    repo = Path(args.repo_root).resolve()
    public = repo / args.public_site
    unredacted = repo / args.unredacted_site
    public.mkdir(parents=True, exist_ok=True)
    unredacted.mkdir(parents=True, exist_ok=True)
    ensure_assets(public, unredacted, repo)
    for site in [public, unredacted]:
        (site / "assets/aq26_operational.css").write_text(css(), encoding="utf-8")
        (site / "assets/aq26_operational.js").write_text(js(), encoding="utf-8")
    overlay_root = public / "data/focus/overlays_v3"
    status_rows = read_csv(overlay_root / "facility_overlay_status.csv") or read_csv(overlay_root / "facility_overlay_status_cumulative.csv")
    register = load_broad_register(repo)
    facilities = merge_register_status(register, status_rows) if register else [dict(r, best_candidate_score=safe_int(r.get("best_candidate_score"),0)) for r in status_rows]
    # stable ordering: validated, high candidates, candidates, unresolved, alpha within groups
    st_rank = {"validated_existing_overlay":0,"candidate_overlay_needs_review":1,"no_candidate_selected_yet":2}
    facilities.sort(key=lambda f: (st_rank.get(f.get("overlay_status"), 9), -safe_int(f.get("best_candidate_score"), 0), f.get("facility", "")))
    overlay_summary = read_json(overlay_root / "incinerator_overlay_summary.json", {}) or {}
    summary = compute_summary(facilities, overlay_summary)
    candidates = read_csv(overlay_root / "selected_candidate_overlays_cumulative.csv") or read_csv(overlay_root / "selected_candidate_overlays_needing_review.csv")
    diagnostics = read_csv(overlay_root / "openaq_query_diagnostics.csv")
    errors = read_csv(overlay_root / "overlay_discovery_errors.json")
    op_root = public / "data/focus/operational"
    write_json(op_root / "public_overlay_summary.json", summary)
    public_rows = []
    for f in facilities:
        public_rows.append({k:f.get(k,"") for k in ["facility","overlay_status","best_candidate_site","best_candidate_score","best_candidate_class","suggested_action"]})
    write_csv(op_root / "public_facility_overlay_status.csv", public_rows)
    write_json(op_root / "chart_data.json", chart_data(facilities, summary))
    build_review_csv(repo, unredacted, facilities, candidates)
    build_public(public, facilities, summary, candidates)
    build_unredacted(unredacted, facilities, summary, candidates, diagnostics, errors)
    # robots and htaccess for unredacted
    public.joinpath("robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    unredacted.joinpath("robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    unredacted.joinpath(".htaccess").write_text("AuthType Basic\nAuthName \"AQ26 Unredacted Review\"\nAuthUserFile .htpasswd\nRequire valid-user\nOptions -Indexes\n", encoding="utf-8")
    write_json(public / "data/focus/operational/build_summary.json", {"ok": True, "summary": summary, "public_site": str(public), "unredacted_site": str(unredacted)})
    print(json.dumps({"ok": True, **summary}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
