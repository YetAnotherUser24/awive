# Flow Validation Statistical Report

## Dataset Summary
- Samples: 36
- SENAMHI matched rows: 36
- Reporte matched rows: 36
- Timestamp range: 2026-02-01 15:00:16+00:00 to 2026-02-12 23:00:17+00:00

## SENAMHI Comparison
- MAE: 1.299
- RMSE: 1.777
- MAPE: 3.02%
- Bias: -1.136
- R²: 0.988
- Pearson r: 0.994 (p=1.499e-34)
- Spearman r: 0.991 (p=3.693e-31)
- NSE: 0.976
- Index of agreement: 0.994
- Min error: 0.033
- Max error: 4.339
- Within ±5%: 77.8%

## Reporte Comparison
- MAE: 1.274
- RMSE: 1.765
- MAPE: 2.94%
- Bias: -1.144
- R²: 0.989
- Pearson r: 0.994 (p=8.256e-35)
- Spearman r: 0.991 (p=2.018e-31)
- NSE: 0.977
- Index of agreement: 0.994
- Min error: 0.033
- Max error: 4.339
- Within ±5%: 80.6%

## Notes
- `recomputed_flow` is calculated from the stored velocimetry arrays.
- SENAMHI flow is filled from the nearest timestamp in `Senamhi_data.csv`.
- If SENAMHI level is unavailable in the source CSV, `current_depth_used` falls back to the existing level fields or the configured profile height.
- `Q_referencia` is used as the comparison reference from `Reporte.csv`.
