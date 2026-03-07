from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
required = [
    root / "notebooks" / "40_target_control_extension.ipynb",
    root / "notebooks" / "41_cross_reference_existing_outputs.ipynb",
    root / "notebooks" / "42_multi_site_comparison.ipynb",
    root / "notebooks" / "43_window_ranking.ipynb",
    root / "notebooks" / "44_gemini_forensic_extension.ipynb",
    root / "notebooks" / "45_phase2_report_builder.ipynb",
    root / "configs" / "run_phase40_patch_example.yml",
]
missing = [str(p.relative_to(root)) for p in required if not p.exists()]
if missing:
    print("Missing files:")
    for m in missing:
        print(" -", m)
    sys.exit(1)
print("Phase 40 files present.")
