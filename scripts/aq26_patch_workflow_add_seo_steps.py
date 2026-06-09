#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

WF = Path('.github/workflows/weekly-production.yml')
SEO_STEPS = '''
      - name: Apply SEO, legal footer, cookie banner and analytics
        if: ${{ steps.gate.outputs.should_run == 'true' }}
        shell: bash
        env:
          GA_MEASUREMENT_ID: ${{ secrets.GA_MEASUREMENT_ID }}
          AQ26_PUBLIC_URL: https://sccairquality.com
        run: |
          set -euo pipefail
          python scripts/aq26_apply_seo_legal_analytics.py --site-root site_public --domain "${AQ26_PUBLIC_URL}" --ga-id "${GA_MEASUREMENT_ID:-}"
          if [ -d site_test ]; then
            python scripts/aq26_apply_seo_legal_analytics.py --site-root site_test --domain "${AQ26_PUBLIC_URL}/test" --ga-id "${GA_MEASUREMENT_ID:-}"
          fi

      - name: Verify SEO, legal pages, sitemap, robots and analytics hooks
        if: ${{ steps.gate.outputs.should_run == 'true' }}
        shell: bash
        env:
          GA_MEASUREMENT_ID: ${{ secrets.GA_MEASUREMENT_ID }}
        run: |
          set -euo pipefail
          python scripts/aq26_verify_seo_legal_analytics.py --site-root site_public --require-ga
'''

def main() -> int:
    if not WF.exists():
        raise SystemExit(f'Missing workflow: {WF}')
    text = WF.read_text(encoding='utf-8')
    if 'Apply SEO, legal footer, cookie banner and analytics' in text:
        print('Workflow already contains SEO steps; no change made.')
        return 0
    marker = '      - name: Create deployment-only unredacted password files'
    if marker not in text:
        raise SystemExit('Could not find insertion marker: Create deployment-only unredacted password files')
    text = text.replace(marker, SEO_STEPS + '\n' + marker, 1)
    WF.write_text(text, encoding='utf-8')
    print(f'Patched {WF}: inserted SEO/legal/analytics steps before deployment auth step.')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
