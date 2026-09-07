"""Tests for awive.utils.ppm_calculator."""

import numpy as np
import pytest

from awive.utils.ppm_calculator import (
    calculate_ppm_from_gcps,
    estimate_output_dimensions,
    find_optimal_ppm,
    validate_ppm_configuration,
)


@pytest.fixture
def sample_gcps():
    # Synthetic square GCP coordinates in pixels (100 px apart)
    return np.array(
        [
            [0.0, 0.0],
            [100.0, 0.0],
            [100.0, 100.0],
            [0.0, 100.0],
        ],
        dtype=np.float32,
    )


@pytest.fixture
def sample_distances():
    # Known real distances in meters (1.0 meter between adjacent points)
    return {
        "(0,1)": 1.0,
        "(1,2)": 1.0,
        "(2,3)": 1.0,
        "(3,0)": 1.0,
    }


def test_calculate_ppm_from_gcps_string_pairs(sample_gcps, sample_distances):
    # 100 pixels / 1.0 meter = 100.0 PPM
    ppm = calculate_ppm_from_gcps(sample_gcps, sample_distances)
    assert pytest.approx(ppm, rel=1e-3) == 100.0


def test_calculate_ppm_from_gcps_tuple_pairs(sample_gcps):
    distances = {
        (0, 1): 2.0,  # 100 px / 2m = 50 PPM
        (1, 2): 2.0,
    }
    ppm = calculate_ppm_from_gcps(sample_gcps, distances)
    assert pytest.approx(ppm, rel=1e-3) == 50.0


def test_estimate_output_dimensions(sample_gcps, sample_distances):
    height, width = estimate_output_dimensions(
        image_shape=(1080, 1920),
        pixels_coordinates=sample_gcps,
        distances=sample_distances,
        ppm=100.0,
    )
    assert height > 0
    assert width > 0


def test_validate_ppm_configuration(sample_gcps, sample_distances):
    analysis = validate_ppm_configuration(
        image_shape=(1080, 1920),
        pixels_coordinates=sample_gcps,
        distances=sample_distances,
        configured_ppm=100.0,
    )
    assert "real_ppm" in analysis
    assert "optimal_ppm" in analysis
    assert pytest.approx(analysis["real_ppm"], rel=1e-3) == 100.0
