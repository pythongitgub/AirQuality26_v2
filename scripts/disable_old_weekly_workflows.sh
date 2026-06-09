#!/usr/bin/env bash
set -euo pipefail
python scripts/aq26_disable_old_weekly_workflows.py
echo
echo "If the dry run lists the old workflow(s), run:"
echo "python scripts/aq26_disable_old_weekly_workflows.py --apply"
