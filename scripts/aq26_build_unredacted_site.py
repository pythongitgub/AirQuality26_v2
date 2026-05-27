#!/usr/bin/env python3
"""Build the AQ26 password-protected unredacted/internal review site.

This is intentionally a *review console*, not the public client site. It copies the public
site for context, then overlays a richer dashboard and searchable evidence catalogue.
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

TEXT_EXTS = {'.json','.csv','.md','.txt','.html','.pdf','.zip','.parquet','.yml','.yaml'}
CORE_ROOTS = ['site_public', 'outputs', 'docs']

BASE_CSS = r'''
:root{--navy:#071628;--navy2:#10243b;--cyan:#4fd6c8;--muted:#64748b;--bg:#eef6fb;--card:#fff;--danger:#dc3545;--gold:#f4b400;}
*{box-sizing:border-box} body{margin:0;font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;background:linear-gradient(180deg,#eef7fb,#f8fbff);color:#071628;}
a{color:inherit}.top{display:flex;align-items:center;justify-content:space-between;gap:1rem;background:#071628;color:white;padding:.85rem 1.2rem;position:sticky;top:0;z-index:10;border-bottom:1px solid rgba(255,255,255,.1)}
.brand{display:flex;align-items:center;gap:.75rem;font-weight:900}.brand img{height:46px;width:auto;background:white;border-radius:8px;padding:2px}.nav{display:flex;gap:.5rem;flex-wrap:wrap}.nav a{padding:.55rem .85rem;border:1px solid rgba(255,255,255,.25);border-radius:999px;text-decoration:none;font-weight:800}.nav a:hover{background:rgba(255,255,255,.12)}
.wrap{max-width:1240px;margin:0 auto;padding:2rem 1rem}.hero{background:linear-gradient(135deg,#08264a,#1596cf);color:#fff;border-radius:28px;padding:3.2rem 3rem;box-shadow:0 18px 45px rgba(7,22,40,.22)}.eyebrow{letter-spacing:.24em;text-transform:uppercase;color:#8ff4ef;font-weight:900;font-size:.85rem}.hero h1{font-size:clamp(2.4rem,5vw,4.7rem);line-height:.98;margin:.7rem 0}.hero p{font-size:1.12rem;max-width:850px;line-height:1.55}.actions{display:flex;gap:.7rem;flex-wrap:wrap;margin-top:1.3rem}.btn{display:inline-flex;align-items:center;gap:.4rem;padding:.8rem 1rem;border-radius:14px;text-decoration:none;font-weight:900}.btn.primary{background:#fff;color:#071628}.btn.ghost{border:1px solid rgba(255,255,255,.45);background:rgba(255,255,255,.12);color:#fff}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:1rem;margin:1.4rem 0}.card{grid-column:span 4;background:#fff;border:1px solid #d9e6ef;border-radius:22px;padding:1.25rem;box-shadow:0 10px 25px rgba(7,22,40,.08)}.card.wide{grid-column:span 8}.card.full{grid-column:1/-1}.label{letter-spacing:.23em;text-transform:uppercase;color:#0f8f90;font-weight:900;font-size:.76rem}.big{font-size:2.15rem;font-weight:950;margin:.3rem 0}.danger{color:#dc3545}.muted{color:#64748b}.chips{display:flex;gap:.5rem;flex-wrap:wrap}.chip{background:#e9fbf8;color:#064b50;border-radius:999px;padding:.35rem .6rem;font-weight:800;font-size:.85rem}.warn{border-left:5px solid #f4b400;background:#fff8df}.ok{border-left:5px solid #4fd6c8}.tools{display:flex;gap:.7rem;flex-wrap:wrap;margin:1rem 0}.tools input,.tools select{padding:.75rem .9rem;border:1px solid #cbd8e3;border-radius:12px;min-width:230px}.tablewrap{overflow:auto;background:#fff;border:1px solid #d9e6ef;border-radius:18px;box-shadow:0 10px 25px rgba(7,22,40,.08)}table{width:100%;border-collapse:collapse;font-size:.92rem}th{position:sticky;top:0;background:#071628;color:#fff;text-align:left;padding:.8rem;z-index:1}td{padding:.7rem .8rem;border-top:1px solid #e5edf5;vertical-align:top}tr:nth-child(even){background:#f8fbff}.path{font-family:ui-monospace,Consolas,monospace;font-size:.82rem;color:#334155;word-break:break-all}.footer{background:#071628;color:#cbd5e1;padding:2rem 1rem;margin-top:3rem}.footer .inner{max-width:1240px;margin:auto}.mobilehint{display:none}@media(max-width:820px){.top{align-items:flex-start}.nav{display:none}.mobilehint{display:block;color:#cbd5e1;font-size:.9rem}.hero{padding:2rem 1.2rem}.card,.card.wide{grid-column:1/-1}.brand img{height:40px}.wrap{padding:1rem}.hero h1{font-size:2.3rem}}
'''

INDEX_JS = r'''
(function(){
  const q = document.getElementById('q');
  const cat = document.getElementById('cat');
  const rows = Array.from(document.querySelectorAll('tbody tr'));
  function apply(){
    const needle=(q.value||'').toLowerCase(); const c=cat.value;
    rows.forEach(r=>{ const okText=r.innerText.toLowerCase().includes(needle); const okCat=!c || r.dataset.category===c; r.style.display=(okText&&okCat)?'':'none'; });
  }
  if(q) q.addEventListener('input', apply); if(cat) cat.addEventListener('change', apply);
})();
'''


def safe_read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def copytree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('.git', '__pycache__'))


def category_for(path: Path) -> str:
    s = str(path).replace('\\','/')
    if '/31_laqn/' in s or '/laqn/' in s: return 'LAQN'
    if '/32_earthdata/' in s or '/34_earthdata' in s or '/earthdata/' in s: return 'NASA Earthdata'
    if '/10_historical_backfill' in s: return 'WeeklyV2 backfill'
    if '/charts/' in s: return 'Chart payloads'
    if '/history/' in s: return 'Weekly history'
    if '/99_integrity/' in s or 'VALIDATION' in s or 'SECRET_DIAGNOSTICS' in s: return 'Integrity / validation'
    if s.startswith('site_public/data'): return 'Public data payloads'
    if s.startswith('site_public/downloads') or s.endswith('.zip') or s.endswith('.pdf'): return 'Downloads / reports'
    if s.startswith('docs'): return 'Documentation'
    return 'Other evidence'


def collect_files(repo: Path, max_files: int):
    records=[]
    for root_name in CORE_ROOTS:
        root = repo / root_name
        if not root.exists():
            continue
        for p in root.rglob('*'):
            if not p.is_file() or p.name.startswith('.'):
                continue
            if p.suffix.lower() not in TEXT_EXTS:
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            rel = p.relative_to(repo).as_posix()
            records.append({
                'name': p.name,
                'path': rel,
                'category': category_for(Path(rel)),
                'size': st.st_size,
                'modified': datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                'public_link': rel[len('site_public/'):] if rel.startswith('site_public/') else '',
            })
    records.sort(key=lambda r: (r['category'], r['path']))
    return records[:max_files]


def load_summary(repo: Path):
    candidates = [
        repo/'site_public/data/latest_backfill_summary.json',
        repo/'site_public/data/latest_summary.json',
        repo/'outputs/10_historical_backfill/LATEST_HARVEST.json',
    ]
    for p in candidates:
        if p.exists():
            data = safe_read_json(p)
            if isinstance(data, dict):
                return data, p.as_posix()
    return {}, ''


def html_escape(s):
    import html
    return html.escape(str(s), quote=True)


def render_top(repo: Path, out: Path, active='dashboard'):
    logo = 'assets/logo_web.svg'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AQ26 Unredacted Review Area</title><link rel="icon" href="favicon.svg?v=aq26-20260527" type="image/svg+xml"><link rel="stylesheet" href="assets/aq26_unredacted.css?v=aq26-20260527"></head><body><header class="top"><a class="brand" href="index.html"><img src="{logo}" alt="SCC Nexus"><span>SCC Nexus · AQ26 internal review</span></a><nav class="nav"><a href="index.html">Dashboard</a><a href="evidence.html">Evidence index</a><a href="../index.html">Public site</a></nav><div class="mobilehint">Internal review site</div></header>'''


def render_index(repo: Path, out: Path, records, summary, summary_source):
    cats = Counter(r['category'] for r in records)
    run_ts = summary.get('run_ts') or summary.get('generated_at_utc') or summary.get('timestamp_utc') or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    source_records = summary.get('source_records') or summary.get('source_record_count') or summary.get('records') or ''
    warnings = summary.get('warnings') or summary.get('warning_count') or ''
    errors = summary.get('errors') or summary.get('error_count') or ''
    body = render_top(repo,out) + f'''
<main class="wrap">
  <section class="hero">
    <div class="eyebrow">Password-protected area</div>
    <h1>AQ26 Unredacted Evidence Review</h1>
    <p>This site is for internal QA, provenance review, unredacted workflow outputs and evidence-readiness checks. It is separate from the public client interface and should not be shared externally.</p>
    <div class="actions"><a class="btn primary" href="evidence.html">Open evidence index</a><a class="btn ghost" href="data/unredacted/evidence_file_index.json">View JSON index</a><a class="btn ghost" href="../index.html">Public site</a></div>
  </section>
  <section class="grid">
    <article class="card"><div class="label">Generated</div><div class="big">{html_escape(run_ts)}</div><p class="muted">UTC build timestamp or latest run timestamp.</p></article>
    <article class="card"><div class="label">Indexed files</div><div class="big">{len(records)}</div><p class="muted">Outputs, data payloads, reports and documentation indexed for review.</p></article>
    <article class="card"><div class="label">Access</div><div class="big danger">Restricted</div><p>Do not share credentials or publish unreviewed evidence externally.</p></article>
    <article class="card"><div class="label">Source records</div><div class="big">{html_escape(source_records or 'Review')}</div><p class="muted">See source-records and manifest files in the index.</p></article>
    <article class="card"><div class="label">Warnings</div><div class="big">{html_escape(warnings if warnings != '' else 'Check')}</div><p class="muted">Review validation outputs before public promotion.</p></article>
    <article class="card"><div class="label">Errors</div><div class="big">{html_escape(errors if errors != '' else 'Check')}</div><p class="muted">Errors should be resolved before external use.</p></article>
    <article class="card full ok"><h2>Evidence groups</h2><div class="chips">{''.join('<span class="chip">%s: %s</span>'%(html_escape(k),v) for k,v in cats.most_common())}</div></article>
    <article class="card wide warn"><h2>Review workflow</h2><ol><li>Check latest run summaries and validation warnings.</li><li>Confirm redacted/public payloads do not leak sensitive fields.</li><li>Use source records and manifests for provenance checks.</li><li>Promote only small, client-friendly summaries to the public website.</li></ol></article>
    <article class="card"><h2>Latest summary source</h2><p class="path">{html_escape(summary_source or 'No summary JSON found')}</p></article>
  </section>
</main><footer class="footer"><div class="inner">© SCC Nexus / AQ26 · Internal review site · noindex</div></footer></body></html>'''
    (out/'index.html').write_text(body, encoding='utf-8')


def render_evidence(repo: Path, out: Path, records):
    cats = sorted(set(r['category'] for r in records))
    options = '<option value="">All categories</option>' + ''.join(f'<option value="{html_escape(c)}">{html_escape(c)}</option>' for c in cats)
    rows=[]
    for r in records:
        link = r['public_link']
        href = link if link else '#'
        name = html_escape(r['name'])
        rows.append(f'<tr data-category="{html_escape(r["category"])}"><td><span class="chip">{html_escape(r["category"])}</span></td><td>{f"<a href=\"{html_escape(href)}\">{name}</a>" if link else name}</td><td class="path">{html_escape(r["path"])}</td><td>{r["size"]:,}</td><td>{html_escape(r["modified"][:19])}</td></tr>')
    body = render_top(repo,out,'evidence') + f'''
<main class="wrap"><section class="hero"><div class="eyebrow">Evidence index</div><h1>Unredacted output catalogue</h1><p>Search and filter files generated from GitHub Actions, provider probes, backfill outputs and site payloads. This is not the public user interface.</p></section>
<section class="card full"><h2>Find evidence</h2><div class="tools"><input id="q" placeholder="Search filename, path or category"><select id="cat">{options}</select></div><div class="tablewrap"><table><thead><tr><th>Category</th><th>Name</th><th>Repository path</th><th>Size</th><th>Modified UTC</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section></main><script>{INDEX_JS}</script><footer class="footer"><div class="inner">© SCC Nexus / AQ26 · Internal review site · noindex</div></footer></body></html>'''
    (out/'evidence.html').write_text(body, encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo-root', default='.')
    ap.add_argument('--public-site', default='site_public')
    ap.add_argument('--output-site', default='site_unredacted')
    ap.add_argument('--max-index-files', default='1000')
    args = ap.parse_args()
    repo = Path(args.repo_root)
    public = repo/args.public_site
    out = repo/args.output_site
    if out.exists(): shutil.rmtree(out)
    if public.exists(): copytree(public, out)
    else: out.mkdir(parents=True, exist_ok=True)
    (out/'assets').mkdir(parents=True, exist_ok=True)
    # copy branding assets if present
    for srcdir in [repo/'website/assets', public/'assets']:
        if srcdir.exists():
            for p in srcdir.iterdir():
                if p.is_file() and (p.name.startswith('favicon') or p.name.startswith('apple') or p.name.startswith('android') or p.name in {'logo_web.svg','site.webmanifest'}):
                    shutil.copy2(p, out/'assets'/p.name)
    if (out/'assets/logo_web.svg').exists(): shutil.copy2(out/'assets/logo_web.svg', out/'favicon.svg')
    (out/'assets/aq26_unredacted.css').write_text(BASE_CSS, encoding='utf-8')
    max_files = int(args.max_index_files)
    records = collect_files(repo, max_files)
    summary, summary_source = load_summary(repo)
    data_dir = out/'data/unredacted'; data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir/'evidence_file_index.json').write_text(json.dumps({'generated_at_utc':datetime.now(timezone.utc).isoformat(),'indexed_files':len(records),'records':records}, indent=2), encoding='utf-8')
    (data_dir/'dashboard_summary.json').write_text(json.dumps({'generated_at_utc':datetime.now(timezone.utc).isoformat(),'indexed_files':len(records),'summary_source':summary_source,'summary':summary}, indent=2), encoding='utf-8')
    render_index(repo,out,records,summary,summary_source)
    render_evidence(repo,out,records)
    (out/'robots.txt').write_text('User-agent: *\nDisallow: /\n', encoding='utf-8')
    print(json.dumps({'ok':True,'output_site':str(out),'indexed_files':len(records)}, indent=2))

if __name__ == '__main__':
    main()
