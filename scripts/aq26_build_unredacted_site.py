#!/usr/bin/env python3
"""
AQ26 Unredacted Site Builder

Builds a small password-protected internal evidence portal from existing AQ26 outputs.
This is a presentation/index layer, not a raw-data lake. It copies selected manifests,
reports and compact tables into site_unredacted/data and generates a navigable index.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_read_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def rel_or_abs(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(path)


def copy_if_exists(src: Path, dest_root: Path, repo: Path, max_bytes: int, group: str, rows: List[Dict[str, Any]]) -> None:
    if not src.exists() or not src.is_file():
        return
    size = src.stat().st_size
    if size > max_bytes:
        rows.append({
            "group": group,
            "source_path": rel_or_abs(src, repo),
            "site_path": None,
            "size_bytes": size,
            "copied": False,
            "reason": f"skipped_over_{max_bytes}_bytes",
        })
        return
    dest = dest_root / rel_or_abs(src, repo)
    mkdir(dest.parent)
    shutil.copy2(src, dest)
    rows.append({
        "group": group,
        "source_path": rel_or_abs(src, repo),
        "site_path": rel_or_abs(dest, dest_root),
        "size_bytes": size,
        "copied": True,
        "reason": "copied",
    })


def find_files(repo: Path, patterns: List[str], max_count: int = 200) -> List[Path]:
    out: List[Path] = []
    seen = set()
    for pat in patterns:
        for p in repo.glob(pat):
            if p.is_file() and p not in seen:
                out.append(p); seen.add(p)
                if len(out) >= max_count:
                    return out
    return out


def write_json(path: Path, obj: Any) -> None:
    mkdir(path.parent)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def write_css(path: Path) -> None:
    mkdir(path.parent)
    path.write_text("""
:root{--bg:#08111f;--panel:#101c2f;--panel2:#13253d;--text:#eef7ff;--muted:#a9bdd1;--accent:#46d9ff;--accent2:#91ffb8;--warn:#ffd166;--bad:#ff6b6b;--line:rgba(255,255,255,.12)}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#17375f 0,#08111f 38%,#050911 100%);font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;color:var(--text)}
a{color:var(--accent)}.wrap{max-width:1180px;margin:0 auto;padding:28px}.hero{padding:38px;border:1px solid var(--line);border-radius:28px;background:linear-gradient(135deg,rgba(70,217,255,.14),rgba(145,255,184,.08)),rgba(16,28,47,.82);box-shadow:0 20px 60px rgba(0,0,0,.35)}
.kicker{letter-spacing:.12em;text-transform:uppercase;color:var(--accent2);font-weight:800;font-size:.78rem}.hero h1{font-size:clamp(2.1rem,5vw,4.4rem);line-height:1.02;margin:.35em 0}.hero p{font-size:1.1rem;color:var(--muted);max-width:860px}.pillbar{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}.pill{border:1px solid var(--line);border-radius:999px;padding:9px 13px;background:rgba(255,255,255,.06);font-size:.9rem;color:#d9ecff}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:18px;margin-top:22px}.card{grid-column:span 4;background:rgba(16,28,47,.78);border:1px solid var(--line);border-radius:22px;padding:20px;box-shadow:0 12px 34px rgba(0,0,0,.25)}.card.wide{grid-column:span 8}.card.full{grid-column:1/-1}.metric{font-size:2.25rem;font-weight:900;color:var(--accent)}.label{color:var(--muted);font-size:.92rem}.section-title{margin:36px 0 12px;font-size:1.6rem}.warning{border-left:4px solid var(--warn);background:rgba(255,209,102,.10);padding:14px 16px;border-radius:14px;color:#fff5d6}.danger{border-left:4px solid var(--bad);background:rgba(255,107,107,.10);padding:14px 16px;border-radius:14px;color:#ffe7e7}.table-wrap{overflow:auto;border-radius:16px;border:1px solid var(--line)}table{width:100%;border-collapse:collapse;background:rgba(255,255,255,.03)}th,td{padding:11px 12px;border-bottom:1px solid var(--line);text-align:left;font-size:.92rem;vertical-align:top}th{background:rgba(255,255,255,.08);position:sticky;top:0}.small{font-size:.86rem;color:var(--muted)}.file-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.file{border:1px solid var(--line);border-radius:16px;padding:14px;background:rgba(255,255,255,.04)}.tag{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 8px;font-size:.75rem;color:var(--muted);margin:2px}.footer{margin:40px 0 10px;color:var(--muted);font-size:.85rem}@media(max-width:850px){.card,.card.wide{grid-column:1/-1}.wrap{padding:16px}.hero{padding:24px}}
""".strip(), encoding="utf-8")


def summarise_manifest(repo: Path) -> Dict[str, Any]:
    candidates = [
        repo / "site_public/data/latest_backfill_summary.json",
        repo / "site_public/data/weekly_index.json",
        repo / "outputs/99_integrity/AQ26_WEEKLYV2_SCIENCE_V33_VALIDATION.json",
        repo / "site_public/data/providers/laqn/chart_safe/index.json",
        repo / "site_public/data/providers/earthdata/summary.json",
        repo / "site_public/data/providers/earthdata/stage2/summary.json",
    ]
    out: Dict[str, Any] = {}
    for p in candidates:
        data = safe_read_json(p)
        if data is not None:
            out[rel_or_abs(p, repo)] = data
    return out


def html_escape(x: Any) -> str:
    return html.escape("" if x is None else str(x))


def build_index(site: Path, manifest: Dict[str, Any], copied: List[Dict[str, Any]], public_url: str) -> None:
    latest = manifest.get("site_public/data/latest_backfill_summary.json", {}) or {}
    weekly = manifest.get("site_public/data/weekly_index.json", {}) or {}
    validation = manifest.get("outputs/99_integrity/AQ26_WEEKLYV2_SCIENCE_V33_VALIDATION.json", {}) or {}
    laqn = manifest.get("site_public/data/providers/laqn/chart_safe/index.json", {}) or {}
    earth = manifest.get("site_public/data/providers/earthdata/summary.json", {}) or manifest.get("site_public/data/providers/earthdata/stage2/summary.json", {}) or {}

    def val(*keys: str, default: Any = "—") -> Any:
        for src in (latest, weekly, validation, laqn, earth):
            cur = src
            ok = True
            for k in keys:
                if isinstance(cur, dict) and k in cur:
                    cur = cur[k]
                else:
                    ok = False; break
            if ok:
                return cur
        return default

    copied_count = sum(1 for r in copied if r.get("copied"))
    skipped_count = sum(1 for r in copied if not r.get("copied"))
    rows = "\n".join(
        f"<tr><td>{html_escape(r.get('group'))}</td><td>{html_escape(r.get('source_path'))}</td><td>{html_escape(r.get('site_path') or 'not copied')}</td><td>{html_escape(r.get('size_bytes'))}</td><td>{html_escape(r.get('reason'))}</td></tr>"
        for r in copied[:400]
    )
    manifest_blocks = "\n".join(
        f"<div class='file'><b>{html_escape(k)}</b><pre class='small'>{html_escape(json.dumps(v, indent=2, default=str)[:2400])}</pre></div>"
        for k, v in manifest.items()
    )
    html_doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><title>AQ26 Unredacted Evidence Portal</title><link rel="stylesheet" href="assets/aq26_unredacted.css"></head>
<body><div class="wrap">
<section class="hero"><div class="kicker">Restricted internal portal</div><h1>AQ26 Unredacted Evidence</h1><p>This password-protected area is for internal review, QA, provenance inspection and unredacted evidence outputs. The public website remains the accessible client-facing interface.</p><div class="pillbar"><span class="pill">Basic-auth protected</span><span class="pill">Noindex</span><span class="pill">Generated {html_escape(now_utc())}</span><span class="pill">Public site: {html_escape(public_url)}</span></div></section>
<div class="grid"><div class="card"><div class="metric">{copied_count}</div><div class="label">Copied evidence files</div></div><div class="card"><div class="metric">{skipped_count}</div><div class="label">Large/skipped files</div></div><div class="card"><div class="metric">{html_escape(val('cmr_collections', default=val('collections', default='—')))}</div><div class="label">Earthdata catalogue candidates</div></div><div class="card"><div class="metric">{html_escape(val('flat_rows', default=val('site_species_flat_rows', default='—')))}</div><div class="label">LAQN flat site/species rows</div></div><div class="card"><div class="metric">{html_escape(val('warnings', default=val('warning_count', default='—')))}</div><div class="label">Validation warnings</div></div><div class="card"><div class="metric">{html_escape(val('errors', default=val('error_count', default='—')))}</div><div class="label">Validation errors</div></div></div>
<h2 class="section-title">Security and use boundary</h2><div class="danger"><b>Restricted:</b> this area may include unredacted internal filenames, record-level payloads, validation detail and candidate evidence. Do not share links, screenshots or downloads externally without review.</div>
<h2 class="section-title">Available summary manifests</h2><div class="file-list">{manifest_blocks or '<div class="file">No recognised summary manifests were found yet.</div>'}</div>
<h2 class="section-title">Copied evidence index</h2><div class="table-wrap"><table><thead><tr><th>Group</th><th>Source path</th><th>Site path</th><th>Size bytes</th><th>Reason</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="footer">AQ26 unredacted portal generated by scripts/aq26_build_unredacted_site.py. Raw data lake remains outside the public website.</p>
</div></body></html>"""
    (site / "index.html").write_text(html_doc, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--site-root", default="site_unredacted")
    ap.add_argument("--max-copy-mb", type=int, default=25, help="Maximum individual file size to copy into unredacted site.")
    ap.add_argument("--public-url", default="https://sccwebdesigntest.co.uk/")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    site = repo / args.site_root
    if site.exists():
        shutil.rmtree(site)
    mkdir(site / "assets")
    mkdir(site / "data")
    write_css(site / "assets/aq26_unredacted.css")

    max_bytes = args.max_copy_mb * 1024 * 1024
    copied: List[Dict[str, Any]] = []

    groups = {
        "public_summaries": [
            "site_public/data/**/*.json",
        ],
        "integrity_validation": [
            "outputs/99_integrity/**/*.json",
            "outputs/**/validation*.json",
            "outputs/**/*validation*.csv",
            "outputs/**/*manifest*.json",
            "outputs/**/*verification*.csv",
        ],
        "reports": [
            "outputs/**/*.html",
            "outputs/**/*.pdf",
            "outputs/**/*.xlsx",
        ],
        "laqn": [
            "outputs/31_laqn/**/*",
            "outputs/35_laqn_backfill/**/*",
        ],
        "earthdata": [
            "outputs/32_earthdata/**/*",
            "outputs/34_earthdata*/*",
        ],
        "weekly": [
            "outputs/10_historical_backfill/**/*",
            "outputs/36_weekly*/*",
            "outputs/40_integrated_evidence/**/*",
            "outputs/41_weekly_report/**/*",
        ],
    }
    for group, pats in groups.items():
        for src in find_files(repo, pats, max_count=500):
            copy_if_exists(src, site / "data", repo, max_bytes, group, copied)

    manifest = summarise_manifest(repo)
    write_json(site / "data/unredacted_file_index.json", copied)
    write_json(site / "data/unredacted_summary_manifest.json", manifest)
    build_index(site, manifest, copied, args.public_url)
    (site / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "site_root": str(site), "copied": sum(1 for r in copied if r.get("copied")), "skipped": sum(1 for r in copied if not r.get("copied"))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
