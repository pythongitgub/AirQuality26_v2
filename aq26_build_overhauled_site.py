#!/usr/bin/env python3
from pathlib import Path
import json, html, os, datetime, shutil, re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'config/aq26_site_config.json').read_text(encoding='utf-8'))
NOW = datetime.datetime.utcnow().strftime('%Y-%m-%d')
GA = os.environ.get('GA_MEASUREMENT_ID','').strip()
GSC = os.environ.get('GOOGLE_SITE_VERIFICATION','').strip()

def analytics():
    if not GA:
        return '<!-- Analytics disabled: set GA_MEASUREMENT_ID secret to enable gtag. -->'
    return f'''<script async src="https://www.googletagmanager.com/gtag/js?id={html.escape(GA)}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{html.escape(GA)}', {{'anonymize_ip': true}});
</script>'''

def verification():
    return f'<meta name="google-site-verification" content="{html.escape(GSC)}">' if GSC else '<!-- Search Console verification disabled: set GOOGLE_SITE_VERIFICATION secret. -->'

def css():
    return '''
:root{--bg:#07111f;--panel:#ffffff;--ink:#102033;--muted:#667085;--brand:#42c3ff;--brand2:#6ee7b7;--accent:#fbbf24;--line:#d9e2ef;--red:#b42318;--green:#067647;--max:1180px;}
*{box-sizing:border-box} html{scroll-behavior:smooth} body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:var(--ink);background:#f5f8fc;line-height:1.58} a{color:#075985} a:focus,button:focus{outline:3px solid var(--accent);outline-offset:3px}.skip{position:absolute;left:-999px;top:0;background:#fff;padding:.75rem;z-index:100}.skip:focus{left:1rem;top:1rem}.site-header{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line);backdrop-filter:blur(10px)}.header-inner{max-width:var(--max);margin:auto;padding:.75rem 1rem;display:flex;align-items:center;gap:1rem}.logo{display:flex;align-items:center;gap:.65rem;text-decoration:none;color:var(--ink);font-weight:900}.logo img{width:48px;height:48px;object-fit:contain}.logo small{display:block;color:var(--muted);font-weight:700}.nav-toggle{margin-left:auto;border:1px solid var(--line);background:#fff;border-radius:999px;padding:.55rem .75rem;font-weight:900}.nav{display:none;position:absolute;left:1rem;right:1rem;top:72px;background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:0 20px 45px rgba(16,32,51,.18);padding:.75rem}.nav[data-open="true"]{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.25rem}.nav a{padding:.7rem .8rem;text-decoration:none;border-radius:12px;font-weight:800;color:#102033}.nav a:hover,.nav a[aria-current="page"]{background:#e6f6ff}.hero{background:radial-gradient(circle at 20% 20%,rgba(66,195,255,.25),transparent 36%),linear-gradient(135deg,#07111f,#0e314a 58%,#062a2f);color:#fff;overflow:hidden}.hero-inner{max-width:var(--max);margin:auto;padding:4.5rem 1rem 3rem;display:grid;grid-template-columns:1.1fr .9fr;gap:2rem;align-items:center}.eyebrow{display:inline-flex;gap:.5rem;align-items:center;padding:.35rem .65rem;border:1px solid rgba(255,255,255,.35);border-radius:999px;color:#dff7ff;font-weight:900}.hero h1{font-size:clamp(2rem,5vw,4.7rem);line-height:1.03;margin:.9rem 0}.hero p{font-size:clamp(1.05rem,2vw,1.35rem);color:#d8e9f7}.hero-card{background:rgba(255,255,255,.11);border:1px solid rgba(255,255,255,.22);border-radius:28px;padding:1.2rem;box-shadow:0 25px 75px rgba(0,0,0,.28)}.hero-card img{width:100%;height:auto;border-radius:22px;background:#fff}.pillrow{display:flex;flex-wrap:wrap;gap:.55rem;margin-top:1rem}.pill{display:inline-flex;border:1px solid rgba(255,255,255,.25);border-radius:999px;padding:.45rem .7rem;color:#eaf8ff;font-weight:800}.container{max-width:var(--max);margin:auto;padding:2rem 1rem}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:1rem}.card{background:#fff;border:1px solid var(--line);border-radius:22px;padding:1.2rem;box-shadow:0 10px 30px rgba(16,32,51,.07)}.card h2,.card h3{margin-top:0}.stat{font-size:2.4rem;font-weight:950;color:#0c4a6e}.notice{border-left:6px solid var(--brand);background:#ecfeff}.warning{border-left-color:var(--accent);background:#fffbeb}.sensitive{border-left-color:var(--red);background:#fff1f2}.cta{display:inline-flex;align-items:center;justify-content:center;margin:.3rem .4rem .3rem 0;padding:.75rem 1rem;border-radius:999px;text-decoration:none;background:#0c4a6e;color:#fff;font-weight:900}.cta.secondary{background:#e0f2fe;color:#0c4a6e}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:18px;background:#fff}table{width:100%;border-collapse:collapse;min-width:680px}th,td{text-align:left;padding:.8rem;border-bottom:1px solid var(--line)}th{background:#eef6ff}.site-footer{background:#07111f;color:#dbeafe;margin-top:3rem}.footer-inner{max-width:var(--max);margin:auto;padding:2.5rem 1rem;display:grid;grid-template-columns:1.1fr repeat(3,.7fr);gap:1.5rem}.site-footer a{color:#bdefff}.footer-bottom{border-top:1px solid rgba(255,255,255,.14);padding:1rem;color:#b7c9dc;text-align:center}.banner-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem}.banner-strip div{min-height:110px;border-radius:20px;background:linear-gradient(135deg,#dff7ff,#ecfdf5);display:flex;align-items:end;padding:1rem;font-weight:900;color:#102033}.breadcrumb{font-weight:800;color:#475467;margin-bottom:1rem}.searchbox{width:100%;padding:1rem;border-radius:16px;border:1px solid var(--line);font-size:1rem}@media (max-width:820px){.hero-inner{grid-template-columns:1fr;padding-top:3rem}.footer-inner{grid-template-columns:1fr}.logo span{font-size:.95rem}.nav{top:68px}.banner-strip{grid-template-columns:1fr}.hero-card{display:none}}
'''

def js():
    return '''
(function(){
 const btn=document.querySelector('.nav-toggle'); const nav=document.querySelector('#site-nav');
 if(btn&&nav){btn.addEventListener('click',()=>{const open=nav.getAttribute('data-open')==='true';nav.setAttribute('data-open',String(!open));btn.setAttribute('aria-expanded',String(!open));});}
 const y=document.querySelector('[data-year]'); if(y)y.textContent=new Date().getFullYear();
 const q=document.querySelector('[data-filter]'); if(q){q.addEventListener('input',()=>{const term=q.value.toLowerCase();document.querySelectorAll('[data-filter-item]').forEach(el=>{el.style.display=el.textContent.toLowerCase().includes(term)?'':'none';});});}
})();
'''

def ensure_assets(out):
    (out/'assets').mkdir(exist_ok=True)
    (out/'assets/aq26-site.css').write_text(css(), encoding='utf-8')
    (out/'assets/aq26-site.js').write_text(js(), encoding='utf-8')

def nav(pages, current, prefix=''):
    links=[]
    for file,title,desc in pages:
        if title in ('Privacy','Terms','Cookies','Accessibility'): continue
        cur=' aria-current="page"' if file==current else ''
        links.append(f'<a href="{prefix}{file}"{cur}>{html.escape(title)}</a>')
    return ''.join(links)

def footer(unredacted=False):
    extra = '<li><a href="/">Public redacted site</a></li>' if unredacted else '<li><a href="/unredacted/">Protected unredacted review area</a></li>'
    return f'''<footer class="site-footer"><div class="footer-inner"><div><h2>AQ26</h2><p>Environmental intelligence observatory for cautious, provenance-led air-quality evidence review. Public outputs are redacted; protected pages support internal evidence assessment.</p><p><strong>Important:</strong> AQ26 publishes screening evidence and provenance. It is not a regulatory determination, medical advice or legal advice.</p></div><div><h3>Site</h3><ul><li><a href="/">Public home</a></li>{extra}<li><a href="/newhaven.html">Newhaven ERF</a></li><li><a href="/methodology.html">Methodology</a></li></ul></div><div><h3>Legal</h3><ul><li><a href="/privacy.html">Privacy</a></li><li><a href="/terms.html">Terms</a></li><li><a href="/cookies.html">Cookies</a></li><li><a href="/accessibility.html">Accessibility</a></li></ul></div><div><h3>Contact</h3><ul><li><a href="/contact.html">Corrections and enquiries</a></li><li><a href="/sources.html">Sources</a></li><li><a href="/downloads.html">Downloads</a></li></ul></div></div><div class="footer-bottom">© <span data-year>{NOW[:4]}</span> SCC Nexus / AQ26. All rights reserved. Public pages are redacted and cautious.</div></footer>'''

def layout(title, desc, body, current, unredacted=False):
    base = CONFIG['unredacted_base_url'] if unredacted else CONFIG['public_base_url']
    pages = CONFIG['unredacted_pages'] if unredacted else CONFIG['public_pages']
    logo='/assets/logo_web.svg' if not unredacted else 'assets/logo_web.svg'
    url = (base.rstrip('/') + '/' + ('' if current=='index.html' else current))
    noindex = '<meta name="robots" content="noindex,nofollow">' if unredacted else '<meta name="robots" content="index,follow">'
    jsonld = {
      '@context':'https://schema.org','@type':'WebPage','name':title,'description':desc,'url':url,
      'publisher':{'@type':'Organization','name':CONFIG['organization'],'url':CONFIG['public_base_url']}
    }
    import json
    return f'''<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} | AQ26</title><meta name="description" content="{html.escape(desc)}">{noindex}<link rel="canonical" href="{html.escape(url)}"><meta property="og:title" content="{html.escape(title)} | AQ26"><meta property="og:description" content="{html.escape(desc)}"><meta property="og:type" content="website"><meta property="og:url" content="{html.escape(url)}"><meta name="twitter:card" content="summary_large_image">{verification()}<link rel="stylesheet" href="assets/aq26-site.css"><link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><script type="application/ld+json">{json.dumps(jsonld,ensure_ascii=False)}</script>{analytics()}</head><body><a class="skip" href="#main">Skip to content</a><header class="site-header"><div class="header-inner"><a class="logo" href="{'index.html' if unredacted else '/'}"><img src="{logo}" alt="AQ26 logo"><span>AQ26<small>{'Protected review area' if unredacted else 'Public redacted site'}</small></span></a><button class="nav-toggle" aria-expanded="false" aria-controls="site-nav">☰ Menu</button><nav id="site-nav" class="nav" data-open="false">{nav(pages,current)}</nav></div></header><main id="main">{body}</main>{footer(unredacted)}<script src="assets/aq26-site.js"></script></body></html>'''

def hero(title, subtitle, unredacted=False):
    badge = 'Protected unredacted review' if unredacted else 'Controlled weekly evidence update'
    return f'''<section class="hero"><div class="hero-inner"><div><span class="eyebrow">{badge}</span><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p><div class="pillrow"><span class="pill">Provenance-first</span><span class="pill">Weekly QA</span><span class="pill">Cautious language</span><span class="pill">Redaction gates</span></div></div><div class="hero-card"><img src="assets/air_quality_web.svg" alt="AQ26 environmental intelligence visual"></div></div></section>'''

def page_body(kind, file, title, desc, unredacted=False):
    b=hero(title, desc, unredacted)
    cards='''<section class="container"><div class="grid"><article class="card"><div class="stat">5</div><h2>Source records</h2><p>Every record should retain timestamp, type, query, output path and checksum where applicable.</p></article><article class="card"><div class="stat">0</div><h2>Leak target</h2><p>Public output must pass redaction checks before deployment.</p></article><article class="card"><div class="stat">7</div><h2>Core checks</h2><p>Navigation, legal pages, analytics hooks, sitemap, robots, canonical URLs and missing-page guards.</p></article></div></section>'''
    if file=='index.html':
        b += cards + '''<section class="container"><article class="card notice"><h2>What this site does</h2><p>AQ26 brings air-quality evidence, source provenance, weekly update discipline and protected operational review into one consistent publication surface. The public site is deliberately cautious and redacted; the protected area contains detailed operational material for authorised review.</p><p><a class="cta" href="newhaven.html">Review Newhaven ERF page</a><a class="cta secondary" href="/unredacted/">Open protected area</a></p></article></section>'''
    elif file=='newhaven.html':
        b += '''<section class="container"><article class="card notice"><h2>Newhaven ERF reference page</h2><p>Newhaven ERF / BV8067IL is used as a controlled reference facility for target/control development, evidence provenance and weekly backfill checks. Public wording remains cautious: screening signals, candidate anomalies and evidence gaps require independent validation.</p></article><div class="grid"><article class="card"><h3>Public view</h3><p>Redacted summaries, methodology, caveats and links to public evidence bundles.</p></article><article class="card"><h3>Protected view</h3><p>Detailed diagnostics, candidate review and operational evidence remain in the password-protected area.</p></article><article class="card"><h3>Next improvements</h3><p>Add date-indexed evidence cards, facility timeline, monitoring locations, map context and plain-English review notes.</p></article></div></section>'''
    elif file in ('privacy.html','terms.html','cookies.html','accessibility.html','contact.html'):
        text={
        'privacy.html':'We collect only the information needed to operate the site, respond to enquiries and understand aggregate site usage. Analytics should be privacy-conscious and configured through the GA_MEASUREMENT_ID secret. Protected unredacted pages are access-controlled and should not be indexed.',
        'terms.html':'AQ26 content is provided for evidence review and public-interest transparency. It is not legal, medical or regulatory advice. Do not rely on screening outputs as final determinations. Reuse requires attribution and respect for third-party source terms.',
        'cookies.html':'The site may use essential cookies for protected access and analytics cookies only where configured. Analytics should be used to understand page performance, device issues and content gaps, not to profile individuals.',
        'accessibility.html':'AQ26 aims to meet WCAG 2.2 AA principles with semantic HTML, visible focus states, alt text, responsive design and readable contrast. Report accessibility issues through the contact page.',
        'contact.html':'For corrections, source updates, missing pages, accessibility issues or data provenance questions, contact SCC Nexus. Include the page URL, the issue, and any supporting source link.'}.get(file,'')
        b += f'''<section class="container"><article class="card"><h2>{html.escape(title)}</h2><p>{html.escape(text)}</p><p><strong>Last reviewed:</strong> {NOW}</p></article></section>'''
    elif file in ('sources.html','methodology.html','downloads.html','historical.html','weekly-update.html','incinerators.html','about.html','evidence.html','candidates.html','diagnostics.html','archive.html'):
        b += f'''<section class="container"><div class="grid"><article class="card"><h2>{html.escape(title)}</h2><p>{html.escape(desc)}</p><p>This page is now present in the uniform AQ26 template and should be connected to generated weekly data files as they are produced.</p></article><article class="card warning"><h3>Publication rule</h3><p>Public pages must use cautious language, avoid personal data, avoid exposed file IDs, and link only to redacted downloads.</p></article><article class="card"><h3>Next content block</h3><p>Add richer narrative, data tables, charts, maps and source cards from the weekly evidence pipeline.</p></article></div></section>'''
    else:
        b += f'''<section class="container"><article class="card"><h2>{html.escape(title)}</h2><p>{html.escape(desc)}</p></article></section>'''
    # page directory and nav list
    pages=CONFIG['unredacted_pages'] if unredacted else CONFIG['public_pages']
    b += '<section class="container"><h2>Page directory</h2><input class="searchbox" data-filter placeholder="Filter pages"><div class="grid">' + ''.join(f'<article class="card" data-filter-item><h3><a href="{p[0]}">{html.escape(p[1])}</a></h3><p>{html.escape(p[2])}</p></article>' for p in pages) + '</div></section>'
    return b

def build_site(out, pages, unredacted=False):
    out.mkdir(parents=True, exist_ok=True); ensure_assets(out)
    for file,title,desc in pages:
        (out/file).write_text(layout(title,desc,page_body('page',file,title,desc,unredacted),file,unredacted), encoding='utf-8')
    # 404 page
    (out/'404.html').write_text(layout('Page not found','AQ26 page not found', hero('Page not found','The page requested was not available. Use the menu or page directory to continue.',unredacted)+'<section class="container"><article class="card"><h2>Try the page directory</h2><p><a class="cta" href="index.html">Return to AQ26 home</a></p></article></section>','404.html',unredacted), encoding='utf-8')
    base=CONFIG['unredacted_base_url'] if unredacted else CONFIG['public_base_url']
    sm=['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    if not unredacted:
        for file,_,_ in pages:
            url=base.rstrip('/')+'/' + ('' if file=='index.html' else file)
            sm.append(f'<url><loc>{url}</loc><lastmod>{NOW}</lastmod><changefreq>weekly</changefreq><priority>{"1.0" if file=="index.html" else "0.7"}</priority></url>')
    sm.append('</urlset>')
    (out/'sitemap.xml').write_text('\n'.join(sm), encoding='utf-8')
    (out/'robots.txt').write_text('User-agent: *\nDisallow: /unredacted/\nSitemap: https://sccairquality.com/sitemap.xml\n' if not unredacted else 'User-agent: *\nDisallow: /\n', encoding='utf-8')

build_site(ROOT/'site_public', CONFIG['public_pages'], False)
build_site(ROOT/'site_unredacted', CONFIG['unredacted_pages'], True)
print('Built AQ26 overhauled public and unredacted sites')
