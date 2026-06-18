#!/usr/bin/env python3
"""Patch aq26_build_evidence_content.py to avoid nested f-string syntax errors.

This is intentionally tiny and idempotent. It rewrites the nav_html return line
that contains an f-string expression with escaped quotes, which Python rejects.
"""
from __future__ import annotations

from pathlib import Path

TARGET = Path("scripts/aq26_build_evidence_content.py")


def main() -> int:
    if not TARGET.exists():
        raise SystemExit(f"Missing target script: {TARGET}")

    original = TARGET.read_text(encoding="utf-8")
    lines = original.splitlines()
    out: list[str] = []
    replaced = 0

    for line in lines:
        if (
            'return "".join(f' in line
            and 'aria-current' in line
            and 'for u, t in links' in line
            and '<a href=' in line
        ):
            indent = line[: len(line) - len(line.lstrip())]
            out.extend([
                indent + "parts = []",
                indent + "for u, t in links:",
                indent + "    current = ' aria-current=\"page\"' if t == active else ''",
                indent + "    parts.append(f'<a href=\"{u}\"{current}>{esc(t)}</a>')",
                indent + "return ''.join(parts)",
            ])
            replaced += 1
        else:
            out.append(line)

    if replaced == 0:
        print("No unsafe nav f-string found; leaving builder unchanged.")
        return 0

    TARGET.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Patched {TARGET}: replaced {replaced} unsafe nav f-string line(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
