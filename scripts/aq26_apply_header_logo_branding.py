#!/usr/bin/env python3
"""
AQ26 header-brand injector.

Purpose:
- Keep the compact SVG/PNG as favicon/touch icon.
- Use air_quality_web.svg as the visible header logo on public and report HTML pages.
- Injects cache-busted CSS/JS into HTML pages and copies brand assets into each site root.
- Safe to run repeatedly.

Example:
  python scripts/aq26_apply_header_logo_branding.py --site-root site_public --asset-source website/assets
  python scripts/aq26_apply_header_logo_branding.py --site-root site_unredacted --asset-source website/assets
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

ASSET_FILES = [
    "air_quality_web.svg",
    "aq26_brand_header.css",
    "aq26_brand_header.js",
]

HEAD_LINKS = """
<link rel="stylesheet" href="assets/aq26_brand_header.css?v=aq26-header-20260527">
<script defer src="assets/aq26_brand_header.js?v=aq26-header-20260527"></script>
""".strip()

FAVICON_LINKS = """
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg?v=aq26-icon-20260527">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png?v=aq26-icon-20260527">
<link rel="manifest" href="assets/site.webmanifest?v=aq26-icon-20260527">
""".strip()


def copy_assets(site_root: Path, asset_source: Path) -> list[str]:
    copied = []
    assets_dir = site_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    for name in ASSET_FILES:
        src = asset_source / name
        if not src.exists():
            raise FileNotFoundError(f"Missing required branding asset: {src}")
        dst = assets_dir / name
        shutil.copy2(src, dst)
        copied.append(str(dst))

    # Optional favicons, copied if present.
    for name in [
        "favicon.svg",
        "apple-touch-icon.png",
        "favicon-32x32.png",
        "favicon-16x16.png",
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
        "site.webmanifest",
    ]:
        src = asset_source / name
        if src.exists():
            shutil.copy2(src, assets_dir / name)
            copied.append(str(assets_dir / name))

    # Also put the favicon at root for browsers that request /favicon.svg directly.
    fav = asset_source / "favicon.svg"
    if fav.exists():
        shutil.copy2(fav, site_root / "favicon.svg")
        copied.append(str(site_root / "favicon.svg"))

    return copied


def inject_into_html(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    original = text

    if "aq26_brand_header.css" not in text:
        if "</head>" in text:
            text = text.replace("</head>", HEAD_LINKS + "\n</head>", 1)
        else:
            text = HEAD_LINKS + "\n" + text

    if "assets/favicon.svg?v=aq26-icon-20260527" not in text:
        if "</head>" in text:
            text = text.replace("</head>", FAVICON_LINKS + "\n</head>", 1)
        else:
            text = FAVICON_LINKS + "\n" + text

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--asset-source", default="website/assets")
    ap.add_argument("--summary", default="")
    args = ap.parse_args()

    site_root = Path(args.site_root)
    asset_source = Path(args.asset_source)

    if not site_root.exists():
        raise SystemExit(f"site root does not exist: {site_root}")
    if not asset_source.exists():
        raise SystemExit(f"asset source does not exist: {asset_source}")

    copied = copy_assets(site_root, asset_source)

    changed = []
    for html in sorted(site_root.rglob("*.html")):
        # avoid editing enormous vendored docs if any
        if html.stat().st_size > 5_000_000:
            continue
        if inject_into_html(html):
            changed.append(str(html))

    summary = {
        "ok": True,
        "site_root": str(site_root),
        "asset_source": str(asset_source),
        "copied_assets": copied,
        "html_pages_changed": changed,
        "html_pages_changed_count": len(changed),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    out = Path(args.summary) if args.summary else site_root / "data" / "public_dashboard" / "header_branding_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
