#!/usr/bin/env python3
"""
Patch .github/workflows/weekly-production.yml so AQ26 /unredacted/
Basic Auth works reliably on Hostinger.

Changes made:
1) htpasswd uses Apache MD5 mode (-m) for broad compatibility.
2) .htaccess uses an absolute AuthUserFile path based on
   AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR.
3) Adds a post-deploy remote verification step if not already present.

Safe to run more than once.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

WORKFLOW = Path(".github/workflows/weekly-production.yml")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if not WORKFLOW.exists():
        fail(f"Workflow not found: {WORKFLOW}")

    text = WORKFLOW.read_text(encoding="utf-8")
    original = text

    # 1) Use Apache MD5 htpasswd hash for better Hostinger compatibility.
    text = text.replace(
        'htpasswd -bc site_unredacted/.htpasswd aq26 "$SCC_UNREDACTED_PASSWORD"',
        'htpasswd -bcm site_unredacted/.htpasswd aq26 "$SCC_UNREDACTED_PASSWORD"',
    )

    # 2) Replace any existing heredoc-created unredacted .htaccess block.
    # Handles both <<'EOF' and <<EOF, and indentation variants.
    htaccess_pattern = re.compile(
        r"cat\s*>\s*site_unredacted/\.htaccess\s*<<'?EOF'?\n"
        r"(?P<body>.*?)\n\s*EOF",
        re.DOTALL,
    )

    replacement = """cat > site_unredacted/.htaccess <<EOF
AuthType Basic
AuthName "AQ26 Unredacted Review"
AuthUserFile ${AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR%/}/unredacted/.htpasswd
Require valid-user
Options -Indexes
EOF"""

    if htaccess_pattern.search(text):
        text = htaccess_pattern.sub(replacement, text, count=1)
    else:
        # Fall back: insert after htpasswd line if the block has drifted.
        anchor = 'htpasswd -bcm site_unredacted/.htpasswd aq26 "$SCC_UNREDACTED_PASSWORD"'
        if anchor not in text:
            fail("Could not find htpasswd line or .htaccess creation block to patch.")
        text = text.replace(anchor, anchor + "\n          " + replacement, 1)

    # 3) Add remote verification step after deploy step if missing.
    verify_step_name = "Verify remote unredacted auth files"
    if verify_step_name not in text:
        marker = """      - name: Remove deployment-only auth files
        if: always()"""
        verify_step = r'''      - name: Verify remote unredacted auth files
        if: ${{ steps.gate.outputs.should_run == 'true' }}
        shell: bash
        run: |
          set -euo pipefail
          DO_DEPLOY="${{ inputs.deploy_to_hostinger }}"
          DRY_RUN="${{ inputs.dry_run }}"
          if [ "${GITHUB_EVENT_NAME:-}" = "schedule" ]; then
            DO_DEPLOY="true"
            DRY_RUN="false"
          fi
          if [ "$DO_DEPLOY" != "true" ] || [ "$DRY_RUN" = "true" ]; then
            echo "Skipping remote auth verification because this was not a live deploy."
            exit 0
          fi
          : "${AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR:?AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR missing}"
          : "${SCCAIRQUALITY_SSH_HOST:?SCCAIRQUALITY_SSH_HOST missing}"
          : "${SCCAIRQUALITY_SSH_PORT:?SCCAIRQUALITY_SSH_PORT missing}"
          : "${SCCAIRQUALITY_SSH_USERNAME:?SCCAIRQUALITY_SSH_USERNAME missing}"
          : "${SCCAIRQUALITY_SSH_PASSWORD:?SCCAIRQUALITY_SSH_PASSWORD missing}"
          REMOTE_ROOT="${AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR%/}"
          SSH_OPTS="-p ${SCCAIRQUALITY_SSH_PORT} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=45"
          export SSHPASS="$SCCAIRQUALITY_SSH_PASSWORD"
          sshpass -e ssh $SSH_OPTS "$SCCAIRQUALITY_SSH_USERNAME@$SCCAIRQUALITY_SSH_HOST" \
            "test -f '$REMOTE_ROOT/unredacted/.htaccess' && test -f '$REMOTE_ROOT/unredacted/.htpasswd' && grep -q '$REMOTE_ROOT/unredacted/.htpasswd' '$REMOTE_ROOT/unredacted/.htaccess'"
          echo "Remote unredacted auth files verified."

'''
        if marker in text:
            text = text.replace(marker, verify_step + marker, 1)
        else:
            print("WARNING: Could not find cleanup step; remote verification step was not inserted.")

    if text == original:
        print("No changes made. Workflow already appears patched.")
    else:
        WORKFLOW.write_text(text, encoding="utf-8")
        print(f"Patched {WORKFLOW}")
        print("Expected key lines now present:")
        print("- htpasswd -bcm site_unredacted/.htpasswd aq26 ...")
        print("- AuthUserFile ${AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR%/}/unredacted/.htpasswd")
        if verify_step_name in text:
            print("- Verify remote unredacted auth files")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
