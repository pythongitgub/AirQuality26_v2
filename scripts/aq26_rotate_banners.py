#!/usr/bin/env python3
"""Rotate AQ26 page hero banners after the site builder has run."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

STAMP = "aq26-visual-20260623e"
BANNER_BY_PAGE = {
    "index.html": 1,
    "newhaven.html": 2,
    "source-records.html": 3,
    "weekly-update.html": 4,
    "readiness.html": 5,
    "methodology.html": 6,
    "downloads.html": 1,
    "archive.html": 2,
    "about.html": 3,
    "privacy.html": 4,
    "terms.html": 5,
    "cookies.html": 6,
    "accessibility.html": 1,
    "contact.html": 2,
    "evidence.html": 3,
}


def choose_banner(assets: Path, page_name: str) -> str:
    number = BANNER_BY_PAGE.get(page_name, ((sum(ord(c) for c in page_name) % 6) + 1))
    choices = [
        f"banners/desktop_banner_{number}.webm",
        f"desktop_banner_{number}.webm",
        "banners/desktop_banner_1.webm",
        "desktop_banner_1.webm",
    ]
    for rel in choices:
        if (assets / rel).exists() and (assets / rel).stat().st_size > 0:
            return rel
    return "air_quality_web.svg"


def patch_root(root: Path) -> int:
    if not root.exists():
        return 0
    assets = root / "assets"
    header_asset = assets / "air_quality_web_header.svg"
    if not header_asset.exists():
        fallback = assets / "logo_web.svg"
        if fallback.exists() and fallback.stat().st_size > 0:
            shutil.copy2(fallback, header_asset)
    favicon_name = "favicon.png" if (assets / "favicon.png").exists() else "favicon.svg"
    favicon = (
        f'<link rel="icon" href="/assets/{favicon_name}?v={STAMP}">'
        f'<link rel="shortcut icon" href="/assets/{favicon_name}?v={STAMP}">'
        f'<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png?v={STAMP}">'
    )
    changed = 0
    for html in root.rglob("*.html"):
        text = html.read_text(encoding="utf-8")
        banner = choose_banner(assets, html.name)
        text = re.sub(r'src="/assets/(?:banners/)?desktop_banner_\d+\.webm(?:\?v=[^"]*)?"', f'src="/assets/{banner}?v={STAMP}"', text)
        text = re.sub(r'src="/assets/logo_web\.svg(?:\?v=[^"]*)?"', f'src="/assets/air_quality_web_header.svg?v={STAMP}"', text)
        text = re.sub(r'src="/assets/aq26-logo\.svg(?:\?v=[^"]*)?"', f'src="/assets/aq26-logo.svg?v={STAMP}"', text)
        text = re.sub(r'href="/assets/aq26-brand\.css(?:\?v=[^"]*)?"', f'href="/assets/aq26-brand.css?v={STAMP}"', text)
        text = re.sub(r'src="/assets/aq26-brand\.js(?:\?v=[^"]*)?"', f'src="/assets/aq26-brand.js?v={STAMP}"', text)
        if 'rel="icon"' not in text:
            text = text.replace("</title>", "</title>" + favicon, 1)
        html.write_text(text, encoding="utf-8")
        changed += 1
    return changed


def main() -> int:
    total = 0
    for folder in ("site_public", "site_unredacted", "site_test"):
        total += patch_root(Path(folder))
    print(f"AQ26 rotated page banners and cache-busted visual assets in {total} HTML files with {STAMP}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
