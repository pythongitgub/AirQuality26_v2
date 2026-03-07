# Phase 40 merge notes

Add these files to the existing repository. Do not delete the existing notebooks.

Recommended upload locations:

- `notebooks/40_target_control_registry.ipynb`
- `notebooks/41_weather_ground_news_cross_reference.ipynb`
- `notebooks/42_multi_site_comparison.ipynb`
- `notebooks/43_forensic_window_analysis.ipynb`
- `notebooks/44_gemini_structured_forensic_analysis.ipynb`
- `notebooks/45_report_packaging_phase2.ipynb`
- `configs/targets_controls.yml`
- `configs/run_phase40_patch_example.yml`
- `src/aq26/*.py`

Then:
1. add `google-genai` to your main `requirements.txt`
2. optionally merge `configs/run_phase40_patch_example.yml` into `configs/run.yml`
3. run notebooks `40` through `45` in order
