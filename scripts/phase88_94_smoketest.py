from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
required = [
    root / "notebooks" / "88_site_coordinate_registry.ipynb",
    root / "notebooks" / "89_ground_monitor_radius_linkage.ipynb",
    root / "notebooks" / "90_meteorology_radius_linkage.ipynb",
    root / "notebooks" / "91_news_radius_context.ipynb",
    root / "notebooks" / "92_population_settlement_linkage.ipynb",
    root / "notebooks" / "93_health_context_layer.ipynb",
    root / "notebooks" / "94_site_geospatial_fusion.ipynb",
    root / "configs" / "phase88_94_geospatial.yml",
    root / "configs" / "site_geospatial_registry.yml",
    root / ".github" / "workflows" / "aq26_phase88_94_geospatial.yml",
]
missing = [str(p.relative_to(root)) for p in required if not p.exists()]
if missing:
    print("Missing files:")
    for m in missing:
        print(" -", m)
    sys.exit(1)
print("Phase 88–94 files present.")
