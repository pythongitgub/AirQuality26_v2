# AirQuality26_v2 Project Analysis (April 30, 2026)

## Executive Summary
The project already has strong breadth: a staged notebook workflow spanning setup, evidence acquisition, fusion, reporting, national screening, historical layers, and geospatial integration. Immediate leverage now comes from hardening reproducibility and reducing notebook execution risk in CI, then strengthening data governance and scoring validation.

## What is working well

1. **Clear phased architecture and naming discipline.**
   - Notebook and config naming communicates progression (e.g., 40/50/70/80/88-94/95+ style milestones) and supports incremental delivery.
2. **Operational smoke checks exist for major phases.**
   - Lightweight scripts verify expected assets exist before expensive runs.
3. **Multiple workflow entry points are already present.**
   - You have both full-pipeline and phase-specific workflows, which is excellent for cost/time control.
4. **Integrity mindset is documented.**
   - Runbook references per-step manifests and SHA256 hashing for provenance.

## Observations and risks

### 1) Notebook-heavy execution remains your biggest scaling risk
You currently have a very notebook-centric stack and a large notebook count. This is productive early but tends to degrade maintainability as logic complexity rises.

**Risk pattern:** hidden state, non-deterministic cell order, and merge conflicts in `.ipynb` JSON.

### 2) Numbering and phase-map drift can confuse onboarding
The notebook set spans 1 to 100 but includes deliberate gaps. That is okay technically, but without an explicit index map, new contributors can misread which steps are active, deprecated, or optional.

### 3) Secret/provider surface area is broad
The smoke test checks many provider keys and mixed optional/required semantics. This is useful, but it increases setup burden and possible brittle dependencies when providers throttle/change.

### 4) Data contracts appear implicit rather than enforced centrally
The repository has many configs and downstream notebooks that likely assume schema shapes. If these assumptions are not codified (column/type validations at boundaries), pipeline regressions can hide until late-stage notebooks.

### 5) Evidence scoring and adjudication layers need calibration governance
You have advanced evidence fusion/adjudication notebooks, which is a strategic strength, but these systems benefit from explicit calibration sets and periodic bias/regression checks.

## Priority recommendations (next 30-60 days)

### P0 — Reproducibility hardening
1. Add a **single machine-readable pipeline index** (`docs/pipeline_index.yaml`) listing each notebook, phase, required inputs, outputs, and status (`active/experimental/deprecated`).
2. Introduce **schema gates** at each phase boundary (Pandera/Great Expectations or lightweight custom checks) to fail fast on contract breaks.
3. Expand smoke tests from file-presence only to **minimal semantic checks** (row count > 0, required columns, key uniqueness where expected).

### P1 — Notebook-to-library extraction
1. Extract high-reuse logic (ranking, fusion joins, scoring transforms, provenance hashing) into `src/` Python modules.
2. Keep notebooks as orchestration/report surfaces calling tested functions.
3. Add unit tests for extracted functions and wire into CI.

### P1 — Execution observability
1. Standardize per-phase runtime metadata: start/end UTC, input fingerprints, output fingerprints, record counts, warning counts.
2. Emit one consolidated `run_report.json` artifact per workflow run.

### P2 — Decision-quality upgrades
1. Create a small **golden adjudication set** (manually reviewed cases) and score model/rule output against it each release.
2. Add sensitivity analysis around evidence thresholds in `configs/evidence_thresholds.yml`.
3. Track changes in site priority rankings across config revisions (rank drift dashboard/report).

## Suggested concrete backlog

1. `docs/pipeline_index.yaml` + `scripts/validate_pipeline_index.py`
2. `scripts/check_phase_outputs.py` for boundary schema checks
3. `src/aq26/scoring.py` + tests for deterministic scoring behavior
4. `src/aq26/provenance.py` for manifest/hash utilities reused by notebooks
5. `docs/OPERATIONS.md` for provider quotas, retry policy, and fallback order

## Recommended success metrics

- % of phases with enforced input/output schemas
- % of notebook logic moved into tested modules
- Median workflow runtime by phase and p95 failure rate
- Number of non-deterministic rerun diffs for same inputs
- Rank stability of top-N national priority sites across releases

## Bottom line
You are past the “proof of concept” stage and entering an engineering-hardening stage. Focus next on contracts, deterministic execution, and extraction of reusable logic from notebooks. That will make your strong analytical architecture durable, auditable, and faster to evolve.
