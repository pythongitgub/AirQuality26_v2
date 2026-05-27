#!/usr/bin/env python3
"""
AQ26 unredacted full-site builder.

Purpose:
- Build a complete password-protected review website under site_unredacted/.
- Prefer copying the existing generated public website (site_public/) so menus,
  CSS, assets, data and footer structure remain available.
- Overlay a clear unredacted/reviewer homepage.
- Add an internal evidence index page pointing to available unredacted artefacts.
- Do not expose secrets in generated HTML.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def copytree_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def discover_files(root: Path, patterns: Iterable[str], max_files: int = 250) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen = set()
    for pattern in patterns:
        for p in sorted(root.glob(pattern)):
            if not p.is_file():
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                rows.append({
                    "path": str(p),
                    "relative_path": str(p.relative_to(root)),
                    "name": p.name,
                    "suffix": p.suffix.lower(),
                    "size_bytes": p.stat().st_size,
                    "modified_utc": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                })
            except Exception:
                pass
            if len(rows) >= max_files:
                return rows
    return rows


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def page_shell(title: str, body: str, generated_utc: str) -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta name=\"robots\" content=\"noindex,nofollow,noarchive\" />
  <title>{html.escape(title)}</title>
  <link rel=\"stylesheet\" href=\"assets/aq26_unredacted.css\" />
</head>
<body>
  <header class=\"aq26-topbar\">
    <a class=\"brand\" href=\"index.html\"><span class=\"brand-mark\">AQ26</span><span>Unredacted Review</span></a>
    <nav>
      <a href=\"index.html\">Dashboard</a>
      <a href=\"evidence.html\">Evidence</a>
      <a href=\"../\">Public site</a>
    </nav>
  </header>
  <main>
    {body}
  </main>
  <footer class=\"aq26-footer\">
    <p><strong>Restricted review area.</strong> Generated {html.escape(generated_utc)}. Do not circulate unredacted outputs without review.</p>
  </footer>
</body>
</html>
"""


def build(args: argparse.Namespace) -> int:
    repo = Path(args.repo_root).resolve()
    public = repo / args.public_site
    out = repo / args.output_site
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    # Full website: copy generated public site first, then overlay unredacted pages/assets.
    copytree_contents(public, out)

    assets = out / "assets"
    data_dir = out / "data" / "unredacted"
    assets.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    generated_utc = utc_now()
    latest_summary = safe_read_json(repo / "site_public" / "data" / "latest_backfill_summary.json")
    weekly_index = safe_read_json(repo / "site_public" / "data" / "weekly_index.json")
    earth_summary = safe_read_json(repo / "site_public" / "data" / "providers" / "earthdata" / "summary.json")
    laqn_summary = safe_read_json(repo / "site_public" / "data" / "providers" / "laqn" / "summary.json")

    evidence_files = discover_files(
        repo,
        [
            "outputs/**/*summary*.json",
            "outputs/**/*validation*.json",
            "outputs/**/*manifest*.json",
            "outputs/**/*verification*.csv",
            "outputs/**/*.html",
            "outputs/**/*.pdf",
            "outputs/**/*.xlsx",
            "site_public/data/**/*.json",
        ],
        max_files=int(args.max_index_files),
    )
    (data_dir / "evidence_file_index.json").write_text(json.dumps({
        "generated_utc": generated_utc,
        "repo_root": str(repo),
        "files_indexed": len(evidence_files),
        "files": evidence_files,
    }, indent=2), encoding="utf-8")

    css = """
:root{--bg:#07111f;--panel:#101c2e;--panel2:#122842;--text:#f5f9ff;--muted:#b8c7da;--cyan:#36d1dc;--green:#6ee7b7;--amber:#fbbf24;--red:#fb7185;--line:rgba(255,255,255,.12)}
*{box-sizing:border-box} body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:radial-gradient(circle at top left,#163454 0,#07111f 42%,#040812 100%);color:var(--text);line-height:1.55}.aq26-topbar{position:sticky;top:0;z-index:10;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem clamp(1rem,3vw,2rem);background:rgba(5,12,24,.86);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}.brand{display:flex;align-items:center;gap:.75rem;color:var(--text);text-decoration:none;font-weight:800}.brand-mark{display:inline-grid;place-items:center;width:42px;height:42px;border-radius:14px;background:linear-gradient(135deg,var(--cyan),var(--green));color:#06111e;font-weight:900}.aq26-topbar nav{display:flex;gap:.5rem;flex-wrap:wrap}.aq26-topbar nav a{color:var(--muted);text-decoration:none;padding:.55rem .8rem;border:1px solid var(--line);border-radius:999px}.aq26-topbar nav a:hover{color:var(--text);border-color:var(--cyan)}main{max-width:1180px;margin:0 auto;padding:2rem clamp(1rem,3vw,2rem) 4rem}.hero{padding:2rem;border:1px solid var(--line);border-radius:28px;background:linear-gradient(135deg,rgba(54,209,220,.16),rgba(110,231,183,.09));box-shadow:0 20px 70px rgba(0,0,0,.25)}.hero h1{margin:.2rem 0;font-size:clamp(2rem,5vw,4.4rem);line-height:1.02}.eyebrow{color:var(--green);text-transform:uppercase;letter-spacing:.14em;font-size:.8rem;font-weight:800}.lead{font-size:1.15rem;color:var(--muted);max-width:850px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem;margin:1.2rem 0}.card{background:rgba(16,28,46,.86);border:1px solid var(--line);border-radius:22px;padding:1.1rem;box-shadow:0 16px 40px rgba(0,0,0,.18)}.card h3{margin:.1rem 0 .5rem}.metric{font-size:2rem;font-weight:900;color:var(--green)}.tag{display:inline-flex;margin:.2rem .25rem .2rem 0;padding:.3rem .6rem;border-radius:999px;background:rgba(54,209,220,.12);border:1px solid rgba(54,209,220,.35);color:#dffbff;font-size:.86rem}.warn{color:var(--amber)}.danger{color:var(--red)}.ok{color:var(--green)}table{width:100%;border-collapse:collapse;background:rgba(16,28,46,.72);border-radius:18px;overflow:hidden}th,td{padding:.75rem;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:#dffbff;background:rgba(54,209,220,.11)}code{color:#dffbff}.aq26-footer{padding:1.5rem clamp(1rem,3vw,2rem);border-top:1px solid var(--line);color:var(--muted);background:#050b14}.actions{display:flex;gap:.75rem;flex-wrap:wrap;margin-top:1rem}.btn{display:inline-flex;align-items:center;gap:.5rem;padding:.75rem 1rem;border-radius:999px;text-decoration:none;background:linear-gradient(135deg,var(--cyan),var(--green));color:#06111e;font-weight:900}.btn.secondary{background:transparent;color:var(--text);border:1px solid var(--line)}
"""
    write(assets / "aq26_unredacted.css", css)

    total_weeks = weekly_index.get("total_weeks") or weekly_index.get("weeks_total") or "—"
    harvested = weekly_index.get("harvested_weeks") or weekly_index.get("weeks_harvested") or "—"
    validation_ok = latest_summary.get("validation_ok", latest_summary.get("overall_ok", "—"))
    source_records = latest_summary.get("source_records", latest_summary.get("total_source_records", "—"))
    earth_collections = earth_summary.get("cmr_collections", "—")
    laqn_status = laqn_summary.get("status", "—")

    body = f"""
<section class=\"hero\">
  <div class=\"eyebrow\">Password-protected internal review</div>
  <h1>AQ26 Unredacted Evidence Review</h1>
  <p class=\"lead\">A complete internal-facing website for reviewing weekly evidence outputs, validation status, provenance, source coverage and deployment readiness. This is separate from the public user-friendly AQ26 interface.</p>
  <div class=\"actions\"><a class=\"btn\" href=\"evidence.html\">Open evidence index</a><a class=\"btn secondary\" href=\"../\">View public site</a></div>
</section>
<section class=\"grid\">
  <article class=\"card\"><h3>Latest validation</h3><div class=\"metric\">{html.escape(str(validation_ok))}</div><p>Latest backfill summary validation flag.</p></article>
  <article class=\"card\"><h3>Source records</h3><div class=\"metric\">{html.escape(str(source_records))}</div><p>Latest weekly evidence/source record count where available.</p></article>
  <article class=\"card\"><h3>Backfill weeks</h3><div class=\"metric\">{html.escape(str(harvested))}/{html.escape(str(total_weeks))}</div><p>Historical weekly coverage index.</p></article>
  <article class=\"card\"><h3>Earthdata CMR</h3><div class=\"metric\">{html.escape(str(earth_collections))}</div><p>NASA Earthdata catalogue candidates discovered.</p></article>
</section>
<section class=\"card\"><h2>Reviewer notes</h2><p>This area may contain unredacted paths, internal run status and detailed artefact links. It is intentionally separate from the public website. Publish only redacted, chart-safe, plain-English payloads to the public homepage.</p><span class=\"tag\">LAQN status: {html.escape(str(laqn_status))}</span><span class=\"tag\">Generated: {html.escape(generated_utc)}</span></section>
"""
    write(out / "index.html", page_shell("AQ26 Unredacted Review", body, generated_utc))

    rows_html = []
    for f in evidence_files[: int(args.max_index_files)]:
        rel = html.escape(f["relative_path"])
        size = f.get("size_bytes", 0)
        rows_html.append(f"<tr><td><code>{rel}</code></td><td>{html.escape(str(f.get('suffix','')))}</td><td>{size:,}</td><td>{html.escape(str(f.get('modified_utc','')))}</td></tr>")
    evidence_body = f"""
<section class=\"hero\"><div class=\"eyebrow\">Evidence artefact index</div><h1>Evidence files and review outputs</h1><p class=\"lead\">Index of selected summaries, manifests, validations, reports and website JSON files found in this repository build. This page is for internal navigation only.</p></section>
<section class=\"card\"><h2>Indexed files</h2><p>{len(evidence_files)} files indexed. Full machine-readable index: <code>data/unredacted/evidence_file_index.json</code>.</p><table><thead><tr><th>File</th><th>Type</th><th>Bytes</th><th>Modified UTC</th></tr></thead><tbody>{''.join(rows_html) or '<tr><td colspan=\"4\">No evidence files found.</td></tr>'}</tbody></table></section>
"""
    write(out / "evidence.html", page_shell("AQ26 Evidence Index", evidence_body, generated_utc))

    # Robots and index controls. .htaccess/.htpasswd are created by workflow because password secret is only available there.
    write(out / "robots.txt", "User-agent: *\nDisallow: /\n")
    marker = {
        "generated_utc": generated_utc,
        "builder": "scripts/aq26_build_unredacted_site.py",
        "public_site_copied": public.exists(),
        "output_site": str(out),
        "evidence_files_indexed": len(evidence_files),
    }
    write(out / "data" / "unredacted" / "build_marker.json", json.dumps(marker, indent=2))
    print(json.dumps(marker, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--public-site", default="site_public")
    p.add_argument("--output-site", default="site_unredacted")
    p.add_argument("--max-index-files", default="250")
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(build(parse_args()))
