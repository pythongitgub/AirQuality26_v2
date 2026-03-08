from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
required = [
    root / "notebooks" / "50_evidence_inventory.ipynb",
    root / "notebooks" / "51_station_provenance_validation.ipynb",
    root / "notebooks" / "52_weather_validation_and_fallback_audit.ipynb",
    root / "notebooks" / "53_news_relevance_filtering.ipynb",
    root / "notebooks" / "54_evidence_cube_builder.ipynb",
    root / "notebooks" / "55_confounder_guardrails.ipynb",
    root / "notebooks" / "56_site_adjudication.ipynb",
    root / "notebooks" / "57_contradictions_red_team_audit.ipynb",
    root / "notebooks" / "58_gemini_evidence_led_adjudication.ipynb",
    root / "notebooks" / "59_verified_forensic_bundle_builder.ipynb",
    root / "notebooks" / "60_final_integrity_report.ipynb",
    root / "configs" / "phase50.yml",
    root / "configs" / "station_overrides.yml",
    root / "configs" / "news_filters.yml",
    root / "configs" / "evidence_thresholds.yml",
]
missing = [str(p.relative_to(root)) for p in required if not p.exists()]
if missing:
    print("Missing files:")
    for m in missing:
        print(" -", m)
    sys.exit(1)
print("Phase 50 files present.")
