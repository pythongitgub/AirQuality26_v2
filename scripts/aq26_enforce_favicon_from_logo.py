#!/usr/bin/env python3
"""AQ26 favicon/touch-icon enforcement from canonical logo_web.svg.

Safe to run repeatedly. It avoids SameFileError, writes root + asset favicon
files for both public and unredacted sites, and updates HTML <head> references.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def same_file(src: Path, dst: Path) -> bool:
    try:
        return src.resolve() == dst.resolve()
    except Exception:
        return False


def safe_copy(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if same_file(src, dst):
        return False
    try:
        if dst.exists() and src.read_bytes() == dst.read_bytes():
            return False
    except Exception:
        pass
    shutil.copyfile(src, dst)
    return True


def ensure_icon_tools() -> None:
    # Workflow normally installs cairosvg+pillow. The script still runs if they are missing.
    return None


def render_pngs(svg: Path, outdir: Path, summary: Dict) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    sizes = {
        "favicon-16x16.png": 16,
        "favicon-32x32.png": 32,
        "apple-touch-icon.png": 180,
        "android-chrome-192x192.png": 192,
        "android-chrome-512x512.png": 512,
    }
    try:
        import cairosvg  # type: ignore
        from PIL import Image  # type: ignore
        png_paths: List[Path] = []
        for name, size in sizes.items():
            dst = outdir / name
            cairosvg.svg2png(url=str(svg), write_to=str(dst), output_width=size, output_height=size)
            png_paths.append(dst)
            summary["generated_pngs"].append(str(dst))
        # Multi-size .ico for browser tabs.
        ico_dst = outdir / "favicon.ico"
        imgs = [Image.open(p).convert("RGBA") for p in png_paths if p.name in {"favicon-16x16.png", "favicon-32x32.png", "android-chrome-192x192.png"}]
        if imgs:
            imgs[0].save(ico_dst, sizes=[(16,16),(32,32),(48,48),(64,64)])
            summary["generated_ico"].append(str(ico_dst))
    except Exception as e:
        summary["warnings"].append(f"PNG/ICO render skipped: {type(e).__name__}: {e}")


def inject_head_refs(path: Path, version: str) -> bool:
    if not path.exists() or path.suffix.lower() != ".html":
        return False
    txt = path.read_text(encoding="utf-8", errors="replace")
    original = txt
    refs = [
        f'<link rel="icon" href="/favicon.ico?v={version}" sizes="any">',
        f'<link rel="icon" href="/favicon.svg?v={version}" type="image/svg+xml">',
        f'<link rel="icon" href="assets/favicon.svg?v={version}" type="image/svg+xml">',
        f'<link rel="apple-touch-icon" href="assets/apple-touch-icon.png?v={version}">',
        f'<link rel="manifest" href="site.webmanifest?v={version}">',
    ]
    # Remove earlier AQ26 favicon refs to avoid browser picking stale duplicate entries.
    txt = txt.replace("<link rel='icon' href='assets/favicon.svg?v=operational'>", "")
    txt = txt.replace('<link rel="icon" href="assets/favicon.svg?v=aq26-weekly">', "")
    txt = txt.replace('<link rel="icon" href="assets/favicon.svg?v=aq26-weekly" type="image/svg+xml">', "")
    txt = txt.replace('<link rel="icon" href="/favicon.svg?v=aq26-weekly" type="image/svg+xml">', "")
    for ref in refs:
        key = ref.split('href="', 1)[1].split('"', 1)[0].split('?', 1)[0]
        if key not in txt:
            txt = txt.replace("</head>", ref + "\n</head>", 1)
    if txt != original:
        path.write_text(txt, encoding="utf-8")
        return True
    return False


def write_manifest(site: Path, version: str) -> None:
    manifest = {
        "name": "AQ26 Incinerator Evidence Observatory",
        "short_name": "AQ26",
        "icons": [
            {"src": "assets/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "assets/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
        "theme_color": "#071a30",
        "background_color": "#f4f8fb",
        "display": "standalone",
    }
    (site / "site.webmanifest").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--public-site", default="site_public")
    ap.add_argument("--unredacted-site", default="site_unredacted")
    ap.add_argument("--source-logo", default="website/assets/logo_web.svg")
    ap.add_argument("--version", default="aq26-favicon-20260528")
    ap.add_argument("--summary", default="site_public/data/weekly/favicon_enforcement_status.json")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    src = (repo / args.source_logo).resolve()
    summary: Dict = {"ok": False, "generated_utc": now_utc(), "source_logo": str(src), "copied": [], "generated_pngs": [], "generated_ico": [], "html_updated": [], "warnings": []}
    if not src.exists():
        raise SystemExit(f"source logo missing: {src}")

    # Canonical repo assets.
    safe_copy(src, repo / "website/assets/logo_web.svg")
    if safe_copy(src, repo / "website/assets/favicon.svg"):
        summary["copied"].append("website/assets/favicon.svg")

    for site_rel in [args.public_site, args.unredacted_site]:
        site = repo / site_rel
        assets = site / "assets"
        site.mkdir(parents=True, exist_ok=True)
        assets.mkdir(parents=True, exist_ok=True)
        for dst in [site / "favicon.svg", assets / "favicon.svg", assets / "logo_web.svg"]:
            if safe_copy(src, dst):
                summary["copied"].append(str(dst.relative_to(repo)))
        render_pngs(src, assets, summary)
        # root favicon.ico mirrors generated asset icon when available.
        safe_copy(assets / "favicon.ico", site / "favicon.ico")
        write_manifest(site, args.version)
        for html_file in site.glob("*.html"):
            if inject_head_refs(html_file, args.version):
                summary["html_updated"].append(str(html_file.relative_to(repo)))

    out = repo / args.summary
    out.parent.mkdir(parents=True, exist_ok=True)
    summary["ok"] = True
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
