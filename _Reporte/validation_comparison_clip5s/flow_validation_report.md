# Flow Validation Statistical Report

## Dataset Summary
- Samples: 36
- SENAMHI matched rows: 36
- Reporte matched rows: 36
- Timestamp range: 2026-02-01 15:00:16+00:00 to 2026-02-12 23:00:17+00:00

## SENAMHI Comparison
- MAE: 1.347
- RMSE: 1.828
- MAPE: 3.14%
- Bias: -1.187
- R²: 0.987
- Pearson r: 0.994 (p=6.984e-34)
- Spearman r: 0.990 (p=2.786e-30)
- NSE: 0.975
- Index of agreement: 0.993
- Min error: 0.034
- Max error: 4.407
- Within ±5%: 80.6%

## Reporte Comparison
- MAE: 1.336
- RMSE: 1.821
- MAPE: 3.11%
- Bias: -1.195
- R²: 0.988
- Pearson r: 0.994 (p=4.800e-34)
- Spearman r: 0.989 (p=7.051e-30)
- NSE: 0.975
- Index of agreement: 0.994
- Min error: 0.074
- Max error: 4.407
- Within ±5%: 80.6%

## Notes
- `recomputed_flow` is calculated from the stored velocimetry arrays.
- SENAMHI flow is filled from the nearest timestamp in `Senamhi_data.csv`.
- If SENAMHI level is unavailable in the source CSV, `current_depth_used` falls back to the existing level fields or the configured profile height.
- `Q_referencia` is used as the comparison reference from `Reporte.csv`.
