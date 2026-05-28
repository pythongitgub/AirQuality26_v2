#!/usr/bin/env python3
"""AQ26 brand/favicon/touch-icon enforcement.

Use after any site builder because generated pages may overwrite <head> links.
The visible header can continue using air_quality_web.svg, while the compact
logo_web.svg is enforced as favicon/touch/home-screen icon.
"""
from __future__ import annotations

import argparse, html, json, re, shutil, sys
from pathlib import Path
from typing import Iterable


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


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


def find_asset(repo: Path, name: str, override: str = "") -> Path | None:
    candidates = []
    if override:
        candidates.append(Path(override))
    candidates += [
        repo / "website/assets" / name,
        repo / "site_public/assets" / name,
        repo / "site_unredacted/assets" / name,
        repo / name,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def generate_pngs_if_possible(svg: Path, assets: Path) -> None:
    sizes = {
        "apple-touch-icon.png": 180,
        "android-chrome-192x192.png": 192,
        "android-chrome-512x512.png": 512,
        "favicon-32x32.png": 32,
        "favicon-16x16.png": 16,
    }
    try:
        import cairosvg  # type: ignore
    except Exception:
        print("cairosvg not available; SVG favicon still enforced, PNG touch icons unchanged/skipped")
        return
    for name, size in sizes.items():
        out = assets / name
        if out.exists():
            continue
        try:
            cairosvg.svg2png(url=str(svg), write_to=str(out), output_width=size, output_height=size)
        except Exception as e:
            print(f"warning: could not generate {name}: {e}")


def ensure_manifest(site: Path) -> None:
    manifest = {
        "name": "AQ26 Incinerator Evidence Observatory",
        "short_name": "AQ26",
        "icons": [
            {"src": "assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
            {"src": "assets/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
            {"src": "assets/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "assets/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
        ],
        "theme_color": "#071a30",
        "background_color": "#f5f8fc",
        "display": "standalone",
    }
    write_text(site / "site.webmanifest", json.dumps(manifest, indent=2))


def strip_old_icon_links(head: str) -> str:
    # Remove existing favicon/touch/manifest links so the canonical set is last and unambiguous.
    patterns = [
        r"<link\s+[^>]*(?:rel=['\"](?:shortcut icon|icon|apple-touch-icon|manifest)['\"]|href=['\"][^'\"]*(?:favicon|apple-touch|android-chrome|site\.webmanifest)[^'\"]*)[^>]*>\s*",
        r"<meta\s+name=['\"]theme-color['\"][^>]*>\s*",
    ]
    for pat in patterns:
        head = re.sub(pat, "", head, flags=re.I)
    return head


def enforce_head(html_text: str, version: str) -> str:
    canonical = "\n".join([
        f'<link rel="icon" href="/favicon.svg?v={version}" type="image/svg+xml">',
        f'<link rel="icon" href="assets/favicon.svg?v={version}" type="image/svg+xml">',
        f'<link rel="icon" sizes="32x32" href="assets/favicon-32x32.png?v={version}" type="image/png">',
        f'<link rel="icon" sizes="16x16" href="assets/favicon-16x16.png?v={version}" type="image/png">',
        f'<link rel="apple-touch-icon" href="assets/apple-touch-icon.png?v={version}">',
        f'<link rel="manifest" href="site.webmanifest?v={version}">',
        '<meta name="theme-color" content="#071a30">',
    ])
    if "</head>" not in html_text.lower():
        return html_text
    def repl(m: re.Match) -> str:
        head = strip_old_icon_links(m.group(1))
        return head + "\n" + canonical + "\n</head>"
    return re.sub(r"(?is)(.*?)(</head>)", lambda m: repl(m), html_text, count=1)


def process_site(site: Path, repo: Path, favicon_override: str, version: str) -> dict:
    assets = site / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    fav = find_asset(repo, "logo_web.svg", favicon_override) or find_asset(repo, "favicon.svg", favicon_override)
    if not fav:
        raise SystemExit("No logo_web.svg/favicon.svg found to use as favicon")
    safe_copy(fav, assets / "favicon.svg")
    safe_copy(fav, assets / "logo_web.svg")
    safe_copy(fav, site / "favicon.svg")
    # Keep visible report header logo if present.
    air = find_asset(repo, "air_quality_web.svg")
    if air:
        safe_copy(air, assets / "air_quality_web.svg")
    generate_pngs_if_possible(assets / "favicon.svg", assets)
    ensure_manifest(site)
    updated = 0
    for html_file in site.glob("*.html"):
        txt = read_text(html_file)
        new = enforce_head(txt, version)
        if new != txt:
            write_text(html_file, new)
            updated += 1
    status = {
        "ok": True,
        "site": str(site),
        "favicon_source": str(fav),
        "updated_html_files": updated,
        "assets": [p.name for p in sorted(assets.glob("favicon*"))] + [p.name for p in sorted(assets.glob("*touch*"))],
    }
    out = site / "data/weekly/brand_asset_status.json"
    write_text(out, json.dumps(status, indent=2))
    print(json.dumps(status, indent=2))
    return status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--site-root", action="append", required=True, help="Can be provided more than once")
    ap.add_argument("--favicon-source", default="")
    ap.add_argument("--version", default="aq26-logo-20260528")
    args = ap.parse_args()
    repo = Path(args.repo_root).resolve()
    for s in args.site_root:
        process_site((repo / s).resolve(), repo, args.favicon_source, args.version)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
