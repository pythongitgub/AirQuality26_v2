#!/usr/bin/env python3
"""AQ26 white-header branding + full logo rollout.

Purpose
-------
Applies a consistent SCC Nexus Air Quality Report header across public,
unredacted and static report pages. The compact symbol remains the favicon / touch
icon only; the visible page header uses assets/air_quality_web.svg.

The script is intentionally defensive:
- copies branding assets into the target site;
- injects cache-busted favicon/touch/head links;
- removes earlier AQ26 injected headers;
- removes the first legacy header/nav block near the top of the document;
- inserts a white responsive header with hamburger navigation;
- injects CSS/JS once;
- writes a JSON summary.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VERSION = "aq26-white-header-20260527"
START = "<!-- AQ26_WHITE_HEADER_START -->"
END = "<!-- AQ26_WHITE_HEADER_END -->"
CSS_NAME = "aq26_white_header.css"
JS_NAME = "aq26_white_header.js"
HEADER_LOGO_NAME = "air_quality_web.svg"
FAVICON_NAME = "favicon.svg"

PUBLIC_NAV = [
    ("Observatory", "index.html"),
    ("Weekly Archive", "archive.html"),
    ("Comparisons", "comparisons.html"),
    ("Source Records", "source-records.html"),
    ("Readiness", "readiness.html"),
    ("Methodology", "methodology.html"),
    ("Downloads", "downloads.html"),
]
UNREDACTED_NAV = [
    ("Dashboard", "index.html"),
    ("Evidence index", "evidence.html"),
    ("Public site", "../index.html"),
]

CORE_PUBLIC_PAGES = {
    "index.html": ("AQ26 Environmental Intelligence Observatory", "Weekly air-quality and emissions intelligence"),
    "archive.html": ("Weekly Archive", "Historical AQ26 runs and evidence windows"),
    "comparisons.html": ("Comparisons", "Interactive weekly comparisons across coverage, readiness and filings"),
    "source-records.html": ("Source Records", "Where the evidence comes from"),
    "readiness.html": ("Readiness", "Evidence gates, caveats and current maturity"),
    "methodology.html": ("Methodology", "How AQ26 collects, validates and presents evidence"),
    "downloads.html": ("Downloads", "Latest public evidence bundles and reports"),
    "about.html": ("About", "About the AQ26 evidence observatory"),
    "privacy.html": ("Privacy", "Privacy and static-site data use"),
    "cookies.html": ("Cookies", "Cookie and local-storage details"),
    "accessibility.html": ("Accessibility", "Accessibility statement"),
    "terms.html": ("Terms", "Terms and caveats"),
    "contact.html": ("Contact", "Contact and project enquiries"),
}

@dataclass
class Result:
    path: str
    status: str
    details: str = ""


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel_prefix(html_path: Path, site_root: Path) -> str:
    rel = html_path.relative_to(site_root)
    depth = max(0, len(rel.parts) - 1)
    return "../" * depth


def is_unredacted_site(site_root: Path) -> bool:
    name = site_root.name.lower()
    if "unredacted" in name:
        return True
    # If evidence.html exists and public archive pages do not, treat as unredacted.
    return (site_root / "evidence.html").exists() and not (site_root / "archive.html").exists()


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def copy_assets(site_root: Path, asset_source: Path) -> dict:
    assets_dir = site_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    copied = {}
    candidates = [
        HEADER_LOGO_NAME,
        FAVICON_NAME,
        "logo_web.svg",
        "apple-touch-icon.png",
        "favicon-32x32.png",
        "favicon-16x16.png",
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
        "site.webmanifest",
    ]
    for name in candidates:
        copied[name] = copy_if_exists(asset_source / name, assets_dir / name)
    # Root favicon improves browser discovery.
    if (assets_dir / FAVICON_NAME).exists():
        shutil.copy2(assets_dir / FAVICON_NAME, site_root / FAVICON_NAME)
    return copied


def write_brand_assets(site_root: Path) -> None:
    assets_dir = site_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    css = r'''
:root{
  --aq26-navy:#061426;
  --aq26-ink:#07182c;
  --aq26-muted:#52647a;
  --aq26-line:#d8e3ef;
  --aq26-teal:#34c5c9;
  --aq26-card:#ffffff;
}
html{scroll-padding-top:110px;}
body{margin:0;}
.aq26-white-header{background:#fff;color:var(--aq26-ink);border-bottom:1px solid var(--aq26-line);box-shadow:0 8px 24px rgba(6,20,38,.08);position:relative;z-index:1000;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
.aq26-white-header__top{background:var(--aq26-navy);color:#e8f3ff;font-size:.78rem;line-height:1.3;padding:.4rem clamp(.8rem,2.5vw,1.4rem);display:flex;justify-content:space-between;gap:.75rem;align-items:center;}
.aq26-white-header__top strong{color:#fff;}
.aq26-white-header__bar{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.75rem clamp(.85rem,3vw,1.8rem);background:#fff;}
.aq26-white-header__brand{display:flex;align-items:center;gap:.9rem;min-width:0;text-decoration:none;color:var(--aq26-ink);}
.aq26-white-header__logo{display:block;width:min(300px,38vw);height:auto;max-height:82px;object-fit:contain;}
.aq26-white-header__title{display:none;font-weight:900;line-height:1.15;font-size:1rem;color:var(--aq26-ink);}
.aq26-white-header__badge{border:1px solid var(--aq26-line);border-radius:999px;padding:.35rem .65rem;background:#f3f8fc;color:var(--aq26-muted);font-weight:800;font-size:.76rem;white-space:nowrap;}
.aq26-white-header__nav{display:flex;align-items:center;justify-content:flex-end;gap:.45rem;flex-wrap:wrap;}
.aq26-white-header__nav a{display:inline-flex;align-items:center;min-height:38px;padding:.45rem .75rem;border-radius:999px;background:#eef5fb;color:var(--aq26-ink);border:1px solid #d5e1ed;text-decoration:none;font-weight:800;font-size:.88rem;line-height:1;}
.aq26-white-header__nav a:hover,.aq26-white-header__nav a:focus{background:#dff7f8;border-color:#9adfe4;outline:2px solid transparent;}
.aq26-white-header__menu{display:none;border:1px solid #c8d7e6;background:#fff;color:var(--aq26-ink);border-radius:999px;padding:.55rem .8rem;font-weight:900;align-items:center;gap:.45rem;}
.aq26-white-header__menu span{display:block;width:1.1rem;height:.12rem;background:currentColor;box-shadow:0 .35rem 0 currentColor,0 -.35rem 0 currentColor;border-radius:99px;}
.aq26-report-masthead{background:#fff;border-bottom:1px solid var(--aq26-line);padding:1rem 1.25rem;margin-bottom:1rem;}
.aq26-report-masthead img{width:280px;max-width:70vw;height:auto;}
@media (max-width: 920px){
  .aq26-white-header__top{font-size:.72rem;}
  .aq26-white-header__bar{align-items:flex-start;}
  .aq26-white-header__logo{width:min(230px,54vw);max-height:68px;}
  .aq26-white-header__menu{display:inline-flex;margin-top:.25rem;}
  .aq26-white-header__nav{display:none;position:absolute;left:.75rem;right:.75rem;top:calc(100% - .25rem);background:#fff;border:1px solid var(--aq26-line);box-shadow:0 18px 32px rgba(6,20,38,.18);border-radius:18px;padding:.7rem;z-index:1001;}
  .aq26-white-header.is-open .aq26-white-header__nav{display:grid;grid-template-columns:1fr;}
  .aq26-white-header__nav a{width:100%;justify-content:flex-start;background:#f7fbff;border-radius:14px;padding:.75rem .85rem;}
  .aq26-white-header__badge{display:none;}
}
@media (max-width: 520px){
  .aq26-white-header__top{display:none;}
  .aq26-white-header__bar{padding:.65rem .75rem;}
  .aq26-white-header__logo{width:205px;max-width:60vw;}
  .aq26-white-header__title{display:none;}
}
'''.strip() + "\n"
    js = r'''
(function(){
  function ready(fn){ if(document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }
  ready(function(){
    var header = document.querySelector('.aq26-white-header');
    if(!header) return;
    var btn = header.querySelector('[data-aq26-menu]');
    var nav = header.querySelector('.aq26-white-header__nav');
    if(!btn || !nav) return;
    btn.addEventListener('click', function(){
      var open = header.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.addEventListener('click', function(ev){
      if(ev.target && ev.target.tagName === 'A'){
        header.classList.remove('is-open');
        btn.setAttribute('aria-expanded','false');
      }
    });
  });
})();
'''.strip() + "\n"
    (assets_dir / CSS_NAME).write_text(css, encoding="utf-8")
    (assets_dir / JS_NAME).write_text(js, encoding="utf-8")


def make_header(html_path: Path, site_root: Path, unredacted: bool) -> str:
    prefix = rel_prefix(html_path, site_root)
    nav = UNREDACTED_NAV if unredacted else PUBLIC_NAV
    nav_html = "\n".join(f'        <a href="{prefix}{href}">{label}</a>' for label, href in nav)
    badge = "Restricted review" if unredacted else "Public observatory"
    title = "SCC Nexus · AQ26 internal review" if unredacted else "AQ26 Environmental Intelligence"
    top = "Password-protected QA and provenance review" if unredacted else "Weekly evidence, provenance and air-quality intelligence"
    return f'''{START}
<header class="aq26-white-header" role="banner">
  <div class="aq26-white-header__top"><span><strong>SCC Nexus · AQ26</strong> {top}</span><span>{badge}</span></div>
  <div class="aq26-white-header__bar">
    <a class="aq26-white-header__brand" href="{prefix}{'index.html'}" aria-label="{title}">
      <img class="aq26-white-header__logo" src="{prefix}assets/{HEADER_LOGO_NAME}?v={VERSION}" alt="SCC Nexus Air Quality Report">
      <span class="aq26-white-header__title">{title}</span>
    </a>
    <span class="aq26-white-header__badge">{badge}</span>
    <button class="aq26-white-header__menu" type="button" data-aq26-menu aria-expanded="false" aria-controls="aq26-site-nav"><span aria-hidden="true"></span>Menu</button>
    <nav class="aq26-white-header__nav" id="aq26-site-nav" aria-label="Primary navigation">
{nav_html}
    </nav>
  </div>
</header>
{END}
'''


def strip_injected_header(text: str) -> str:
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END) + r"\s*", re.S)
    return pattern.sub("", text)


def strip_legacy_top_header(body_inner: str) -> str:
    # Work only on the first few KB to avoid removing document content.
    prefix = body_inner[:8000]
    suffix = body_inner[8000:]
    changed = True
    while changed:
        changed = False
        new_prefix = re.sub(r"^\s*<header\b[^>]*>.*?</header>\s*", "", prefix, count=1, flags=re.I | re.S)
        if new_prefix != prefix:
            prefix = new_prefix; changed = True; continue
        new_prefix = re.sub(r"^\s*<nav\b[^>]*>.*?</nav>\s*", "", prefix, count=1, flags=re.I | re.S)
        if new_prefix != prefix:
            prefix = new_prefix; changed = True; continue
        # Common previously injected wrappers.
        new_prefix = re.sub(r"^\s*<div\b(?=[^>]*(?:topbar|site-header|brand-header|navbar|aq26-header))[^>]*>.*?</div>\s*", "", prefix, count=1, flags=re.I | re.S)
        if new_prefix != prefix:
            prefix = new_prefix; changed = True
    return prefix + suffix


def ensure_head_links(text: str, html_path: Path, site_root: Path) -> str:
    prefix = rel_prefix(html_path, site_root)
    # Remove old AQ26 branding includes so we avoid duplicates/stale cache.
    text = re.sub(r'\s*<link[^>]+aq26_white_header\.css[^>]*>\s*', "\n", text, flags=re.I)
    text = re.sub(r'\s*<script[^>]+aq26_white_header\.js[^>]*></script>\s*', "\n", text, flags=re.I)
    text = re.sub(r'\s*<link[^>]+rel=["\'](?:icon|apple-touch-icon|manifest)["\'][^>]*>\s*', "\n", text, flags=re.I)
    text = re.sub(r'\s*<meta\s+name=["\']theme-color["\'][^>]*>\s*', "\n", text, flags=re.I)

    links = f'''\n<link rel="icon" type="image/svg+xml" href="{prefix}assets/{FAVICON_NAME}?v={VERSION}">
<link rel="alternate icon" href="{prefix}{FAVICON_NAME}?v={VERSION}">
<link rel="apple-touch-icon" href="{prefix}assets/apple-touch-icon.png?v={VERSION}">
<link rel="manifest" href="{prefix}assets/site.webmanifest?v={VERSION}">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="{prefix}assets/{CSS_NAME}?v={VERSION}">
<script defer src="{prefix}assets/{JS_NAME}?v={VERSION}"></script>\n'''
    if "</head>" in text.lower():
        return re.sub(r"</head>", links + "</head>", text, count=1, flags=re.I)
    return links + text


def apply_header_to_html(html_path: Path, site_root: Path, unredacted: bool) -> Result:
    try:
        text = html_path.read_text(encoding="utf-8", errors="replace")
        original = text
        text = strip_injected_header(text)
        text = ensure_head_links(text, html_path, site_root)
        header = make_header(html_path, site_root, unredacted)
        m = re.search(r"<body\b[^>]*>", text, flags=re.I)
        if m:
            body_start_end = m.end()
            before = text[:body_start_end]
            after = text[body_start_end:]
            after = strip_legacy_top_header(after)
            text = before + "\n" + header + after
        else:
            # Minimal HTML fallback.
            title = html_path.stem.replace("-", " ").title()
            text = f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head><body>\n{header}\n" + text + "\n</body></html>"
            text = ensure_head_links(text, html_path, site_root)
        if text != original:
            html_path.write_text(text, encoding="utf-8")
            return Result(str(html_path.relative_to(site_root)), "updated")
        return Result(str(html_path.relative_to(site_root)), "unchanged")
    except Exception as exc:  # pragma: no cover
        return Result(str(html_path), "error", str(exc))


def build_stub_page(path: Path, title: str, subtitle: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 600:
        return
    path.write_text(f'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · AQ26</title></head>
<body>
<main style="max-width:1100px;margin:2rem auto;padding:1rem;font-family:system-ui,-apple-system,Segoe UI,sans-serif">
  <section style="border:1px solid #d8e3ef;border-radius:24px;padding:2rem;background:#f8fbff">
    <p style="text-transform:uppercase;letter-spacing:.16em;font-weight:800;color:#088">SCC Nexus · AQ26</p>
    <h1 style="font-size:clamp(2rem,5vw,4rem);margin:.2rem 0;color:#07182c">{title}</h1>
    <p style="font-size:1.15rem;color:#52647a">{subtitle}</p>
  </section>
  <section style="margin-top:1rem;border-left:5px solid #34c5c9;background:#ffffff;padding:1rem 1.2rem;border-radius:14px;box-shadow:0 8px 24px rgba(6,20,38,.08)">
    <strong>Live evidence page:</strong> this page is prepared so users never see a blank screen while the AQ26 backfill populates richer charts and tables.
  </section>
</main>
</body>
</html>
''', encoding="utf-8")


def ensure_core_pages(site_root: Path, unredacted: bool) -> None:
    if unredacted:
        build_stub_page(site_root / "index.html", "AQ26 Unredacted Evidence Review", "Internal QA, provenance review and restricted evidence-readiness checks.")
        build_stub_page(site_root / "evidence.html", "Unredacted output catalogue", "Search and filter workflow outputs, provider probes and evidence payloads.")
    else:
        for name, (title, subtitle) in CORE_PUBLIC_PAGES.items():
            build_stub_page(site_root / name, title, subtitle)
        aliases = {
            "historical-comparisons.html": "comparisons.html",
            "weekly-archive.html": "archive.html",
            "evidence-downloads.html": "downloads.html",
        }
        for alias, target in aliases.items():
            p = site_root / alias
            if not p.exists():
                p.write_text(f'<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={target}"><link rel="canonical" href="{target}"><title>Redirecting · AQ26</title></head><body><p>Redirecting to <a href="{target}">{target}</a>.</p></body></html>', encoding="utf-8")


def find_html_files(site_root: Path) -> list[Path]:
    skip_parts = {"node_modules", ".git", "__pycache__"}
    files = []
    for p in site_root.rglob("*.html"):
        if any(part in skip_parts for part in p.parts):
            continue
        files.append(p)
    return sorted(files)


def validate(site_root: Path, unredacted: bool) -> list[str]:
    problems = []
    required = ["index.html", "evidence.html"] if unredacted else list(CORE_PUBLIC_PAGES.keys())
    for name in required:
        p = site_root / name
        if not p.exists() or p.stat().st_size < 600:
            problems.append(f"{name}: missing or too small")
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if HEADER_LOGO_NAME not in txt or CSS_NAME not in txt:
            problems.append(f"{name}: header branding not injected")
    if not (site_root / "assets" / HEADER_LOGO_NAME).exists():
        problems.append("assets/air_quality_web.svg missing")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--asset-source", default="website/assets")
    ap.add_argument("--force", action="store_true", help="Create/repair core pages before applying branding")
    ap.add_argument("--unredacted", action="store_true", help="Force unredacted navigation/header")
    ap.add_argument("--public", action="store_true", help="Force public navigation/header")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--summary", default=None)
    args = ap.parse_args()

    site_root = Path(args.site_root)
    asset_source = Path(args.asset_source)
    site_root.mkdir(parents=True, exist_ok=True)
    unredacted = args.unredacted or (not args.public and is_unredacted_site(site_root))

    if not args.validate_only:
        if args.force:
            ensure_core_pages(site_root, unredacted)
        copied = copy_assets(site_root, asset_source)
        write_brand_assets(site_root)
        results = [apply_header_to_html(p, site_root, unredacted) for p in find_html_files(site_root)]
    else:
        copied = {}
        results = []

    problems = validate(site_root, unredacted)
    summary = {
        "ok": not problems,
        "run_ts_utc": now_utc(),
        "site_root": str(site_root),
        "mode": "unredacted" if unredacted else "public",
        "version": VERSION,
        "copied_assets": copied,
        "updated_count": sum(1 for r in results if r.status == "updated"),
        "html_count": len(find_html_files(site_root)),
        "problems": problems,
        "results": [r.__dict__ for r in results[:500]],
    }
    out = Path(args.summary) if args.summary else site_root / "data" / "branding" / "white_header_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["ok", "site_root", "mode", "updated_count", "html_count", "problems"]}, indent=2))
    return 0 if not problems else 2

if __name__ == "__main__":
    raise SystemExit(main())
