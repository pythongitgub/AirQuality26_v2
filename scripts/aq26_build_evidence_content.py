#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path.cwd()
PUBLIC = ROOT / "site_public"
UNREDACTED = ROOT / "site_unredacted"
CONFIG_CANDIDATES = [ROOT / "configs" / "aq26_site_config.json", ROOT / "config" / "aq26_site_config.json"]

DEFAULT_CONFIG = {
    "site_name": "AirQuality26 Environmental Intelligence Observatory",
    "short_name": "AQ26",
    "base_url": "https://sccairquality.com",
    "description": "Weekly public-interest air-quality intelligence for Newhaven and surrounding communities.",
    "analytics_id": "",
    "search_console_verification": "",
    "og_image": "/assets/air_quality_web.svg",
    "contact_email": "enquiries@sccairquality.com",
}

def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)

def load_config() -> dict:
    cfg = DEFAULT_CONFIG.copy()
    for path in CONFIG_CANDIDATES:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    cfg.update(data)
                    break
            except Exception as exc:
                print(f"Warning: could not read {path}: {exc}")
    env_ga = os.environ.get("GA_MEASUREMENT_ID") or os.environ.get("AQ26_GA_MEASUREMENT_ID") or os.environ.get("AQ26_ANALYTICS_ID")
    if env_ga:
        cfg["analytics_id"] = env_ga.strip()
    env_verify = os.environ.get("GOOGLE_SITE_VERIFICATION") or os.environ.get("AQ26_GOOGLE_SITE_VERIFICATION") or os.environ.get("SEARCH_CONSOLE_VERIFICATION")
    if env_verify:
        cfg["search_console_verification"] = env_verify.strip()
    env_contact = os.environ.get("AQ26_CONTACT_EMAIL") or os.environ.get("CONTACT_EMAIL") or os.environ.get("SITE_CONTACT_EMAIL")
    if env_contact:
        cfg["contact_email"] = env_contact.strip()
    return cfg

CFG = load_config()
BASE = str(CFG.get("base_url", DEFAULT_CONFIG["base_url"])).rstrip("/")
SITE = str(CFG.get("site_name", DEFAULT_CONFIG["site_name"]))
SHORT = str(CFG.get("short_name", DEFAULT_CONFIG["short_name"]))
DESC = str(CFG.get("description", DEFAULT_CONFIG["description"]))
CONTACT_EMAIL = str(CFG.get("contact_email", DEFAULT_CONFIG["contact_email"])).strip() or DEFAULT_CONFIG["contact_email"]
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def analytics() -> str:
    gid = str(CFG.get("analytics_id") or CFG.get("ga_measurement_id") or "").strip()
    if not gid:
        return ""
    gid_e = esc(gid)
    return (
        f'\n<script async src="https://www.googletagmanager.com/gtag/js?id={gid_e}"></script>\n'
        f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}};"
        f"gtag('js',new Date());gtag('config','{gid_e}');</script>"
    )

def json_ld(url: str) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE,
        "url": BASE,
        "publisher": {"@type": "Organization", "name": "SCC Nexus"},
        "inLanguage": "en-GB",
    }
    if url.endswith("contact.html"):
        data = {
            "@context": "https://schema.org",
            "@type": "ContactPage",
            "name": f"Contact {SHORT}",
            "url": f"{BASE}{url}",
            "email": CONTACT_EMAIL,
            "inLanguage": "en-GB",
        }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + '</script>'

def head(title: str, url: str, noindex: bool=False) -> str:
    canonical = f"{BASE}{url}"
    robots = "noindex,nofollow" if noindex else "index,follow"
    verify_token = str(CFG.get("search_console_verification") or CFG.get("google_site_verification") or "").strip()
    verify = f'<meta name="google-site-verification" content="{esc(verify_token)}">' if verify_token else ""
    og_img = str(CFG.get("og_image", DEFAULT_CONFIG["og_image"]))
    og_url = og_img if og_img.startswith("http") else BASE + og_img
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {esc(SITE)}</title>
<meta name="description" content="{esc(DESC)}">
<meta name="robots" content="{esc(robots)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:title" content="{esc(title)} · {esc(SITE)}">
<meta property="og:description" content="{esc(DESC)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(og_url)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)} · {esc(SITE)}">
<meta name="twitter:description" content="{esc(DESC)}">
<meta name="twitter:image" content="{esc(og_url)}">
{verify}
{json_ld(url)}
{analytics()}
<style>
:root{{--ink:#102033;--muted:#5f6b7a;--line:#d8e0ea;--blue:#0f4c81;--cyan:#0e7490;--bg:#f5f8fc;--card:#fff;--warn:#7c2d12;}}
*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.6}}
a{{color:var(--blue)}}.wrap{{max-width:1180px;margin:0 auto;padding:0 20px}}
header{{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10}}.bar{{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:14px 0}}.brand{{font-weight:800;font-size:1.15rem;text-decoration:none;color:var(--ink)}}.brand small{{display:block;color:var(--muted);font-weight:600;font-size:.76rem}}
nav{{display:flex;gap:12px;flex-wrap:wrap}}nav a{{text-decoration:none;color:var(--ink);font-weight:650;font-size:.92rem;padding:8px 10px;border-radius:10px}}nav a:hover,nav a[aria-current="page"]{{background:#eef4fb}}
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
</head>"""

def header(active: str="") -> str:
    links = [
        ("/", "Home"), ("/newhaven.html", "Newhaven"), ("/source-records.html", "Sources"),
        ("/weekly-update.html", "Weekly update"), ("/archive.html", "Archive"),
        ("/methodology.html", "Methodology"), ("/contact.html", "Contact"), ("/unredacted/", "Unredacted")
    ]
    parts = []
    for url, title in links:
        current = ' aria-current="page"' if title == active else ""
        parts.append(f'<a href="{url}"{current}>{esc(title)}</a>')
    nav = "".join(parts)
    return f'<body><header><div class="wrap bar"><a class="brand" href="/">{esc(SHORT)}<small>Environmental Intelligence Observatory</small></a><button class="menu" onclick="toggleMenu()">☰ Menu</button><nav id="nav">{nav}</nav></div></header>'

def footer() -> str:
    return f"""<footer><div class="wrap footgrid"><div><strong>{esc(SITE)}</strong><p>Weekly evidence tracking, public-interest transparency and protected reviewer material where appropriate.</p><p class="muted">Last rebuilt {esc(NOW)}.</p></div><div><strong>Legal</strong><br><a href="/privacy.html">Privacy</a><br><a href="/terms.html">Terms</a><br><a href="/cookies.html">Cookies</a><br><a href="/accessibility.html">Accessibility</a></div><div><strong>Site</strong><br><a href="/contact.html">Contact</a><br><a href="mailto:{esc(CONTACT_EMAIL)}">{esc(CONTACT_EMAIL)}</a><br><a href="/sitemap.xml">Sitemap</a><br><a href="/unredacted/">Protected evidence</a></div></div><div class="wrap"><p>© 2026 SCC Nexus · AQ26. All rights reserved. Corrections welcome.</p></div></footer><script>document.querySelectorAll('a[href="/unredacted/"]').forEach(a=>a.setAttribute('rel','nofollow'));</script></body></html>"""

def page(title: str, label: str, body: str, url: str, noindex: bool=False, active: str="") -> str:
    return head(title, url, noindex) + header(active) + f'<section class="hero"><div class="wrap"><span class="badge">{esc(label)}</span><h1>{esc(title)}</h1><p>{esc(DESC)}</p></div></section><main class="wrap">{body}</main>' + footer()

def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print("wrote", path)

EVIDENCE_ROWS = [
    ("Weekly evidence bundle", "Latest production evidence archive", "Protected", "Bundle generated by weekly pipeline; kept out of public surface."),
    ("Source record index", "Structured provenance records", "Public/protected", "Timestamp, type, query, output path and SHA256 where available."),
    ("Newhaven ERF reference", "BV8067IL / Newhaven ERF", "Context", "Reference facility for controlled target/control development."),
    ("Redaction gate", "Public surface safety", "Required", "Protected bundles, raw file IDs and secrets must not appear publicly."),
    ("Drive evidence lake", "Indexed evidence storage", "Protected", "File IDs are hashed/redacted on public pages."),
]
TIMELINE = [
    ("Baseline", "Establish cautious public site, protected unredacted library and evidence bundle discipline."),
    ("Weekly production", "Generate source records, readiness notes, public summaries and protected reviewer material."),
    ("Current rebuild", "Restore evidence/history content into a uniform SEO-ready site with footer and legal pages."),
    ("Next phase", "Expand Newhaven timeline, monitoring context, mapping, source confidence and archive filtering."),
]

def rows_table() -> str:
    body = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td><td>{esc(d)}</td></tr>" for a,b,c,d in EVIDENCE_ROWS)
    return "<table><thead><tr><th>Record</th><th>Description</th><th>Status</th><th>Notes</th></tr></thead><tbody>" + body + "</tbody></table>"

def timeline_table() -> str:
    body = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a,b in TIMELINE)
    return "<table><thead><tr><th>Stage</th><th>Purpose</th></tr></thead><tbody>" + body + "</tbody></table>"

def public_pages() -> dict[str, tuple[str, str, str]]:
    email = esc(CONTACT_EMAIL)
    return {
        "weekly-update.html": ("Weekly update", "Weekly update", "<div class='card'><h2>Weekly update</h2><p>The public weekly update summarises redacted evidence, source counts, warnings and evidence-readiness notes. Protected reviewer material remains behind the unredacted login.</p></div>"),
        "archive.html": ("Archive", "Archive", "<div class='card'><h2>Archive</h2><p>Public archive entries will link to redacted weekly reports and summaries. Protected evidence bundles remain in the unredacted downloads library.</p></div>"),
        "methodology.html": ("Methodology", "Methodology", "<div class='card'><h2>Methodology</h2><p>AQ26 uses cautious public-interest language, source traceability, SHA256 checks where available, redaction gates and protected reviewer evidence for unredacted material.</p></div>"),
        "downloads.html": ("Downloads", "Downloads", "<div class='card'><h2>Public downloads</h2><p>Only redacted public downloads should appear here. Protected ZIP bundles remain in the password-protected unredacted area.</p></div>"),
        "privacy.html": ("Privacy", "", f"<div class='card'><h2>Privacy policy</h2><p>AQ26 publishes public-interest environmental information. Public pages avoid exposing personal data, secrets, private file IDs or unredacted reviewer material.</p><p>Contact: <a href='mailto:{email}'>{email}</a></p></div>"),
        "terms.html": ("Terms", "", "<div class='card'><h2>Terms</h2><p>Information is provided for public-interest evidence review and transparency. It is not regulatory, legal, medical or investment advice. Source records and warnings should be interpreted cautiously.</p></div>"),
        "cookies.html": ("Cookies", "", "<div class='card'><h2>Cookies</h2><p>The site may use essential hosting cookies and, where configured, Google Analytics 4. Analytics can be disabled by removing the GA_MEASUREMENT_ID secret/config.</p></div>"),
        "accessibility.html": ("Accessibility", "", "<div class='card'><h2>Accessibility</h2><p>The AQ26 site is designed with responsive layout, semantic headings, clear contrast, keyboard-friendly links and a consistent footer/menu across public and protected pages.</p></div>"),
        "contact.html": ("Contact", "Contact", f"<div class='card'><h2>Contact AQ26</h2><p>For corrections, source queries, evidence issues or accessibility concerns, email <a href='mailto:{email}'>{email}</a>.</p><p>Please include the page URL, source record or evidence bundle reference, and a short description of the correction requested.</p></div>"),
    }

def build_public() -> None:
    PUBLIC.mkdir(exist_ok=True)
    write(PUBLIC/"index.html", page("AirQuality26", "Public site", f"<div class='two'><section class='card'><h2>Public-interest air-quality intelligence</h2><p>{esc(DESC)}</p><p>This public site summarises AQ26 evidence without exposing protected reviewer material.</p><p><a href='/newhaven.html'>Open the Newhaven evidence hub</a> · <a href='/unredacted/'>Protected unredacted evidence area</a></p></section><aside class='card'><h3>Evidence status</h3><p class='muted'>For full reviewer traceability, use the password-protected evidence library.</p></aside></div>", "/", False, "Home"))
    write(PUBLIC/"newhaven.html", page("Newhaven evidence hub", "AQ26 evidence hub", f"<div class='card'><h2>Newhaven ERF context</h2><p>A focused public hub for Newhaven air-quality evidence, weekly reports and source traceability.</p>{timeline_table()}</div><div class='card'><h2>Protected reviewer material</h2><p>Unredacted source records and evidence bundles are available in the protected area.</p><p><a href='/unredacted/newhaven.html'>Open protected Newhaven page</a></p></div>", "/newhaven.html", False, "Newhaven"))
    write(PUBLIC/"source-records.html", page("Source records", "Public source index", f"<div class='card'><h2>Traceable public records</h2>{rows_table()}</div>", "/source-records.html", False, "Sources"))
    for filename, (title, active, body) in public_pages().items():
        write(PUBLIC/filename, page(title, "AQ26", body, f"/{filename}", False, active))
    write(PUBLIC/"robots.txt", "User-agent: *\nAllow: /\nDisallow: /unredacted/\nSitemap: https://sccairquality.com/sitemap.xml\n")
    urls = ["/","/newhaven.html","/source-records.html","/weekly-update.html","/archive.html","/methodology.html","/downloads.html","/privacy.html","/terms.html","/cookies.html","/accessibility.html","/contact.html"]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{BASE}{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    write(PUBLIC/"sitemap.xml", sitemap)

def build_unredacted() -> None:
    UNREDACTED.mkdir(exist_ok=True)
    write(UNREDACTED/"index.html", page("Unredacted evidence library", "Protected unredacted site", "<div class='grid'><section class='card'><h2>Evidence bundles</h2><p>Protected weekly evidence bundles, source indexes and reviewer notes.</p><p><a href='/unredacted/evidence.html'>Open evidence library</a></p></section><section class='card'><h2>Source traceability</h2><p>Structured source records, warnings and provenance.</p><p><a href='/unredacted/source-records.html'>Open source records</a></p></section><section class='card'><h2>Downloads</h2><p>Protected ZIP bundles and latest evidence artefacts.</p><p><a href='/unredacted/downloads.html'>Open downloads</a></p></section></div>", "/unredacted/", True, "Unredacted"))
    write(UNREDACTED/"newhaven.html", page("Newhaven evidence hub", "AQ26 evidence hub", f"<div class='card'><h2>Newhaven ERF context and history</h2><p>Newhaven ERF / BV8067IL remains the reference facility for controlled target/control development. This page preserves protected reviewer context and source traceability.</p>{timeline_table()}</div><div class='card'><h2>Evidence records</h2>{rows_table()}</div>", "/unredacted/newhaven.html", True, "Unredacted"))
    write(UNREDACTED/"evidence.html", page("Evidence library", "Protected evidence library", f"<div class='card'><h2>Evidence bundles and source records</h2>{rows_table()}</div><div class='callout'><strong>Redaction control:</strong> protected pages are noindex and remain behind HTTP Basic Auth.</div>", "/unredacted/evidence.html", True, "Unredacted"))
    write(UNREDACTED/"source-records.html", page("Source records", "Protected source records", f"<div class='card'><h2>Traceable source record index</h2>{rows_table()}</div>", "/unredacted/source-records.html", True, "Unredacted"))
    write(UNREDACTED/"history.html", page("AQ26 history", "Protected history", f"<div class='card'><h2>Evidence and project history</h2>{timeline_table()}</div>", "/unredacted/history.html", True, "Unredacted"))
    write(UNREDACTED/"weekly-update.html", page("Weekly update", "Protected weekly update", "<div class='card'><h2>Protected weekly update</h2><p>Reviewer-facing weekly detail, warnings and traceability notes sit here before redacted public publication.</p></div>", "/unredacted/weekly-update.html", True, "Unredacted"))
    write(UNREDACTED/"downloads.html", page("Protected downloads", "Protected downloads", "<div class='card'><h2>Downloads</h2><p>Protected evidence bundles may be placed in this folder by the weekly pipeline.</p><ul><li><a href='/unredacted/downloads/AQ26_WEEKLY_EVIDENCE_BUNDLE.zip'>AQ26 weekly evidence bundle</a></li><li><a href='/unredacted/downloads/latest-evidence.zip'>Latest evidence ZIP</a></li></ul></div>", "/unredacted/downloads.html", True, "Unredacted"))
    write(UNREDACTED/"diagnostics.html", page("Diagnostics", "Protected diagnostics", "<div class='card'><h2>Diagnostics</h2><p>Deployment, redaction and weekly production diagnostics for reviewers.</p></div>", "/unredacted/diagnostics.html", True, "Unredacted"))
    write(UNREDACTED/"candidates.html", page("Candidates", "Protected candidate signals", "<div class='card'><h2>Candidate signals</h2><p>Screening candidates and unresolved evidence gaps requiring independent validation.</p></div>", "/unredacted/candidates.html", True, "Unredacted"))
    for filename, (title, _active, body) in public_pages().items():
        if filename in {"privacy.html", "terms.html", "cookies.html", "accessibility.html", "contact.html"}:
            write(UNREDACTED/filename, page(title, "Protected legal", body, f"/unredacted/{filename}", True, "Unredacted"))

if __name__ == "__main__":
    build_public()
    build_unredacted()
    print("AQ26 evidence content build completed.")
