# Plan: Create and Organize `dev` Branch Integrating Cross-Branch Assets

Set up a unified, production-ready development branch (`dev`) that consolidates the active multi-resolution work with high-value utilities, validation tools, and datasets created across other branches (`formula_check`, `fix-awive-process`, `water-flow-analysis`). This creates a clean, organized, and test-ready foundation for all feature development.

---

## User Review Required

> [!IMPORTANT]
> - **Branch Base**: `dev` will branch from `feat/multi-resolution-otv` (commit `06cf02a`), preserving the verified calibration scaling bugfix, `Config.scale_for_resolution()`, and OTV multi-resolution tools.
> - **Cross-Branch Assets Included**:
>   1. **`awive/algorithms/validation_compare.py`** & tests (from `formula_check`): The core validation and statistical metrics comparison suite ($R^2$, NSE, MAE, RMSE, PBIAS, etc.).
>   2. **`awive/utils/ppm_calculator.py`** (from `fix-awive-process`): Automatic pixels-per-meter (PPM) calculator and canvas dimension estimator from GCP coordinates.
>   3. **`experiments/water_flow_statistical_analysis.py`** (from `water-flow-analysis`): Statistical analysis for cross-sectional velocimetry profiles.
>   4. **`_Reporte/` Benchmark Datasets** (from `formula_check`): SENAMHI ground-truth reference table (`Reporte.csv`), radar level telemetry (`Senamhi_data_level.csv`), and the 36 processed validation points.
> - **Root Cleanup**: All loose scratch files (`*.jpg`, `*.png`, plan and transcript markdowns) will be moved into structured subdirectories (`docs/`, `tmp/debug/`), leaving the project root completely clean.

---

## Cross-Branch Asset Inventory & Decisions

| Source Branch | Asset / File | Destination on `dev` | Purpose & Ladder Decision |
| :--- | :--- | :--- | :--- |
| **`feat/multi-resolution-otv`** *(current)* | `awive/config.py` & `awive.yaml` | `awive/` | Retains `depths_meters` fix and `scale_for_resolution` helper. |
| **`feat/multi-resolution-otv`** *(current)* | `experiments/resolution_study.py`<br>`experiments/realtime_otv_viewer.py` | `experiments/` | Retains multi-resolution benchmark & real-time visualizer suite. |
| **`formula_check`** | `awive/algorithms/validation_compare.py`<br>`awive/tests/test_algorithms/test_validation_compare.py` | `awive/algorithms/`<br>`awive/tests/test_algorithms/` | **Rung 2**: Reuses tested comparison logic and error metric computations ($R^2$, NSE, MAE, RMSE, PBIAS). |
| **`formula_check`** | `_Reporte/Reporte.csv`<br>`_Reporte/Senamhi_data_level.csv`<br>`_Reporte/flow_validation_results_...clip60s.csv` | `_Reporte/` | **Rung 4**: Reuses ground-truth SENAMHI telemetry and 36 baseline observation runs. |
| **`fix-awive-process`** | `awive/utils/ppm_calculator.py` | `awive/utils/` | **Rung 2**: Reuses automatic GCP-based PPM calculation and dimension estimation. |
| **`fix-awive-process`** | `SCRIPTS_GUIDE.md` | `docs/guides/SCRIPTS_GUIDE.md` | **Rung 4**: Preserves operational documentation for OTV debugging. |
| **`water-flow-analysis`** | `experiments/water_flow_statistical_analysis.py` | `experiments/` | **Rung 2**: Reuses cross-sectional statistical flow profiling script. |

---

## Proposed Changes

### 1. Branch Management

#### [NEW BRANCH] `dev`
- Create and checkout `dev` branching from `feat/multi-resolution-otv`.

---

### 2. Core Library (`awive/`)

#### [NEW] [awive/utils/__init__.py](file:///root/awive/awive/utils/__init__.py)
#### [NEW] [awive/utils/ppm_calculator.py](file:///root/awive/awive/utils/ppm_calculator.py)
- Extracted from `fix-awive-process`. Provides `calculate_ppm_from_gcps()` and `estimate_output_dimensions()`.

#### [NEW] [awive/algorithms/validation_compare.py](file:///root/awive/awive/algorithms/validation_compare.py)
- Extracted from `formula_check`. Refined to support pure NumPy calculations (with Pandas fallback) so all metrics run without extra heavy dependencies.

---

### 3. Experiments & Tooling (`experiments/`)

#### [NEW] [experiments/water_flow_statistical_analysis.py](file:///root/awive/experiments/water_flow_statistical_analysis.py)
- Extracted from `water-flow-analysis`. Standalone script for statistical velocimetry analysis.

#### [MODIFY] [experiments/realtime_otv_viewer.py](file:///root/awive/experiments/realtime_otv_viewer.py)
- Auto-format code via `ruff format`.

---

### 4. Tests (`awive/tests/`)

#### [NEW] [awive/tests/test_algorithms/test_validation_compare.py](file:///root/awive/awive/tests/test_algorithms/test_validation_compare.py)
- Automated unit test suite verifying $R^2$, NSE, MAE, and RMSE computations.

#### [NEW] [awive/tests/test_utils/test_ppm_calculator.py](file:///root/awive/awive/tests/test_utils/test_ppm_calculator.py)
- Unit tests verifying automatic PPM calculation from GCP pairs.

---

### 5. Documentation & Workspace Organization (`docs/` & `_Reporte/`)

#### [RESTORE] `_Reporte/Reporte.csv`, `Senamhi_data_level.csv`, `flow_validation_results_20260201_20260212_10_14_18_local_clip60s.csv`
- Checked out from `formula_check` into `_Reporte/`.

#### [MOVE]
- `IMPLEMENTATION_PLAN_multi_resolution_benchmark.md` ➔ `docs/plans/IMPLEMENTATION_PLAN_multi_resolution_benchmark.md`
- `RECOVERED_CHAT_resolution_study_a0df501d.md` ➔ `docs/recovered_chats/RECOVERED_CHAT_resolution_study_a0df501d.md`
- `SCRIPTS_GUIDE.md` (from `fix-awive-process`) ➔ `docs/guides/SCRIPTS_GUIDE.md`

#### [CLEANUP]
- Move untracked loose images in root (`video_rpi_zero_*.jpg`, `tmp.jpg`, `validation.png`, etc.) to gitignored `tmp/debug/`.

---

## Verification Plan

### Automated Tests
```bash
# 1. Verify branch state
git branch --show-current
git status -s

# 2. Run full test suite (including new validation and ppm tests)
uv run pytest awive/tests

# 3. Verify code style & formatting
uv run ruff check .
uv run ruff format --check .

# 4. Smoke test the imported tools
uv run python -c "from awive.utils.ppm_calculator import calculate_ppm_from_gcps; print('PPM Calculator OK')"
uv run python -c "from awive.algorithms.validation_compare import calculate_metrics; print('Validation Compare OK')"
```

### Manual Verification
- Verify `git status` shows a completely clean working directory on `dev`.
- Verify that `experiments/resolution_study.py` runs seamlessly against `video_rimac.mp4`.
