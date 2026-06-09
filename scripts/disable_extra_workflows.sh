#!/usr/bin/env bash
set -euo pipefail
mkdir -p docs/disabled_workflows
KEEP_REGEX='^(weekly-production|aq26-hostinger-ssh-preflight)\.ya?ml$'
for f in .github/workflows/*.yml .github/workflows/*.yaml; do
  [ -e "$f" ] || continue
  base="$(basename "$f")"
  if [[ "$base" =~ $KEEP_REGEX ]]; then
    echo "KEEP $f"
  else
    echo "DISABLE $f -> docs/disabled_workflows/${base}.txt"
    git mv "$f" "docs/disabled_workflows/${base}.txt" 2>/dev/null || mv "$f" "docs/disabled_workflows/${base}.txt"
  fi
done
