#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

WORKFLOW = Path('.github/workflows/weekly-production.yml')
MARKER = 'Apply SEO, legal footer, cookie banner and analytics'
BLOCK = '''

      - name: Apply SEO, legal footer, cookie banner and analytics
        if: ${{ steps.gate.outputs.should_run == 'true' }}
        shell: bash
        env:
          GA_MEASUREMENT_ID: ${{ secrets.GA_MEASUREMENT_ID }}
          AQ26_PUBLIC_BASE_URL: https://sccairquality.com
        run: |
          set -euo pipefail
          python scripts/aq26_apply_seo_legal_analytics.py

      - name: Verify SEO, legal pages, sitemap, robots and analytics hooks
        if: ${{ steps.gate.outputs.should_run == 'true' }}
        shell: bash
        env:
          GA_MEASUREMENT_ID: ${{ secrets.GA_MEASUREMENT_ID }}
        run: |
          set -euo pipefail
          python scripts/aq26_verify_seo_legal_analytics.py
'''

ANCHORS = [
    '      - name: Catalogue visual assets and prune heavy website bundles\n',
    '      - name: Create deployment-only unredacted password files\n',
    '      - name: Install deployment tools\n',
]

def main() -> int:
    if not WORKFLOW.exists():
        raise SystemExit(f'Missing {WORKFLOW}')
    text = WORKFLOW.read_text(encoding='utf-8')
    if MARKER in text:
        print('SEO workflow steps already present; no change made.')
        return 0
    for anchor in ANCHORS:
        idx = text.find(anchor)
        if idx != -1:
            text = text[:idx] + BLOCK + text[idx:]
            WORKFLOW.write_text(text, encoding='utf-8')
            print(f'Inserted SEO workflow steps before: {anchor.strip()}')
            return 0
    raise SystemExit('Could not find a safe insertion point in weekly-production.yml')

if __name__ == '__main__':
    raise SystemExit(main())
