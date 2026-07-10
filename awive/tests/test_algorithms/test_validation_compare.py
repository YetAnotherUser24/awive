import numpy as np
import pandas as pd
import pytest

from awive.algorithms.validation_compare import (
    ComparisonMetrics,
    attach_reporte_data,
    attach_senamhi_data,
    build_statistics_report,
    calculate_metrics,
    nearest_timestamp_merge,
    parse_velocimetry,
    recompute_flow_for_row,
)


def test_parse_velocimetry_handles_strings_and_lists() -> None:
    assert parse_velocimetry("[1, 2.5, 3]") == [1.0, 2.5, 3.0]
    assert parse_velocimetry([1, 2, 3]) == [1.0, 2.0, 3.0]


def test_nearest_timestamp_merge_with_tolerance() -> None:
    left = pd.DataFrame(
        {
            "timestamp_dt": pd.to_datetime(
                ["2026-02-01 15:00:00+00:00", "2026-02-01 19:00:00+00:00"],
                utc=True,
            ),
            "value": [1, 2],
        }
    )
    right = pd.DataFrame(
        {
            "reference_dt": pd.to_datetime(
                ["2026-02-01 14:58:00+00:00", "2026-02-01 19:10:00+00:00"],
                utc=True,
            ),
            "reference_value": [10, 20],
        }
    )

    merged = nearest_timestamp_merge(
        left,
        right,
        left_time_col="timestamp_dt",
        right_time_col="reference_dt",
        tolerance_minutes=15,
    )

    assert merged["reference_value"].tolist() == [10, 20]


def test_calculate_metrics_returns_expected_values() -> None:
    metrics = calculate_metrics(
        pd.Series([100.0, 200.0, 300.0, 400.0]),
        pd.Series([99.0, 201.0, 299.0, 401.0]),
    )

    assert isinstance(metrics, ComparisonMetrics)
    assert metrics.sample_size == 4
    assert metrics.mae == pytest.approx(1.0)
    assert metrics.bias == pytest.approx(0.0)
    assert metrics.within_5pct == pytest.approx(100.0)


def test_recompute_flow_for_row_uses_resolution_cache(monkeypatch) -> None:
    calls = []

    def fake_get_water_flow(**kwargs):
        calls.append(kwargs)
        return 42.0

    monkeypatch.setattr(
        "awive.algorithms.validation_compare.get_water_flow",
        fake_get_water_flow,
    )

    class DummyProfile:
        height = 2.0

        def depths_meters(self, ppm, resolution=1.0):
            return np.array([[1.0 * resolution, 0.0], [2.0 * resolution, 1.0]])

    class DummyWaterFlow:
        profile = DummyProfile()
        roughness = 8.0

    class DummyPreprocessing:
        ppm = 100
        resolution = 1.0

    class DummyConfig:
        water_flow = DummyWaterFlow()
        preprocessing = DummyPreprocessing()

    row = pd.Series(
        {
            "resolution": 1.0,
            "velocimetry_values": [1.0, 2.0],
            "senamhi_level": 3.0,
        }
    )
    cache: dict[float, np.ndarray] = {}

    result = recompute_flow_for_row(row, DummyConfig(), cache)

    assert result == pytest.approx(42.0)
    assert len(calls) == 1
    assert 1.0 in cache


def test_attach_senamhi_and_reporte_data_builds_errors() -> None:
    validation = pd.DataFrame(
        {
            "timestamp_dt": pd.to_datetime(
                ["2026-02-01 15:00:00+00:00"], utc=True
            ),
            "velocimetry": ["[1, 2]"],
            "velocimetry_values": [[1.0, 2.0]],
            "resolution": [1.0],
            "calculated_flow": [5.0],
        }
    )
    senamhi = pd.DataFrame(
        {
            "senamhi_timestamp_dt": pd.to_datetime(
                ["2026-02-01 15:01:00+00:00"], utc=True
            ),
            "senamhi_flow": [4.5],
            "senamhi_level": [2.1],
        }
    )
    reporte = pd.DataFrame(
        {
            "reporte_timestamp_dt": pd.to_datetime(
                ["2026-02-01 15:00:00+00:00"], utc=True
            ),
            "Q_referencia": [4.8],
            "Q_p05": [4.0],
            "Q_p25": [4.2],
            "Q_p75": [5.0],
            "Q_p95": [5.2],
            "Q_med": [4.7],
        }
    )

    merged = attach_senamhi_data(validation, senamhi, tolerance_minutes=5)

    assert merged["senamhi_flow"].iloc[0] == pytest.approx(4.5)
    assert merged["flow_time_diff_minutes"].iloc[0] == pytest.approx(1.0)

    merged["recomputed_flow"] = [5.5]
    merged = attach_reporte_data(merged, reporte, tolerance_minutes=5)

    assert merged["Q_referencia"].iloc[0] == pytest.approx(4.8)
    assert merged["reporte_absolute_error"].iloc[0] == pytest.approx(0.7)


def test_recompute_flow_for_row_falls_back_to_profile_height(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "awive.algorithms.validation_compare.get_water_flow",
        lambda **kwargs: kwargs["current_depth"],
    )

    class DummyProfile:
        height = 2.5

        def depths_meters(self, ppm, resolution=1.0):
            return np.array([[1.0, 0.0], [2.0, 1.0]])

    class DummyWaterFlow:
        profile = DummyProfile()
        roughness = 8.0

    class DummyPreprocessing:
        ppm = 100
        resolution = 1.0

    class DummyConfig:
        water_flow = DummyWaterFlow()
        preprocessing = DummyPreprocessing()

    row = pd.Series(
        {
            "resolution": 1.0,
            "velocimetry_values": [1.0, 2.0],
            "senamhi_level": np.nan,
            "water_level_used": np.nan,
        }
    )

    result = recompute_flow_for_row(row, DummyConfig(), {})

    assert result == pytest.approx(2.5)


def test_build_statistics_report_mentions_both_sources() -> None:
    df = pd.DataFrame(
        {
            "timestamp_dt": pd.to_datetime(
                ["2026-02-01 15:00:00+00:00"], utc=True
            ),
            "senamhi_flow": [4.5],
            "Q_referencia": [4.8],
        }
    )
    metrics = ComparisonMetrics(
        sample_size=1,
        mae=1.0,
        rmse=1.0,
        mape=10.0,
        bias=0.2,
        r2=0.9,
        pearson_r=0.95,
        pearson_p=0.01,
        spearman_r=0.94,
        spearman_p=0.02,
        nash_sutcliffe_efficiency=0.8,
        index_of_agreement=0.9,
        min_error=0.1,
        max_error=1.1,
        within_5pct=100.0,
    )

    report = build_statistics_report(df, metrics, metrics)

    assert "SENAMHI Comparison" in report
    assert "Reporte Comparison" in report
    assert "Q_referencia" in report
