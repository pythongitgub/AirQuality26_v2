#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
PUBLIC = ROOT / "site_public"
UNREDACTED = ROOT / "site_unredacted"
BASE = "https://sccairquality.com"
SITE = "Environmental Intelligence Observatory · AQ26"
DESC = "Weekly public-interest air-quality intelligence for Newhaven and surrounding communities."
CONTACT_EMAIL = os.environ.get("AQ26_CONTACT_EMAIL", "enquiries@sccairquality.com")
GA_ID = os.environ.get("GA_MEASUREMENT_ID", "") or os.environ.get("AQ26_GA_MEASUREMENT_ID", "") or "G-MV116PW7GF"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

SCAN_ROOTS = [
    "outputs", "docs", "data_sources", "content_seed", ".aq26_weekly_alerts",
    "site_unredacted/downloads", "configs", "notebooks"
]
EXCLUDE_PARTS = {".git", ".github", "__pycache__", ".ipynb_checkpoints", "node_modules"}
PROTECTED_KEYWORDS = (
    "evidence", "source", "record", "readiness", "gate", "backfill", "satellite", "catalogue",
    "newhaven", "bv8067il", "incinerator", "erf", "laqn", "ukair", "earthdata", "sentinel",
    "cems", "permit", "monitor", "anomaly", "candidate", "diagnostic", "weekly"
)

@dataclass
class EvidenceFile:
    path: Path
    rel: str
    size: int
    mtime: str
    suffix: str
    sha256: str
    keywords: str
    public_safe: bool


def esc(v: object) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def file_sha256(path: Path, max_bytes: int = 50_000_000) -> str:
    size = path.stat().st_size
    if size > max_bytes:
        return f"skipped-large-{size}b"
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_read_text(path: Path, limit: int = 400_000) -> str:
    try:
        if path.stat().st_size > limit:
            with path.open("rb") as fh:
                return fh.read(limit).decode("utf-8", "replace")
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def is_public_safe(rel: str) -> bool:
    low = rel.lower()
    if "unredacted" in low or "private" in low or "secret" in low or low.endswith(".zip"):
        return False
    return True


def classify_keywords(rel: str, text_sample: str = "") -> str:
    low = (rel + " " + text_sample[:2000]).lower()
    hits = [k for k in PROTECTED_KEYWORDS if k in low]
    return ", ".join(dict.fromkeys(hits)) or "general"


def collect_files() -> list[EvidenceFile]:
    files: list[EvidenceFile] = []
    for root_name in SCAN_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in EXCLUDE_PARTS for part in path.parts):
                continue
            rel = path.relative_to(ROOT).as_posix()
            if path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".webm", ".svg", ".css", ".js"} and "downloads" not in rel:
                continue
            stat = path.stat()
            sample = safe_read_text(path, 60_000) if path.suffix.lower() in {".json", ".csv", ".yml", ".yaml", ".md", ".txt", ".html"} else ""
            files.append(EvidenceFile(
                path=path,
                rel=rel,
                size=stat.st_size,
                mtime=datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                suffix=path.suffix.lower().lstrip(".") or "file",
                sha256=file_sha256(path),
                keywords=classify_keywords(rel, sample),
                public_safe=is_public_safe(rel),
            ))
    files.sort(key=lambda f: (f.mtime, f.rel), reverse=True)
    return files


def flatten_json_records(obj: Any, source: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    def add_record(item: Any, hint: str) -> None:
        if isinstance(item, dict):
            rec = dict(item)
            rec.setdefault("_source_file", source)
            rec.setdefault("_section", hint)
            records.append(rec)
    def walk(x: Any, hint: str = "root", depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(x, dict):
            for k, v in x.items():
                lk = str(k).lower()
                if isinstance(v, list) and any(word in lk for word in ["record", "source", "evidence", "candidate", "diagnostic", "gate", "archive"]):
                    for item in v[:500]:
                        add_record(item, str(k))
                elif isinstance(v, (dict, list)):
                    walk(v, str(k), depth + 1)
        elif isinstance(x, list):
            for item in x[:500]:
                if isinstance(item, dict):
                    add_record(item, hint)
                elif isinstance(item, (dict, list)):
                    walk(item, hint, depth + 1)
    walk(obj)
    return records


def collect_records(files: list[EvidenceFile]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for f in files:
        if f.path.stat().st_size > 20_000_000:
            continue
        suf = f.suffix
        try:
            if suf == "json":
                obj = json.loads(f.path.read_text(encoding="utf-8", errors="replace"))
                records.extend(flatten_json_records(obj, f.rel))
            elif suf == "csv":
                with f.path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
                    for i, row in enumerate(csv.DictReader(fh)):
                        if i >= 500:
                            break
                        row = dict(row)
                        row.setdefault("_source_file", f.rel)
                        row.setdefault("_section", "csv")
                        records.append(row)
        except Exception as exc:
            records.append({"_source_file": f.rel, "_section": "parse-warning", "warning": str(exc)})
    # de-duplicate by JSON string prefix
    seen = set()
    out = []
    for r in records:
        key = json.dumps(r, sort_keys=True, default=str)[:1000]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def copy_protected_downloads(files: list[EvidenceFile]) -> None:
    downloads = UNREDACTED / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    wanted = [f for f in files if f.suffix in {"zip", "pdf", "xlsx", "csv", "json"} and any(k in f.rel.lower() for k in ["evidence", "weekly", "bundle", "source", "readiness", "backfill"])]
    for f in wanted[:80]:
        dest = downloads / f.path.name
        try:
            if f.path.resolve() != dest.resolve():
                shutil.copy2(f.path, dest)
        except Exception:
            pass


def analytics() -> str:
    if not GA_ID:
        return ""
    gid = esc(GA_ID)
    return f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}};gtag("js",new Date());gtag("config","{gid}");</script>'


def assets_for(url: str) -> str:
    return "/unredacted/assets" if url.startswith("/unredacted/") else "/assets"


def banner_for(url: str) -> str:
    mapping = {
        "/": "desktop_banner_1.webm",
        "/index.html": "desktop_banner_1.webm",
        "/newhaven.html": "desktop_banner_2.webm",
        "/source-records.html": "desktop_banner_3.webm",
        "/weekly-update.html": "desktop_banner_4.webm",
        "/archive.html": "desktop_banner_5.webm",
        "/methodology.html": "desktop_banner_6.webm",
        "/unredacted/": "desktop_banner_2.webm",
        "/unredacted/newhaven.html": "desktop_banner_2.webm",
        "/unredacted/source-records.html": "desktop_banner_3.webm",
        "/unredacted/weekly-update.html": "desktop_banner_4.webm",
        "/unredacted/history.html": "desktop_banner_5.webm",
        "/unredacted/evidence.html": "desktop_banner_6.webm",
    }
    return mapping.get(url, "desktop_banner_1.webm")


def head(title: str, url: str, noindex: bool = False) -> str:
    canonical = BASE + url
    robots = "noindex,nofollow" if noindex else "index,follow"
    assets = assets_for(url)
    og = BASE + assets.replace("/unredacted", "") + "/air_quality_web.svg"
    return f'''<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {esc(SITE)}</title><meta name="description" content="{esc(DESC)}"><meta name="robots" content="{robots}"><link rel="canonical" href="{esc(canonical)}">
<meta property="og:title" content="{esc(title)} · {esc(SITE)}"><meta property="og:description" content="{esc(DESC)}"><meta property="og:type" content="website"><meta property="og:url" content="{esc(canonical)}"><meta property="og:image" content="{esc(og)}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)} · {esc(SITE)}"><meta name="twitter:description" content="{esc(DESC)}"><meta name="twitter:image" content="{esc(og)}">
<script type="application/ld+json">{json.dumps({"@context":"https://schema.org","@type":"WebPage","name":title,"url":canonical,"isPartOf":{"@type":"WebSite","name":SITE,"url":BASE},"publisher":{"@type":"Organization","name":"SCC Nexus"},"inLanguage":"en-GB"}, ensure_ascii=False)}</script>{analytics()}<link rel="stylesheet" href="{assets}/aq26-brand.css"></head>'''


def nav_html(active: str, protected: bool) -> str:
    if protected:
        links = [
            ("/unredacted/", "Protected home"), ("/unredacted/newhaven.html", "Newhaven"), ("/unredacted/evidence.html", "Evidence"),
            ("/unredacted/source-records.html", "Sources"), ("/unredacted/weekly-update.html", "Weekly"), ("/unredacted/downloads.html", "Downloads"),
            ("/unredacted/history.html", "History"), ("/unredacted/diagnostics.html", "Diagnostics"), ("/unredacted/candidates.html", "Candidates"), ("/", "Public site")]
    else:
        links = [("/", "Home"), ("/newhaven.html", "Newhaven"), ("/source-records.html", "Sources"), ("/weekly-update.html", "Weekly update"), ("/archive.html", "Archive"), ("/methodology.html", "Methodology"), ("/contact.html", "Contact"), ("/unredacted/", "Unredacted")]
    return "".join(f'<a href="{u}"{(" aria-current=\"page\"" if t == active else "")}>{esc(t)}</a>' for u, t in links)


def header(active: str, url: str, protected: bool) -> str:
    assets = assets_for(url)
    return f'<body><header class="site-header"><div class="topbar"><a class="brand" href="/" aria-label="AirQuality26 home"><img src="{assets}/logo_web.svg" alt="SCC Nexus Air Quality Report"></a><button class="menu-toggle" onclick="toggleMenu()">☰</button><nav class="primary" id="nav">{nav_html(active, protected)}</nav></div></header>'


def hero(title: str, label: str, url: str) -> str:
    assets = assets_for(url)
    banner = banner_for(url)
    return f'<section class="hero"><div class="hero-media"><video autoplay muted loop playsinline><source src="{assets}/{banner}" type="video/webm"></video></div><div class="hero-inner wrap"><span class="badge">{esc(label)}</span><h1>{esc(title)}</h1><p>{esc(DESC)}</p></div></section><div class="ticker"><span>Weekly AQ26 update • Newhaven ERF context • source records • redacted public output • protected reviewer library •</span></div>'


def footer(url: str, protected: bool) -> str:
    prefix = "/unredacted" if protected else ""
    public_link = '<a href="/">Public site</a>' if protected else '<a href="/unredacted/">Protected evidence</a>'
    return f'<footer><div class="footgrid"><div><strong>{esc(SITE)}</strong><p>Weekly evidence tracking, public-interest transparency and protected reviewer material where appropriate.</p><p class="muted">Last rebuilt {esc(NOW)}.</p></div><div><strong>Legal</strong><br><a href="{prefix}/privacy.html">Privacy</a><br><a href="{prefix}/terms.html">Terms</a><br><a href="{prefix}/cookies.html">Cookies</a><br><a href="{prefix}/accessibility.html">Accessibility</a></div><div><strong>Site</strong><br><a href="{prefix}/contact.html">Contact</a><br><a href="mailto:{esc(CONTACT_EMAIL)}">{esc(CONTACT_EMAIL)}</a><br><a href="/sitemap.xml">Sitemap</a><br>{public_link}</div></div><p class="copyright">© 2026 SCC Nexus · AQ26. All rights reserved. Corrections welcome.</p></footer><script src="{assets_for(url)}/aq26-brand.js"></script></body></html>'


def page(title: str, label: str, body: str, url: str, active: str, protected: bool = False) -> str:
    return head(title, url, protected) + header(active, url, protected) + hero(title, label, url) + f'<main class="wrap">{body}</main>' + footer(url, protected)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print("wrote", path)


def fmt_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.1f} {u}" if u != "B" else f"{n} B"
        x /= 1024
    return str(n)


def file_table(files: list[EvidenceFile], limit: int = 200, only_newhaven: bool = False) -> str:
    rows = []
    src = files
    if only_newhaven:
        src = [f for f in files if re.search(r"newhaven|bv8067il|erf|incinerator", f.rel + " " + f.keywords, re.I)]
    for f in src[:limit]:
        link = f"downloads/{esc(Path(f.rel).name)}" if f.rel.startswith("site_unredacted/downloads/") else "#"
        open_cell = f'<a href="{link}">download</a>' if link != "#" else "indexed"
        rows.append(f"<tr><td>{esc(f.rel)}</td><td>{esc(f.suffix)}</td><td>{fmt_size(f.size)}</td><td>{esc(f.mtime)}</td><td>{esc(f.keywords)}</td><td><code>{esc(f.sha256[:24])}</code></td><td>{open_cell}</td></tr>")
    if not rows:
        rows.append("<tr><td colspan='7'>No matching harvested files found in outputs/docs/data_sources/content_seed. The site shell is working, but the repository evidence outputs are not present in the expected folders.</td></tr>")
    return "<table><thead><tr><th>Path</th><th>Type</th><th>Size</th><th>Modified</th><th>Signals</th><th>SHA256</th><th>Link</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def record_table(records: list[dict[str, Any]], limit: int = 200, only_newhaven: bool = False) -> str:
    filtered = []
    for r in records:
        text = json.dumps(r, default=str).lower()
        if only_newhaven and not re.search(r"newhaven|bv8067il|erf|incinerator", text):
            continue
        filtered.append(r)
    rows = []
    for r in filtered[:limit]:
        source = r.get("_source_file", "")
        section = r.get("_section", "")
        title = r.get("title") or r.get("name") or r.get("record_type") or r.get("type") or r.get("source") or r.get("query") or "record"
        status = r.get("status") or r.get("gate") or r.get("severity") or r.get("result") or "indexed"
        note = r.get("note") or r.get("summary") or r.get("description") or r.get("warning") or json.dumps({k:v for k,v in r.items() if not k.startswith('_')}, default=str)[:350]
        rows.append(f"<tr><td>{esc(source)}</td><td>{esc(section)}</td><td>{esc(title)}</td><td>{esc(status)}</td><td>{esc(note)}</td></tr>")
    if not rows:
        rows.append("<tr><td colspan='5'>No structured JSON/CSV source records were found. File-level evidence index is still shown on the Evidence and Downloads pages.</td></tr>")
    return "<table><thead><tr><th>Source file</th><th>Section</th><th>Record</th><th>Status</th><th>Note</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def public_pages(files: list[EvidenceFile], records: list[dict[str, Any]]) -> None:
    PUBLIC.mkdir(exist_ok=True)
    safe_count = sum(1 for f in files if f.public_safe)
    total_count = len(files)
    home = f"""<div class='grid'><section class='card'><h2>Public-interest air-quality intelligence</h2><p>This public site summarises AQ26 evidence without exposing protected reviewer material.</p><p><a href='/newhaven.html'>Open the Newhaven evidence hub</a> · <a href='/unredacted/'>Protected unredacted evidence area</a></p></section><section class='card'><h2>Evidence status</h2><div class='metric'>{total_count}</div><p>harvested evidence files indexed for protected review.</p></section><section class='card'><h2>Public-safe index</h2><div class='metric'>{safe_count}</div><p>files classified as public-safe or non-sensitive references.</p></section></div>"""
    write(PUBLIC/"index.html", page("AirQuality26", "Public site", home, "/", "Home"))
    newhaven = "<div class='card'><h2>Newhaven public evidence hub</h2><p>Public-safe Newhaven context is shown here. Full reviewer tables and evidence files remain inside the password-protected library.</p>" + record_table(records, 30, True) + "</div>"
    write(PUBLIC/"newhaven.html", page("Newhaven evidence hub", "AQ26 evidence hub", newhaven, "/newhaven.html", "Newhaven"))
    sources = "<div class='card'><h2>Public source records</h2><p>Public summaries are redacted; protected records remain behind authentication.</p>" + record_table([r for r in records if True], 50, False) + "</div>"
    write(PUBLIC/"source-records.html", page("Source records", "Public source index", sources, "/source-records.html", "Sources"))
    write(PUBLIC/"weekly-update.html", page("Weekly update", "Weekly update", "<div class='card'><h2>Weekly update</h2><p>Latest AQ26 weekly evidence has been indexed for protected review. Public notes remain cautious pending independent validation.</p></div>", "/weekly-update.html", "Weekly update"))
    write(PUBLIC/"archive.html", page("Archive", "Archive", "<div class='card'><h2>Archive</h2><p>Historical public summaries will be listed here. Protected historical files are in the unredacted history and downloads pages.</p></div>", "/archive.html", "Archive"))
    write(PUBLIC/"methodology.html", page("Methodology", "Methodology", "<div class='card'><h2>Methodology</h2><p>AQ26 separates public readability from protected reviewer traceability. Public pages use redaction controls and avoid raw file IDs, private links and reviewer notes.</p></div>", "/methodology.html", "Methodology"))
    legal = {
        "privacy.html": "Privacy policy", "terms.html": "Terms", "cookies.html": "Cookies", "accessibility.html": "Accessibility", "contact.html": "Contact"
    }
    for fn, title in legal.items():
        body = f"<div class='card'><h2>{esc(title)}</h2><p>Contact AQ26 at <a href='mailto:{esc(CONTACT_EMAIL)}'>{esc(CONTACT_EMAIL)}</a>.</p><p>For corrections, include the page URL, proposed correction and supporting public source.</p></div>"
        write(PUBLIC/fn, page(title, "AQ26", body, "/"+fn, "Contact" if fn == "contact.html" else ""))
    urls = ["/", "/newhaven.html", "/source-records.html", "/weekly-update.html", "/archive.html", "/methodology.html", "/privacy.html", "/terms.html", "/cookies.html", "/accessibility.html", "/contact.html"]
    write(PUBLIC/"robots.txt", "User-agent: *\nAllow: /\nDisallow: /unredacted/\nSitemap: https://sccairquality.com/sitemap.xml\n")
    write(PUBLIC/"sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{BASE}{u}</loc></url>\n" for u in urls) + "</urlset>\n")


def protected_pages(files: list[EvidenceFile], records: list[dict[str, Any]]) -> None:
    UNREDACTED.mkdir(exist_ok=True)
    copy_protected_downloads(files)
    download_files = sorted((UNREDACTED/"downloads").glob("*"), key=lambda p: p.name.lower()) if (UNREDACTED/"downloads").exists() else []
    download_rows = "".join(f"<tr><td><a href='/unredacted/downloads/{esc(p.name)}'>{esc(p.name)}</a></td><td>{fmt_size(p.stat().st_size)}</td><td>{datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</td></tr>" for p in download_files)
    if not download_rows:
        download_rows = "<tr><td colspan='3'>No protected download files found yet.</td></tr>"
    home = f"<div class='grid'><section class='card'><h2>Evidence library</h2><div class='metric'>{len(files)}</div><p>files indexed from repository evidence folders.</p><p><a href='/unredacted/evidence.html'>Open evidence index</a></p></section><section class='card'><h2>Structured records</h2><div class='metric'>{len(records)}</div><p>JSON/CSV records discovered.</p><p><a href='/unredacted/source-records.html'>Open source records</a></p></section><section class='card'><h2>Downloads</h2><div class='metric'>{len(download_files)}</div><p>protected download artefacts available.</p><p><a href='/unredacted/downloads.html'>Open downloads</a></p></section></div>"
    write(UNREDACTED/"index.html", page("Unredacted evidence library", "Protected unredacted site", home, "/unredacted/", "Protected home", True))
    write(UNREDACTED/"newhaven.html", page("Newhaven evidence hub", "Protected unredacted site", "<div class='card'><h2>Newhaven protected evidence hub</h2><p>Authenticated Newhaven ERF/BV8067IL context, weekly evidence and source records.</p>" + record_table(records, 100, True) + "</div><div class='card'><h2>Newhaven-related files</h2>" + file_table(files, 120, True) + "</div>", "/unredacted/newhaven.html", "Newhaven", True))
    write(UNREDACTED/"evidence.html", page("Evidence library", "Protected evidence library", "<div class='card'><h2>Harvested evidence file index</h2>" + file_table(files, 250) + "</div>", "/unredacted/evidence.html", "Evidence", True))
    write(UNREDACTED/"source-records.html", page("Source records", "Protected source records", "<div class='card'><h2>Structured JSON/CSV source records</h2>" + record_table(records, 250) + "</div>", "/unredacted/source-records.html", "Sources", True))
    write(UNREDACTED/"downloads.html", page("Protected downloads", "Protected downloads", "<div class='card'><h2>Protected downloads</h2><table><thead><tr><th>File</th><th>Size</th><th>Modified</th></tr></thead><tbody>" + download_rows + "</tbody></table></div>", "/unredacted/downloads.html", "Downloads", True))
    write(UNREDACTED/"history.html", page("AQ26 history", "Protected history", "<div class='card'><h2>Historical file/backfill index</h2>" + file_table([f for f in files if re.search(r"history|archive|backfill|weekly", f.rel, re.I)], 200) + "</div>", "/unredacted/history.html", "History", True))
    write(UNREDACTED/"weekly-update.html", page("Weekly update", "Protected weekly update", "<div class='card'><h2>Weekly source and readiness records</h2>" + record_table([r for r in records if re.search(r"weekly|readiness|gate|warning|status", json.dumps(r, default=str), re.I)], 200) + "</div>", "/unredacted/weekly-update.html", "Weekly", True))
    write(UNREDACTED/"diagnostics.html", page("Diagnostics", "Protected diagnostics", "<div class='card'><h2>Diagnostics</h2>" + record_table([r for r in records if re.search(r"diagnostic|warning|error|gate|redaction", json.dumps(r, default=str), re.I)], 200) + "</div>", "/unredacted/diagnostics.html", "Diagnostics", True))
    write(UNREDACTED/"candidates.html", page("Candidates", "Protected candidate signals", "<div class='card'><h2>Candidate signals and unresolved evidence gaps</h2>" + record_table([r for r in records if re.search(r"candidate|anomaly|signal|gap", json.dumps(r, default=str), re.I)], 200) + "</div>", "/unredacted/candidates.html", "Candidates", True))
    for fn, title in {"privacy.html":"Privacy", "terms.html":"Terms", "cookies.html":"Cookies", "accessibility.html":"Accessibility", "contact.html":"Contact"}.items():
        body = f"<div class='card'><h2>{esc(title)}</h2><p>Protected AQ26 page. Contact: <a href='mailto:{esc(CONTACT_EMAIL)}'>{esc(CONTACT_EMAIL)}</a>.</p></div>"
        write(UNREDACTED/fn, page(title, "Protected legal", body, "/unredacted/"+fn, "", True))


def main() -> int:
    files = collect_files()
    records = collect_records(files)
    print(f"AQ26 evidence ingest found {len(files)} files and {len(records)} structured records")
    public_pages(files, records)
    protected_pages(files, records)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
