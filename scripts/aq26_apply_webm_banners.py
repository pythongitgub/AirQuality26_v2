#!/usr/bin/env python3
"""Apply AQ26 uploaded WEBM moving banners to public and unredacted HTML sites.

This script is intentionally conservative: it copies banner assets, injects CSS/JS
links, and adds a video hero/ticker only when one is not already present.
"""
from __future__ import annotations
import argparse, json, re, shutil
from datetime import datetime, timezone
from pathlib import Path

BANNER_FILES = [f"desktop_banner_{i}.webm" for i in range(1,7)]
CSS = "aq26_webm_banners.css"
JS = "aq26_webm_banners.js"

DEFAULT_STATS = {
    "facilities": "46",
    "validated": "8",
    "candidates": "35",
    "unresolved": "3",
}

TEXTS = {
    "index.html": ("SCC Nexus · AQ26", "Incinerator evidence observatory", "England and Wales incinerator coverage, monitoring overlays, public-safe summaries and protected provenance review."),
    "incinerators.html": ("Facility register", "England & Wales incinerator coverage", "A facility-led evidence spine for validated overlays, candidate monitoring sites and unresolved discovery gaps."),
    "newhaven.html": ("Newhaven focus", "Newhaven ERF / BV8067IL", "The high-confidence reference case for facility-control evidence, official reporting and public-safe interpretation."),
    "overlays.html": ("Monitoring overlays", "Validated and candidate monitoring sites", "Coverage status across incinerator facilities, control candidates and review priorities."),
    "comparisons.html": ("Comparisons", "Facility, pollutant and overlay comparison dashboard", "Interactive chart-ready summaries for evidence coverage and monitoring overlay status."),
    "methodology.html": ("Methodology", "How AQ26 separates evidence, context and review", "A transparent, cautious workflow for public summaries and protected unredacted provenance."),
    "downloads.html": ("Downloads", "Redacted public evidence downloads", "Public-safe downloads and summary outputs, with full diagnostics restricted to the review area."),
    "legal.html": ("Legal safety", "Public-safe wording and limitations", "No regulatory, causal, medical or legal conclusion is made by the public interface."),
}

def rel_prefix(html: Path, root: Path) -> str:
    try:
        depth = len(html.relative_to(root).parts) - 1
    except Exception:
        depth = 0
    return "../" * max(depth, 0)

def load_counts(site_root: Path) -> dict:
    counts = dict(DEFAULT_STATS)
    for p in [site_root/"data/focus/overlays_v3/incinerator_overlay_summary.json", site_root/"data/focus/incinerator_register_summary.json"]:
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                counts["facilities"] = str(d.get("broad_facilities") or d.get("facilities") or d.get("facility_count") or counts["facilities"])
                counts["validated"] = str(d.get("validated_overlays") or counts["validated"])
                counts["candidates"] = str(d.get("candidate_facilities_cumulative") or d.get("candidate_overlay_needs_review") or counts["candidates"])
                counts["unresolved"] = str(d.get("no_candidate_selected_yet") or counts["unresolved"])
            except Exception:
                pass
    return counts

def copy_assets(site_root: Path, asset_source: Path) -> None:
    (site_root/"assets/banners").mkdir(parents=True, exist_ok=True)
    (site_root/"assets").mkdir(parents=True, exist_ok=True)
    for name in BANNER_FILES:
        src = asset_source/"banners"/name
        if src.exists():
            shutil.copy2(src, site_root/"assets/banners"/name)
    for name in [CSS, JS, "air_quality_web.svg", "favicon.svg", "logo_web.svg"]:
        src = asset_source/name
        if src.exists():
            shutil.copy2(src, site_root/"assets"/name)

def ensure_head_links(html_text: str, prefix: str) -> str:
    additions = []
    if CSS not in html_text:
        additions.append(f'<link rel="stylesheet" href="{prefix}assets/{CSS}?v=aq26-webm-banners-20260528">')
    if 'rel="icon"' not in html_text and "favicon.svg" not in html_text:
        additions.append(f'<link rel="icon" type="image/svg+xml" href="{prefix}assets/favicon.svg?v=aq26-icon-20260528">')
    if 'apple-touch-icon' not in html_text:
        additions.append(f'<link rel="apple-touch-icon" href="{prefix}assets/favicon.svg?v=aq26-touch-20260528">')
    if additions:
        if "</head>" in html_text:
            html_text = html_text.replace("</head>", "  " + "\n  ".join(additions) + "\n</head>", 1)
        else:
            html_text = "<head>" + "\n".join(additions) + "</head>\n" + html_text
    if JS not in html_text:
        script = f'<script src="{prefix}assets/{JS}?v=aq26-webm-banners-20260528" defer></script>'
        if "</body>" in html_text:
            html_text = html_text.replace("</body>", f"  {script}\n</body>", 1)
        else:
            html_text += "\n" + script + "\n"
    return html_text

def banner_html(page: str, counts: dict) -> str:
    kicker, title, subtitle = TEXTS.get(page, ("AQ26", "Incinerator evidence platform", "Public-safe evidence summaries and protected provenance review."))
    return f'''
<section class="aq26-video-banner" aria-label="AQ26 moving evidence banner">
  <div class="aq26-video-banner__media" aria-hidden="true"></div>
  <div class="aq26-video-banner__shade" aria-hidden="true"></div>
  <div class="aq26-video-banner__glow" aria-hidden="true"></div>
  <div class="aq26-video-banner__inner">
    <div class="aq26-video-banner__kicker">{kicker}</div>
    <h1>{title}</h1>
    <p>{subtitle}</p>
    <div class="aq26-video-banner__actions">
      <a class="aq26-video-banner__btn aq26-video-banner__btn--primary" href="incinerators.html">Explore facilities</a>
      <a class="aq26-video-banner__btn" href="newhaven.html">Newhaven focus</a>
      <a class="aq26-video-banner__btn" href="overlays.html">Overlay status</a>
    </div>
    <div class="aq26-video-banner__stats" aria-label="AQ26 headline evidence statistics">
      <div class="aq26-video-banner__stat"><strong>{counts['facilities']}</strong><span>incinerator / EfW facilities</span></div>
      <div class="aq26-video-banner__stat"><strong>{counts['validated']}</strong><span>validated monitoring overlays</span></div>
      <div class="aq26-video-banner__stat"><strong>{counts['candidates']}</strong><span>candidate overlays under review</span></div>
      <div class="aq26-video-banner__stat"><strong>{counts['unresolved']}</strong><span>manual fallback discovery</span></div>
    </div>
  </div>
</section>
'''

def ticker_html(counts: dict) -> str:
    items = [
        f"{counts['facilities']} incinerator / EfW facilities in the AQ26 register",
        f"{counts['validated']} validated monitoring overlays retained",
        f"{counts['candidates']} candidate overlays under review",
        f"{counts['unresolved']} facilities remain in manual fallback discovery",
        "Newhaven ERF remains the high-confidence reference case",
        "Public pages are redacted; full diagnostics remain protected",
    ]
    one = ''.join(f'<span class="aq26-video-ticker__item"><span class="aq26-video-ticker__dot"></span>{x}</span>' for x in items)
    return f'<div class="aq26-video-ticker" aria-label="Moving AQ26 evidence ticker"><div class="aq26-video-ticker__track">{one}{one}</div></div>\n'

def inject_banner(html_text: str, page: str, counts: dict) -> str:
    if 'aq26-video-banner' in html_text:
        return html_text
    block = banner_html(page, counts) + ticker_html(counts)
    # Prefer inserting after header/nav, otherwise after body open.
    m = re.search(r"</header>", html_text, flags=re.I)
    if m:
        return html_text[:m.end()] + "\n" + block + html_text[m.end():]
    m = re.search(r"<body[^>]*>", html_text, flags=re.I)
    if m:
        return html_text[:m.end()] + "\n" + block + html_text[m.end():]
    return block + html_text

def process_site(site_root: Path, asset_source: Path, force: bool) -> dict:
    copy_assets(site_root, asset_source)
    counts = load_counts(site_root)
    changed = []
    for html in sorted(site_root.rglob("*.html")):
        if html.name.startswith("."):
            continue
        txt = html.read_text(encoding="utf-8", errors="replace")
        prefix = rel_prefix(html, site_root)
        new = ensure_head_links(txt, prefix)
        if force or 'aq26-video-banner' not in new:
            new = inject_banner(new, html.name, counts)
        if new != txt:
            html.write_text(new, encoding="utf-8")
            changed.append(str(html.relative_to(site_root)))
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "site_root": str(site_root),
        "changed_pages": changed,
        "changed_count": len(changed),
        "banner_files": [x for x in BANNER_FILES if (site_root/"assets/banners"/x).exists()],
        "counts_used": counts,
    }
    out = site_root/"data/focus/webm_banner_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--asset-source", default="website/assets")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--summary", default="")
    args = ap.parse_args()
    summary = process_site(Path(args.site_root), Path(args.asset_source), args.force)
    if args.summary:
        Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
if __name__ == "__main__":
    main()
