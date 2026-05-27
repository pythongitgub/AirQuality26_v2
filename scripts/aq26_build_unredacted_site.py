#!/usr/bin/env python3
"""
AQ26 unredacted internal review site builder.

Builds a complete password-protected review website payload in site_unredacted/.
The workflow adds .htaccess/.htpasswd afterwards; this script only builds the site.

Usage:
  python scripts/aq26_build_unredacted_site.py \
    --repo-root . \
    --public-site site_public \
    --output-site site_unredacted \
    --max-index-files 250
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SKIP_DIR_NAMES = {
    ".git",
    ".github",
    "__pycache__",
    ".ipynb_checkpoints",
    "node_modules",
    "site_unredacted",
}

INTERNAL_EXTS = {
    ".json", ".csv", ".parquet", ".xlsx", ".xls", ".pdf", ".html", ".txt", ".md", ".png", ".jpg", ".jpeg", ".svg"
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def rel_to(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except Exception:
        return path.as_posix()


def copy_public_site(public_site: Path, output_site: Path) -> Dict[str, Any]:
    if output_site.exists():
        shutil.rmtree(output_site)
    ensure_dir(output_site)

    copied = 0
    skipped = 0
    if public_site.exists():
        for src in public_site.rglob("*"):
            if src.is_dir():
                continue
            parts = set(src.parts)
            if any(part in SKIP_DIR_NAMES for part in parts):
                skipped += 1
                continue
            dst = output_site / src.relative_to(public_site)
            ensure_dir(dst.parent)
            shutil.copy2(src, dst)
            copied += 1
    return {"public_site_exists": public_site.exists(), "files_copied": copied, "files_skipped": skipped}


def discover_files(repo_root: Path, output_site: Path, max_files: int) -> List[Dict[str, Any]]:
    roots = [repo_root / "outputs", repo_root / "site_public" / "data", repo_root / "docs"]
    rows: List[Dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if len(rows) >= max_files:
                break
            if not p.is_file():
                continue
            if p.suffix.lower() not in INTERNAL_EXTS:
                continue
            if output_site in p.parents:
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            rows.append({
                "name": p.name,
                "relative_path": rel_to(p, repo_root),
                "suffix": p.suffix.lower(),
                "size_bytes": int(size),
                "size_mb": round(size / 1024 / 1024, 3),
                "modified_utc": dt.datetime.fromtimestamp(p.stat().st_mtime, tz=dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            })
    rows.sort(key=lambda r: (r.get("modified_utc", ""), r.get("relative_path", "")), reverse=True)
    return rows[:max_files]


def read_json_optional(path: Path) -> Optional[Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def dashboard_summary(repo_root: Path, indexed_files: List[Dict[str, Any]]) -> Dict[str, Any]:
    latest_backfill = read_json_optional(repo_root / "site_public" / "data" / "latest_backfill_summary.json")
    weekly_index = read_json_optional(repo_root / "site_public" / "data" / "weekly_index.json")
    laqn_summary = read_json_optional(repo_root / "site_public" / "data" / "providers" / "laqn" / "chart_safe" / "index.json")
    earthdata_summary = read_json_optional(repo_root / "site_public" / "data" / "providers" / "earthdata" / "summary.json")
    auth_summary = read_json_optional(repo_root / "site_public" / "data" / "providers" / "earthdata" / "auth_smoke_summary.json")

    return {
        "generated_utc": utc_now(),
        "site_type": "unredacted_internal_review",
        "caveat": "Password-protected internal review interface. Do not share publicly.",
        "indexed_file_count": len(indexed_files),
        "latest_backfill_summary_available": latest_backfill is not None,
        "weekly_index_available": weekly_index is not None,
        "laqn_summary_available": laqn_summary is not None,
        "earthdata_summary_available": earthdata_summary is not None,
        "earthdata_auth_summary_available": auth_summary is not None,
        "latest_backfill_summary": latest_backfill if isinstance(latest_backfill, dict) else None,
        "laqn_summary": laqn_summary if isinstance(laqn_summary, dict) else None,
        "earthdata_summary": earthdata_summary if isinstance(earthdata_summary, dict) else None,
        "earthdata_auth_summary": auth_summary if isinstance(auth_summary, dict) else None,
    }


def css() -> str:
    return """
:root{--bg:#08111f;--panel:#101b2e;--panel2:#14243d;--text:#edf6ff;--muted:#a9bad3;--accent:#49d3ff;--accent2:#9cff6b;--warn:#ffd166;--bad:#ff6b6b;--line:rgba(255,255,255,.12)}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:radial-gradient(circle at 20% 0%,#193762 0,#08111f 38%,#050914 100%);color:var(--text);line-height:1.55}.wrap{width:min(1180px,92vw);margin:0 auto}.topbar{position:sticky;top:0;z-index:20;background:rgba(8,17,31,.88);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}.nav{display:flex;align-items:center;justify-content:space-between;padding:16px 0}.brand{display:flex;align-items:center;gap:12px;font-weight:800;letter-spacing:.2px}.logo{width:42px;height:42px;border-radius:14px;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 0 24px rgba(73,211,255,.35)}.nav a{color:var(--text);text-decoration:none;margin-left:18px;font-weight:700;opacity:.88}.hero{padding:58px 0 34px}.eyebrow{color:var(--accent2);font-weight:800;text-transform:uppercase;letter-spacing:.12em;font-size:13px}.hero h1{font-size:clamp(34px,6vw,72px);line-height:.98;margin:16px 0;max-width:960px}.hero p{color:var(--muted);font-size:20px;max-width:850px}.pillrow{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}.pill{border:1px solid var(--line);background:rgba(255,255,255,.07);padding:9px 13px;border-radius:999px;color:#dbeafe;font-weight:700}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:18px;margin:26px 0}.card{grid-column:span 4;background:linear-gradient(180deg,rgba(255,255,255,.08),rgba(255,255,255,.04));border:1px solid var(--line);border-radius:24px;padding:22px;box-shadow:0 18px 50px rgba(0,0,0,.24)}.card.wide{grid-column:span 8}.card.full{grid-column:1/-1}.metric{font-size:42px;font-weight:900;line-height:1;margin:10px 0}.label{color:var(--muted);font-weight:700}.ok{color:var(--accent2)}.warn{color:var(--warn)}.bad{color:var(--bad)}.section{padding:20px 0 48px}.section h2{font-size:30px;margin:0 0 12px}.tablewrap{overflow:auto;border-radius:18px;border:1px solid var(--line)}table{width:100%;border-collapse:collapse;background:rgba(255,255,255,.04)}th,td{text-align:left;padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}th{color:#d7eeff;background:rgba(73,211,255,.08)}td{color:#dce8f7;font-size:14px}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}.btn{display:inline-block;padding:12px 16px;border-radius:14px;background:linear-gradient(135deg,var(--accent),#6aa6ff);color:#02101d;text-decoration:none;font-weight:900}.btn.alt{background:rgba(255,255,255,.08);color:var(--text);border:1px solid var(--line)}.footer{border-top:1px solid var(--line);padding:24px 0 42px;color:var(--muted)}code{background:rgba(255,255,255,.08);padding:2px 6px;border-radius:8px}@media(max-width:850px){.card,.card.wide{grid-column:1/-1}.nav{align-items:flex-start;gap:10px;flex-direction:column}.nav a{margin-left:0;margin-right:12px}.hero{padding-top:34px}}
""".strip()


def html_page(title: str, active: str, body: str, generated_utc: str) -> str:
    nav_links = "".join([
        '<a href="index.html">Dashboard</a>',
        '<a href="evidence.html">Evidence files</a>',
        '<a href="../">Public site</a>',
    ])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="assets/aq26_unredacted.css">
</head>
<body>
  <header class="topbar"><div class="wrap nav"><div class="brand"><span class="logo"></span><span>AQ26 Unredacted Review</span></div><nav>{nav_links}</nav></div></header>
  {body}
  <footer class="footer"><div class="wrap">Internal unredacted review site. Generated {html.escape(generated_utc)}. Protected by server-side authentication where configured.</div></footer>
</body>
</html>
"""


def card(title: str, value: str, label: str, cls: str = "") -> str:
    return f"""<article class="card"><div class="label">{html.escape(title)}</div><div class="metric {html.escape(cls)}">{html.escape(value)}</div><p>{html.escape(label)}</p></article>"""


def build_index_html(summary: Dict[str, Any]) -> str:
    latest = summary.get("latest_backfill_summary") or {}
    laqn = summary.get("laqn_summary") or {}
    earth = summary.get("earthdata_summary") or {}
    auth = summary.get("earthdata_auth_summary") or {}

    status = str(latest.get("status") or latest.get("overall_status") or "review")
    records = str(latest.get("source_records") or latest.get("record_count") or "—")
    weeks = "—"
    if isinstance(latest.get("weekly_index"), dict):
        weeks = str(latest["weekly_index"].get("harvested_weeks", "—"))

    body = f"""
<main>
  <section class="hero"><div class="wrap">
    <div class="eyebrow">Password-protected internal evidence interface</div>
    <h1>Unredacted AQ26 review dashboard</h1>
    <p>Internal access point for validation, provenance checks, source files, evidence QA and deployment review. The public site remains the accessible client interface; this area is for deeper review.</p>
    <div class="pillrow">
      <span class="pill">Unredacted review</span><span class="pill">Provenance</span><span class="pill">Validation</span><span class="pill">Weekly evidence</span>
    </div>
    <div class="actions"><a class="btn" href="evidence.html">Open evidence file index</a><a class="btn alt" href="data/unredacted/dashboard_summary.json">Download summary JSON</a></div>
  </div></section>
  <section class="section"><div class="wrap grid">
    {card('Latest run status', status.upper(), 'Status from the latest available backfill/integrated summary.', 'ok' if status.lower() in {'ok','success','passed'} else 'warn')}
    {card('Indexed review files', str(summary.get('indexed_file_count', 0)), 'Files discovered for internal review from outputs, site data and docs.')}
    {card('Latest source records', records, 'Available source/evidence record count from latest summary where present.')}
    {card('LAQN layer', 'READY' if summary.get('laqn_summary_available') else 'PENDING', 'London Air / LAQN chart-safe outputs detected.' if summary.get('laqn_summary_available') else 'LAQN chart-safe summary not found.', 'ok' if summary.get('laqn_summary_available') else 'warn')}
    {card('Earthdata CMR', 'READY' if summary.get('earthdata_summary_available') else 'PENDING', 'NASA Earthdata discovery summary detected.' if summary.get('earthdata_summary_available') else 'Earthdata summary not found.', 'ok' if summary.get('earthdata_summary_available') else 'warn')}
    {card('Earthdata auth', 'READY' if summary.get('earthdata_auth_summary_available') else 'PENDING', 'Earthdata authentication smoke summary detected.' if summary.get('earthdata_auth_summary_available') else 'Earthdata auth smoke summary not found.', 'ok' if summary.get('earthdata_auth_summary_available') else 'warn')}
    <article class="card full"><h2>Review priorities</h2>
      <p>Use this internal site to check that the public dashboard is backed by valid source records, that warnings are clearly caveated, and that unredacted evidence remains separated from the client-facing website.</p>
      <div class="pillrow"><span class="pill">Check missing data</span><span class="pill">Verify provenance</span><span class="pill">Review warnings</span><span class="pill">Approve public summaries</span></div>
    </article>
  </div></section>
</main>
"""
    return html_page("AQ26 Unredacted Review", "dashboard", body, summary.get("generated_utc", utc_now()))


def build_evidence_html(files: List[Dict[str, Any]], generated_utc: str) -> str:
    rows = []
    for item in files:
        rp = str(item.get("relative_path", ""))
        rows.append(
            "<tr>"
            f"<td>{html.escape(item.get('name', ''))}</td>"
            f"<td><code>{html.escape(rp)}</code></td>"
            f"<td>{html.escape(item.get('suffix', ''))}</td>"
            f"<td>{html.escape(str(item.get('size_mb', '')))}</td>"
            f"<td>{html.escape(item.get('modified_utc', ''))}</td>"
            "</tr>"
        )
    table_rows = "\n".join(rows) if rows else '<tr><td colspan="5">No review files were indexed.</td></tr>'
    body = f"""
<main>
  <section class="hero"><div class="wrap">
    <div class="eyebrow">Internal evidence index</div>
    <h1>Evidence files and review artefacts</h1>
    <p>This index lists recent output, site-data and documentation artefacts detected at build time. Use it for review and QA; do not expose unredacted internals on the public site.</p>
    <div class="actions"><a class="btn" href="data/unredacted/evidence_file_index.json">Download JSON index</a><a class="btn alt" href="index.html">Back to dashboard</a></div>
  </div></section>
  <section class="section"><div class="wrap">
    <div class="tablewrap"><table><thead><tr><th>Name</th><th>Repository path</th><th>Type</th><th>MB</th><th>Modified UTC</th></tr></thead><tbody>{table_rows}</tbody></table></div>
  </div></section>
</main>
"""
    return html_page("AQ26 Evidence File Index", "evidence", body, generated_utc)


def build_site(repo_root: Path, public_site: Path, output_site: Path, max_index_files: int) -> Dict[str, Any]:
    copy_result = copy_public_site(public_site, output_site)
    ensure_dir(output_site / "assets")
    ensure_dir(output_site / "data" / "unredacted")

    files = discover_files(repo_root, output_site, max_index_files)
    summary = dashboard_summary(repo_root, files)
    summary["copy_result"] = copy_result

    write_text(output_site / "assets" / "aq26_unredacted.css", css())
    write_json(output_site / "data" / "unredacted" / "evidence_file_index.json", files)
    write_json(output_site / "data" / "unredacted" / "dashboard_summary.json", summary)
    write_text(output_site / "index.html", build_index_html(summary))
    write_text(output_site / "evidence.html", build_evidence_html(files, summary["generated_utc"]))
    write_text(output_site / "robots.txt", "User-agent: *\nDisallow: /\n")

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--public-site", default="site_public")
    parser.add_argument("--output-site", default="site_unredacted")
    parser.add_argument("--max-index-files", type=int, default=250)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    public_site = (repo_root / args.public_site).resolve()
    output_site = (repo_root / args.output_site).resolve()
    summary = build_site(repo_root, public_site, output_site, args.max_index_files)
    print(json.dumps({
        "status": "ok",
        "output_site": str(output_site),
        "indexed_file_count": summary.get("indexed_file_count"),
        "copy_result": summary.get("copy_result"),
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
