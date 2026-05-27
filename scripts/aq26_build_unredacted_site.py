#!/usr/bin/env python3
"""Build a minimal password-protected AQ26 unredacted review site payload.

This builder deliberately writes a real index.html so Hostinger/Apache does not
return a directory-listing 403 when /unredacted/ is opened.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    out = Path(os.environ.get("AQ26_UNREDACTED_SITE_DIR", "site_unredacted"))
    out.mkdir(parents=True, exist_ok=True)
    generated = now_utc()

    summary = {
        "site": "AQ26 unredacted review site",
        "generated_utc": generated,
        "purpose": "Password-protected internal review interface for unredacted AQ26 evidence outputs.",
        "status": "built",
        "security_note": "Protected by server-side Basic Auth in the deployment workflow. Do not publish highly sensitive personal data unless separately approved.",
    }
    write(out / "data" / "summary.json", json.dumps(summary, indent=2))

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex,nofollow,noarchive" />
  <title>AQ26 Unredacted Review</title>
  <style>
    :root {{ --bg:#07111f; --panel:#0f2035; --ink:#eff6ff; --muted:#a9bdd6; --accent:#48d1cc; --warn:#ffd166; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family: Inter, system-ui, -apple-system, Segoe UI, sans-serif; background: radial-gradient(circle at top left,#173b60 0,#07111f 42%,#050910 100%); color:var(--ink); }}
    main {{ max-width:1100px; margin:0 auto; padding:40px 18px 80px; }}
    .hero {{ padding:34px; border:1px solid rgba(255,255,255,.13); background:rgba(15,32,53,.88); border-radius:28px; box-shadow:0 22px 70px rgba(0,0,0,.35); }}
    .badge {{ display:inline-flex; gap:8px; align-items:center; padding:8px 12px; border-radius:999px; background:rgba(72,209,204,.14); color:var(--accent); font-weight:700; font-size:13px; }}
    h1 {{ font-size:clamp(34px,7vw,68px); line-height:.98; margin:20px 0 14px; letter-spacing:-.05em; }}
    p {{ color:var(--muted); font-size:18px; line-height:1.6; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:16px; margin-top:24px; }}
    .card {{ border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.055); border-radius:22px; padding:20px; }}
    .card strong {{ display:block; font-size:15px; color:#fff; margin-bottom:8px; }}
    .card span {{ color:var(--muted); font-size:14px; line-height:1.5; }}
    .warn {{ border-color:rgba(255,209,102,.45); background:rgba(255,209,102,.08); }}
    code {{ color:#d8fbff; background:rgba(255,255,255,.08); padding:2px 6px; border-radius:6px; }}
    a {{ color:#9ff8ff; }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="badge">🔒 Password-protected internal review area</div>
      <h1>AQ26 Unredacted Evidence Review</h1>
      <p>This area is separate from the public client interface. It is intended for internal QA, provenance review, validation summaries, run manifests, unredacted report payloads and evidence-pack checks.</p>
      <div class="grid">
        <div class="card"><strong>Generated</strong><span>{generated}</span></div>
        <div class="card"><strong>Access model</strong><span>Server-side Basic Auth via <code>.htaccess</code> and <code>.htpasswd</code>.</span></div>
        <div class="card"><strong>Public site split</strong><span>Public users see the friendly dashboard. This area is for audit and review.</span></div>
        <div class="card warn"><strong>Security note</strong><span>Restricted does not mean suitable for unrestricted sensitive personal data. Keep highly sensitive evidence in the private evidence lake unless explicitly approved.</span></div>
      </div>
    </section>
  </main>
</body>
</html>
"""
    write(out / "index.html", html)
    write(out / "robots.txt", "User-agent: *\nDisallow: /\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
