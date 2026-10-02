# Multi-Resolution SENAMHI Benchmark Pipeline (10 Representative Flow Points)

This plan implements the multi-resolution benchmark described at the end of the previous session (message #9). We will evaluate the Optical Tracking Velocimetry (OTV) algorithm across multiple resolutions (**4K**, **1080p**, **720p tuned**, and **480p tuned**) against the official SENAMHI hydrological reference and SENAMHI LSPIV report across **10 representative points** covering low, medium, and peak flood regimes.

---

## User Review Required

> [!IMPORTANT]
> - **Video Downloads**: The 10 sample 60-second raw videos will be downloaded directly via Google Drive API using existing [`credentials.json`](file:///root/awive/credentials.json). Total download size is approximately **~500 MB to 1 GB**, saved in `experiments/sample_videos/`.
> - **Resolution Threshold Tuning**: In accordance with the previous session's findings, 720p will be tested both with the uncalibrated default (`final_min_distance = 8 px`) and the optimal tuned threshold (`final_min_distance = 3 px`), and 480p with `final_min_distance = 2 px` to evaluate whether resolution-adaptive thresholding eliminates low-flow bias across varying water levels.

---

## The 10 Representative Hydrological Points

Selected from the 36 observation points in `_Reporte/Reporte.csv` to span the complete hydrograph dynamic range ($30\text{--}63\text{ m³/s}$):

| Point | Date & Local Hour | UTC Timestamp | $Q_{\text{referencia}}$ (m³/s) | Hydrological Regime | Google Drive Video ID |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | 2026-02-02 10:00 | 2026-02-02 15:00:17 | **62.62** | Peak Flood (Maximum) | `1p5098AJpcwbDUYdnOxyPqkvUoecxw3Km` |
| **2** | 2026-02-03 14:00 | 2026-02-03 19:00:17 | **59.63** | Peak Flood | `1dvQeFxORCrq1wW7QRjhHx-f81ZUM_BLp` |
| **3** | 2026-02-04 14:00 | 2026-02-04 19:00:16 | **56.04** | High Flow | `1BZdDVRGsgqirCS7iJFDUm28M_Gt6iryu` |
| **4** | 2026-02-05 18:00 | 2026-02-05 23:00:16 | **46.20** | Medium-High Flow | `1jgENkCJQTb5GvtrgP5tdUtnPcMCj5HUj` |
| **5** | 2026-02-01 14:00 | 2026-02-01 19:00:17 | **42.87** | Medium Flow | `1QE-D1iM_yxDwWnJpqvRGACmZHwv7Vezr` |
| **6** | 2026-02-01 10:00 | 2026-02-01 15:00:16 | **39.88** | Medium Flow | `1KolOFV0wcm1eJ8wkXkgbdLkNT07b5sNr` |
| **7** | 2026-02-05 10:00 | 2026-02-05 15:00:17 | **37.19** | Recession Flow | `116_vMc1N9kGHv2ukpQOzrCy_8MRur7Zg` |
| **8** | 2026-02-07 14:00 | 2026-02-07 19:00:17 | **32.70** | Low Base Flow | `16_BZLJv2-xb2TyIZ-Z6NpP5PLuKmUgE7` |
| **9** | 2026-02-09 10:00 | 2026-02-09 15:00:16 | **31.50** | Low Base Flow | `1atmk-h-4GL1psGytEB6r1hqt_L3kqB6i` |
| **10**| 2026-02-12 14:00 | 2026-02-12 19:00:17 | **30.30** | Base Flow (Minimum) | `1ELk1hKP3MlXsdWaCCS-QbWdTkpziWX6-` |

---

## 7-Rung Efficiency Ladder & Decisions

- **Step 1 (Extract Reference Data)**: **Rung 4** (Native Git command to checkout ground truth CSV files from branch `formula_check` into `_Reporte/` with zero redundant re-creation).
- **Step 2 (Robust Google Drive Downloader)**: **Rung 2/5** (Reuses `google.oauth2.service_account` credentials and plain `requests` streaming chunked download, bypassing broken `oauth2client` / `pyOpenSSL` dependencies).
- **Step 3 (Multi-Resolution Batch OTV Runner)**: **Rung 2** (Reuses `Config.scale_for_resolution()` and existing OTV pipeline in a lean batch script [experiments/multi_res_benchmark.py](file:///root/awive/experiments/multi_res_benchmark.py)).
- **Step 4 (Metrics & Comparative Visualization)**: **Rung 2/5** (Reuses statistical formulas from `validation_compare.py`: $R^2$, NSE, MAE, RMSE, PBIAS; plots multi-resolution hydrograph and scatter plots).

---

## Proposed Changes

### Data Layer

#### [RESTORE] `_Reporte/Reporte.csv`, `Senamhi_data_level.csv`, `flow_validation_results_20260201_20260212_10_14_18_local_clip60s.csv`
- Restore official reference CSV files from branch `formula_check` into `_Reporte/`.

---

### Execution & Downloader Tools

#### [NEW] [experiments/download_sample_videos.py](file:///root/awive/experiments/download_sample_videos.py)
- Download the 10 selected videos using service account credentials and stream to `experiments/sample_videos/<timestamp>_<video_id>.mp4`.
- Skip download if file already exists with non-zero size.

#### [NEW] [experiments/multi_res_benchmark.py](file:///root/awive/experiments/multi_res_benchmark.py)
- Automated runner that loops over the 10 downloaded videos:
  1. Pulls the exact water level from `_Reporte/Senamhi_data_level.csv` for that timestamp.
  2. Runs OTV at:
     - **4K** ($d_{\min} = 8\text{ px}$)
     - **1080p** ($d_{\min} = 8\text{ px}$)
     - **720p (default)** ($d_{\min} = 8\text{ px}$)
     - **720p (tuned)** ($d_{\min} = 3\text{ px}$)
     - **480p (tuned)** ($d_{\min} = 2\text{ px}$)
  3. Computes cross-sectional discharge $Q$ via `get_water_flow`.
  4. Saves complete table of results to `_Reporte/multi_resolution_benchmark_10pts.csv`.

---

### Analysis & Visualization

#### [NEW] [experiments/plot_multi_res_benchmark.py](file:///root/awive/experiments/plot_multi_res_benchmark.py)
- Computes statistical metrics ($R^2$, NSE, MAE, RMSE, PBIAS) for each resolution vs SENAMHI reference and SENAMHI LSPIV.
- Generates a publication-quality comparative figure saved to `_Reporte/multi_resolution_senamhi_comparison.png`:
  - **Panel 1**: Hydrograph timeseries across the 10 points (SENAMHI Reference, SENAMHI LSPIV, 4K, 1080p, 720p tuned, 480p tuned).
  - **Panel 2**: Parity scatter plot with 1:1 identity line and $R^2$ values.
  - **Panel 3**: Bar chart of MAE and RMSE across resolutions.
  - **Panel 4**: Mean processing FPS comparison.

---

## Verification Plan

### Automated Verification
```bash
# 1. Verify reference data checkout
ls -lh _Reporte/Reporte.csv _Reporte/Senamhi_data_level.csv

# 2. Download sample videos (or test on first point)
uv run python experiments/download_sample_videos.py --count 10

# 3. Run multi-resolution batch evaluation
uv run python experiments/multi_res_benchmark.py --frames 90

# 4. Generate comparison plots and summary table
uv run python experiments/plot_multi_res_benchmark.py
```

### Manual Verification
- Verify that the hydrograph curve closely tracks the reference $Q_{\text{referencia}}$ across all 10 points.
- Confirm that 720p tuned ($3\text{ px}$) achieves $R^2 > 0.98$ and $\text{NSE} > 0.95$ comparable to native 4K.
