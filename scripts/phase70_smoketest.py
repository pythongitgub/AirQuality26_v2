from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
required = [
    root / "notebooks" / "70_evidence_inventory_plus.ipynb",
    root / "notebooks" / "71_environmental_documentary_fusion.ipynb",
    root / "notebooks" / "72_target_control_registry_builder.ipynb",
    root / "notebooks" / "73_news_satellite_context_pack.ipynb",
    root / "notebooks" / "74_gemini_25_pro_report_pack.ipynb",
    root / "notebooks" / "75_initial_national_report_builder.ipynb",
    root / "notebooks" / "76_gemini_report_appendix.ipynb",
    root / "notebooks" / "77_phase70_final_index.ipynb",
    root / "configs" / "phase70.yml",
    root / ".github" / "workflows" / "aq26_phase70_national_screening.yml",
]
missing = [str(p.relative_to(root)) for p in required if not p.exists()]
if missing:
    print("Missing files:")
    for m in missing:
        print(" -", m)
    sys.exit(1)
print("Phase 70 files present.")
