from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
required = [
    root / "notebooks" / "80_master_permit_registry.ipynb",
    root / "notebooks" / "81_historical_emissions_warehouse.ipynb",
    root / "notebooks" / "82_documentary_noncompliance_warehouse.ipynb",
    root / "notebooks" / "83_historical_site_year_fusion.ipynb",
    root / "notebooks" / "84_colab_satellite_batch_spec_builder.ipynb",
    root / "notebooks" / "85_national_priority_matrix.ipynb",
    root / "notebooks" / "86_forensic_dossier_index.ipynb",
    root / "notebooks" / "87_phase80_summary.ipynb",
    root / "configs" / "phase80.yml",
    root / "configs" / "permit_registry.yml",
    root / "configs" / "colab_satellite.yml",
    root / ".github" / "workflows" / "aq26_phase80_historical.yml",
]
missing = [str(p.relative_to(root)) for p in required if not p.exists()]
if missing:
    print("Missing files:")
    for m in missing:
        print(" -", m)
    sys.exit(1)
print("Phase 80 files present.")
