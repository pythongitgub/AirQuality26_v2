#!/usr/bin/env python3
import json
import uuid
from pathlib import Path

def ensure_cell_id(cell: dict) -> None:
    if "id" not in cell or not cell["id"]:
        cell["id"] = uuid.uuid4().hex[:8]

def ensure_code_outputs(cell: dict) -> None:
    if cell.get("cell_type") == "code":
        cell.setdefault("outputs", [])
        cell.setdefault("execution_count", None)

def normalize_notebook(nb_path: Path) -> bool:
    nb = json.loads(nb_path.read_text(encoding="utf-8"))

    changed = False
    for cell in nb.get("cells", []):
        before = dict(cell)
        ensure_cell_id(cell)
        ensure_code_outputs(cell)
        if cell != before:
            changed = True

    # Ensure top-level keys exist (nbconvert expects these)
    nb.setdefault("metadata", {})
    nb.setdefault("nbformat", 4)
    nb.setdefault("nbformat_minor", 5)

    if changed:
        nb_path.write_text(json.dumps(nb, indent=2), encoding="utf-8")
    return changed

def main():
    notebooks_dir = Path("notebooks")
    if not notebooks_dir.exists():
        raise SystemExit("No notebooks/ directory found. Run from repo root.")

    changed_any = False
    for nb_path in sorted(notebooks_dir.glob("*.ipynb")):
        changed = normalize_notebook(nb_path)
        print(("UPDATED" if changed else "OK     "), nb_path)
        changed_any = changed_any or changed

    print("\nDone. Any changes:", changed_any)

if __name__ == "__main__":
    main()
