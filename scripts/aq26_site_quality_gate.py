#!/usr/bin/env python3
"""AQ26 website quality gate.

Checks the rebuilt core page set only. It deliberately avoids blocking deployment
on legacy pages that have not yet been migrated into the shared template.
"""
from __future__ import annotations

from pathlib import Path
from bs4 import BeautifulSoup

PUBLIC_DIR = Path("site_public")
UNREDACTED_DIR = Path("site_unredacted")

PUBLIC_REQUIRED = [
    "index.html", "newhaven.html", "privacy.html", "terms.html", "cookies.html",
    "accessibility.html", "contact.html", "sitemap.xml", "robots.txt",
]
UNREDACTED_REQUIRED = [
    "index.html", "newhaven.html", "privacy.html", "terms.html", "cookies.html",
    "accessibility.html", "contact.html", "evidence.html", "review-notes.html",
    "sitemap.xml", "robots.txt",
]
HTML_REQUIRED_SNIPPETS = [
    "<footer", "canonical", "og:title", "twitter:card", "application/ld+json", "menu-toggle",
]


def check_page(path: Path, unredacted: bool, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")
    for snippet in HTML_REQUIRED_SNIPPETS:
        if snippet not in text:
            errors.append(f"{path}: missing {snippet}")
    if not soup.find("footer"):
        errors.append(f"{path}: missing footer element")
    if not soup.find("nav"):
        errors.append(f"{path}: missing nav element")
    if not soup.find("link", rel="canonical"):
        errors.append(f"{path}: missing canonical link")
    if unredacted:
        robots = soup.find("meta", attrs={"name": "robots"})
        if not robots or "noindex" not in robots.get("content", "").lower():
            errors.append(f"{path}: unredacted page must contain noindex robots meta")


def main() -> None:
    errors: list[str] = []
    for name in PUBLIC_REQUIRED:
        path = PUBLIC_DIR / name
        if not path.exists():
            errors.append(f"{path}: required public page missing")
        elif path.suffix == ".html":
            check_page(path, False, errors)
    for name in UNREDACTED_REQUIRED:
        path = UNREDACTED_DIR / name
        if not path.exists():
            errors.append(f"{path}: required unredacted page missing")
        elif path.suffix == ".html":
            check_page(path, True, errors)
    if errors:
        print("AQ26 site quality gate failed:")
        for err in errors:
            print(f" - {err}")
        raise SystemExit(1)
    print("AQ26 site quality gate passed.")


if __name__ == "__main__":
    main()
