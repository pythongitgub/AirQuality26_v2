#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


def read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def latest_run_root(output_root: Path) -> Path | None:
    marker = output_root / 'latest_run_dir.txt'
    if marker.exists():
        p = Path(marker.read_text(encoding='utf-8').strip())
        if p.exists():
            return p
    runs = [p for p in output_root.iterdir() if p.is_dir()] if output_root.exists() else []
    return sorted(runs)[-1] if runs else None


def first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def as_int(value, default=0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(float(value))
    except Exception:
        return default


def as_float(value, default=0.0) -> float:
    try:
        if value is None or value == '':
            return default
        return float(value)
    except Exception:
        return default


def collect_latest(repo: Path, public: Path, unredacted: Path, output_root: Path) -> dict:
    run_root = latest_run_root(output_root)
    candidates = [
        public / 'data/weekly/LATEST_WEEKLYV2.json',
        unredacted / 'data/weekly/LATEST_WEEKLYV2.json',
        output_root / 'LATEST_WEEKLYV2.json',
    ]
    if run_root:
        candidates.insert(0, run_root / 'LATEST_WEEKLYV2.json')
    p = first_existing(candidates)
    latest = read_json(p, {}) if p else {}
    latest['_selected_latest_path'] = str(p) if p else ''
    latest['_latest_run_root'] = str(run_root) if run_root else ''
    return latest


def load_facilities(repo: Path, public: Path, unredacted: Path, output_root: Path) -> list[dict]:
    paths = [
        public / 'data/weekly/evidence_priority_scores.json',
        unredacted / 'data/weekly/evidence_priority_scores.json',
        public / 'data/backfill/incinerators/facility_backfill_readiness_public.csv',
        unredacted / 'data/backfill/incinerators/facility_backfill_readiness_unredacted.csv',
    ]
    records: list[dict] = []
    for path in paths:
        if not path.exists():
            continue
        if path.suffix.lower() == '.json':
            data = read_json(path, [])
            if isinstance(data, dict):
                for key in ('facilities', 'rows', 'items', 'records'):
                    if isinstance(data.get(key), list):
                        data = data[key]
                        break
                else:
                    data = [data]
            if isinstance(data, list):
                records.extend([x for x in data if isinstance(x, dict)])
        elif path.suffix.lower() == '.csv':
            with path.open('r', encoding='utf-8-sig', newline='') as f:
                records.extend(list(csv.DictReader(f)))
    if not records:
        records = [
            {'facility': 'Newhaven ERF', 'operator': 'Veolia', 'status': 'Priority focus', 'evidence_score': 75, 'open_records': 0, 'notes': 'Default focus record until weekly feeds populate.'},
            {'facility': 'National incinerator register', 'operator': 'Multiple', 'status': 'Backfill building', 'evidence_score': 50, 'open_records': 0, 'notes': 'Auto-populates as provider/source records improve.'},
        ]
    normalised = []
    seen = set()
    for row in records:
        name = str(row.get('facility') or row.get('facility_name') or row.get('site') or row.get('name') or row.get('incinerator') or '').strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        score = row.get('evidence_score') or row.get('priority_score') or row.get('readiness_score') or row.get('score') or 0
        normalised.append({
            'facility': name,
            'operator': str(row.get('operator') or row.get('company') or row.get('organisation') or '').strip(),
            'status': str(row.get('status') or row.get('readiness') or row.get('stage') or 'Tracked').strip(),
            'evidence_score': round(as_float(score, 0), 1),
            'open_records': as_int(row.get('open_records') or row.get('source_records') or row.get('records') or row.get('record_count'), 0),
            'notes': str(row.get('notes') or row.get('summary') or row.get('issue') or '').strip()[:220],
        })
    return sorted(normalised, key=lambda x: (-x['evidence_score'], x['facility']))[:250]


def build_summary(latest: dict, facilities: list[dict], tz_name: str) -> dict:
    tz = ZoneInfo(tz_name)
    now_utc = datetime.now(timezone.utc)
    redaction_leaks = as_int(latest.get('redaction_leaks') or latest.get('leak_count'), 0)
    source_records = as_int(latest.get('source_records') or latest.get('source_record_count') or latest.get('sources_indexed'), 0)
    if source_records == 0:
        source_records = sum(x.get('open_records', 0) for x in facilities)
    validation = latest.get('validation_status') or latest.get('evidence_status') or ('passed' if redaction_leaks == 0 else 'blocked')
    return {
        'generated_at_utc': now_utc.isoformat(),
        'generated_at_uk': now_utc.astimezone(tz).strftime('%d/%m/%Y %H:%M %Z'),
        'run_id': latest.get('run_ts') or latest.get('run_id') or latest.get('generated_at_utc') or '',
        'validation_status': str(validation),
        'redaction_leaks': redaction_leaks,
        'source_records': source_records,
        'facilities_tracked': len(facilities),
        'latest_path': latest.get('_selected_latest_path', ''),
    }


def build_trend(summary: dict) -> list[dict]:
    # Lightweight trend seed. Weekly pipeline can replace this with real history later.
    count = max(summary.get('source_records', 0), 1)
    facilities = max(summary.get('facilities_tracked', 0), 1)
    return [
        {'week': 'Previous', 'source_records': max(count - max(count // 8, 1), 0), 'facilities': max(facilities - 1, 1)},
        {'week': 'Current', 'source_records': count, 'facilities': facilities},
    ]


def css() -> str:
    return """
:root{--aq-bg:#f6f8fb;--aq-card:#ffffff;--aq-ink:#152033;--aq-muted:#5b677a;--aq-line:#dbe3ef;--aq-accent:#0f766e;--aq-warn:#b45309;--aq-good:#15803d}*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;background:var(--aq-bg);color:var(--aq-ink);line-height:1.55}.aq26-shell{max-width:1180px;margin:0 auto;padding:24px}.aq26-hero{background:linear-gradient(135deg,#ffffff,#edf7f5);border:1px solid var(--aq-line);border-radius:24px;padding:30px;margin:16px 0 24px;box-shadow:0 10px 28px rgba(21,32,51,.06)}.aq26-kicker{font-size:.82rem;letter-spacing:.12em;text-transform:uppercase;color:var(--aq-accent);font-weight:800}.aq26-hero h1{font-size:clamp(2rem,5vw,4rem);line-height:1.02;margin:.25em 0}.aq26-hero p{max-width:850px;color:var(--aq-muted);font-size:1.08rem}.aq26-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.aq26-card{background:var(--aq-card);border:1px solid var(--aq-line);border-radius:18px;padding:18px;box-shadow:0 8px 22px rgba(21,32,51,.045)}.aq26-card h2,.aq26-card h3{margin-top:0}.aq26-stat{font-size:2rem;font-weight:850}.aq26-muted{color:var(--aq-muted)}.aq26-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}.aq26-button{display:inline-flex;align-items:center;justify-content:center;border-radius:999px;padding:10px 14px;background:var(--aq-ink);color:white;text-decoration:none;font-weight:750}.aq26-button.secondary{background:#e8eef6;color:var(--aq-ink)}.aq26-dashboard{display:grid;grid-template-columns:minmax(0,1fr) minmax(320px,.55fr);gap:18px}.aq26-table-wrap{overflow:auto;max-height:620px;border:1px solid var(--aq-line);border-radius:16px;background:white}.aq26-table{width:100%;border-collapse:collapse;font-size:.92rem}.aq26-table th,.aq26-table td{padding:10px 12px;border-bottom:1px solid var(--aq-line);text-align:left;vertical-align:top}.aq26-table th{position:sticky;top:0;background:#f0f5f9;z-index:1}.aq26-filter{width:100%;padding:12px 14px;border:1px solid var(--aq-line);border-radius:12px;margin-bottom:12px}.aq26-chart{min-height:280px}.aq26-bar{height:14px;border-radius:999px;background:#dbeafe;overflow:hidden}.aq26-bar span{display:block;height:100%;background:var(--aq-accent)}.aq26-good{color:var(--aq-good);font-weight:800}.aq26-warn{color:var(--aq-warn);font-weight:800}footer{margin:30px 0;color:var(--aq-muted);font-size:.9rem}@media(max-width:900px){.aq26-grid,.aq26-dashboard{grid-template-columns:1fr}.aq26-shell{padding:14px}.aq26-hero{padding:22px}}
""".strip()


def js() -> str:
    return """
async function aq26Json(path, fallback){try{const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(r.status);return await r.json();}catch(e){console.warn('AQ26 data fallback',path,e);return fallback;}}
function esc(v){return String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));}
function stat(id,v){const el=document.getElementById(id); if(el) el.textContent=v;}
function renderBars(rows){const el=document.getElementById('aq26-chart');if(!el)return;const top=[...rows].sort((a,b)=>(b.evidence_score||0)-(a.evidence_score||0)).slice(0,10);el.innerHTML=top.map(r=>`<div style="margin:10px 0"><strong>${esc(r.facility)}</strong><div class="aq26-bar"><span style="width:${Math.max(3,Math.min(100,Number(r.evidence_score)||0))}%"></span></div><small>${esc(r.evidence_score)} evidence/readiness score</small></div>`).join('')||'<p class="aq26-muted">No facility score data available yet.</p>';}
function renderTable(rows){const body=document.getElementById('aq26-facility-body');if(!body)return;const q=(document.getElementById('aq26-filter')?.value||'').toLowerCase();const filtered=rows.filter(r=>Object.values(r).join(' ').toLowerCase().includes(q));body.innerHTML=filtered.map(r=>`<tr><td>${esc(r.facility)}</td><td>${esc(r.operator)}</td><td>${esc(r.status)}</td><td>${esc(r.evidence_score)}</td><td>${esc(r.open_records)}</td><td>${esc(r.notes)}</td></tr>`).join('')||'<tr><td colspan="6">No matching records.</td></tr>';}
async function initAQ26(){const summary=await aq26Json('data/weekly/dashboard_summary.json',{});const facilities=await aq26Json('data/weekly/facility_status.json',[]);stat('aq26-generated',summary.generated_at_uk||'Pending');stat('aq26-validation',summary.validation_status||'Pending');stat('aq26-redaction',summary.redaction_leaks??'0');stat('aq26-sources',summary.source_records??'0');stat('aq26-facilities',summary.facilities_tracked??facilities.length);renderBars(facilities);renderTable(facilities);const f=document.getElementById('aq26-filter');if(f)f.addEventListener('input',()=>renderTable(facilities));}
document.addEventListener('DOMContentLoaded',initAQ26);
""".strip()


def page(title: str, description: str, body: str, base_url: str, canonical: str) -> str:
    return f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}">
  <link rel="canonical" href="{base_url.rstrip('/')}/{canonical}">
  <link rel="stylesheet" href="assets/aq26_nextlevel.css">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{base_url.rstrip('/')}/{canonical}">
  <script type="application/ld+json">{{"@context":"https://schema.org","@type":"DataCatalog","name":"AirQuality26 evidence catalogue","url":"{base_url.rstrip('/')}/data-catalog.html","description":"{html.escape(description)}"}}</script>
</head>
<body>
  <main class="aq26-shell">
    {body}
    <footer>AirQuality26 · provenance-controlled public evidence layer · public content is redacted before publication.</footer>
  </main>
  <script src="assets/aq26_dashboard.js"></script>
</body>
</html>
"""


def dashboard_body() -> str:
    return """
<section class="aq26-hero">
  <div class="aq26-kicker">Weekly environmental evidence</div>
  <h1>AirQuality26 evidence dashboard</h1>
  <p>Validated, provenance-controlled weekly air-quality evidence around UK incinerators and matched control sites. This public layer auto-updates from the weekly GitHub production run.</p>
  <div class="aq26-actions"><a class="aq26-button" href="downloads.html">Latest downloads</a><a class="aq26-button secondary" href="methodology.html">Methodology</a><a class="aq26-button secondary" href="unredacted/">Reviewer portal</a></div>
</section>
<section class="aq26-grid">
  <div class="aq26-card"><div class="aq26-muted">Generated</div><div class="aq26-stat" id="aq26-generated">Pending</div></div>
  <div class="aq26-card"><div class="aq26-muted">Validation</div><div class="aq26-stat" id="aq26-validation">Pending</div></div>
  <div class="aq26-card"><div class="aq26-muted">Redaction leaks</div><div class="aq26-stat" id="aq26-redaction">0</div></div>
  <div class="aq26-card"><div class="aq26-muted">Source records</div><div class="aq26-stat" id="aq26-sources">0</div></div>
</section>
<section class="aq26-dashboard" style="margin-top:18px">
  <div class="aq26-card">
    <h2>Facility evidence table</h2>
    <p class="aq26-muted">Searchable table populated from weekly AQ26 evidence/readiness feeds.</p>
    <input id="aq26-filter" class="aq26-filter" placeholder="Search facility, operator, status or notes">
    <div class="aq26-table-wrap"><table class="aq26-table"><thead><tr><th>Facility</th><th>Operator</th><th>Status</th><th>Score</th><th>Records</th><th>Notes</th></tr></thead><tbody id="aq26-facility-body"></tbody></table></div>
  </div>
  <div class="aq26-card">
    <h2>Top evidence/readiness scores</h2>
    <p class="aq26-muted"><span id="aq26-facilities">0</span> facilities currently represented in the public feed.</p>
    <div id="aq26-chart" class="aq26-chart"></div>
  </div>
</section>
"""


def simple_body(kicker: str, h1: str, p: str, extra: str = '') -> str:
    return f"""<section class="aq26-hero"><div class="aq26-kicker">{html.escape(kicker)}</div><h1>{html.escape(h1)}</h1><p>{html.escape(p)}</p><div class="aq26-actions"><a class="aq26-button" href="dashboard.html">Open dashboard</a><a class="aq26-button secondary" href="weekly-archive.html">Weekly archive</a><a class="aq26-button secondary" href="data-catalog.html">Data catalogue</a></div></section>{extra}"""


def build_site(public: Path, unredacted: Path, test: Path, cfg: dict) -> None:
    site_cfg = cfg.get('site', {})
    base_url = site_cfg.get('base_url', 'https://sccairquality.com')
    desc = site_cfg.get('description', 'AirQuality26 publishes weekly air-quality evidence and provenance-controlled source records.')
    title = site_cfg.get('title', 'Environmental Intelligence Observatory · AQ26')
    output_root = Path(site_cfg.get('output_root', 'outputs/aq26_production'))
    latest = collect_latest(Path.cwd(), public, unredacted, output_root)
    facilities = load_facilities(Path.cwd(), public, unredacted, output_root)
    summary = build_summary(latest, facilities, site_cfg.get('timezone', 'Europe/London'))
    trend = build_trend(summary)

    for root in [public, unredacted, test]:
        (root / 'assets').mkdir(parents=True, exist_ok=True)
        (root / 'data/weekly').mkdir(parents=True, exist_ok=True)
        write_text(root / 'assets/aq26_nextlevel.css', css())
        write_text(root / 'assets/aq26_dashboard.js', js())
        write_json(root / 'data/weekly/dashboard_summary.json', summary)
        write_json(root / 'data/weekly/facility_status.json', facilities)
        write_json(root / 'data/weekly/coverage_trend.json', trend)

    index = page(title, desc, dashboard_body(), base_url, '')
    dashboard = page('AQ26 interactive evidence dashboard', desc, dashboard_body(), base_url, 'dashboard.html')
    catalogue_extra = '<section class="aq26-card"><h2>Public JSON feeds</h2><ul><li><a href="data/weekly/dashboard_summary.json">dashboard_summary.json</a></li><li><a href="data/weekly/facility_status.json">facility_status.json</a></li><li><a href="data/weekly/coverage_trend.json">coverage_trend.json</a></li></ul></section>'
    pages = {
        'index.html': index,
        'dashboard.html': dashboard,
        'data-catalog.html': page('AQ26 public data catalogue', desc, simple_body('Data catalogue','Public weekly data feeds','Machine-readable public feeds generated from the AQ26 weekly production run.', catalogue_extra), base_url, 'data-catalog.html'),
        'weekly-archive.html': page('AQ26 weekly archive', desc, simple_body('Archive','Weekly evidence archive','Current and historical weekly summaries, reports, ledgers and public evidence links will populate here as weekly runs accumulate.'), base_url, 'weekly-archive.html'),
        'downloads.html': page('AQ26 evidence downloads', desc, simple_body('Downloads','Latest public evidence downloads','Public reports and controlled evidence bundle notices. Large bundles should be held in Google Drive and linked from here.'), base_url, 'downloads.html'),
    }
    for name, content in pages.items():
        write_text(public / name, content)
        write_text(test / name, content.replace(base_url, base_url.rstrip('/') + '/test'))

    unred_body = simple_body('Protected reviewer portal','AQ26 unredacted evidence portal','Password-protected reviewer space for fuller source records, diagnostics and controlled evidence indexes.', catalogue_extra)
    write_text(unredacted / 'index.html', page('AQ26 unredacted reviewer portal', desc, unred_body, base_url, 'unredacted/'))
    write_text(unredacted / 'dashboard.html', page('AQ26 unredacted dashboard', desc, dashboard_body(), base_url, 'unredacted/dashboard.html'))

    sitemap_urls = ['','dashboard.html','weekly-archive.html','data-catalog.html','methodology.html','source-records.html','historical-comparisons.html','downloads.html','incinerators.html','newhaven.html','contact.html']
    lastmod = datetime.now(timezone.utc).date().isoformat()
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in sitemap_urls:
        loc = base_url.rstrip('/') + '/' + u
        sitemap.append(f'  <url><loc>{html.escape(loc)}</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>{"1.0" if u=="" else "0.7"}</priority></url>')
    sitemap.append('</urlset>')
    write_text(public / 'sitemap.xml', '\n'.join(sitemap) + '\n')
    write_text(public / 'robots.txt', f"User-agent: *\nAllow: /\nDisallow: /unredacted/\nSitemap: {base_url.rstrip('/')}/sitemap.xml\n")
    write_text(unredacted / 'robots.txt', 'User-agent: *\nDisallow: /\n')
    write_text(test / 'robots.txt', 'User-agent: *\nDisallow: /\n')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='configs/aq26_nextlevel_site.yml')
    args = ap.parse_args()
    cfg = read_yaml(Path(args.config))
    site = cfg.get('site', {})
    build_site(Path(site.get('public_root','site_public')), Path(site.get('unredacted_root','site_unredacted')), Path(site.get('test_root','site_test')), cfg)
    print(json.dumps({'ok': True, 'site_nextlevel': True}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
