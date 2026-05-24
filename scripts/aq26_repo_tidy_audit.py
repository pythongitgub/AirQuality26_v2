#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, datetime as dt
from pathlib import Path
from collections import Counter

def write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", default="outputs")
    args = ap.parse_args()
    root = Path(".")
    workflows = sorted(str(p) for p in (root / ".github" / "workflows").glob("*.yml")) + sorted(str(p) for p in (root / ".github" / "workflows").glob("*.yaml"))
    scripts = sorted(str(p) for p in (root / "scripts").glob("*.py"))
    configs = sorted(str(p) for p in (root / "configs").glob("*"))
    notebooks = sorted(str(p) for p in (root / "notebooks").glob("*.ipynb")) if (root / "notebooks").exists() else []
    active_weekly = [w for w in workflows if "weekly_v2" in w or "weekly_integrated" in w or "weekly_comprehensive" in w or "weekly_report" in w]
    result = {
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": "Repository tidy audit only; no files are deleted or moved.",
        "counts": {
            "workflows": len(workflows),
            "scripts": len(scripts),
            "configs": len(configs),
            "notebooks": len(notebooks),
            "active_weekly_like_workflows": len(active_weekly),
        },
        "recommended_primary_workflow": ".github/workflows/aq26_weekly_v2.yml",
        "workflow_files": workflows,
        "weekly_like_workflows": active_weekly,
        "script_files": scripts,
        "config_files": configs,
        "notebook_count": len(notebooks),
        "tidy_recommendations": [
            "Keep aq26_weekly_v2.yml as the primary GitHub weekly evidence workflow.",
            "Do not delete historical notebook workflows until their outputs have been archived and compared.",
            "Move obsolete experiment/phase workflows to .github/workflows_disabled/ only after a clean WeeklyV2 run is certified.",
            "Keep scripts-only WeeklyV2 separate from Google Colab paths.",
            "Use docs/ as the source of operational truth for secrets, outputs and readiness gates.",
        ],
    }
    out = Path(args.output_root) / "13_repo_tidy" / "repo_tidy_audit.json"
    write(out, result)
    md = Path(args.output_root) / "13_repo_tidy" / "repo_tidy_audit.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(
        "# AQ26 Repository Tidy Audit\n\n"
        f"- Workflows: {len(workflows)}\n"
        f"- Scripts: {len(scripts)}\n"
        f"- Config files: {len(configs)}\n"
        f"- Notebooks: {len(notebooks)}\n"
        f"- Recommended primary workflow: `.github/workflows/aq26_weekly_v2.yml`\n\n"
        "No files were deleted or moved by this audit.\n",
        encoding="utf-8",
    )
    print(json.dumps({"repo_tidy_audit": str(out), "workflows": len(workflows), "scripts": len(scripts), "notebooks": len(notebooks)}, indent=2))

if __name__ == "__main__":
    main()
