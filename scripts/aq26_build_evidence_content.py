#!/usr/bin/env python3
"""
AQ26 evidence content builder.
Builds evidence/history pages into site_public and site_unredacted without touching auth files.
Designed to work with the existing AQ26 repo layout, including configs/aq26_site_config.json.
"""
from __future__ import annotations

import json
import html
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path.cwd()
CONFIG_CANDIDATES = [ROOT / "configs" / "aq26_site_config.json", ROOT / "config" / "aq26_site_config.json"]
PUBLIC = ROOT / "site_public"
UNREDACTED = ROOT / "site_unredacted"
SEED = ROOT / "content_seed"

DEFAULT_CONFIG = {
    "site_name": "AirQuality26 Environmental Intelligence Observatory",
    "short_name": "AQ26",
    "base_url": "https://sccairquality.com",
    "description": "Weekly public-interest air-quality intelligence for Newhaven and surrounding communities.",
    "analytics_id": "",
    "search_console_verification": ""
}

def load_config() -> dict:
    for p in CONFIG_CANDIDATES:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {**DEFAULT_CONFIG, **data}
            except Exception:
                pass
    return DEFAULT_CONFIG

CFG = load_config()
BASE = str(CFG.get("base_url", "https://sccairquality.com")).rstrip("/")
SITE = CFG.get("site_name", DEFAULT_CONFIG["site_name"])
SHORT = CFG.get("short_name", "AQ26")
DESC = CFG.get("description", DEFAULT_CONFIG["description"])
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def esc(x: object) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)

def analytics() -> str:
    gid = (CFG.get("analytics_id") or CFG.get("ga_measurement_id") or "").strip()
    if not gid:
        return ""
    return f'''\n<script async src="https://www.googletagmanager.com/gtag/js?id={esc(gid)}"></script>\n<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}};gtag('js',new Date());gtag('config','{esc(gid)}');</script>'''

def head(title: str, url: str, noindex: bool=False) -> str:
    canonical = f"{BASE}{url}"
    robots = "noindex,nofollow" if noindex else "index,follow"
    ver = CFG.get("search_console_verification") or CFG.get("google_site_verification") or ""
    verify = f'<meta name="google-site-verification" content="{esc(ver)}">' if ver else ""
    return f'''<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {esc(SITE)}</title>
<meta name="description" content="{esc(DESC)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:title" content="{esc(title)} · {esc(SITE)}">
<meta property="og:description" content="{esc(DESC)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)} · {esc(SITE)}">
<meta name="twitter:description" content="{esc(DESC)}">
{verify}
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"WebSite","name":{json.dumps(SITE)},"url":{json.dumps(BASE)}}}</script>
{analytics()}
<style>
:root{{--ink:#102033;--muted:#5f6b7a;--line:#d8e0ea;--blue:#0f4c81;--cyan:#0e7490;--bg:#f5f8fc;--card:#fff;--warn:#7c2d12;}}
*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.6}}
a{{color:var(--blue)}}.wrap{{max-width:1180px;margin:0 auto;padding:0 20px}}
header{{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10}}.bar{{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:14px 0}}.brand{{font-weight:800;font-size:1.15rem;text-decoration:none;color:var(--ink)}}.brand small{{display:block;color:var(--muted);font-weight:600;font-size:.76rem}}
nav{{display:flex;gap:12px;flex-wrap:wrap}}nav a{{text-decoration:none;color:var(--ink);font-weight:650;font-size:.92rem;padding:8px 10px;border-radius:10px}}nav a:hover{{background:#eef4fb}}
.menu{{display:none;background:#fff;border:1px solid var(--line);border-radius:12px;padding:9px 11px;font-weight:800}}
.hero{{background:linear-gradient(135deg,#0f4c81,#0e7490);color:#fff;padding:54px 0}}.hero p{{font-size:1.15rem;max-width:820px}}
.badge{{display:inline-block;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.25);border-radius:999px;padding:6px 12px;font-weight:800;font-size:.82rem;text-transform:uppercase;letter-spacing:.04em}}
main{{padding:32px 0}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}}.two{{display:grid;grid-template-columns:2fr 1fr;gap:18px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:0 4px 18px rgba(16,32,51,.05)}}.card h2,.card h3{{margin-top:0}}.muted{{color:var(--muted)}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}}th,td{{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:10px}}th{{background:#eaf2fb;font-size:.9rem}}tr:last-child td{{border-bottom:0}}
.callout{{border-left:5px solid var(--cyan);background:#ecfeff;padding:15px;border-radius:12px}}.risk{{border-left-color:var(--warn);background:#fff7ed}}
footer{{background:#102033;color:#dbe7f5;margin-top:36px;padding:30px 0}}footer a{{color:#dbeafe}}.footgrid{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:18px}}
@media(max-width:820px){{.menu{{display:block}}nav{{display:none;width:100%;flex-direction:column}}nav.open{{display:flex}}.bar{{align-items:flex-start;flex-wrap:wrap}}.grid,.two,.footgrid{{grid-template-columns:1fr}}}}
</style>
<script>function toggleMenu(){{document.getElementById('nav').classList.toggle('open')}}</script>
</head>'''

def header(active: str="") -> str:
    links = [
        ("/", "Home"), ("/newhaven.html", "Newhaven"), ("/source-records.html", "Sources"), ("/weekly-update.html", "Weekly update"), ("/archive.html", "Archive"), ("/methodology.html", "Methodology"), ("/contact.html", "Contact"), ("/unredacted/", "Unredacted")
    ]
    parts = []
    for u, t in links:
        current = ' aria-current="page"' if t == active else ''
        parts.append(f'<a href="{u}"{current}>{t}</a>')
    nav = "".join(parts)
    return f'''<body><header><div class="wrap bar"><a class="brand" href="/">{esc(SHORT)}<small>Environmental Intelligence Observatory</small></a><button class="menu" onclick="toggleMenu()">☰ Menu</button><nav id="nav">{nav}</nav></div></header>'''

def footer() -> str:
    return f'''<footer><div class="wrap footgrid"><div><strong>{esc(SITE)}</strong><p>Weekly evidence tracking, public-interest transparency and protected reviewer material where appropriate.</p><p class="muted">Last rebuilt {esc(NOW)}.</p></div><div><strong>Legal</strong><br><a href="/privacy.html">Privacy</a><br><a href="/terms.html">Terms</a><br><a href="/cookies.html">Cookies</a><br><a href="/accessibility.html">Accessibility</a></div><div><strong>Site</strong><br><a href="/contact.html">Contact</a><br><a href="/sitemap.xml">Sitemap</a><br><a href="/unredacted/">Protected evidence</a></div></div><div class="wrap"><p>© 2026 SCC Nexus · AQ26. All rights reserved. Corrections welcome.</p></div></footer><script>document.querySelectorAll('a[href="/unredacted/"]').forEach(a=>a.setAttribute('rel','nofollow'));</script></body></html>'''

def page(title: str, label: str, body: str, url: str, noindex: bool=False, active: str="") -> str:
    return head(title, url, noindex) + header(active) + f'<section class="hero"><div class="wrap"><span class="badge">{esc(label)}</span><h1>{esc(title)}</h1></div></section><main class="wrap">{body}</main>' + footer()

EVIDENCE_ROWS = [
    ("Weekly evidence bundle", "Latest production evidence archive", "Protected", "Bundle generated by weekly AQ26 pipeline; expected to contain source indexes, readiness checks, monitoring extracts and reviewer notes."),
    ("Newhaven ERF context", "Facility and local receptor context", "Public / protected", "Newhaven Energy Recovery Facility, local receptors, road corridors, weather context and monitoring evidence."),
    ("Source records", "Traceable evidence index", "Public / protected", "Catalogues documents, APIs, monitoring feeds, official registers and evidence provenance."),
    ("Readiness gates", "Quality and completeness checks", "Protected", "Used to decide whether a weekly report can be published or needs review."),
    ("History timeline", "Operational and documentary chronology", "Public / protected", "Chronology for permits, monitoring, complaints, filings, satellite evidence and website changes."),
]

def rows_table(rows=EVIDENCE_ROWS) -> str:
    trs = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td><td>{esc(d)}</td></tr>" for a,b,c,d in rows)
    return f"<table><thead><tr><th>Record</th><th>Purpose</th><th>Status</th><th>Notes</th></tr></thead><tbody>{trs}</tbody></table>"

NEW_HAVEN_TIMELINE = [
    ("Facility context", "Newhaven ERF is treated as the core local point-source context for AQ26 weekly evidence review."),
    ("Monitoring context", "Evidence should combine local monitoring feeds, official public datasets, weather conditions and receptor proximity."),
    ("Weekly pipeline", "Each weekly run should produce source records, evidence bundles, readiness gates and a public summary where appropriate."),
    ("Protected reviewer layer", "Unredacted material remains behind HTTP Basic Auth and noindex controls to reduce accidental disclosure."),
]

def timeline_table() -> str:
    return "<table><thead><tr><th>Theme</th><th>Evidence role</th></tr></thead><tbody>" + "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a,b in NEW_HAVEN_TIMELINE) + "</tbody></table>"

def write(path: Path, html_text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")
    print(f"wrote {path}")

def build_public():
    PUBLIC.mkdir(exist_ok=True)
    write(PUBLIC/"index.html", page("AirQuality26", "Public site", f"<div class='two'><section class='card'><h2>Public-interest air-quality intelligence</h2><p>{esc(DESC)}</p><p>This public site summarises AQ26 evidence without exposing protected reviewer material.</p><p><a href='/newhaven.html'>Open the Newhaven evidence hub</a> · <a href='/unredacted/'>Protected unredacted evidence area</a></p></section><aside class='card'><h3>Evidence status</h3><p class='muted'>For full reviewer traceability, use the password-protected evidence library.</p></aside></div>", "/", False, "Home"))
    write(PUBLIC/"newhaven.html", page("Newhaven evidence hub", "AQ26 evidence hub", f"<div class='card'><h2>Newhaven ERF context</h2><p>A focused public hub for Newhaven air-quality evidence, weekly reports and source traceability.</p>{timeline_table()}</div><div class='card'><h2>Protected reviewer material</h2><p>Unredacted source records and evidence bundles are available in the protected area.</p><p><a href='/unredacted/newhaven.html'>Open protected Newhaven page</a></p></div>", "/newhaven.html", False, "Newhaven"))
    write(PUBLIC/"source-records.html", page("Source records", "Public source index", f"<div class='card'><h2>Traceable public records</h2>{rows_table()}</div>", "/source-records.html", False, "Sources"))
    for name,title in [("weekly-update.html","Weekly update"),("archive.html","Archive"),("methodology.html","Methodology"),("privacy.html","Privacy"),("terms.html","Terms"),("cookies.html","Cookies"),("accessibility.html","Accessibility"),("contact.html","Contact")]:
        write(PUBLIC/name, page(title, "AQ26", f"<div class='card'><h2>{esc(title)}</h2><p>This page is part of the AQ26 rebuilt site shell and will be expanded by the weekly production pipeline.</p></div>", f"/{name}", False, title if title in ["Weekly update","Archive","Methodology","Contact"] else ""))
    write(PUBLIC/"robots.txt", "User-agent: *\nAllow: /\nDisallow: /unredacted/\nSitemap: https://sccairquality.com/sitemap.xml\n")
    urls = ["/","/newhaven.html","/source-records.html","/weekly-update.html","/archive.html","/methodology.html","/privacy.html","/terms.html","/cookies.html","/accessibility.html","/contact.html"]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f"<url><loc>{BASE}{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    write(PUBLIC/"sitemap.xml", sm)

def build_unredacted():
    UNREDACTED.mkdir(exist_ok=True)
    un_nav = lambda: "<p><a href='/unredacted/evidence.html'>Evidence library</a> · <a href='/unredacted/source-records.html'>Source records</a> · <a href='/unredacted/newhaven.html'>Newhaven hub</a> · <a href='/unredacted/history.html'>History</a> · <a href='/unredacted/downloads.html'>Downloads</a></p>"
    write(UNREDACTED/"index.html", page("Unredacted evidence library", "Protected unredacted site", f"<div class='card'><h2>Reviewer evidence dashboard</h2><p>This protected area restores the AQ26 evidence/history layer behind HTTP Basic Auth.</p>{un_nav()}{rows_table()}</div>", "/unredacted/", True, "Unredacted"))
    write(UNREDACTED/"newhaven.html", page("Newhaven evidence hub", "Protected AQ26 evidence hub", f"<div class='card'><h2>Newhaven ERF evidence context</h2><p>Protected reviewer hub for Newhaven ERF history, local receptors, monitoring context, weather signals and weekly evidence traceability.</p>{timeline_table()}</div><div class='card'><h2>Weekly evidence handling</h2><p>Use this page to link reviewer notes, bundle outputs, source records, local-monitoring extracts and readiness decisions.</p>{un_nav()}</div>", "/unredacted/newhaven.html", True, "Unredacted"))
    write(UNREDACTED/"evidence.html", page("Protected evidence library", "Evidence bundles", f"<div class='card'><h2>Evidence records</h2>{rows_table()}</div><div class='card'><h2>Bundle locations</h2><p>Expected weekly bundle locations include <code>/unredacted/downloads.html</code>, uploaded archives, and any generated evidence ZIP retained by the weekly production pipeline.</p></div>", "/unredacted/evidence.html", True, "Unredacted"))
    write(UNREDACTED/"source-records.html", page("Source records", "Traceability", f"<div class='card'><h2>Source traceability index</h2>{rows_table()}</div><div class='callout'><strong>Discipline:</strong> every public claim should map back to a source record, capture date, confidence status and redaction status.</div>", "/unredacted/source-records.html", True, "Unredacted"))
    write(UNREDACTED/"history.html", page("AQ26 history and evidence timeline", "History", f"<div class='card'><h2>Evidence chronology</h2>{timeline_table()}</div>", "/unredacted/history.html", True, "Unredacted"))
    write(UNREDACTED/"weekly-update.html", page("Weekly update", "Protected weekly update", f"<div class='card'><h2>Weekly update workspace</h2><p>Protected summary for the latest AQ26 weekly evidence cycle.</p>{rows_table()}</div>", "/unredacted/weekly-update.html", True, "Unredacted"))
    write(UNREDACTED/"downloads.html", page("Downloads", "Protected downloads", "<div class='card'><h2>Evidence downloads</h2><p>Place weekly evidence bundles, source indexes and reviewer packs here. The deploy script preserves auth controls.</p><ul><li><a href='latest-evidence.zip'>latest-evidence.zip</a></li><li><a href='AQ26_WEEKLY_EVIDENCE_BUNDLE.zip'>AQ26_WEEKLY_EVIDENCE_BUNDLE.zip</a></li></ul></div>", "/unredacted/downloads.html", True, "Unredacted"))
    write(UNREDACTED/"diagnostics.html", page("Diagnostics", "Protected diagnostics", "<div class='card'><h2>Pipeline diagnostics</h2><p>Use this page for quality gates, source gaps, redaction checks and deployment status notes.</p></div>", "/unredacted/diagnostics.html", True, "Unredacted"))
    write(UNREDACTED/"candidates.html", page("Candidate evidence", "Protected candidates", "<div class='card'><h2>Candidate records</h2><p>Evidence candidates awaiting reviewer confidence checks and public/redacted classification.</p></div>", "/unredacted/candidates.html", True, "Unredacted"))
    for name,title in [("privacy.html","Privacy"),("terms.html","Terms"),("cookies.html","Cookies"),("accessibility.html","Accessibility"),("contact.html","Contact")]:
        write(UNREDACTED/name, page(title, "Protected legal", f"<div class='card'><h2>{esc(title)}</h2><p>Protected copy of the site legal/contact page for reviewer navigation.</p></div>", f"/unredacted/{name}", True, "Unredacted"))

if __name__ == "__main__":
    build_public()
    build_unredacted()
    print("AQ26 evidence content build completed.")
