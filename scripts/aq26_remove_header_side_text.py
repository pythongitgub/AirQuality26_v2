#!/usr/bin/env python3
"""AQ26 header-brand text polish.

Removes generated text labels placed inside/next to the logo anchor, e.g.
`<span><small>SCC Nexus · AQ26</small></span>`, while preserving the logo,
menu, weekly alert, moving banners and page content.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

BRAND_SPAN_RE = re.compile(
    r"(<a\b[^>]*class=[\"'][^\"']*\bbrand\b[^\"']*[\"'][^>]*>\s*(?:(?!</a>).)*?<img\b[^>]*>)\s*"
    r"(?:<span\b[^>]*>\s*<small\b[^>]*>.*?</small>\s*</span>\s*)+",
    re.IGNORECASE | re.DOTALL,
)

# Some older pages place a textual badge immediately after the logo link and before nav/menu.
HEADER_ADJACENT_TEXT_RE = re.compile(
    r"(</a>\s*)<span\b[^>]*>\s*<small\b[^>]*>\s*(?:SCC\s+Nexus\s*·\s*AQ26|AQ26|SCC\s+Nexus)\s*</small>\s*</span>",
    re.IGNORECASE | re.DOTALL,
)

CSS_HIDE_BRAND_SPAN = ".brand span,.brand small{display:none!important}\n"


def polish_html(text: str) -> tuple[str, int]:
    changes = 0
    text2, n = BRAND_SPAN_RE.subn(r"\1", text)
    changes += n
    text2, n = HEADER_ADJACENT_TEXT_RE.subn(r"\1", text2)
    changes += n
    return text2, changes


def ensure_css(site: Path) -> bool:
    css = site / "assets" / "aq26_header_text_polish.css"
    css.parent.mkdir(parents=True, exist_ok=True)
    old = css.read_text(encoding="utf-8") if css.exists() else ""
    if CSS_HIDE_BRAND_SPAN not in old:
        css.write_text((old.rstrip() + "\n" + CSS_HIDE_BRAND_SPAN).lstrip(), encoding="utf-8")
        return True
    return False


def inject_css_ref(text: str) -> tuple[str, bool]:
    href = "assets/aq26_header_text_polish.css"
    if href in text:
        return text, False
    ref = '<link rel="stylesheet" href="assets/aq26_header_text_polish.css?v=aq26-header-polish">'
    if "</head>" in text.lower():
        text = re.sub(r"</head>", ref + "\n</head>", text, count=1, flags=re.IGNORECASE)
    else:
        text = ref + "\n" + text
    return text, True


def process_site(site: Path) -> Dict[str, object]:
    result: Dict[str, object] = {"site": str(site), "exists": site.exists(), "files_changed": 0, "html_changes": 0, "css_changed": False, "changed_files": []}
    if not site.exists():
        return result
    css_changed = ensure_css(site)
    result["css_changed"] = css_changed
    changed_files: List[str] = []
    html_changes = 0
    for html_path in sorted(site.rglob("*.html")):
        original = html_path.read_text(encoding="utf-8", errors="replace")
        polished, n = polish_html(original)
        polished, css_injected = inject_css_ref(polished)
        if polished != original:
            html_path.write_text(polished, encoding="utf-8")
            changed_files.append(str(html_path.relative_to(site)))
            html_changes += n + (1 if css_injected else 0)
    result["files_changed"] = len(changed_files) + (1 if css_changed else 0)
    result["html_changes"] = html_changes
    result["changed_files"] = changed_files[:100]
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", action="append", required=True, help="Site folder to polish. Can be supplied more than once.")
    ap.add_argument("--summary", default="outputs/header_text_polish_summary.json")
    args = ap.parse_args()
    summaries = [process_site(Path(s)) for s in args.site_root]
    out = Path(args.summary)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"ok": True, "sites": summaries}, indent=2), encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
