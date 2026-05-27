#!/usr/bin/env python3
"""Build a complete AQ26 password-protected unredacted review website.

This builder creates a full sub-site under site_unredacted/ by copying the public
site assets/data where available, then overlaying internal-review pages and an
index of evidence files. It deliberately does not create .htaccess/.htpasswd;
the GitHub workflow creates those using SCC_UNREDACTED_PASSWORD.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SAFE_SKIP_DIRS = {".git", ".github", "node_modules", "__pycache__"}
EVIDENCE_SUFFIXES = {".json", ".csv", ".html", ".pdf", ".txt", ".md", ".xlsx"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def copytree_contents(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    mkdir(dst)
    for item in src.iterdir():
        if item.name in SAFE_SKIP_DIRS:
            continue
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        else:
            mkdir(target.parent)
            shutil.copy2(item, target)


def collect_files(repo: Path, max_files: int) -> List[Dict[str, Any]]:
    roots = [repo / "outputs", repo / "site_public" / "data", repo / "docs"]
    rows: List[Dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if len(rows) >= max_files:
                break
            if not p.is_file() or p.suffix.lower() not in EVIDENCE_SUFFIXES:
                continue
            try:
                rel = p.relative_to(repo).as_posix()
            except Exception:
                rel = p.as_posix()
            rows.append({
                "path": rel,
                "name": p.name,
                "suffix": p.suffix.lower(),
                "size_bytes": p.stat().st_size,
                "size_kb": round(p.stat().st_size / 1024, 1),
                "modified_utc": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            })
    rows.sort(key=lambda r: (r.get("modified_utc", ""), r.get("path", "")), reverse=True)
    return rows[:max_files]


def write_json(path: Path, obj: Any) -> None:
    mkdir(path.parent)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def html_escape(s: Any) -> str:
    text = str(s if s is not None else "")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_index(summary: Dict[str, Any]) -> str:
    generated = html_escape(summary.get("generated_utc"))
    file_count = html_escape(summary.get("indexed_files"))
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta name=\"robots\" content=\"noindex,nofollow,noarchive\" />
  <title>AQ26 Unredacted Review Area</title>
  <link rel=\"stylesheet\" href=\"assets/aq26_unredacted.css\" />
</head>
<body>
  <header class=\"topbar\">
    <div><strong>SCC Nexus</strong> · AQ26 internal review</div>
    <nav>
      <a href=\"index.html\">Dashboard</a>
      <a href=\"evidence.html\">Evidence index</a>
      <a href=\"../\">Public site</a>
    </nav>
  </header>
  <main>
    <section class=\"hero\">
      <p class=\"eyebrow\">Password-protected area</p>
      <h1>AQ26 Unredacted Evidence Review</h1>
      <p>This site is for internal QA, provenance review, unredacted workflow outputs and evidence-readiness checks. It is separate from the public client interface.</p>
      <div class=\"actions\">
        <a class=\"button\" href=\"evidence.html\">Open evidence index</a>
        <a class=\"button secondary\" href=\"data/unredacted/evidence_file_index.json\">View JSON index</a>
      </div>
    </section>
    <section class=\"grid\">
      <article class=\"card\"><span>Generated</span><strong>{generated}</strong><p>UTC build timestamp.</p></article>
      <article class=\"card\"><span>Indexed files</span><strong>{file_count}</strong><p>Outputs, data payloads and reports indexed for review.</p></article>
      <article class=\"card warning\"><span>Access</span><strong>Restricted</strong><p>Do not share credentials or publish unreviewed evidence externally.</p></article>
    </section>
    <section class=\"panel\">
      <h2>Review workflow</h2>
      <ol>
        <li>Check latest run summaries and validation warnings.</li>
        <li>Confirm redacted/public payloads do not leak sensitive fields.</li>
        <li>Use source records and manifests for provenance checks.</li>
        <li>Promote only small, client-friendly summaries to the public website.</li>
      </ol>
    </section>
  </main>
  <footer>© SCC Nexus / AQ26 · Internal review site · noindex</footer>
</body>
</html>
"""


def build_evidence(files: List[Dict[str, Any]]) -> str:
    rows = []
    for r in files:
        rows.append(
            "<tr>"
            f"<td>{html_escape(r.get('name'))}</td>"
            f"<td><code>{html_escape(r.get('path'))}</code></td>"
            f"<td>{html_escape(r.get('suffix'))}</td>"
            f"<td>{html_escape(r.get('size_kb'))}</td>"
            f"<td>{html_escape(r.get('modified_utc'))}</td>"
            "</tr>"
        )
    body = "\n".join(rows) or "<tr><td colspan='5'>No files indexed yet.</td></tr>"
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta name=\"robots\" content=\"noindex,nofollow,noarchive\" />
  <title>AQ26 Evidence Index</title>
  <link rel=\"stylesheet\" href=\"assets/aq26_unredacted.css\" />
</head>
<body>
  <header class=\"topbar\">
    <div><strong>SCC Nexus</strong> · AQ26 internal review</div>
    <nav><a href=\"index.html\">Dashboard</a><a href=\"evidence.html\">Evidence index</a><a href=\"../\">Public site</a></nav>
  </header>
  <main>
    <section class=\"hero compact\"><p class=\"eyebrow\">Evidence index</p><h1>Unredacted output catalogue</h1><p>Review files generated from GitHub Actions and site payloads. This is not the public user interface.</p></section>
    <section class=\"panel\">
      <table>
        <thead><tr><th>Name</th><th>Repository path</th><th>Type</th><th>KB</th><th>Modified UTC</th></tr></thead>
        <tbody>{body}</tbody>
      </table>
    </section>
  </main>
  <footer>© SCC Nexus / AQ26 · Internal review site · noindex</footer>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--public-site", default="site_public")
    ap.add_argument("--output-site", default="site_unredacted")
    ap.add_argument("--max-index-files", type=int, default=250)
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    public_site = (repo / args.public_site).resolve()
    out = (repo / args.output_site).resolve()

    if out.exists():
        shutil.rmtree(out)
    mkdir(out)
    copytree_contents(public_site, out)

    files = collect_files(repo, args.max_index_files)
    summary = {
        "site": "aq26_unredacted",
        "generated_utc": now_iso(),
        "indexed_files": len(files),
        "public_site_copied": public_site.exists(),
        "access": "password_protected_by_workflow_basic_auth",
        "remote_expected": "sccwebdesigntest.co.uk/unredacted/",
    }

    mkdir(out / "assets")
    mkdir(out / "data" / "unredacted")
    (out / "assets" / "aq26_unredacted.css").write_text(CSS, encoding="utf-8")
    (out / "index.html").write_text(build_index(summary), encoding="utf-8")
    (out / "evidence.html").write_text(build_evidence(files), encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    write_json(out / "data" / "unredacted" / "dashboard_summary.json", summary)
    write_json(out / "data" / "unredacted" / "evidence_file_index.json", {"generated_utc": now_iso(), "files": files})

    print(json.dumps(summary, indent=2))
    return 0


CSS = """
:root{--navy:#071b33;--blue:#0c6fb7;--cyan:#24c6dc;--ink:#10213a;--muted:#607086;--bg:#eef6fb;--card:#ffffff;--line:#dbe7f1;--gold:#ffc857;--red:#d64545;}
*{box-sizing:border-box} body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;background:linear-gradient(135deg,#eef7ff,#f8fbff);color:var(--ink)}
a{color:inherit}.topbar{position:sticky;top:0;z-index:5;display:flex;justify-content:space-between;gap:1rem;align-items:center;background:rgba(7,27,51,.96);color:white;padding:1rem 1.4rem;box-shadow:0 8px 24px rgba(7,27,51,.18)}
.topbar nav{display:flex;gap:.6rem;flex-wrap:wrap}.topbar a{color:white;text-decoration:none;border:1px solid rgba(255,255,255,.24);border-radius:999px;padding:.45rem .75rem;font-weight:700;font-size:.9rem}
main{max-width:1180px;margin:0 auto;padding:1.2rem}.hero{margin:1.2rem 0;border-radius:28px;padding:3rem;background:radial-gradient(circle at top right,rgba(36,198,220,.38),transparent 40%),linear-gradient(135deg,#09203f,#0c6fb7);color:white;box-shadow:0 20px 55px rgba(7,27,51,.22)}
.hero.compact{padding:2rem}.eyebrow{text-transform:uppercase;letter-spacing:.18em;font-size:.78rem;font-weight:900;opacity:.86}.hero h1{font-size:clamp(2rem,5vw,4.8rem);line-height:.95;margin:.3rem 0}.hero p{max-width:780px;font-size:1.08rem;line-height:1.55}.actions{display:flex;gap:.75rem;flex-wrap:wrap;margin-top:1.2rem}.button{display:inline-flex;text-decoration:none;font-weight:900;border-radius:14px;background:white;color:#09203f;padding:.85rem 1rem}.button.secondary{background:rgba(255,255,255,.14);color:white;border:1px solid rgba(255,255,255,.3)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem}.card,.panel{background:var(--card);border:1px solid var(--line);border-radius:22px;box-shadow:0 14px 36px rgba(20,45,75,.08);padding:1.2rem}.card span{display:block;font-size:.75rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:900}.card strong{display:block;font-size:1.8rem;margin:.35rem 0;color:var(--navy)}.card.warning strong{color:var(--red)}
.panel{margin:1rem 0;overflow:auto}.panel h2{margin-top:0} table{width:100%;border-collapse:collapse;font-size:.92rem} th,td{text-align:left;padding:.75rem;border-bottom:1px solid var(--line);vertical-align:top} th{font-size:.76rem;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)} code{font-size:.82rem;white-space:normal} footer{margin-top:2rem;background:var(--navy);color:#cfe1f0;padding:2rem 1.4rem;text-align:center}
@media(max-width:700px){.topbar{align-items:flex-start;flex-direction:column}.hero{padding:2rem 1.25rem}main{padding:.8rem}}
"""

if __name__ == "__main__":
    raise SystemExit(main())
