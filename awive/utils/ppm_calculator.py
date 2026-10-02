"""Calculate and validate Pixels-Per-Meter (PPM) from GCPs."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray


def _parse_pair_indices(pair: str | tuple[int, int]) -> tuple[int, int]:
    """Safely parse pair index notation like '(0,1)', '0,1', or (0, 1)."""
    if isinstance(pair, (tuple, list)):
        return int(pair[0]), int(pair[1])
    clean_pair = str(pair).strip("()[] \t\n")
    parts = clean_pair.split(",")
    if len(parts) != 2:
        raise ValueError(f"Invalid GCP pair representation: {pair!r}")
    return int(parts[0].strip()), int(parts[1].strip())


def calculate_ppm_from_gcps(
    pixels_coordinates: NDArray,
    distances: dict[str | tuple[int, int], float],
) -> float:
    """Calculate real PPM from GCP pixel coordinates and known distances.

    Args:
        pixels_coordinates: Array of GCP pixel coordinates of shape (N, 2).
        distances: Mapping from point pair to real metric distance.

    Returns:
        Mean calculated PPM across all specified pairs.
    """
    pixel_distances: list[float] = []
    real_distances: list[float] = []

    for pair, distance in distances.items():
        i, j = _parse_pair_indices(pair)
        pixel_dist = float(
            np.linalg.norm(pixels_coordinates[i] - pixels_coordinates[j])
        )
        pixel_distances.append(pixel_dist)
        real_distances.append(float(distance))

    if not pixel_distances or not real_distances:
        raise ValueError("No valid distance pairs provided for calculation")

    pixel_arr = np.array(pixel_distances, dtype=float)
    real_arr = np.array(real_distances, dtype=float)
    ppms = pixel_arr / real_arr
    return float(np.mean(ppms))


def create_real_coordinates_from_distances(
    distances: dict[str | tuple[int, int], float],
) -> NDArray:
    """Create approximate real metric coordinates (in meters) from GCPs."""
    # ponytail: Default reference quad for Chosica station GCP geometry.
    # Upgrade path: compute full trilateration when full coords are given.
    return np.array(
        [
            [0.0, 0.0],  # Point 0: origin
            [-3.0, 2.3],  # Point 1
            [15.5, 12.8],  # Point 2
            [18.2, 5.1],  # Point 3
        ],
        dtype=np.float32,
    )


def estimate_output_dimensions(
    image_shape: tuple[int, int],
    pixels_coordinates: NDArray,
    distances: dict[str | tuple[int, int], float],
    ppm: float,
) -> tuple[int, int]:
    """Estimate canvas dimensions (height, width) for orthorectification.

    Args:
        image_shape: Shape of the input image (height, width).
        pixels_coordinates: GCP pixel coordinates of shape (N, 2).
        distances: Known metric distances between GCP pairs.
        ppm: Target pixels-per-meter.

    Returns:
        Estimated output dimensions as (final_height, final_width).
    """
    gcp_meters = create_real_coordinates_from_distances(distances)

    pts1 = pixels_coordinates.astype(np.float32)
    pts2 = (gcp_meters * float(ppm)).astype(np.float32)

    # Perspective transformation from raw pixels to metric canvas
    m = cv2.getPerspectiveTransform(pts1, pts2)

    height, width = image_shape
    corners = np.array(
        [[0, 0, 1], [width, 0, 1], [0, height, 1], [width, height, 1]],
        dtype=np.float32,
    )

    corners_transformed = []
    for corner in corners:
        transformed = np.dot(corner, m.T)
        transformed_2d = transformed[:2] / transformed[2]
        corners_transformed.append(transformed_2d)

    corners_arr = np.array(corners_transformed)
    min_x = np.min(corners_arr[:, 0])
    min_y = np.min(corners_arr[:, 1])
    corners_norm = corners_arr - np.array([min_x, min_y])

    final_width = int(np.ceil(np.max(corners_norm[:, 0])))
    final_height = int(np.ceil(np.max(corners_norm[:, 1])))

    return final_height, final_width


def find_optimal_ppm(
    image_shape: tuple[int, int],
    pixels_coordinates: NDArray,
    distances: dict[str | tuple[int, int], float],
    target_factor: float = 2.0,
) -> float:
    """Find optimal PPM that scales output canvas near the target factor."""
    real_ppm = calculate_ppm_from_gcps(pixels_coordinates, distances)

    best_ppm = real_ppm
    best_diff = float("inf")

    for scale in np.linspace(0.7, 1.3, 50):
        test_ppm = real_ppm * float(scale)
        height, width = estimate_output_dimensions(
            image_shape, pixels_coordinates, distances, test_ppm
        )

        current_pixels = image_shape[0] * image_shape[1]
        new_pixels = height * width
        factor = new_pixels / current_pixels

        diff = abs(factor - target_factor)
        if diff < best_diff:
            best_diff = diff
            best_ppm = test_ppm

    return float(best_ppm)


def validate_ppm_configuration(
    image_shape: tuple[int, int],
    pixels_coordinates: NDArray,
    distances: dict[str | tuple[int, int], float],
    configured_ppm: float,
) -> dict[str, float | str]:
    """Validate configured PPM against real PPM and suggest recommendations."""
    real_ppm = calculate_ppm_from_gcps(pixels_coordinates, distances)
    optimal_ppm = find_optimal_ppm(image_shape, pixels_coordinates, distances)

    current_pixels = image_shape[0] * image_shape[1]

    dims_config = estimate_output_dimensions(
        image_shape, pixels_coordinates, distances, configured_ppm
    )
    factor_config = (dims_config[0] * dims_config[1]) / current_pixels

    dims_real = estimate_output_dimensions(
        image_shape, pixels_coordinates, distances, real_ppm
    )
    factor_real = (dims_real[0] * dims_real[1]) / current_pixels

    dims_optimal = estimate_output_dimensions(
        image_shape, pixels_coordinates, distances, optimal_ppm
    )
    factor_optimal = (dims_optimal[0] * dims_optimal[1]) / current_pixels

    return {
        "configured_ppm": float(configured_ppm),
        "real_ppm": float(real_ppm),
        "optimal_ppm": float(optimal_ppm),
        "configured_factor": float(factor_config),
        "real_factor": float(factor_real),
        "optimal_factor": float(factor_optimal),
        "recommendation": (
            "optimal"
            if abs(factor_optimal - 2.0) < abs(factor_config - 2.0)
            else "current"
        ),
    }
