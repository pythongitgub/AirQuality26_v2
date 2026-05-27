#!/usr/bin/env python3
"""
AQ26 public site branding + mobile navigation polish.

Purpose:
- Copies the supplied AQ26/SCC Nexus logo into the generated site.
- Adds favicon, Apple touch icon and web manifest links.
- Adds a mobile-friendly hamburger menu layer without requiring the existing
  generated desktop menu to be rewritten.
- Designed to run AFTER the site builder and BEFORE deployment.

Safe defaults:
- Does not delete existing website files.
- Updates HTML idempotently using marked injection blocks.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Iterable

MARKER_START = "<!-- AQ26_BRANDING_MOBILE_START -->"
MARKER_END = "<!-- AQ26_BRANDING_MOBILE_END -->"

ASSET_NAMES = [
    "logo_web.svg",
    "favicon.svg",
    "favicon-16x16.png",
    "favicon-32x32.png",
    "apple-touch-icon.png",
    "android-chrome-192x192.png",
    "android-chrome-512x512.png",
    "aq26_mobile_nav.css",
    "aq26_mobile_nav.js",
]

ROOT_NAMES = [
    "site.webmanifest",
]


def rel_href(from_html: Path, target: Path) -> str:
    rel = os.path.relpath(target, from_html.parent).replace("\\", "/")
    return rel


def copy_assets(asset_source: Path, site_root: Path) -> list[str]:
    copied: list[str] = []
    site_assets = site_root / "assets"
    site_assets.mkdir(parents=True, exist_ok=True)

    for name in ASSET_NAMES:
        src = asset_source / name
        if src.exists():
            dst = site_assets / name
            shutil.copy2(src, dst)
            copied.append(str(dst))

    for name in ROOT_NAMES:
        src = asset_source / name
        if src.exists():
            dst = site_root / name
            shutil.copy2(src, dst)
            copied.append(str(dst))

    # iOS and legacy browser fallbacks often request these at the web root.
    for name in ["apple-touch-icon.png", "favicon.svg", "favicon-32x32.png"]:
        src = site_assets / name
        if src.exists():
            dst = site_root / name
            shutil.copy2(src, dst)
            copied.append(str(dst))

    return copied


def remove_old_block(html: str) -> str:
    while MARKER_START in html and MARKER_END in html:
        a = html.index(MARKER_START)
        b = html.index(MARKER_END) + len(MARKER_END)
        html = html[:a] + html[b:]
    return html


def ensure_viewport(html: str) -> str:
    if "name=\"viewport\"" in html or "name='viewport'" in html:
        return html
    tag = '<meta name="viewport" content="width=device-width, initial-scale=1">'
    if "</head>" in html:
        return html.replace("</head>", f"  {tag}\n</head>", 1)
    return tag + "\n" + html


def inject_into_html(path: Path, site_root: Path) -> bool:
    html = path.read_text(encoding="utf-8", errors="ignore")
    original = html
    html = remove_old_block(html)
    html = ensure_viewport(html)

    assets_dir = site_root / "assets"
    css_href = rel_href(path, assets_dir / "aq26_mobile_nav.css")
    js_href = rel_href(path, assets_dir / "aq26_mobile_nav.js")
    favicon_svg = rel_href(path, assets_dir / "favicon.svg")
    favicon_32 = rel_href(path, assets_dir / "favicon-32x32.png")
    apple = rel_href(path, assets_dir / "apple-touch-icon.png")
    manifest = rel_href(path, site_root / "site.webmanifest")

    block = f"""
{MARKER_START}
<link rel="icon" type="image/svg+xml" href="{favicon_svg}">
<link rel="alternate icon" type="image/png" sizes="32x32" href="{favicon_32}">
<link rel="apple-touch-icon" sizes="180x180" href="{apple}">
<link rel="manifest" href="{manifest}">
<meta name="theme-color" content="#07243a">
<link rel="stylesheet" href="{css_href}">
<script defer src="{js_href}"></script>
{MARKER_END}
""".strip()

    if "</head>" in html:
        html = html.replace("</head>", f"  {block}\n</head>", 1)
    else:
        html = block + "\n" + html

    if html != original:
        path.write_text(html, encoding="utf-8")
        return True
    return False


def iter_html(site_root: Path) -> Iterable[Path]:
    for p in site_root.rglob("*.html"):
        if p.is_file():
            yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_public", help="Generated public site root")
    ap.add_argument("--asset-source", default="website/assets", help="Source asset folder")
    ap.add_argument("--include-unredacted", action="store_true", help="Also polish site_unredacted if present")
    args = ap.parse_args()

    site_roots = [Path(args.site_root)]
    if args.include_unredacted and Path("site_unredacted").exists():
        site_roots.append(Path("site_unredacted"))

    asset_source = Path(args.asset_source)
    summary = {"asset_source": str(asset_source), "sites": []}

    for site_root in site_roots:
        site_root.mkdir(parents=True, exist_ok=True)
        copied = copy_assets(asset_source, site_root)
        changed = []
        for html in iter_html(site_root):
            if inject_into_html(html, site_root):
                changed.append(str(html))
        summary["sites"].append({
            "site_root": str(site_root),
            "copied_assets": copied,
            "html_files_updated": changed,
            "html_count": len(list(iter_html(site_root))),
        })

    out = Path(args.site_root) / "data" / "public_dashboard"
    out.mkdir(parents=True, exist_ok=True)
    (out / "branding_mobile_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
