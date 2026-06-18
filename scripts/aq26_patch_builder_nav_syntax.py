#!/usr/bin/env python3
from pathlib import Path

path = Path("scripts/aq26_build_evidence_content.py")
if not path.exists():
    raise SystemExit("scripts/aq26_build_evidence_content.py not found")

text = path.read_text(encoding="utf-8")
old = '''def nav_html(active: str, protected: bool) -> str:\n    if protected:\n        links = [\n            ("/unredacted/", "Protected home"), ("/unredacted/newhaven.html", "Newhaven"), ("/unredacted/evidence.html", "Evidence"),\n            ("/unredacted/source-records.html", "Sources"), ("/unredacted/weekly-update.html", "Weekly"), ("/unredacted/downloads.html", "Downloads"),\n            ("/unredacted/history.html", "History"), ("/unredacted/diagnostics.html", "Diagnostics"), ("/unredacted/candidates.html", "Candidates"), ("/", "Public site")]\n    else:\n        links = [("/", "Home"), ("/newhaven.html", "Newhaven"), ("/source-records.html", "Sources"), ("/weekly-update.html", "Weekly update"), ("/archive.html", "Archive"), ("/methodology.html", "Methodology"), ("/contact.html", "Contact"), ("/unredacted/", "Unredacted")]\n    return "".join(f'<a href="{u}"{(" aria-current=\\"page\\"" if t == active else "")}>{esc(t)}</a>' for u, t in links)\n'''
new = '''def nav_html(active: str, protected: bool) -> str:\n    if protected:\n        links = [\n            ("/unredacted/", "Protected home"), ("/unredacted/newhaven.html", "Newhaven"), ("/unredacted/evidence.html", "Evidence"),\n            ("/unredacted/source-records.html", "Sources"), ("/unredacted/weekly-update.html", "Weekly"), ("/unredacted/downloads.html", "Downloads"),\n            ("/unredacted/history.html", "History"), ("/unredacted/diagnostics.html", "Diagnostics"), ("/unredacted/candidates.html", "Candidates"), ("/", "Public site")]\n    else:\n        links = [("/", "Home"), ("/newhaven.html", "Newhaven"), ("/source-records.html", "Sources"), ("/weekly-update.html", "Weekly update"), ("/archive.html", "Archive"), ("/methodology.html", "Methodology"), ("/contact.html", "Contact"), ("/unredacted/", "Unredacted")]\n    parts = []\n    for u, t in links:\n        current = ' aria-current="page"' if t == active else ''\n        parts.append(f'<a href="{u}"{current}>{esc(t)}</a>')\n    return "".join(parts)\n'''
if old in text:
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("Patched nav_html f-string syntax.")
else:
    bad = 'return "".join(f\'<a href="{u}"{(" aria-current=\\"page\\"" if t == active else "")}>{esc(t)}</a>\' for u, t in links)'
    if bad in text:
        text = text.replace(bad, '''parts = []\n    for u, t in links:\n        current = ' aria-current="page"' if t == active else ''\n        parts.append(f'<a href="{u}"{current}>{esc(t)}</a>')\n    return "".join(parts)''')
        path.write_text(text, encoding="utf-8")
        print("Patched unsafe nav_html return line.")
    else:
        print("No unsafe nav_html f-string found; no patch needed.")
