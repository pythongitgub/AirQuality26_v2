#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_PUBLIC = [
    "index.html",
    "newhaven.html",
    "privacy.html",
    "terms.html",
    "cookies.html",
    "accessibility.html",
    "contact.html",
    "404.html",
]

REQUIRED_UNREDACTED = [
    "index.html",
    "newhaven.html",
    "privacy.html",
    "terms.html",
    "cookies.html",
    "accessibility.html",
    "contact.html",
    "404.html",
]


def pick_site_dir(name: str) -> Path:
    """Prefer generated dist output, fall back to legacy folder."""
    candidates = [Path("dist") / name, Path(name)]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return candidates[0]


def check_html_file(path: Path, *, require_noindex: bool = False) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()

    checks = {
        "<title": "missing <title>",
        'name="description"': 'missing meta name="description"',
        'rel="canonical"': 'missing rel="canonical"',
        'property="og:title"': 'missing property="og:title"',
        'name="twitter:card"': 'missing twitter:card',
        'site-footer': 'missing site-footer',
        'nav-toggle': 'missing nav-toggle',
        'application/ld+json': 'missing application/ld+json',
    }
    for needle, message in checks.items():
        if needle not in lowered:
            errors.append(f"{path}: {message}")

    if require_noindex and "noindex" not in lowered:
        errors.append(f"{path}: unredacted page missing noindex")

    return errors


def main() -> int:
    public_dir = pick_site_dir("site_public")
    unredacted_dir = pick_site_dir("site_unredacted")
    errors: list[str] = []

    if not public_dir.exists():
        errors.append(f"Missing public site folder: {public_dir}")
    if not unredacted_dir.exists():
        errors.append(f"Missing unredacted site folder: {unredacted_dir}")

    if errors:
        print("AQ26 site quality gate failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    for filename in REQUIRED_PUBLIC:
        path = public_dir / filename
        if not path.exists():
            errors.append(f"{path}: required public page missing")
        else:
            errors.extend(check_html_file(path))

    for filename in REQUIRED_UNREDACTED:
        path = unredacted_dir / filename
        if not path.exists():
            errors.append(f"{path}: required unredacted page missing")
        else:
            errors.extend(check_html_file(path, require_noindex=True))

    sitemap = public_dir / "sitemap.xml"
    robots = public_dir / "robots.txt"
    if not sitemap.exists():
        errors.append(f"{sitemap}: missing sitemap.xml")
    if not robots.exists():
        errors.append(f"{robots}: missing robots.txt")

    if errors:
        print("AQ26 site quality gate failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print(f"AQ26 site quality gate passed using public={public_dir} unredacted={unredacted_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
