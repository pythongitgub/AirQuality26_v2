#!/usr/bin/env python3
"""
AQ26 SEO, footer and analytics gate.

Checks the generated AQ26 public and unredacted HTML for:
- footer/legal/site links
- canonical URL
- meta description and robots
- Open Graph and Twitter Card metadata
- JSON-LD
- GA4 analytics when GA_MEASUREMENT_ID / analytics_id is configured
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
PUBLIC = ROOT / "site_public"
UNREDACTED = ROOT / "site_unredacted"
CONFIG_CANDIDATES = [ROOT / "configs" / "aq26_site_config.json", ROOT / "config" / "aq26_site_config.json"]

CORE_PUBLIC = [
    "index.html",
    "newhaven.html",
    "source-records.html",
    "weekly-update.html",
    "downloads.html",
    "privacy.html",
    "terms.html",
    "cookies.html",
    "accessibility.html",
    "contact.html",
]
CORE_UNREDACTED = [
    "index.html",
    "newhaven.html",
    "evidence.html",
    "source-records.html",
    "weekly-update.html",
    "history.html",
    "downloads.html",
    "diagnostics.html",
    "candidates.html",
]

FOOTER_LINKS = [
    "/privacy.html",
    "/terms.html",
    "/cookies.html",
    "/accessibility.html",
    "/contact.html",
    "/sitemap.xml",
]

def read_config() -> dict:
    cfg = {}
    for p in CONFIG_CANDIDATES:
        if p.exists():
            try:
                cfg = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(cfg, dict):
                    break
            except Exception:
                pass
    env_ga = os.environ.get("GA_MEASUREMENT_ID") or os.environ.get("AQ26_GA_MEASUREMENT_ID") or os.environ.get("AQ26_ANALYTICS_ID")
    if env_ga:
        cfg["analytics_id"] = env_ga.strip()
    env_verify = os.environ.get("GOOGLE_SITE_VERIFICATION") or os.environ.get("AQ26_GOOGLE_SITE_VERIFICATION") or os.environ.get("SEARCH_CONSOLE_VERIFICATION")
    if env_verify:
        cfg["search_console_verification"] = env_verify.strip()
    env_contact = os.environ.get("AQ26_CONTACT_EMAIL") or os.environ.get("CONTACT_EMAIL") or os.environ.get("SITE_CONTACT_EMAIL")
    if env_contact:
        cfg["contact_email"] = env_contact.strip()
    elif not cfg.get("contact_email"):
        cfg["contact_email"] = "enquiries@sccairquality.com"
    return cfg

def has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.I | re.S) is not None

def check_page(path: Path, public: bool, cfg: dict, errors: list[str], warnings: list[str]) -> None:
    rel = path.relative_to(ROOT)
    if not path.exists():
        errors.append(f"{rel}: missing")
        return
    text = path.read_text(encoding="utf-8", errors="ignore")

    required = {
        "footer": r"<footer\b",
        "meta description": r'<meta\s+name=["\']description["\']',
        "robots": r'<meta\s+name=["\']robots["\']',
        "canonical": r'<link\s+rel=["\']canonical["\']',
        "Open Graph title": r'<meta\s+property=["\']og:title["\']',
        "Open Graph description": r'<meta\s+property=["\']og:description["\']',
        "Open Graph URL": r'<meta\s+property=["\']og:url["\']',
        "Twitter card": r'<meta\s+name=["\']twitter:card["\']',
        "Twitter title": r'<meta\s+name=["\']twitter:title["\']',
        "Twitter image": r'<meta\s+name=["\']twitter:image["\']\s+content=["\'][^"\']+["\']',
        "JSON-LD": r'<script\s+type=["\']application/ld\+json["\']',
    }
    for label, pattern in required.items():
        if not has(pattern, text):
            errors.append(f"{rel}: missing {label}")

    for link in FOOTER_LINKS:
        if link not in text:
            errors.append(f"{rel}: footer missing {link}")

    if public and "/unredacted/" not in text:
        errors.append(f"{rel}: public footer/header missing /unredacted/ link")

    if not public:
        if not has(r'<meta\s+name=["\']robots["\']\s+content=["\']noindex,nofollow["\']', text):
            errors.append(f"{rel}: unredacted page must be noindex,nofollow")

    contact_email = (cfg.get("contact_email") or "enquiries@sccairquality.com").strip()
    if path.name == "contact.html" and contact_email not in text:
        errors.append(f"{rel}: contact email {contact_email} not installed")
    if "<footer" in text and "/contact.html" in text and contact_email not in text:
        errors.append(f"{rel}: footer missing contact email {contact_email}")

    ga = (cfg.get("analytics_id") or cfg.get("ga_measurement_id") or "").strip()
    if ga:
        if ga not in text or "googletagmanager.com/gtag/js" not in text:
            errors.append(f"{rel}: GA4 analytics ID {ga} not installed")
    else:
        warnings.append("GA_MEASUREMENT_ID / analytics_id not set, so GA4 analytics snippet is not expected.")

    verify = (cfg.get("search_console_verification") or cfg.get("google_site_verification") or "").strip()
    if verify and public and verify not in text:
        errors.append(f"{rel}: Google Search Console verification token not installed")

def main() -> int:
    cfg = read_config()
    errors: list[str] = []
    warnings: list[str] = []

    for name in CORE_PUBLIC:
        check_page(PUBLIC / name, True, cfg, errors, warnings)

    for name in CORE_UNREDACTED:
        check_page(UNREDACTED / name, False, cfg, errors, warnings)

    # avoid repeating the same no-GA warning for every page
    warnings = sorted(set(warnings))

    for w in warnings:
        print("SEO gate warning:", w)

    if errors:
        print("AQ26 SEO/footer/analytics gate failed:")
        for e in errors:
            print(" -", e)
        return 1

    print("AQ26 SEO/footer/analytics gate passed.")
    ga = (cfg.get("analytics_id") or cfg.get("ga_measurement_id") or "").strip()
    if ga:
        print(f"GA4 analytics installed: {ga}")
    else:
        print("GA4 analytics not installed because no GA_MEASUREMENT_ID / analytics_id is configured.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
