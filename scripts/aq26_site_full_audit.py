#!/usr/bin/env python3
"""AQ26 publication-site audit.

Strict for public SEO/assets/links and leak safety. Protected pages are checked
for auth/noindex/sensitive-file safety without treating every public-footer link
as a protected local file requirement.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        self.tags.append((tag, dict(attrs)))

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.tags.append((tag, dict(attrs)))


def local_exists(base: Path, html_file: Path, ref: str) -> bool:
    if not ref or ref.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        return True
    parsed = urlparse(ref)
    if parsed.scheme in {"http", "https"}:
        return True
    path = parsed.path
    if not path:
        return True
    if path.startswith("/"):
        if path == "/unredacted/":
            return (ROOT / "site_unredacted" / "index.html").exists()
        if path.startswith("/unredacted/"):
            rest = path[len("/unredacted/"):].strip("/") or "index.html"
            return (ROOT / "site_unredacted" / rest).exists()
        return (ROOT / "site_public" / path.lstrip("/")).exists()
    return (html_file.parent / path).exists()


def scan_sensitive(base: Path, errors: list[str]) -> None:
    for bad in ["git-test", ".git", "node_modules", "__pycache__"]:
        if (base / bad).exists():
            errors.append(f"Unsafe/stale directory present: {base / bad}")
    for p in base.rglob("*"):
        if p.is_file() and p.name in {".env", ".htpasswd", "id_rsa", "id_ed25519"}:
            errors.append(f"Sensitive file must not be deployed: {p}")
        if p.is_file() and "git-test" in p.as_posix():
            errors.append(f"Repo/source file leaked to web root: {p}")


def audit_html(base: Path, public: bool, errors: list[str], warnings: list[str]) -> None:
    for html_file in base.rglob("*.html"):
        text = html_file.read_text(encoding="utf-8", errors="ignore")
        rel = html_file.relative_to(base)
        lower = text.lower()
        if len(text.strip()) < 1200:
            errors.append(f"{rel} suspiciously small/blank")
        for needle, label in [
            ("<title>", "title"),
            ("name=\"description\"", "meta description"),
            ("rel=\"canonical\"", "canonical"),
            ("property=\"og:title\"", "Open Graph title"),
            ("twitter:card", "Twitter card"),
            ("application/ld+json", "JSON-LD"),
            ("<h1", "h1"),
        ]:
            if needle not in lower:
                errors.append(f"{rel} missing {label}")
        if public:
            if "googletagmanager.com/gtag/js?id=" not in text and "GA disabled" not in text:
                warnings.append(f"{rel} analytics not configured")
            parser = Parser()
            parser.feed(text)
            for _tag, attrs in parser.tags:
                for key in ["href", "src", "poster"]:
                    if key in attrs and not local_exists(base, html_file, attrs[key]):
                        errors.append(f"{rel} broken local asset/link: {attrs[key]}")
        else:
            if "noindex" not in lower:
                errors.append(f"{rel} protected page missing noindex")


def audit_public(base: Path, errors: list[str]) -> None:
    required = [
        "index.html", "newhaven.html", "weekly-update.html", "source-records.html", "readiness.html", "methodology.html",
        "downloads.html", "privacy.html", "terms.html", "cookies.html", "accessibility.html", "contact.html",
        "sitemap.xml", "robots.txt", "site.webmanifest", "assets/aq26-logo.svg", "assets/aq26-canonical.css",
    ]
    for rel in required:
        if not (base / rel).exists():
            errors.append(f"Missing public required file: {rel}")
    robots = (base / "robots.txt").read_text(encoding="utf-8", errors="ignore") if (base / "robots.txt").exists() else ""
    if "Disallow: /unredacted/" not in robots:
        errors.append("robots.txt must disallow /unredacted/")
    if "Sitemap:" not in robots:
        errors.append("robots.txt missing Sitemap line")
    sitemap = (base / "sitemap.xml").read_text(encoding="utf-8", errors="ignore") if (base / "sitemap.xml").exists() else ""
    urls = re.findall(r"<loc>(.*?)</loc>", sitemap)
    if len(urls) < 12:
        errors.append(f"sitemap.xml too small: {len(urls)} URLs")
    if any("/unredacted/" in url for url in urls):
        errors.append("Public sitemap must not include /unredacted/")
    downloads = base / "downloads"
    if downloads.exists():
        for p in downloads.glob("*.zip"):
            if "public" not in p.name.lower():
                errors.append(f"Full ZIP bundle must not be public: downloads/{p.name}")


def audit_unredacted(base: Path, errors: list[str]) -> None:
    if not (base / ".htaccess").exists():
        errors.append("Protected unredacted site missing .htaccess")
    robots = (base / "robots.txt").read_text(encoding="utf-8", errors="ignore") if (base / "robots.txt").exists() else ""
    if "Disallow: /" not in robots:
        errors.append("Unredacted robots.txt must disallow all")


def audit_dir(base: Path, public: bool, errors: list[str], warnings: list[str]) -> None:
    if not base.exists():
        errors.append(f"Missing folder: {base}")
        return
    scan_sensitive(base, errors)
    audit_html(base, public, errors, warnings)
    if public:
        audit_public(base, errors)
    else:
        audit_unredacted(base, errors)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", default="site_public")
    ap.add_argument("--unredacted", default="site_unredacted")
    ap.add_argument("--json-out", default="outputs/AQ26_SITE_AUDIT.json")
    args = ap.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    audit_dir(ROOT / args.public, True, errors, warnings)
    audit_dir(ROOT / args.unredacted, False, errors, warnings)
    out = ROOT / args.json_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"ok": not errors, "error_count": len(errors), "warning_count": len(warnings), "errors": errors, "warnings": warnings}, indent=2), encoding="utf-8")
    if errors:
        print("AQ26 site audit failed:")
        for error in errors:
            print(" -", error)
        print(f"Full audit written to {out}")
        return 1
    print(f"AQ26 site audit passed with {len(warnings)} warnings. Report: {out}")
    for warning in warnings[:20]:
        print(" - warning:", warning)
    return 0


if __name__ == "__main__":
    sys.exit(main())
