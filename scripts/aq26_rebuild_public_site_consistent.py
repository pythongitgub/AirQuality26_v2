#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, json, os, shutil
from datetime import datetime, timezone
from pathlib import Path

PAGES = {
  "index.html": ("AQ26 Environmental Intelligence Observatory", "Weekly air-quality and emissions intelligence", "SCC NEXUS · AQ26"),
  "archive.html": ("Weekly evidence archive", "Backfill windows, status summaries and generated evidence weeks.", "AQ26 WEEKLY ARCHIVE"),
  "comparisons.html": ("Comparison dashboard", "Chart-ready comparisons across source coverage, readiness and filings.", "AQ26 COMPARISONS"),
  "source-records.html": ("Source records", "Where the evidence comes from and how it was captured.", "AQ26 PROVENANCE"),
  "readiness.html": ("Readiness", "Evidence gates and validation status.", "AQ26 READINESS"),
  "methodology.html": ("Methodology", "How AQ26 separates collection, validation, public summaries and internal review.", "AQ26 METHOD"),
  "downloads.html": ("Downloads", "Public redacted evidence bundles and latest reports.", "AQ26 DOWNLOADS"),
  "about.html": ("About AQ26", "A public environmental intelligence interface backed by controlled evidence workflows.", "ABOUT"),
  "privacy.html": ("Privacy", "Static site privacy information and data-use boundaries.", "PRIVACY"),
  "cookies.html": ("Cookies", "Essential local preferences and chart-display support.", "COOKIES"),
  "accessibility.html": ("Accessibility", "Readable, keyboard-friendly pages for a broad user audience.", "ACCESSIBILITY"),
  "terms.html": ("Terms", "Public information, caveats and evidence-use conditions.", "TERMS"),
  "contact.html": ("Contact", "How to raise feedback on AQ26 outputs and public presentation.", "CONTACT"),
}
NAV = [("Observatory","index.html"),("Weekly Archive","archive.html"),("Comparisons","comparisons.html"),("Source Records","source-records.html"),("Readiness","readiness.html"),("Methodology","methodology.html"),("Downloads","downloads.html")]
CSS = """
:root{--navy:#061426;--ink:#09213f;--muted:#58708f;--border:#d8e4f2;--bg:#f5f9fd;--teal:#48d8cf;--warn:#fff7dc;--shadow:0 18px 42px rgba(9,33,63,.10)}*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.55;font-size:16px}a{color:#075ea8;text-underline-offset:.18em}.top{background:var(--navy);color:#fff;font-size:.82rem;font-weight:800;display:flex;justify-content:space-between;gap:1rem;padding:.45rem clamp(1rem,3vw,2.2rem)}.head{background:#fff;border-bottom:1px solid var(--border);box-shadow:0 2px 16px rgba(9,33,63,.06);position:relative;z-index:10}.headin{max-width:1560px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:1.5rem;padding:1rem clamp(1rem,3vw,2.2rem)}.brand img{width:min(300px,32vw);height:auto;display:block}.pill{border:1px solid var(--border);background:#eef6ff;border-radius:999px;padding:.45rem .85rem;font-weight:900;color:#38506b;white-space:nowrap}.nav{display:flex;align-items:center;gap:.55rem;flex-wrap:wrap;justify-content:flex-end}.nav a,.menubtn{border:1px solid #cbd9e8;background:#f1f7fd;color:var(--ink);font-weight:900;border-radius:999px;padding:.65rem .92rem;text-decoration:none;box-shadow:0 1px 3px rgba(9,33,63,.04)}.nav a[aria-current='page']{background:var(--navy);color:white;border-color:var(--navy)}.menubtn{display:none;cursor:pointer}main{max-width:1240px;margin:0 auto;padding:clamp(1.25rem,3vw,2.2rem)}.hero{background:linear-gradient(135deg,#123a63,#1e6f9c 58%,#36a7d7);border-radius:28px;box-shadow:var(--shadow);padding:clamp(2rem,5vw,4.5rem);color:white;margin:1.2rem 0 1.8rem}.eyebrow{font-size:.85rem;letter-spacing:.18em;text-transform:uppercase;color:#8ff5ec;font-weight:950;margin:0 0 .75rem}.hero h1{font-size:clamp(2.2rem,5vw,4.4rem);line-height:1.05;margin:0 0 1rem;color:white;max-width:980px}.hero p{font-size:clamp(1.05rem,2vw,1.32rem);max-width:820px;margin:0 0 1.4rem;color:#f5fbff}.actions{display:flex;gap:.75rem;flex-wrap:wrap}.btn{display:inline-flex;border-radius:14px;padding:.86rem 1.05rem;text-decoration:none;font-weight:950;border:1px solid rgba(255,255,255,.28)}.primary{background:var(--teal);color:#03192a;border-color:var(--teal)}.secondary{background:rgba(255,255,255,.13);color:white}.notice{background:var(--warn);border-left:5px solid #ffc400;border-radius:14px;padding:1rem 1.2rem;margin:1.3rem 0;color:var(--ink)}.section-title{font-size:1.35rem;margin:2rem 0 1rem}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.card{background:#fff;border:1px solid var(--border);border-radius:22px;padding:1.25rem;box-shadow:0 8px 22px rgba(9,33,63,.06);color:var(--ink)}.kicker{font-size:.78rem;letter-spacing:.18em;text-transform:uppercase;color:#0e887e;font-weight:950;margin-bottom:.45rem}.card h2,.card h3{margin:.15rem 0 .55rem;color:var(--ink)}.metric{font-size:2.1rem;font-weight:950}.muted{color:var(--muted)}.table-card{background:#fff;border:1px solid var(--border);border-radius:22px;overflow:auto;box-shadow:0 8px 22px rgba(9,33,63,.06);margin:1rem 0}table{width:100%;border-collapse:collapse;min-width:720px;background:white;color:var(--ink)}th{background:var(--navy);color:#fff;text-align:left;padding:.9rem}td{padding:.85rem .9rem;border-top:1px solid var(--border);vertical-align:top}.badge{display:inline-flex;border-radius:999px;background:#e9fbf8;color:#075b56;font-weight:900;padding:.25rem .6rem;font-size:.82rem}.ok{background:#e6f8ea;color:#0f6a2a}.warn{background:#fff3cd;color:#725800}.info{background:#eaf3ff;color:#164e85}.placeholder{height:230px;border:1px dashed #b8cada;border-radius:18px;background:linear-gradient(180deg,#fafdff,#f1f7fd);display:flex;align-items:center;justify-content:center;text-align:center;padding:1rem;color:var(--muted);font-weight:800}.footer{background:var(--navy);color:#dbe8f7;margin-top:3rem;padding:2rem clamp(1rem,3vw,2rem)}.footin{max-width:1240px;margin:0 auto;display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}.footer a{color:#fff;margin-right:.8rem}.cookie{position:fixed;left:1rem;right:1rem;bottom:1rem;background:white;border:1px solid var(--border);border-radius:18px;box-shadow:var(--shadow);padding:1rem;display:none;z-index:20}.cookie.show{display:flex;gap:1rem;justify-content:space-between;align-items:center}.cookie button{border:0;border-radius:12px;background:var(--navy);color:white;font-weight:900;padding:.7rem .9rem}.watermark{position:fixed;right:1rem;bottom:1rem;opacity:.035;width:260px;pointer-events:none}@media(max-width:900px){.top{font-size:.72rem}.headin{align-items:flex-start}.brand img{width:220px}.pill{display:none}.menubtn{display:inline-flex}.nav{display:none;position:absolute;top:100%;left:0;right:0;background:#fff;padding:1rem;border-bottom:1px solid var(--border);box-shadow:var(--shadow);justify-content:flex-start}.nav.open{display:flex}.nav a{width:100%;border-radius:12px}.grid{grid-template-columns:1fr}main{padding:1rem}.hero{border-radius:22px;padding:2rem}.cookie.show{display:block}.cookie button{margin-top:.7rem}}
"""
JS = """(function(){function r(f){document.readyState!=='loading'?f():document.addEventListener('DOMContentLoaded',f)}r(function(){var b=document.querySelector('[data-menu]'),n=document.querySelector('.nav');if(b&&n)b.onclick=function(){var o=n.classList.toggle('open');b.setAttribute('aria-expanded',o?'true':'false')};var c=document.querySelector('.cookie');if(c&&localStorage.getItem('aq26_cookie_ok')!=='1')c.classList.add('show');var a=document.querySelector('[data-cookie-accept]');if(a)a.onclick=function(){localStorage.setItem('aq26_cookie_ok','1');if(c)c.classList.remove('show')}})})();"""

def e(x): return html.escape('' if x is None else str(x))
def load_json(p):
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return None

def find_first(root, names):
    for name in names:
        p = root / name
        if p.exists(): return p
    for name in names:
        hits = list(root.rglob(Path(name).name))
        if hits: return hits[0]
    return None

def write_assets(site, src):
    a = site/'assets'; a.mkdir(parents=True, exist_ok=True)
    if src and src.exists():
        for name in ['air_quality_web.svg','favicon.svg','logo_web.svg','apple-touch-icon.png','android-chrome-192x192.png','android-chrome-512x512.png','favicon-32x32.png','favicon-16x16.png','site.webmanifest']:
            if (src/name).exists(): shutil.copy2(src/name, a/name)
    if not (a/'air_quality_web.svg').exists():
        if (a/'logo_web.svg').exists(): shutil.copy2(a/'logo_web.svg', a/'air_quality_web.svg')
        else: (a/'air_quality_web.svg').write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 480 120'><rect width='480' height='120' fill='white'/><text x='20' y='72' font-family='Arial' font-size='42' fill='#09213f'>SCC Nexus</text><text x='24' y='102' font-family='Arial' font-size='24' fill='#2c93c9'>Air Quality Report</text></svg>", encoding='utf-8')
    if not (a/'favicon.svg').exists():
        (a/'favicon.svg').write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='14' fill='#09213f'/><path d='M16 32 32 16l16 16-16 16z' fill='#48d8cf'/></svg>", encoding='utf-8')
    (a/'aq26_consistent.css').write_text(CSS, encoding='utf-8')
    (a/'aq26_consistent.js').write_text(JS, encoding='utf-8')

def head(title):
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+e(title)+' - AQ26</title><link rel="icon" type="image/svg+xml" href="assets/favicon.svg?v=aq26-consistent"><link rel="apple-touch-icon" href="assets/apple-touch-icon.png?v=aq26-consistent"><link rel="stylesheet" href="assets/aq26_consistent.css?v=aq26-consistent"><script defer src="assets/aq26_consistent.js?v=aq26-consistent"></script></head><body>'

def header(active):
    nav = ''.join('<a href="'+href+'" '+('aria-current="page"' if href==active else '')+'>'+e(label)+'</a>' for label, href in NAV)
    return '<div class="top"><span>SCC Nexus - AQ26 Weekly evidence, provenance and air-quality intelligence</span><span>Public observatory</span></div><header class="head"><div class="headin"><a class="brand" href="index.html"><img src="assets/air_quality_web.svg?v=aq26-consistent" alt="SCC Nexus Air Quality Report"></a><span class="pill">Public observatory</span><button class="menubtn" type="button" data-menu aria-expanded="false">Menu</button><nav class="nav" aria-label="Main navigation">'+nav+'</nav></div></header>'

def footer():
    links = ''.join('<a href="'+href+'">'+e(label)+'</a>' for label, href in [('About','about.html'),('Privacy','privacy.html'),('Cookies','cookies.html'),('Accessibility','accessibility.html'),('Terms','terms.html'),('Contact','contact.html')])
    return '<footer class="footer"><div class="footin"><div><strong>AQ26 WeeklyV2</strong><p>Public interface for environmental evidence summaries; no endorsement, regulatory determination or causal attribution is claimed.</p></div><div>'+links+'</div></div></footer><img class="watermark" src="assets/air_quality_web.svg" alt="" aria-hidden="true"><div class="cookie"><div><strong>Cookies on AQ26</strong><br>We use essential local-storage preferences and may load chart assets. No advertising cookies are intentionally set.</div><button type="button" data-cookie-accept>Accept</button></div></body></html>'

def hero(title, subtitle, eyebrow):
    return '<section class="hero"><p class="eyebrow">'+e(eyebrow)+'</p><h1>'+e(title)+'</h1><p>'+e(subtitle)+'</p><div class="actions"><a class="btn primary" href="downloads.html">Latest downloads</a><a class="btn secondary" href="comparisons.html">Explore comparisons</a></div></section>'

def notice(title): return '<div class="notice"><strong>'+e(title)+':</strong> this page has been prepared so users never see a blank screen while the AQ26 evidence backfill populates richer content.</div>'
def cards(): return '<section class="grid"><article class="card"><div class="kicker">Evidence</div><h2>Weekly</h2><p class="muted">Backfill outputs and public summaries are refreshed by the AQ26 workflow.</p></article><article class="card"><div class="kicker">Coverage</div><h2>Multi-source</h2><p class="muted">Ground monitoring, weather, official records and satellite/reanalysis context.</p></article><article class="card"><div class="kicker">Integrity</div><h2>Provenance</h2><p class="muted">Public pages use redacted summaries. Internal QA remains in the protected review area.</p></article></section>'

def render_index(site):
    d = load_json(find_first(site, ['data/weekly_index.json','data/latest_summary.json','data/latest_backfill_summary.json']) or Path('')) or {}
    keys=[('Source records',['source_records','source_record_count','records','total_source_records']),('OK records',['ok_records','ok_count','success_records']),('Warnings',['warnings','warning_count']),('Satellite products',['satellite_products','satellite_product_count']),('Drive files',['drive_files','gdrive_files','file_count']),('Redaction leaks',['redaction_leaks','leaks'])]
    out=[]
    for label, ks in keys:
        val='-'
        for k in ks:
            if isinstance(d,dict) and k in d: val=d[k]; break
        out.append('<article class="card"><div class="kicker">'+e(label)+'</div><div class="metric">'+e(val)+'</div></article>')
    return '<h2 class="section-title">Latest evidence status</h2><section class="grid">'+''.join(out)+'</section><h2 class="section-title">What this means</h2>'+cards()

def render_archive(site):
    hist = sorted((site/'data'/'history').glob('*.json')) if (site/'data'/'history').exists() else []
    rows = ''.join('<tr><td>'+e(p.stem)+'</td><td><span class="badge info">Indexed</span></td><td><a href="'+e(str(p.relative_to(site)).replace(os.sep,'/'))+'">View JSON</a></td></tr>' for p in hist[-80:][::-1]) or '<tr><td>Latest weekly window</td><td><span class="badge warn">Awaiting next backfill index</span></td><td>Run the AQ26 backfill workflow to populate historical windows.</td></tr>'
    return '<section class="table-card"><table><thead><tr><th>Week</th><th>Status</th><th>Payload</th></tr></thead><tbody>'+rows+'</tbody></table></section>'

def render_comparisons(site):
    chart_dir=site/'data'/'charts'; charts=sorted(chart_dir.glob('*.json')) if chart_dir.exists() else []
    blocks=[]
    for p in charts[:12]:
        label=p.stem.replace('_',' ').title(); href=str(p.relative_to(site)).replace(os.sep,'/')
        blocks.append('<article class="card"><div class="kicker">Chart payload</div><h3>'+e(label)+'</h3><p class="muted">Public chart-ready JSON is available.</p><a class="btn primary" href="'+e(href)+'">Open payload</a></article>')
    if not blocks: blocks.append('<article class="card"><div class="kicker">Pending</div><h3>Comparison data is being prepared</h3><p class="muted">Run the WeeklyV2 backfill to populate chart-ready source coverage, readiness and historical comparison data.</p></article>')
    return '<section class="grid">'+''.join(blocks)+'</section><h2 class="section-title">Preview area</h2><div class="placeholder">Interactive charts will render here once chart payloads are available.</div>'

def render_source(site):
    p=find_first(site,['data/source_records_latest.json','data/source_records.json','data/providers/laqn/source_records.json']); d=load_json(p) if p else None; recs=d if isinstance(d,list) else d.get('records',[]) if isinstance(d,dict) else []
    rows=[]
    for r in recs[:120]:
        if isinstance(r,dict): rows.append('<tr><td><span class="badge">'+e(r.get('provider') or r.get('source') or r.get('source_class') or 'source')+'</span></td><td>'+e(r.get('status') or r.get('validation_status') or 'record')+'</td><td>'+e(str(r.get('path') or r.get('url') or r.get('normalised_path') or r.get('raw_path') or '')[:180])+'</td></tr>')
    if not rows: rows.append('<tr><td>WeeklyV2</td><td><span class="badge warn">Awaiting source-record payload</span></td><td>Run backfill/provider workflows to populate public source records.</td></tr>')
    return '<section class="table-card"><table><thead><tr><th>Provider</th><th>Status</th><th>Reference</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></section>'

def render_readiness(site):
    p=find_first(site,['data/science_validation_latest.json','data/readiness.json','outputs/10_historical_backfill/evidence_readiness_gates.json']); d=load_json(p) if p else None; gates=d.get('gates',d) if isinstance(d,dict) else {}
    rows=[]
    if isinstance(gates,dict):
        for k,v in list(gates.items())[:80]:
            status='Ready' if v is True else 'Not ready' if v is False else str(v); cls='ok' if v is True else 'warn' if v is False else 'info'
            rows.append('<tr><td>'+e(str(k).replace('_',' ').title())+'</td><td><span class="badge '+cls+'">'+e(status)+'</span></td><td>Evidence gate tracked by AQ26 workflows.</td></tr>')
    if not rows: rows.append('<tr><td>External submission</td><td><span class="badge warn">Not ready</span></td><td>Formal external submission remains disabled until validation gates pass.</td></tr><tr><td>Public dashboard</td><td><span class="badge ok">Active</span></td><td>Public summaries are available with transparent caveats.</td></tr>')
    return '<section class="table-card"><table><thead><tr><th>Gate</th><th>Status</th><th>Note</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></section>'

def render_downloads(site):
    dl=site/'downloads'; dl.mkdir(exist_ok=True)
    for name, content in [('latest-evidence.zip', b'AQ26 public evidence ZIP placeholder. Run WeeklyV2 backfill to replace this file.\n'),('latest-report.pdf', b'AQ26 latest report placeholder. Run WeeklyV2 backfill to replace this file.\n')]:
        p=dl/name
        if not p.exists(): p.write_bytes(content)
    rows=''.join('<tr><td><a href="downloads/'+e(p.name)+'">'+e(p.name)+'</a></td><td>'+format(p.stat().st_size, ',')+' bytes</td><td><span class="badge info">Public/redacted</span></td></tr>' for p in sorted(dl.iterdir()) if p.is_file())
    return '<section class="table-card"><table><thead><tr><th>File</th><th>Size</th><th>Status</th></tr></thead><tbody>'+rows+'</tbody></table></section>'

def static_body(filename):
    texts={'about.html':'AQ26 is an environmental intelligence observatory that brings together public evidence streams, provenance checks and weekly reporting outputs.','privacy.html':'This static public site does not intentionally collect personal information. Server logs may be handled by the hosting provider. Internal evidence review remains password-protected.','cookies.html':'AQ26 uses essential local-storage preferences for cookie-banner state and may load chart assets for interactive visualisations. No advertising cookies are intentionally set.','accessibility.html':'AQ26 aims for readable contrast, keyboard-friendly navigation, responsive layout and clear language. Please report accessibility issues for correction.','terms.html':'AQ26 provides public evidence summaries and context. It does not make medical, legal, regulatory or causal determinations and does not imply endorsement by external institutions.','contact.html':'For feedback, use the contact route provided by SCC Nexus or the project owner. Do not submit sensitive personal data through public channels.'}
    return '<section class="card"><p>'+e(texts.get(filename,'AQ26 public information page.'))+'</p></section>'+cards()

def body_for(fn, site):
    if fn=='index.html': return render_index(site)
    if fn=='archive.html': return render_archive(site)
    if fn=='comparisons.html': return render_comparisons(site)
    if fn=='source-records.html': return render_source(site)
    if fn=='readiness.html': return render_readiness(site)
    if fn=='downloads.html': return render_downloads(site)
    if fn=='methodology.html': return '<section class="grid"><article class="card"><h2>Collect</h2><p>Provider workflows gather ground AQ, weather, official records and catalogue context.</p></article><article class="card"><h2>Validate</h2><p>Checks record provenance, warning status and redaction readiness.</p></article><article class="card"><h2>Publish</h2><p>Only suitable public summaries and redacted evidence bundles are surfaced.</p></article></section>'+cards()
    return static_body(fn)

def render_page(fn, site):
    title, sub, brow = PAGES[fn]
    return head(title)+header(fn)+'<main>'+hero(title, sub, brow)+notice(title)+'<h2 class="section-title">'+e(sub)+'</h2>'+body_for(fn, site)+'</main>'+footer()

def alias(site, fn, target):
    (site/fn).write_text("<!doctype html><html><head><meta charset='utf-8'><meta http-equiv='refresh' content='0; url="+target+"'><title>Redirecting - AQ26</title></head><body><p>Redirecting to <a href='"+target+"'>"+target+"</a>.</p></body></html>", encoding='utf-8')

def validate(site):
    problems=[]
    for fn in PAGES:
        p=site/fn
        if not p.exists() or p.stat().st_size<1200: problems.append(fn+': missing or too small')
        else:
            txt=p.read_text(encoding='utf-8',errors='ignore')
            if 'aq26_consistent.css' not in txt or 'class="head"' not in txt: problems.append(fn+': missing consistent template')
    return {'ok':not problems,'problems':problems,'site_root':str(site),'checked_at_utc':datetime.now(timezone.utc).isoformat()}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--site-root',default='site_public'); ap.add_argument('--asset-source',default='website/assets'); ap.add_argument('--summary',default=''); ap.add_argument('--force',action='store_true'); ap.add_argument('--validate-only',action='store_true')
    args=ap.parse_args(); site=Path(args.site_root); site.mkdir(parents=True,exist_ok=True)
    if not args.validate_only:
        write_assets(site, Path(args.asset_source) if args.asset_source else None)
        for fn in PAGES: (site/fn).write_text(render_page(fn, site), encoding='utf-8')
        alias(site,'historical-comparisons.html','comparisons.html'); alias(site,'weekly-archive.html','archive.html'); alias(site,'evidence-downloads.html','downloads.html')
        (site/'robots.txt').write_text('User-agent: *\nAllow: /\n', encoding='utf-8'); (site/'sitemap.txt').write_text('\n'.join(PAGES.keys())+'\n', encoding='utf-8')
    result=validate(site); sp=Path(args.summary) if args.summary else site/'data'/'public_dashboard'/'consistent_rebuild_summary.json'; sp.parent.mkdir(parents=True,exist_ok=True); sp.write_text(json.dumps(result, indent=2), encoding='utf-8'); print(json.dumps(result, indent=2)); return 0 if result['ok'] else 2
if __name__ == '__main__': raise SystemExit(main())
