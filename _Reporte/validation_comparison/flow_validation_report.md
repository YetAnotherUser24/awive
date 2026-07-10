# Flow Validation Statistical Report

## Dataset Summary
- Samples: 36
- SENAMHI matched rows: 36
- Reporte matched rows: 36
- Timestamp range: 2026-02-01 15:00:16+00:00 to 2026-02-12 23:00:17+00:00

## SENAMHI Comparison
- MAE: 4.036
- RMSE: 4.419
- MAPE: 9.66%
- Bias: -4.036
- R²: 0.989
- Pearson r: 0.995 (p=3.607e-35)
- Spearman r: 0.992 (p=8.279e-32)
- NSE: 0.854
- Index of agreement: 0.960
- Min error: 0.800
- Max error: 8.214
- Within ±5%: 2.8%

## Reporte Comparison
- MAE: 4.044
- RMSE: 4.419
- MAPE: 9.69%
- Bias: -4.044
- R²: 0.990
- Pearson r: 0.995 (p=1.946e-35)
- Spearman r: 0.992 (p=4.270e-32)
- NSE: 0.854
- Index of agreement: 0.960
- Min error: 1.085
- Max error: 8.214
- Within ±5%: 2.8%

## Notes
- `recomputed_flow` is calculated from the stored velocimetry arrays.
- SENAMHI flow is filled from the nearest timestamp in `Senamhi_data.csv`.
- If SENAMHI level is unavailable in the source CSV, `current_depth_used` falls back to the existing level fields or the configured profile height.
- `Q_referencia` is used as the comparison reference from `Reporte.csv`.
