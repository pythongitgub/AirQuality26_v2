#!/usr/bin/env python3
"""AQ26 favicon/touch-icon enforcement from canonical logo_web.svg.

Uses the attached/committed website/assets/logo_web.svg as the single source of truth
for browser favicons and mobile touch icons. The SVG currently contains an embedded PNG,
so this script extracts it and builds proper PNG/ICO favicons that browsers prefer over
older cached SVG icons.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("aq26-favicon-%Y%m%d%H%M%S")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def extract_png_from_svg(svg_path: Path) -> Image.Image:
    txt = read_text(svg_path)
    m = re.search(r"data:image/(?:png|PNG);base64,([A-Za-z0-9+/=\n\r]+)", txt)
    if not m:
        raise RuntimeError(f"No embedded PNG found inside {svg_path}")
    raw = base64.b64decode(re.sub(r"\s+", "", m.group(1)))
    img = Image.open(BytesIO(raw)).convert("RGBA")
    return img


def square_icon(img: Image.Image, size: int, padding_ratio: float = 0.08) -> Image.Image:
    """Crop transparent margins, place on white square and resize."""
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    w, h = rgba.size
    side = max(w, h)
    pad = max(8, int(side * padding_ratio))
    canvas_side = side + pad * 2
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (255, 255, 255, 0))
    canvas.alpha_composite(rgba, ((canvas_side - w) // 2, (canvas_side - h) // 2))
    # Favicon backgrounds are inconsistent across browsers; add a very light backing so the icon reads on dark tabs.
    backing = Image.new("RGBA", canvas.size, (255, 255, 255, 255))
    backing.alpha_composite(canvas)
    return backing.resize((size, size), Image.Resampling.LANCZOS)


def remove_old_icon_refs(html: str) -> str:
    # Remove old icon/apple/manifest references; leave styles/scripts alone.
    html = re.sub(r"\n?\s*<link[^>]+rel=['\"](?:icon|shortcut icon|apple-touch-icon|manifest)['\"][^>]*>", "", html, flags=re.I)
    html = re.sub(r"\n?\s*<link[^>]+href=['\"][^'\"]*(?:favicon|apple-touch-icon|site\.webmanifest)[^'\"]*['\"][^>]*>", "", html, flags=re.I)
    return html


def inject_icon_refs(html: str, version: str) -> str:
    refs = f"""
<link rel="icon" href="favicon.ico?v={version}" sizes="any">
<link rel="icon" href="favicon.svg?v={version}" type="image/svg+xml">
<link rel="icon" href="assets/favicon.svg?v={version}" type="image/svg+xml">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png?v={version}">
<link rel="manifest" href="site.webmanifest?v={version}">
<meta name="theme-color" content="#0b1f3a">
""".strip()
    html = remove_old_icon_refs(html)
    if "</head>" in html.lower():
        return re.sub(r"</head>", refs + "\n</head>", html, count=1, flags=re.I)
    return refs + "\n" + html


def enforce_for_site(site: Path, svg_source: Path, version: str) -> dict:
    site.mkdir(parents=True, exist_ok=True)
    assets = site / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    # Copy canonical SVG icon to root and assets.
    shutil.copyfile(svg_source, assets / "logo_web.svg")
    shutil.copyfile(svg_source, assets / "favicon.svg")
    shutil.copyfile(svg_source, site / "favicon.svg")

    img = extract_png_from_svg(svg_source)
    icons = {
        "apple-touch-icon.png": 180,
        "android-chrome-192x192.png": 192,
        "android-chrome-512x512.png": 512,
        "favicon-32x32.png": 32,
        "favicon-16x16.png": 16,
    }
    generated = []
    for name, size in icons.items():
        out = assets / name
        square_icon(img, size).save(out)
        generated.append(str(out))

    ico_images = [square_icon(img, s) for s in (16, 32, 48)]
    ico_images[0].save(site / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    shutil.copyfile(site / "favicon.ico", assets / "favicon.ico")

    manifest = {
        "name": "AQ26 Incinerator Evidence Observatory",
        "short_name": "AQ26",
        "icons": [
            {"src": "assets/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "assets/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
        "theme_color": "#0b1f3a",
        "background_color": "#f4f8fb",
        "display": "standalone",
    }
    write_text(site / "site.webmanifest", json.dumps(manifest, indent=2))

    html_count = 0
    for html_path in site.glob("*.html"):
        txt = read_text(html_path)
        new = inject_icon_refs(txt, version)
        if new != txt:
            write_text(html_path, new)
            html_count += 1

    return {
        "site": str(site),
        "version": version,
        "html_files_updated": html_count,
        "favicon_svg": str(site / "favicon.svg"),
        "favicon_ico": str(site / "favicon.ico"),
        "assets_favicon_svg": str(assets / "favicon.svg"),
        "png_icons": generated,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--icon-source", default="website/assets/logo_web.svg")
    ap.add_argument("--public-site", default="site_public")
    ap.add_argument("--unredacted-site", default="site_unredacted")
    ap.add_argument("--summary", default="outputs/favicon/aq26_favicon_enforcement_summary.json")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    icon_source = repo / args.icon_source
    if not icon_source.exists():
        raise SystemExit(f"Icon source not found: {icon_source}")

    # Keep canonical website assets in sync.
    (repo / "website/assets").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(icon_source, repo / "website/assets/logo_web.svg")
    shutil.copyfile(icon_source, repo / "website/assets/favicon.svg")

    version = now_tag()
    results = [
        enforce_for_site(repo / args.public_site, icon_source, version),
        enforce_for_site(repo / args.unredacted_site, icon_source, version),
    ]
    summary = {"ok": True, "version": version, "icon_source": str(icon_source), "sites": results}
    out = repo / args.summary
    write_text(out, json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
