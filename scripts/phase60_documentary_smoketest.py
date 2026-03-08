from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
required = [
    root / "notebooks" / "61_report_catalog_ingest.ipynb",
    root / "notebooks" / "62_emissions_documentary_layer.ipynb",
    root / "notebooks" / "63_cems_noncompliance_layer.ipynb",
    root / "notebooks" / "64_documentary_site_year_linkage.ipynb",
    root / "notebooks" / "65_documentary_evidence_fusion.ipynb",
    root / "notebooks" / "66_documentary_adjudication_patch.ipynb",
    root / "notebooks" / "67_final_forensic_summary.ipynb",
    root / "configs" / "documentary_sources.yml",
    root / ".github" / "workflows" / "aq26_documentary_layer.yml",
]
missing = [str(p.relative_to(root)) for p in required if not p.exists()]
if missing:
    print("Missing files:")
    for m in missing:
        print(" -", m)
    sys.exit(1)
print("Documentary layer files present.")
