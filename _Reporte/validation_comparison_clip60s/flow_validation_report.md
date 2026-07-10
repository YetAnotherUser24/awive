# Flow Validation Statistical Report

## Dataset Summary
- Samples: 36
- SENAMHI matched rows: 36
- Reporte matched rows: 36
- Timestamp range: 2026-02-01 15:00:16+00:00 to 2026-02-12 23:00:17+00:00

## SENAMHI Comparison
- MAE: 1.283
- RMSE: 1.778
- MAPE: 2.97%
- Bias: -1.094
- R²: 0.988
- Pearson r: 0.994 (p=4.503e-34)
- Spearman r: 0.992 (p=8.279e-32)
- NSE: 0.976
- Index of agreement: 0.994
- Min error: 0.076
- Max error: 4.720
- Within ±5%: 80.6%

## Reporte Comparison
- MAE: 1.253
- RMSE: 1.765
- MAPE: 2.87%
- Bias: -1.102
- R²: 0.988
- Pearson r: 0.994 (p=2.533e-34)
- Spearman r: 0.992 (p=4.270e-32)
- NSE: 0.977
- Index of agreement: 0.994
- Min error: 0.051
- Max error: 4.720
- Within ±5%: 83.3%

## Notes
- `recomputed_flow` is calculated from the stored velocimetry arrays.
- SENAMHI flow is filled from the nearest timestamp in `Senamhi_data.csv`.
- If SENAMHI level is unavailable in the source CSV, `current_depth_used` falls back to the existing level fields or the configured profile height.
- `Q_referencia` is used as the comparison reference from `Reporte.csv`.
