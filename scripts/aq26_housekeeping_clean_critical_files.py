#!/usr/bin/env python3
"""AQ26 one-time critical housekeeping cleanup.

Removes deployment-only auth files from the working tree before commit,
creates safe placeholders where helpful, and writes a cleanup summary.
"""
from __future__ import annotations
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('.').resolve()
REMOVED = []
WARNINGS = []

TRACKED_REMOVE = [
    'site_unredacted/.htpasswd',
    'site_unredacted/.htpasswd.tmp',
]

for rel in TRACKED_REMOVE:
    p = REPO / rel
    if p.exists():
        try:
            p.unlink()
            REMOVED.append(rel)
        except Exception as e:
            WARNINGS.append(f'Could not delete {rel}: {e}')

# Keep a safe .htaccess template committed if present/needed. It does not contain the password hash.
htaccess = REPO / 'site_unredacted/.htaccess'
htaccess.parent.mkdir(parents=True, exist_ok=True)
htaccess.write_text('''AuthType Basic
AuthName "AQ26 Unredacted Review"
AuthUserFile .htpasswd
Require valid-user
''', encoding='utf-8')

robots = REPO / 'site_unredacted/robots.txt'
robots.write_text('User-agent: *\nDisallow: /\n', encoding='utf-8')

summary = {
    'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'removed_working_tree_files': REMOVED,
    'warnings': WARNINGS,
    'notes': [
        'Rotate SCC_UNREDACTED_PASSWORD after this cleanup because an old .htpasswd hash was previously committed.',
        '.htpasswd is now ignored and should be generated only immediately before deployment.',
    ],
}
out = REPO / 'outputs/housekeeping/critical_cleanup_summary.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
