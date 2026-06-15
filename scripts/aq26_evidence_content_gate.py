#!/usr/bin/env python3
from pathlib import Path
import sys
required = {
    "site_unredacted/index.html": ["Protected reviewer console", "Evidence readiness gates", "Newhaven evidence hub"],
    "site_unredacted/newhaven.html": ["Newhaven ERF focus", "Structured emissions measurement records", "Local evidence inventory"],
    "site_unredacted/evidence.html": ["High-priority evidence queue", "Evidence downloads", "Source index"],
    "site_unredacted/source-records.html": ["Traceable AQ26 source records", "SHA256", "Official filing search index"],
    "site_unredacted/weekly-update.html": ["Missing-date backfill plan", "Facility backfill readiness"],
    "site_unredacted/candidates.html": ["Candidate overlay review queue"],
    "site_unredacted/diagnostics.html": ["Internal diagnostics", "Live OpenAQ probe diagnostics"],
    "site_public/index.html": ["Protected reviewer evidence", "Open protected evidence area"],
    "site_public/newhaven.html": ["Open protected Newhaven evidence hub"],
}
errors=[]
for file, needles in required.items():
    p=Path(file)
    if not p.exists():
        errors.append(f"{file}: missing")
        continue
    txt=p.read_text(encoding='utf-8', errors='replace')
    for n in needles:
        if n not in txt:
            errors.append(f"{file}: missing content marker {n!r}")
    if "What this page provides" in txt or "Next improvement" in txt:
        errors.append(f"{file}: still contains placeholder overhaul text")
    if file.startswith('site_unredacted') and 'noindex,nofollow' not in txt:
        errors.append(f"{file}: protected page missing noindex,nofollow")
    if '<button class="burger"' not in txt:
        errors.append(f"{file}: burger menu missing")
    if '© 2026 SCC Nexus' not in txt:
        errors.append(f"{file}: footer/copyright missing")
if errors:
    print('AQ26 evidence content gate failed:')
    for e in errors:
        print(' -', e)
    sys.exit(1)
print('AQ26 evidence content gate passed.')
