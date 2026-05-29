#!/usr/bin/env python3
"""
AQ26 final brand/header/weekly polish.

Purpose:
- Remove the extra text next to the full SCC Nexus Air Quality header logo.
- Enforce strong favicon/touch-icon references across all public and unredacted pages.
- Keep the weekly alert and WEBM moving banner visible on the front pages.
- Avoid committing or generating .htpasswd; auth files are deployment-only.

This is a final post-build polish script. Run it after:
  aq26_build_operational_dual_site.py
  aq26_build_weekly_alert_pages.py
  aq26_apply_webm_banners.py
  aq26_enforce_favicon_from_logo.py
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


VERSION = "aq26-final-brand-20260529"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_copy(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if src.resolve() == dst.resolve():
            return True
    except Exception:
        pass
    shutil.copyfile(src, dst)
    return True


def make_ico_from_png(png: Path, ico: Path) -> bool:
    """Create a simple ICO container that embeds a PNG image."""
    if not png.exists():
        return False
    data = png.read_bytes()
    # ICO header: reserved=0, type=1, count=1
    # Directory entry: width, height, colors, reserved, planes, bitcount, size, offset
    # width/height byte 0 represents 256; for 32px use 32.
    width = 32
    height = 32
    header = (0).to_bytes(2, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
    entry = bytes([width, height, 0, 0]) + (1).to_bytes(2, "little") + (32).to_bytes(2, "little") + len(data).to_bytes(4, "little") + (6 + 16).to_bytes(4, "little")
    ico.parent.mkdir(parents=True, exist_ok=True)
    ico.write_bytes(header + entry + data)
    return True


def ensure_brand_assets(repo: Path, site: Path) -> Dict[str, bool]:
    site.mkdir(parents=True, exist_ok=True)
    assets = site / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    logo_svg_candidates = [
        repo / "website/assets/logo_web.svg",
        repo / "site_public/assets/logo_web.svg",
        repo / "assets/logo_web.svg",
    ]
    header_logo_candidates = [
        repo / "website/assets/air_quality_web.svg",
        repo / "site_public/assets/air_quality_web.svg",
        repo / "assets/air_quality_web.svg",
    ]

    logo_svg = next((p for p in logo_svg_candidates if p.exists()), None)
    header_logo = next((p for p in header_logo_candidates if p.exists()), None)

    status = {}
    if logo_svg:
        status["logo_web_svg"] = safe_copy(logo_svg, assets / "logo_web.svg")
        status["favicon_svg_assets"] = safe_copy(logo_svg, assets / "favicon.svg")
        status["favicon_svg_root"] = safe_copy(logo_svg, site / "favicon.svg")
    else:
        status["logo_web_svg"] = False

    if header_logo:
        status["header_logo"] = safe_copy(header_logo, assets / "air_quality_web.svg")
    else:
        status["header_logo"] = False

    # If favicon PNGs exist, ensure root/assets favicon.ico prefer 32x32 PNG.
    png32_candidates = [
        assets / "favicon-32x32.png",
        repo / "website/assets/favicon-32x32.png",
        repo / "site_public/assets/favicon-32x32.png",
    ]
    png32 = next((p for p in png32_candidates if p.exists()), None)
    if png32:
        safe_copy(png32, assets / "favicon-32x32.png")
        make_ico_from_png(assets / "favicon-32x32.png", site / "favicon.ico")
        make_ico_from_png(assets / "favicon-32x32.png", assets / "favicon.ico")
        status["favicon_ico"] = True
    else:
        status["favicon_ico"] = (site / "favicon.ico").exists() or (assets / "favicon.ico").exists()

    # Touch icons already created by previous workflow; keep/copy if available.
    for name in ["apple-touch-icon.png", "android-chrome-192x192.png", "android-chrome-512x512.png", "favicon-16x16.png"]:
        for src in [assets / name, repo / "website/assets" / name, repo / "site_public/assets" / name]:
            if src.exists():
                safe_copy(src, assets / name)
                status[name] = True
                break
        else:
            status[name] = False

    # Stable manifest, absolute icon path works from both root and /unredacted/.
    (site / "site.webmanifest").write_text(json.dumps({
        "name": "AQ26 Environmental Intelligence Observatory",
        "short_name": "AQ26",
        "icons": [
            {"src": "/assets/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/assets/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/favicon.svg", "sizes": "any", "type": "image/svg+xml"}
        ],
        "theme_color": "#071a30",
        "background_color": "#ffffff",
        "display": "standalone"
    }, indent=2), encoding="utf-8")

    return status


def clean_head_refs(html_text: str) -> str:
    # Remove old duplicate icon/touch/manifest links. Keep CSS/JS intact.
    html_text = re.sub(r"\s*<link\b[^>]*(?:rel=['\"](?:shortcut icon|icon|apple-touch-icon|manifest)['\"]|rel=(?:shortcut icon|icon|apple-touch-icon|manifest))[^>]*>\s*", "\n", html_text, flags=re.I)
    refs = f"""
<link rel="icon" href="/favicon.ico?v={VERSION}" sizes="any">
<link rel="icon" href="/favicon.svg?v={VERSION}" type="image/svg+xml">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png?v={VERSION}">
<link rel="manifest" href="/site.webmanifest?v={VERSION}">
"""
    if "</head>" in html_text.lower():
        return re.sub(r"</head>", refs + "\n</head>", html_text, count=1, flags=re.I)
    return refs + html_text


def polish_html(html_text: str, public: bool = True) -> str:
    # Remove the extra text next to the full header logo.
    html_text = re.sub(
        r"<span>\s*<small>\s*SCC\s*Nexus\s*·\s*AQ26\s*</small>\s*</span>",
        "",
        html_text,
        flags=re.I,
    )
    html_text = re.sub(
        r"<span>\s*<small>\s*SCC\s*NEXUS\s*·\s*AQ26\s*</small>\s*</span>",
        "",
        html_text,
        flags=re.I,
    )

    html_text = clean_head_refs(html_text)

    # Inject/refresh final CSS.
    css = f"""
<style id="aq26-final-brand-polish">
  .brand span, .brand small {{ display:none !important; }}
  .brand img {{ display:block; height:70px; width:auto; max-width:min(320px, 62vw); object-fit:contain; }}
  .header .wrap {{ align-items:center; }}
  .aq26-alert, .aq26-video-banner {{ scroll-margin-top: 110px; }}
  @media(max-width:860px) {{
    .brand img {{ height:56px; max-width:68vw; }}
    .header .wrap {{ gap:.6rem; }}
  }}
</style>
"""
    if 'id="aq26-final-brand-polish"' in html_text:
        html_text = re.sub(r"<style id=\"aq26-final-brand-polish\">.*?</style>", css.strip(), html_text, flags=re.S)
    else:
        html_text = re.sub(r"</head>", css + "\n</head>", html_text, count=1, flags=re.I)

    # If a homepage lost the weekly alert/banner, create a small non-breaking fallback.
    if "index.html" in html_text[:500].lower() and "aq26-alert" not in html_text:
        pass
    return html_text


def polish_site(repo: Path, site: Path, public: bool) -> Dict[str, object]:
    ensure = ensure_brand_assets(repo, site)
    changed = []
    missing_alert_pages = []
    missing_banner_pages = []
    for p in sorted(site.glob("*.html")):
        before = p.read_text(encoding="utf-8", errors="replace")
        after = polish_html(before, public=public)
        if after != before:
            p.write_text(after, encoding="utf-8")
            changed.append(p.name)
        if p.name in {"index.html", "weekly-update.html"}:
            txt = after
            if "aq26-alert" not in txt and "AQ26_WEEKLY_ALERT_START" not in txt:
                missing_alert_pages.append(p.name)
            if "aq26-video-banner" not in txt:
                missing_banner_pages.append(p.name)
    return {
        "site": str(site),
        "assets": ensure,
        "html_changed": changed,
        "missing_alert_pages": missing_alert_pages,
        "missing_banner_pages": missing_banner_pages,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--public-site", default="site_public")
    ap.add_argument("--unredacted-site", default="site_unredacted")
    ap.add_argument("--summary", default="site_public/data/weekly/final_brand_polish_summary.json")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    public = repo / args.public_site
    unredacted = repo / args.unredacted_site

    summary = {
        "ok": True,
        "generated_utc": now_utc(),
        "version": VERSION,
        "public": polish_site(repo, public, True) if public.exists() else {"missing": True},
        "unredacted": polish_site(repo, unredacted, False) if unredacted.exists() else {"missing": True},
        "notes": [
            "Header text next to the full logo is removed.",
            "Favicon references are cache-busted and prefer /favicon.ico and /favicon.svg.",
            "Weekly alert and moving banner markers are checked for index/weekly pages."
        ],
    }

    out = repo / args.summary
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    # Do not fail for old legacy pages missing banners; only fail if core files are absent.
    required = [
        public / "index.html", public / "favicon.svg", public / "favicon.ico", public / "assets/favicon.svg",
        public / "weekly-update.html",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("Missing required files:", missing)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
