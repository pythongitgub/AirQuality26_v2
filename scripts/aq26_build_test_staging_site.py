#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, shutil
from datetime import datetime, timezone
from pathlib import Path

TEST_BANNER = """<!--AQ26_TEST_STAGING_BANNER_START-->
<div class="aq26-test-staging-banner" role="note" aria-label="AQ26 test staging notice">
  <strong>TEST / STAGING COPY</strong>
  <span>This /test site is for review only. Live redacted pages remain at / and protected review remains at /unredacted/.</span>
</div>
<!--AQ26_TEST_STAGING_BANNER_END-->"""

TEST_CSS = """.aq26-test-staging-banner{position:sticky;top:0;z-index:99999;display:flex;gap:.75rem;align-items:center;justify-content:center;flex-wrap:wrap;padding:.65rem 1rem;background:#ffd966;color:#1f2937;border-bottom:2px solid #8a6200;font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;font-size:.92rem;box-shadow:0 8px 25px rgba(0,0,0,.15)}.aq26-test-staging-banner strong{letter-spacing:.08em;text-transform:uppercase}.aq26-test-index-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem;margin:1rem 0}.aq26-test-index-grid a{display:block;border:1px solid #d9e4ef;border-radius:18px;background:#fff;padding:1rem;text-decoration:none;font-weight:800}"""

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def copytree_clean(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Missing source site folder: {src}")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".htpasswd", "__pycache__", "*.pyc"))

def ensure_noindex(txt: str) -> str:
    if 'name="robots"' not in txt and "name='robots'" not in txt:
        txt = re.sub(r"</head>", '<meta name="robots" content="noindex,nofollow">\n</head>', txt, count=1, flags=re.I)
    return txt

def ensure_css(txt: str) -> str:
    if "aq26_test_staging.css" not in txt:
        txt = re.sub(r"</head>", '<link rel="stylesheet" href="assets/aq26_test_staging.css?v=aq26-test">\n</head>', txt, count=1, flags=re.I)
    return txt

def inject_banner(txt: str) -> str:
    txt = re.sub(r"<!--AQ26_TEST_STAGING_BANNER_START-->.*?<!--AQ26_TEST_STAGING_BANNER_END-->", "", txt, flags=re.S)
    if "<body" in txt:
        return re.sub(r"(<body[^>]*>)", r"\1\n" + TEST_BANNER, txt, count=1, flags=re.I)
    return TEST_BANNER + txt

def patch_html(root: Path) -> int:
    n = 0
    for p in sorted(root.rglob("*.html")):
        txt = p.read_text(encoding="utf-8", errors="replace")
        txt = inject_banner(ensure_css(ensure_noindex(txt)))
        p.write_text(txt, encoding="utf-8")
        n += 1
    return n

def write_test_index(site_test: Path, include_unredacted: bool) -> None:
    links = [
        ("Public home", "index.html"),
        ("Incinerator register", "incinerators.html"),
        ("Newhaven focus", "newhaven.html"),
        ("Weekly update", "weekly-update.html"),
        ("Overlay status", "overlays.html"),
        ("Downloads", "downloads.html"),
    ]
    if include_unredacted:
        links.append(("Protected unredacted review", "unredacted/index.html"))
    cards = "\n".join(f'<a href="{href}">{label}<br><small>{href}</small></a>' for label, href in links)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>AQ26 Test Staging Index</title><link rel="stylesheet" href="assets/aq26_operational.css?v=operational"><link rel="stylesheet" href="assets/aq26_test_staging.css?v=aq26-test"><link rel="icon" href="favicon.ico"><link rel="icon" href="favicon.svg" type="image/svg+xml"></head><body>{TEST_BANNER}<main class="main"><section class="card section"><h1>AQ26 /test staging site</h1><p>This is a disposable review copy generated at <b>{now_utc()}</b>. Use it to check website updates before promoting changes to the live root.</p><p><b>Live redacted:</b> <code>/index.html</code> | <b>Live protected:</b> <code>/unredacted/</code> | <b>Test staging:</b> <code>/test/</code></p><div class="aq26-test-index-grid">{cards}</div></section></main></body></html>"""
    (site_test / "test-index.html").write_text(page, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--public-site", default="site_public")
    ap.add_argument("--unredacted-site", default="site_unredacted")
    ap.add_argument("--test-site", default="site_test")
    ap.add_argument("--include-unredacted", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo_root).resolve()
    public = repo / args.public_site
    unredacted = repo / args.unredacted_site
    test = repo / args.test_site
    copytree_clean(public, test)
    (test / "assets").mkdir(parents=True, exist_ok=True)
    (test / "assets/aq26_test_staging.css").write_text(TEST_CSS, encoding="utf-8")
    copied = False
    if args.include_unredacted and unredacted.exists():
        copytree_clean(unredacted, test / "unredacted")
        copied = True
        (test / "unredacted/robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        (test / "unredacted/.htaccess").write_text('AuthType Basic\nAuthName "AQ26 Test Unredacted Review"\nAuthUserFile .htpasswd\nRequire valid-user\nOptions -Indexes\n', encoding="utf-8")
    patched = patch_html(test)
    write_test_index(test, copied)
    (test / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    for p in test.rglob(".htpasswd"):
        p.unlink(missing_ok=True)
    summary = {"ok": True, "generated_utc": now_utc(), "include_unredacted": copied, "html_files_patched": patched, "recommended_urls": ["/test/index.html", "/test/test-index.html", "/test/incinerators.html", "/test/newhaven.html", "/test/weekly-update.html", "/test/unredacted/index.html" if copied else ""]}
    out = test / "data/test/test_site_build_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
