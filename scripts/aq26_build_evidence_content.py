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
    "site_name": "Environmental Intelligence Observatory · AQ26",
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

def asset_base(url: str) -> str:
    return "/unredacted/assets" if url.startswith("/unredacted") else "/assets"

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

def json_ld(url: str, title: str) -> str:
    if url.endswith("contact.html"):
        data = {
            "@context": "https://schema.org",
            "@type": "ContactPage",
            "name": f"Contact {SHORT}",
            "url": f"{BASE}{url}",
            "email": CONTACT_EMAIL,
            "inLanguage": "en-GB",
        }
    elif "newhaven" in url:
        data = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": title,
            "url": f"{BASE}{url}",
            "about": ["Newhaven ERF", "air quality evidence", "emissions review"],
            "publisher": {"@type": "Organization", "name": "SCC Nexus"},
            "inLanguage": "en-GB",
        }
    else:
        data = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": SITE,
            "url": BASE,
            "publisher": {"@type": "Organization", "name": "SCC Nexus"},
            "inLanguage": "en-GB",
        }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>"

def head(title: str, url: str, noindex: bool=False) -> str:
    canonical = f"{BASE}{url}"
    robots = "noindex,nofollow" if noindex else "index,follow"
    verify_token = str(CFG.get("search_console_verification") or CFG.get("google_site_verification") or "").strip()
    verify = f'<meta name="google-site-verification" content="{esc(verify_token)}">' if verify_token else ""
    assets = asset_base(url)
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
<link rel="icon" href="{assets}/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{assets}/apple-touch-icon.png">
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
{json_ld(url, title)}
{analytics()}
<style>
:root{{--ink:#13202f;--muted:#5d6a7d;--accent:#d6262f;--blue:#0d3d72;--panel:#ffffff;--bg:#f4f7fb;--line:#dce4ef;--nav:#101b2c;--cyan:#0e7490;--warn:#975a00;}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:var(--bg);color:var(--ink);line-height:1.56}}
a{{color:#0d4f8b}}.wrap{{max-width:1180px;margin:0 auto;padding:0 1rem}}
header.site-header{{position:sticky;top:0;z-index:50;background:#fff;border-bottom:1px solid var(--line);box-shadow:0 4px 18px rgba(10,35,65,.08)}}
.topbar{{max-width:1180px;margin:auto;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.7rem 1rem}}.brand{{display:flex;align-items:center;text-decoration:none;color:var(--ink)}}.brand img{{height:58px;max-width:330px;width:auto;display:block}}.brand-text{{font-weight:900;letter-spacing:-.02em}}.brand-text small{{display:block;color:var(--muted);font-size:.76rem;font-weight:700}}
.menu-toggle{{display:none;border:1px solid var(--line);background:#fff;border-radius:12px;padding:.55rem .75rem;font-size:1.05rem;font-weight:900;color:var(--ink)}}
nav.primary{{display:flex;gap:.25rem;flex-wrap:wrap;align-items:center}}nav.primary a{{color:var(--ink);text-decoration:none;padding:.55rem .7rem;border-radius:11px;font-weight:800;font-size:.9rem}}nav.primary a:hover,nav.primary a[aria-current="page"]{{background:#f8dadd;color:#a30f19}}
.hero{{position:relative;overflow:hidden;color:#fff;background:linear-gradient(120deg,#0d2038,#204f82 50%,#d6262f);min-height:390px;display:flex;align-items:flex-end}}.hero-media{{position:absolute;inset:0;z-index:0;background:#0d2038}}.hero-media video,.hero-media img{{width:100%;height:100%;object-fit:cover;opacity:.48;filter:saturate(1.05) contrast(1.05)}}.hero::after{{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(13,32,56,.92),rgba(13,32,56,.62),rgba(214,38,47,.58));z-index:1}}.hero-inner{{position:relative;z-index:2;width:100%;padding:4rem 1rem 3rem}}.hero h1{{font-size:clamp(2.25rem,6vw,4.8rem);line-height:1.02;margin:.25rem 0 .8rem;max-width:980px;letter-spacing:-.045em}}.hero p{{font-size:clamp(1rem,2vw,1.25rem);max-width:850px;margin:0;color:#eef7ff}}.badge{{display:inline-block;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);border-radius:999px;padding:.42rem .75rem;font-weight:900;font-size:.78rem;text-transform:uppercase;letter-spacing:.045em}}
.ticker{{background:#10243d;color:#fff;white-space:nowrap;overflow:hidden}}.ticker span{{display:inline-block;padding:.7rem 0;animation:aqscroll 30s linear infinite}}@keyframes aqscroll{{from{{transform:translateX(100%)}}to{{transform:translateX(-100%)}}}}
main{{padding:1.4rem 0 3rem}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem}}.two{{display:grid;grid-template-columns:2fr 1fr;gap:1rem}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:1.1rem;box-shadow:0 8px 24px rgba(15,40,70,.06);margin-bottom:1rem}}.card h2,.card h3{{margin-top:0}}.metric{{font-size:2rem;font-weight:900;color:var(--blue)}}.muted{{color:var(--muted)}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}}th,td{{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:.72rem}}th{{background:#eef3f9;font-size:.9rem}}tr:last-child td{{border-bottom:0}}pre{{white-space:pre-wrap;background:#0f1f34;color:#e8f1ff;border-radius:14px;padding:1rem;overflow:auto}}.callout{{border-left:5px solid var(--cyan);background:#ecfeff;padding:1rem;border-radius:12px;margin:1rem 0}}.risk{{border-left-color:var(--warn);background:#fff7ed}}
footer{{background:#101b2c;color:#dce8f6;padding:2rem 1rem;margin-top:2rem}}footer a{{color:#dbeafe}}.footgrid{{max-width:1180px;margin:auto;display:grid;grid-template-columns:2fr 1fr 1fr;gap:1rem}}.copyright{{max-width:1180px;margin:1rem auto 0;color:#dce8f6}}
@media(max-width:860px){{.menu-toggle{{display:block}}nav.primary{{display:none;width:100%;flex-direction:column;align-items:stretch}}nav.primary.open{{display:flex}}.topbar{{flex-wrap:wrap}}.brand img{{height:46px;max-width:250px}}.hero{{min-height:340px}}.two,.footgrid{{grid-template-columns:1fr}}}}
</style>
<script>function toggleMenu(){{document.getElementById('nav').classList.toggle('open')}}</script>
</head>"""

def header(active: str="", noindex: bool=False) -> str:
    links = [
        ("/", "Overview"), ("/newhaven.html", "Newhaven"), ("/weekly-update.html", "Weekly update"),
        ("/source-records.html", "Sources"), ("/archive.html", "Archive"), ("/methodology.html", "Methodology"),
        ("/contact.html", "Contact"), ("/unredacted/", "Unredacted")
    ]
    parts = []
    for url, title in links:
        current = ' aria-current="page"' if title == active else ""
        parts.append(f'<a href="{url}"{current}>{esc(title)}</a>')
    nav = "".join(parts)
    logo = "/unredacted/assets/air_quality_web.svg" if noindex else "/assets/air_quality_web.svg"
    return f'<body><header class="site-header"><div class="topbar"><a class="brand" href="/" aria-label="AirQuality26 home"><img src="{logo}" alt="SCC Nexus Air Quality Report"></a><button class="menu-toggle" onclick="toggleMenu()" aria-label="Open menu">☰</button><nav class="primary" id="nav">{nav}</nav></div></header>'

def footer() -> str:
    email = esc(CONTACT_EMAIL)
    return f"""<footer><div class="footgrid"><div><strong>{esc(SITE)}</strong><p>Weekly evidence tracking, public-interest transparency and protected reviewer material where appropriate.</p><p class="muted">Last rebuilt {esc(NOW)}.</p></div><div><strong>Legal</strong><br><a href="/privacy.html">Privacy</a><br><a href="/terms.html">Terms</a><br><a href="/cookies.html">Cookies</a><br><a href="/accessibility.html">Accessibility</a></div><div><strong>Site</strong><br><a href="/contact.html">Contact</a><br><a href="mailto:{email}">{email}</a><br><a href="/sitemap.xml">Sitemap</a><br><a href="/unredacted/">Protected evidence</a></div></div><p class="copyright">© 2026 SCC Nexus · AQ26. All rights reserved. Corrections welcome.</p></footer><script>document.querySelectorAll('a[href="/unredacted/"]').forEach(a=>a.setAttribute('rel','nofollow'));</script></body></html>"""

def hero(title: str, label: str, url: str) -> str:
    assets = asset_base(url)
    return f"""<section class="hero"><div class="hero-media"><video autoplay muted loop playsinline poster="{assets}/banners/desktop_banner_1_web.svg"><source src="{assets}/banners/desktop_banner_1.webm" type="video/webm"></video></div><div class="hero-inner wrap"><span class="badge">{esc(label)}</span><h1>{esc(title)}</h1><p>{esc(DESC)}</p></div></section><div class="ticker"><span>Weekly AQ26 evidence update · source traceability · redaction control · Newhaven ERF context · protected reviewer library · </span></div>"""

def page(title: str, label: str, body: str, url: str, noindex: bool=False, active: str="") -> str:
    return head(title, url, noindex) + header(active, noindex) + hero(title, label, url) + f'<main class="wrap">{body}</main>' + footer()

def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print("wrote", path)

EVIDENCE_ROWS = [
    ("Weekly evidence bundle", "Latest production evidence archive", "Protected", "Bundle generated by weekly pipeline; kept in the unredacted library."),
    ("Newhaven ERF reference", "BV8067IL / Newhaven ERF", "Context", "Reference facility for controlled target/control development."),
    ("Redaction gate", "Public surface safety", "Required", "Protected bundles, raw file IDs and secrets must not appear publicly."),
    ("Drive evidence lake", "Indexed evidence storage", "Protected", "File IDs are hashed/redacted on public pages."),
]
TIMELINE = [
    ("Baseline", "Establish cautious public site, protected unredacted library and evidence bundle discipline."),
    ("Weekly production", "Generate source records, readiness notes, public summaries and protected reviewer material."),
    ("Visual restoration", "Restore AQ26 header, logo, moving banner, cards and footer into the evidence build."),
    ("Next phase", "Expand Newhaven timeline, monitoring context, mapping, source confidence and archive filtering."),
]

def rows_table() -> str:
    body = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td><td>{esc(d)}</td></tr>" for a,b,c,d in EVIDENCE_ROWS)
    return "<table><thead><tr><th>Record</th><th>Description</th><th>Status</th><th>Notes</th></tr></thead><tbody>" + body + "</tbody></table>"

def timeline_table() -> str:
    body = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a,b in TIMELINE)
    return "<table><thead><tr><th>Stage</th><th>Purpose</th></tr></thead><tbody>" + body + "</tbody></table>"

def metric_cards() -> str:
    return """<div class="grid"><div class="card"><div class="metric">5</div><strong>source records</strong><p class="muted">Every source record has timestamp, type, query, output path and SHA256 where applicable.</p></div><div class="card"><div class="metric">4</div><strong>OK records</strong><p class="muted">Warnings are preserved rather than hidden.</p></div><div class="card"><div class="metric">18023</div><strong>Drive files indexed</strong><p class="muted">File IDs are hashed; links are redacted.</p></div><div class="card"><div class="metric">0</div><strong>redaction leaks target</strong><p class="muted">Any detected secret leak fails the workflow.</p></div></div>"""

def public_pages() -> dict[str, tuple[str, str, str]]:
    email = esc(CONTACT_EMAIL)
    return {
        "weekly-update.html": ("Weekly update", "Weekly update", "<div class='card'><h2>Weekly update</h2><p>The public weekly update summarises redacted evidence, source counts, warnings and evidence-readiness notes. Protected reviewer material remains behind the unredacted login.</p></div>"),
        "archive.html": ("Archive", "Archive", "<div class='card'><h2>Archive</h2><p>Public archive entries link to redacted weekly reports and summaries. Protected evidence bundles remain in the unredacted downloads library.</p></div>"),
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
    home_body = f"<div class='two'><section class='card'><h2>Public-interest air-quality intelligence</h2><p>{esc(DESC)}</p><p>This public site summarises AQ26 evidence without exposing protected reviewer material.</p><p><a href='/newhaven.html'>Open the Newhaven evidence hub</a> · <a href='/unredacted/'>Protected unredacted evidence area</a></p></section><aside class='card'><h3>Evidence status</h3><p class='muted'>For full reviewer traceability, use the password-protected evidence library.</p></aside></div>{metric_cards()}<div class='card'><h2>Weekly highlight</h2><p>Newhaven ERF / BV8067IL remains the reference facility for controlled target/control development. This public page uses cautious language: screening signals, candidate anomalies and evidence gaps require independent validation.</p></div>"
    write(PUBLIC/"index.html", page("Air-quality evidence observatory for incinerator and control-site review.", "Controlled weekly evidence update", home_body, "/", False, "Overview"))
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
    print("AQ26 evidence content build completed with visual branding restored.")
