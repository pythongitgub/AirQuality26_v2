#!/usr/bin/env python3
"""Build a stable AQ26 weekly operational website.

This script deliberately does not run the heavy emissions science backfill.
It publishes validated files already present in the repo/workspace and clearly
marks unavailable data as pending Colab/Drive science validation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def london_now() -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo

        return dt.datetime.now(ZoneInfo("Europe/London"))
    except Exception:
        return dt.datetime.utcnow()


def page_template(
    *,
    title: str,
    body: str,
    nav: list[dict[str, str]],
    generated: str,
    disclaimer: str,
) -> str:
    nav_html = "\n".join(
        f'<a href="{html.escape(item.get("href", "#"))}">{html.escape(item.get("title", "Page"))}</a>'
        for item in nav
    )
    return f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} · AirQuality26</title>
  <meta name="description" content="AirQuality26 weekly evidence publishing site.">
  <style>
    :root {{ --bg:#f6f8fb; --card:#ffffff; --ink:#172033; --muted:#64748b; --line:#d8e0ea; --accent:#1455d9; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Arial, Helvetica, sans-serif; background:var(--bg); color:var(--ink); line-height:1.55; }}
    header {{ background:#fff; border-bottom:1px solid var(--line); position:sticky; top:0; z-index:10; }}
    .wrap {{ max-width:1180px; margin:0 auto; padding:20px; }}
    .brand {{ display:flex; gap:14px; align-items:center; }}
    .logo {{ width:52px; height:52px; border-radius:14px; background:linear-gradient(135deg,#1455d9,#0ea5e9); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:800; }}
    nav {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }}
    nav a {{ color:var(--accent); background:#eef4ff; padding:8px 11px; border-radius:10px; text-decoration:none; font-weight:700; font-size:14px; }}
    main .hero {{ background:var(--card); border:1px solid var(--line); border-radius:20px; padding:24px; margin:22px 0; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:18px; padding:18px; }}
    .status {{ display:inline-block; border-radius:999px; padding:5px 10px; background:#fff7ed; color:#9a3412; font-weight:800; font-size:13px; }}
    .ok {{ background:#ecfdf5; color:#047857; }}
    .warn {{ background:#fff7ed; color:#9a3412; }}
    code, pre {{ background:#0f172a; color:#e2e8f0; border-radius:12px; padding:12px; overflow:auto; }}
    table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:14px; overflow:hidden; }}
    th, td {{ text-align:left; border-bottom:1px solid var(--line); padding:10px; vertical-align:top; }}
    th {{ background:#eef4ff; }}
    footer {{ color:var(--muted); font-size:13px; padding:30px 0; }}
  </style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="brand">
      <div class="logo">AQ26</div>
      <div>
        <strong>AirQuality26</strong><br>
        <span>Weekly operational evidence publishing</span>
      </div>
    </div>
    <nav>{nav_html}</nav>
  </div>
</header>
<main class="wrap">
{body}
</main>
<footer class="wrap">
  <p>{html.escape(disclaimer)}</p>
  <p>Generated: {html.escape(generated)} Europe/London.</p>
</footer>
</body>
</html>
"""


def card(title: str, content: str, status: str | None = None) -> str:
    badge = f'<p><span class="status">{html.escape(status)}</span></p>' if status else ""
    return f'<section class="card"><h2>{html.escape(title)}</h2>{badge}{content}</section>'


def write_page(path: Path, title: str, body: str, nav: list[dict[str, str]], generated: str, disclaimer: str) -> None:
    ensure_dir(path.parent)
    path.write_text(page_template(title=title, body=body, nav=nav, generated=generated, disclaimer=disclaimer), encoding="utf-8")


def latest_existing_files(paths: list[Path], limit: int = 20) -> list[Path]:
    found: list[Path] = []
    for base in paths:
        if not base.exists():
            continue
        found.extend([p for p in base.rglob("*") if p.is_file()])
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def build_public_site(runtime: dict[str, Any], manifest: dict[str, Any]) -> None:
    paths = runtime.get("paths", {})
    public = Path(paths.get("public_site", "site_public"))
    unredacted = Path(paths.get("unredacted_site", "site_unredacted"))
    test = Path(paths.get("test_site", "site_test"))
    weekly = Path(paths.get("weekly_data", "site_public/data/weekly"))
    unred_weekly = Path(paths.get("unredacted_weekly_data", "site_unredacted/data/weekly"))
    downloads = Path(paths.get("downloads_public", "site_public/downloads"))
    reports = Path(paths.get("reports", "outputs/reports"))
    evidence = Path(paths.get("evidence", "outputs/evidence"))
    logs = Path(paths.get("logs", "outputs/logs"))

    for p in [public, unredacted, test, weekly, unred_weekly, downloads, reports, evidence, logs]:
        ensure_dir(p)

    now = london_now()
    generated = now.strftime("%d/%m/%Y %H:%M:%S")
    iso = now.isoformat()

    nav = manifest.get("navigation") or [
        {"title": "Home", "href": "index.html"},
        {"title": "Weekly update", "href": "weekly-update.html"},
        {"title": "Methodology", "href": "methodology.html"},
    ]
    disclaimer = manifest.get("public_disclaimer", "Operational public evidence site.")
    unred_disclaimer = manifest.get("unredacted_disclaimer", "Password-protected review area.")

    status = {
        "generated_at_london": iso,
        "generated_at_display": generated,
        "weekly_status": "operational_publish_ready",
        "science_backfill_status": "pending_colab_drive_validation",
        "message": "GitHub publishes validated available outputs. Heavy historical science backfill remains in Colab/Drive.",
    }
    (weekly / "backfill-status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    (unred_weekly / "backfill-status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    recent_files = latest_existing_files([reports, evidence, weekly], limit=12)
    file_rows = "".join(
        f"<tr><td>{html.escape(str(p))}</td><td>{p.stat().st_size:,} bytes</td></tr>" for p in recent_files
    ) or "<tr><td colspan='2'>No validated weekly files found yet. Pending Colab/Drive science backfill.</td></tr>"

    alert_panel = """
<section class="hero">
  <h1>AQ26 weekly operational update</h1>
  <p><span class="status warn">Pending Colab/Drive science backfill where source data is unavailable</span></p>
  <p>This site is now structured for stable weekly publishing: public website, unredacted review area, evidence bundle, Drive upload and Hostinger deployment.</p>
  <p><a href="downloads/AQ26_WEEKLY_EVIDENCE_BUNDLE.zip">Download latest evidence bundle</a> · <a href="data/weekly/backfill-status.json">Backfill status JSON</a></p>
</section>
"""

    index_body = alert_panel + "<div class='grid'>" + "".join(
        [
            card("Operational publishing", "<p>Weekly GitHub workflow builds and validates the site structure, evidence bundle and deployment staging.</p>", "Ready"),
            card("Science backfill", "<p>Historical emissions science backfill remains in Colab/Drive. GitHub will publish validated outputs when present.</p>", "Pending validation"),
            card("Public and unredacted split", "<p>Public redacted material is served from the main site. Extended reviewer material is staged under /unredacted/.</p>", "Configured"),
        ]
    ) + "</div>"
    write_page(public / "index.html", "Home", index_body, nav, generated, disclaimer)

    weekly_body = f"""
<section class="hero"><h1>Weekly update</h1><p>Generated {html.escape(generated)} Europe/London.</p></section>
<section class="card"><h2>Latest files</h2><table><tr><th>File</th><th>Size</th></tr>{file_rows}</table></section>
<section class="card"><h2>Backfill status</h2><pre>{html.escape(json.dumps(status, indent=2))}</pre></section>
"""
    write_page(public / "weekly-update.html", "Weekly update", weekly_body, nav, generated, disclaimer)

    generic_pages = {
        "incinerators.html": ("Incinerators", "Tracked facilities", "Facility-specific pages and evidence links are populated when validated outputs are present."),
        "methodology.html": ("Methodology", "Methodology", "AQ26 separates heavy science processing from operational publishing. Colab/Drive produces validated backfill outputs; GitHub publishes those outputs with provenance."),
        "source-records.html": ("Source records", "Source records", "Source records, manifests, logs and provenance files are linked here as validated weekly outputs become available."),
        "readiness.html": ("Readiness", "Readiness", "This page tracks operational readiness of the weekly publishing system."),
        "archive.html": ("Archive", "Archive", "Weekly evidence bundles and status files will be archived here."),
        "comparisons.html": ("Comparisons", "Comparisons", "Facility/control comparisons will be published here once validated by the science backfill pipeline."),
        "historical-comparisons.html": ("Historical comparisons", "Historical comparisons", "Historical comparison outputs are pending Colab/Drive validation."),
        "about.html": ("About", "About AirQuality26", "AirQuality26 is an evidence publishing system for structured air-quality monitoring outputs."),
        "contact.html": ("Contact", "Contact", "For review queries, use the project contact channel configured by the site owner."),
        "privacy.html": ("Privacy", "Privacy", "This static site minimises personal data collection. Hosting and analytics providers may process basic access logs where configured."),
        "cookies.html": ("Cookies", "Cookies", "This static site does not require non-essential cookies unless analytics or embedded third-party services are later enabled."),
        "accessibility.html": ("Accessibility", "Accessibility", "The site is built with semantic HTML and responsive layouts. Accessibility issues should be reported for correction."),
        "terms.html": ("Terms", "Terms", "Material is provided for review and transparency, subject to validation status and source licensing."),
    }
    for filename, (title, h1, text) in generic_pages.items():
        body = f"<section class='hero'><h1>{html.escape(h1)}</h1><p>{html.escape(text)}</p></section>"
        write_page(public / filename, title, body, nav, generated, disclaimer)

    unred_nav = [
        {"title": "Review home", "href": "index.html"},
        {"title": "Weekly update", "href": "weekly-update.html"},
        {"title": "Source records", "href": "source-records.html"},
    ]
    unred_body = """
<section class="hero"><h1>AQ26 unredacted review area</h1><p><span class="status warn">Password protection required at hosting level</span></p><p>This area is intended for extended review materials, logs and unredacted provenance.</p></section>
"""
    write_page(unredacted / "index.html", "Unredacted review", unred_body, unred_nav, generated, unred_disclaimer)
    write_page(unredacted / "weekly-update.html", "Unredacted weekly update", weekly_body, unred_nav, generated, unred_disclaimer)
    write_page(unredacted / "source-records.html", "Unredacted source records", "<section class='hero'><h1>Source records</h1><p>Extended logs and source manifests are staged here.</p></section>", unred_nav, generated, unred_disclaimer)

    # Test site mirrors public for browser validation.
    for src in public.rglob("*"):
        if src.is_file():
            dest = test / src.relative_to(public)
            ensure_dir(dest.parent)
            dest.write_bytes(src.read_bytes())

    (logs / "weekly_build_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/aq26_weekly_runtime.yml")
    parser.add_argument("--manifest", default="configs/aq26_site_manifest.yml")
    args = parser.parse_args()

    runtime = load_yaml(args.config)
    manifest = load_yaml(args.manifest)
    build_public_site(runtime, manifest)
    print("AQ26 weekly site build completed.")


if __name__ == "__main__":
    main()
