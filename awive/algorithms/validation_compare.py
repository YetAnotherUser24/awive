"""Validation and comparison pipeline for velocimetry flow results."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from awive.algorithms.water_flow import get_water_flow
from awive.config import Config


DEFAULT_VALIDATION_CSV = Path(
    "/root/awive/_Reporte/flow_validation_results_20260201_20260212_10_14_18_local.csv"
)
DEFAULT_SENAMHI_CSV = Path("/root/awive/_Reporte/Senamhi_data.csv")
DEFAULT_SENAMHI_LEVEL_CSV = Path("/root/awive/_Reporte/Senamhi_data_level.csv")
DEFAULT_REPORTE_CSV = Path("/root/awive/_Reporte/Reporte.csv")
DEFAULT_CONFIG_FP = Path("/root/.config/nflow/awive.yaml")
DEFAULT_OUTPUT_DIR = Path("/root/awive/_Reporte/validation_comparison")


@dataclass(slots=True)
class ComparisonMetrics:
    """Statistical summary for one comparison target."""

    sample_size: int
    mae: float
    rmse: float
    mape: float
    bias: float
    r2: float
    pearson_r: float
    pearson_p: float
    spearman_r: float
    spearman_p: float
    nash_sutcliffe_efficiency: float
    index_of_agreement: float
    min_error: float
    max_error: float
    within_5pct: float


def parse_velocimetry(value: Any) -> list[float]:
    """Parse a velocimetry column value into a list of floats."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, list):
        return [float(item) for item in value]
    if isinstance(value, np.ndarray):
        return [float(item) for item in value.tolist()]

    if isinstance(value, str):
        parsed = ast.literal_eval(value)
        if not isinstance(parsed, list):
            raise ValueError("Velocimetry value must be a list")
        return [float(item) for item in parsed]

    raise TypeError(f"Unsupported velocimetry value type: {type(value)!r}")


def _to_utc_datetime(series: pd.Series) -> pd.Series:
    """Convert a series to timezone-aware UTC datetimes."""
    return pd.to_datetime(series, utc=True, errors="coerce")


def load_validation_data(csv_path: Path) -> pd.DataFrame:
    """Load validation rows and normalize the velocimetry payload."""
    df = pd.read_csv(csv_path).copy()

    if "timestamp_dt" in df.columns:
        df["timestamp_dt"] = _to_utc_datetime(df["timestamp_dt"])
    elif "timestamp" in df.columns:
        timestamp_numeric = pd.to_numeric(df["timestamp"], errors="coerce")
        df["timestamp_dt"] = pd.to_datetime(
            timestamp_numeric, unit="ms", utc=True, errors="coerce"
        )

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")

    df["velocimetry_values"] = df["velocimetry"].apply(parse_velocimetry)
    df["resolution"] = pd.to_numeric(df["resolution"], errors="coerce")
    return df


def load_senamhi_data(csv_path: Path) -> pd.DataFrame:
    """Load SENAMHI flow and level data."""
    df = pd.read_csv(csv_path).copy()
    df["senamhi_timestamp_dt"] = _to_utc_datetime(df["timestamp"])
    df["senamhi_flow"] = pd.to_numeric(df["water_flow"], errors="coerce")
    level_column = next(
        (
            column
            for column in ("water_level", "senamhi_level", "level")
            if column in df.columns
        ),
        None,
    )
    if level_column is not None:
        df["senamhi_level"] = pd.to_numeric(df[level_column], errors="coerce")
    else:
        df["senamhi_level"] = np.nan
    return df[["senamhi_timestamp_dt", "senamhi_flow", "senamhi_level"]]


def load_reporte_data(csv_path: Path) -> pd.DataFrame:
    """Load the Reporte comparison data."""
    df = pd.read_csv(csv_path).copy()
    df["reporte_timestamp_dt"] = _to_utc_datetime(df["timestamp_utc"])
    df["Q_referencia"] = pd.to_numeric(df["Q_referencia"], errors="coerce")
    for column in ["Q_p05", "Q_p25", "Q_p75", "Q_p95", "Q_med"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def load_senamhi_level_data(csv_path: Path) -> pd.DataFrame:
    """Load SENAMHI level-only data."""
    df = pd.read_csv(csv_path).copy()
    df["level_timestamp_dt"] = _to_utc_datetime(df["timestamp"])
    df["level_water_level"] = pd.to_numeric(df["water_level"], errors="coerce")
    return df[["level_timestamp_dt", "level_water_level"]]


def enrich_senamhi_with_levels(
    senamhi_df: pd.DataFrame,
    level_df: pd.DataFrame,
    tolerance_minutes: int = 30,
) -> pd.DataFrame:
    """Attach level data to the SENAMHI flow dataframe using nearest timestamps."""
    base = senamhi_df.drop(columns=["senamhi_level"], errors="ignore").copy()
    merged = nearest_timestamp_merge(
        base,
        level_df,
        left_time_col="senamhi_timestamp_dt",
        right_time_col="level_timestamp_dt",
        tolerance_minutes=tolerance_minutes,
    )
    merged["senamhi_level"] = merged["level_water_level"]
    return merged.drop(columns=["level_timestamp_dt", "level_water_level"])


def nearest_timestamp_merge(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_time_col: str,
    right_time_col: str,
    tolerance_minutes: int = 30,
) -> pd.DataFrame:
    """Merge two tables on the nearest timestamp within a tolerance."""
    left_sorted = left.sort_values(left_time_col).copy()
    left_sorted["__merge_order"] = np.arange(len(left_sorted))

    right_sorted = right.sort_values(right_time_col).copy()

    merged = pd.merge_asof(
        left_sorted,
        right_sorted,
        left_on=left_time_col,
        right_on=right_time_col,
        direction="nearest",
        tolerance=pd.Timedelta(minutes=tolerance_minutes),
    )

    return merged.sort_values("__merge_order").drop(columns="__merge_order")


def calculate_metrics(
    predicted: pd.Series, actual: pd.Series
) -> ComparisonMetrics:
    """Compute standard validation statistics for two aligned series."""
    predicted_values = pd.to_numeric(predicted, errors="coerce").to_numpy()
    actual_values = pd.to_numeric(actual, errors="coerce").to_numpy()

    valid_mask = np.isfinite(predicted_values) & np.isfinite(actual_values)
    predicted_values = predicted_values[valid_mask]
    actual_values = actual_values[valid_mask]

    if len(predicted_values) == 0:
        raise ValueError("No aligned samples available for statistics")

    errors = predicted_values - actual_values
    abs_errors = np.abs(errors)
    nonzero_mask = actual_values != 0
    relative_errors = np.full_like(abs_errors, np.nan, dtype=float)
    relative_errors[nonzero_mask] = (
        abs_errors[nonzero_mask] / np.abs(actual_values[nonzero_mask]) * 100
    )

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(errors**2)))
    mape = float(np.nanmean(relative_errors))
    bias = float(np.mean(errors))

    if len(predicted_values) > 1:
        pearson_r, pearson_p = stats.pearsonr(predicted_values, actual_values)
        spearman_r, spearman_p = stats.spearmanr(
            predicted_values, actual_values
        )
        r2 = float(pearson_r**2)
    else:
        pearson_r = pearson_p = spearman_r = spearman_p = np.nan
        r2 = np.nan

    denominator = np.sum((actual_values - np.mean(actual_values)) ** 2)
    if denominator == 0:
        nash_sutcliffe_efficiency = np.nan
    else:
        nash_sutcliffe_efficiency = float(1 - np.sum(errors**2) / denominator)

    agreement_denominator = np.sum(
        (
            np.abs(predicted_values - np.mean(actual_values))
            + np.abs(actual_values - np.mean(actual_values))
        )
        ** 2
    )
    if agreement_denominator == 0:
        index_of_agreement = np.nan
    else:
        index_of_agreement = float(
            1
            - np.sum((predicted_values - actual_values) ** 2)
            / agreement_denominator
        )

    within_5pct = float(np.mean(relative_errors <= 5.0) * 100)

    return ComparisonMetrics(
        sample_size=len(predicted_values),
        mae=mae,
        rmse=rmse,
        mape=mape,
        bias=bias,
        r2=r2,
        pearson_r=float(pearson_r),
        pearson_p=float(pearson_p),
        spearman_r=float(spearman_r),
        spearman_p=float(spearman_p),
        nash_sutcliffe_efficiency=nash_sutcliffe_efficiency,
        index_of_agreement=index_of_agreement,
        min_error=float(np.min(abs_errors)),
        max_error=float(np.max(abs_errors)),
        within_5pct=within_5pct,
    )


def _depths_for_resolution(config: Config, resolution: float) -> np.ndarray:
    """Build the depth profile for a given resolution."""
    return config.water_flow.profile.depths_meters(
        config.preprocessing.ppm,
        resolution=resolution,
    )


def recompute_flow_for_row(
    row: pd.Series,
    config: Config,
    depth_cache: dict[float, np.ndarray],
) -> float:
    """Recompute a single water-flow value from velocimetry."""
    resolution = float(row.get("resolution", config.preprocessing.resolution))
    if resolution not in depth_cache:
        depth_cache[resolution] = _depths_for_resolution(config, resolution)

    velocities = np.asarray(row["velocimetry_values"], dtype=float)
    depths = depth_cache[resolution]
    current_depth = row.get("senamhi_level")
    if pd.isna(current_depth):
        current_depth = row.get("water_level_used")
    if pd.isna(current_depth):
        current_depth = config.water_flow.profile.height

    return float(
        get_water_flow(
            depths=depths,
            vels=velocities,
            old_depth=config.water_flow.profile.height,
            roughness=config.water_flow.roughness,
            current_depth=float(current_depth),
        )
    )


def recompute_flows(df: pd.DataFrame, config_path: Path) -> pd.DataFrame:
    """Add recomputed flow values to a validation dataframe."""
    config = Config.from_fp(config_path)
    depth_cache: dict[float, np.ndarray] = {}
    results = df.copy()

    results["recomputed_flow"] = results.apply(
        recompute_flow_for_row,
        axis=1,
        config=config,
        depth_cache=depth_cache,
    )

    results["current_depth_used"] = results.apply(
        lambda row: _resolve_current_depth(
            row, config.water_flow.profile.height
        ),
        axis=1,
    )

    # Keep legacy column populated so exported CSVs show the depth explicitly.
    if "water_level_used" in results.columns:
        results["water_level_used"] = results["water_level_used"].fillna(
            results["current_depth_used"]
        )
    else:
        results["water_level_used"] = results["current_depth_used"]

    results["recomputed_absolute_error"] = (
        results["recomputed_flow"] - results["senamhi_flow"]
    ).abs()
    results["recomputed_relative_error"] = np.where(
        results["senamhi_flow"].astype(float) != 0,
        results["recomputed_absolute_error"]
        / results["senamhi_flow"].abs()
        * 100,
        np.nan,
    )

    return results


def _resolve_current_depth(row: pd.Series, fallback_depth: float) -> float:
    """Resolve the depth to use for recomputation."""
    for column in ("senamhi_level", "water_level_used"):
        if column in row and pd.notna(row[column]):
            return float(row[column])
    return float(fallback_depth)


def attach_senamhi_data(
    validation_df: pd.DataFrame,
    senamhi_df: pd.DataFrame,
    tolerance_minutes: int = 30,
) -> pd.DataFrame:
    """Fill SENAMHI flow and level fields using nearest timestamp matches."""
    validation = validation_df.copy()
    placeholder_columns = [
        column
        for column in (
            "senamhi_flow",
            "senamhi_level",
            "flow_timestamp",
            "level_timestamp",
            "flow_time_diff_minutes",
            "level_time_diff_minutes",
        )
        if column in validation.columns
    ]
    if placeholder_columns:
        validation = validation.drop(columns=placeholder_columns)

    merged = nearest_timestamp_merge(
        validation,
        senamhi_df,
        left_time_col="timestamp_dt",
        right_time_col="senamhi_timestamp_dt",
        tolerance_minutes=tolerance_minutes,
    )

    merged["flow_timestamp"] = merged["senamhi_timestamp_dt"]
    merged["level_timestamp"] = merged["senamhi_timestamp_dt"]
    merged["flow_time_diff_minutes"] = (
        merged["timestamp_dt"] - merged["senamhi_timestamp_dt"]
    ).abs().dt.total_seconds() / 60
    merged["level_time_diff_minutes"] = merged["flow_time_diff_minutes"]
    return merged


def attach_reporte_data(
    validation_df: pd.DataFrame,
    reporte_df: pd.DataFrame,
    tolerance_minutes: int = 30,
) -> pd.DataFrame:
    """Attach Reporte.csv data using the nearest timestamp."""
    merged = nearest_timestamp_merge(
        validation_df,
        reporte_df,
        left_time_col="timestamp_dt",
        right_time_col="reporte_timestamp_dt",
        tolerance_minutes=tolerance_minutes,
    )

    merged["reporte_time_diff_minutes"] = (
        merged["timestamp_dt"] - merged["reporte_timestamp_dt"]
    ).abs().dt.total_seconds() / 60
    merged["reporte_absolute_error"] = (
        merged["recomputed_flow"] - merged["Q_referencia"]
    ).abs()
    merged["reporte_relative_error"] = np.where(
        merged["Q_referencia"].astype(float) != 0,
        merged["reporte_absolute_error"] / merged["Q_referencia"].abs() * 100,
        np.nan,
    )
    return merged


def build_statistics_report(
    df: pd.DataFrame,
    senamhi_metrics: ComparisonMetrics,
    reporte_metrics: ComparisonMetrics,
) -> str:
    """Create a markdown statistical report."""
    matched_senamhi = int(df["senamhi_flow"].notna().sum())
    matched_reporte = int(df["Q_referencia"].notna().sum())

    return f"""# Flow Validation Statistical Report

## Dataset Summary
- Samples: {len(df)}
- SENAMHI matched rows: {matched_senamhi}
- Reporte matched rows: {matched_reporte}
- Timestamp range: {df["timestamp_dt"].min()} to {df["timestamp_dt"].max()}

## SENAMHI Comparison
- MAE: {senamhi_metrics.mae:.3f}
- RMSE: {senamhi_metrics.rmse:.3f}
- MAPE: {senamhi_metrics.mape:.2f}%
- Bias: {senamhi_metrics.bias:.3f}
- R²: {senamhi_metrics.r2:.3f}
- Pearson r: {senamhi_metrics.pearson_r:.3f} (p={senamhi_metrics.pearson_p:.3e})
- Spearman r: {senamhi_metrics.spearman_r:.3f} (p={senamhi_metrics.spearman_p:.3e})
- NSE: {senamhi_metrics.nash_sutcliffe_efficiency:.3f}
- Index of agreement: {senamhi_metrics.index_of_agreement:.3f}
- Min error: {senamhi_metrics.min_error:.3f}
- Max error: {senamhi_metrics.max_error:.3f}
- Within ±5%: {senamhi_metrics.within_5pct:.1f}%

## Reporte Comparison
- MAE: {reporte_metrics.mae:.3f}
- RMSE: {reporte_metrics.rmse:.3f}
- MAPE: {reporte_metrics.mape:.2f}%
- Bias: {reporte_metrics.bias:.3f}
- R²: {reporte_metrics.r2:.3f}
- Pearson r: {reporte_metrics.pearson_r:.3f} (p={reporte_metrics.pearson_p:.3e})
- Spearman r: {reporte_metrics.spearman_r:.3f} (p={reporte_metrics.spearman_p:.3e})
- NSE: {reporte_metrics.nash_sutcliffe_efficiency:.3f}
- Index of agreement: {reporte_metrics.index_of_agreement:.3f}
- Min error: {reporte_metrics.min_error:.3f}
- Max error: {reporte_metrics.max_error:.3f}
- Within ±5%: {reporte_metrics.within_5pct:.1f}%

## Notes
- `recomputed_flow` is calculated from the stored velocimetry arrays.
- SENAMHI flow is filled from the nearest timestamp in `Senamhi_data.csv`.
- If SENAMHI level is unavailable in the source CSV, `current_depth_used` falls back to the existing level fields or the configured profile height.
- `Q_referencia` is used as the comparison reference from `Reporte.csv`.
"""


def run_pipeline(
    validation_csv: Path = DEFAULT_VALIDATION_CSV,
    senamhi_csv: Path = DEFAULT_SENAMHI_CSV,
    senamhi_level_csv: Path | None = DEFAULT_SENAMHI_LEVEL_CSV,
    reporte_csv: Path = DEFAULT_REPORTE_CSV,
    config_fp: Path = DEFAULT_CONFIG_FP,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    tolerance_minutes: int = 30,
) -> tuple[pd.DataFrame, dict[str, ComparisonMetrics], Path, Path]:
    """Run the full validation and comparison pipeline."""
    output_dir.mkdir(parents=True, exist_ok=True)

    validation_df = load_validation_data(validation_csv)
    senamhi_df = load_senamhi_data(senamhi_csv)
    if senamhi_level_csv is not None and senamhi_level_csv.exists():
        level_df = load_senamhi_level_data(senamhi_level_csv)
        senamhi_df = enrich_senamhi_with_levels(
            senamhi_df,
            level_df,
            tolerance_minutes=tolerance_minutes,
        )
    reporte_df = load_reporte_data(reporte_csv)

    merged = attach_senamhi_data(
        validation_df,
        senamhi_df,
        tolerance_minutes=tolerance_minutes,
    )
    merged = recompute_flows(merged, config_fp)
    merged = attach_reporte_data(
        merged,
        reporte_df,
        tolerance_minutes=tolerance_minutes,
    )

    senamhi_metrics = calculate_metrics(
        merged["recomputed_flow"], merged["senamhi_flow"]
    )
    reporte_metrics = calculate_metrics(
        merged["recomputed_flow"], merged["Q_referencia"]
    )

    merged_csv = output_dir / "flow_validation_comparison.csv"
    merged.to_csv(merged_csv, index=False)

    report_text = build_statistics_report(
        merged,
        senamhi_metrics,
        reporte_metrics,
    )
    report_path = output_dir / "flow_validation_report.md"
    report_path.write_text(report_text, encoding="utf-8")

    return (
        merged,
        {
            "senamhi": senamhi_metrics,
            "reporte": reporte_metrics,
        },
        merged_csv,
        report_path,
    )


def _metrics_to_dict(metrics: ComparisonMetrics) -> dict[str, float]:
    return {
        "sample_size": metrics.sample_size,
        "mae": metrics.mae,
        "rmse": metrics.rmse,
        "mape": metrics.mape,
        "bias": metrics.bias,
        "r2": metrics.r2,
        "pearson_r": metrics.pearson_r,
        "pearson_p": metrics.pearson_p,
        "spearman_r": metrics.spearman_r,
        "spearman_p": metrics.spearman_p,
        "nash_sutcliffe_efficiency": metrics.nash_sutcliffe_efficiency,
        "index_of_agreement": metrics.index_of_agreement,
        "min_error": metrics.min_error,
        "max_error": metrics.max_error,
        "within_5pct": metrics.within_5pct,
    }


def main() -> None:
    """Run the comparison pipeline from the command line."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Process validation results using SENAMHI and Reporte data"
    )
    parser.add_argument(
        "--validation-csv",
        type=Path,
        default=DEFAULT_VALIDATION_CSV,
        help="Input validation CSV containing velocimetry results",
    )
    parser.add_argument(
        "--senamhi-csv",
        type=Path,
        default=DEFAULT_SENAMHI_CSV,
        help="SENAMHI flow and level CSV",
    )
    parser.add_argument(
        "--senamhi-level-csv",
        type=Path,
        default=DEFAULT_SENAMHI_LEVEL_CSV,
        help="Optional SENAMHI level-only CSV",
    )
    parser.add_argument(
        "--reporte-csv",
        type=Path,
        default=DEFAULT_REPORTE_CSV,
        help="Reporte.csv comparison file",
    )
    parser.add_argument(
        "--config-fp",
        type=Path,
        default=DEFAULT_CONFIG_FP,
        help="AWIVE config file used for flow recomputation",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where outputs will be written",
    )
    parser.add_argument(
        "--tolerance-minutes",
        type=int,
        default=30,
        help="Timestamp matching tolerance in minutes",
    )
    args = parser.parse_args()

    merged, metrics, merged_csv, report_path = run_pipeline(
        validation_csv=args.validation_csv,
        senamhi_csv=args.senamhi_csv,
        senamhi_level_csv=args.senamhi_level_csv,
        reporte_csv=args.reporte_csv,
        config_fp=args.config_fp,
        output_dir=args.output_dir,
        tolerance_minutes=args.tolerance_minutes,
    )

    summary = {
        "merged_csv": str(merged_csv),
        "report_path": str(report_path),
        "rows": len(merged),
        "senamhi_metrics": _metrics_to_dict(metrics["senamhi"]),
        "reporte_metrics": _metrics_to_dict(metrics["reporte"]),
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
