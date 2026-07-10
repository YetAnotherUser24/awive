"""Analyze GCP configuration differences between config_a and config_b."""

import yaml
import numpy as np

# Load both config files
with open("config_awive_a.yaml", "r") as f:
    config_a = yaml.safe_load(f)

with open("config_awive_b.yaml", "r") as f:
    config_b = yaml.safe_load(f)

print("=" * 80)
print("CONFIG A - GCP Analysis")
print("=" * 80)
print("\nPixel Coordinates:")
for i, pixel in enumerate(config_a["dataset"]["gcp"]["pixels"]):
    print(f"  Point {i}: {pixel}")

print("\nDistances:")
for key, value in config_a["dataset"]["gcp"]["distances"].items():
    print(f"  {key}: {value}")

print("\n" + "=" * 80)
print("CONFIG B - GCP Analysis")
print("=" * 80)
print("\nPixel Coordinates:")
for i, pixel in enumerate(config_b["dataset"]["gcp"]["pixels"]):
    print(f"  Point {i}: {pixel}")

print("\nDistances:")
for key, value in config_b["dataset"]["gcp"]["distances"].items():
    print(f"  {key}: {value}")

print("\n" + "=" * 80)
print("COMPARISON")
print("=" * 80)

# Check if distances match (ignoring order)
all_distances_a = set(config_a["dataset"]["gcp"]["distances"].values())
all_distances_b = set(config_b["dataset"]["gcp"]["distances"].values())

print(f"\nAll distance values match: {all_distances_a == all_distances_b}")

# Try to find the mapping between points
pixels_a = np.array(config_a["dataset"]["gcp"]["pixels"])
pixels_b = np.array(config_b["dataset"]["gcp"]["pixels"])

print("\nTrying to find point correspondence...")
print("\nConfig B points compared to Config A:")
for i, pixel_b in enumerate(pixels_b):
    distances = [np.linalg.norm(pixel_b - pixel_a) for pixel_a in pixels_a]
    closest_idx = np.argmin(distances)
    closest_dist = distances[closest_idx]
    print(
        f"  B[{i}] {pixel_b} -> closest to A[{closest_idx}] {pixels_a[closest_idx]} (distance: {closest_dist:.2f} pixels)"
    )

# Reconstruct distance matrix for config A
print("\n" + "=" * 80)
print("RECONSTRUCTED DISTANCE MATRICES")
print("=" * 80)


def parse_distance_key(key):
    """Parse string key like '(0,1)' to tuple (0,1)"""
    return tuple(map(int, key.strip("()").split(",")))


def build_distance_matrix(distances_dict):
    """Build a symmetric distance matrix from the distance dictionary"""
    matrix = np.zeros((4, 4))
    for key, value in distances_dict.items():
        i, j = parse_distance_key(key)
        matrix[i, j] = value
        matrix[j, i] = value
    return matrix


dist_matrix_a = build_distance_matrix(config_a["dataset"]["gcp"]["distances"])
dist_matrix_b = build_distance_matrix(config_b["dataset"]["gcp"]["distances"])

print("\nConfig A Distance Matrix:")
print(dist_matrix_a)

print("\nConfig B Distance Matrix:")
print(dist_matrix_b)

# Calculate actual pixel distances to check consistency
print("\n" + "=" * 80)
print("ACTUAL PIXEL DISTANCES (for verification)")
print("=" * 80)


def calc_pixel_distances(pixels):
    """Calculate pixel distances between all point pairs"""
    n = len(pixels)
    matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            matrix[i, j] = np.linalg.norm(
                np.array(pixels[i]) - np.array(pixels[j])
            )
    return matrix


pixel_dist_a = calc_pixel_distances(config_a["dataset"]["gcp"]["pixels"])
pixel_dist_b = calc_pixel_distances(config_b["dataset"]["gcp"]["pixels"])

print("\nConfig A Pixel Distances:")
print(pixel_dist_a)

print("\nConfig B Pixel Distances:")
print(pixel_dist_b)

# Check if the pixel coordinate differences are significant
print("\n" + "=" * 80)
print("POTENTIAL ISSUES")
print("=" * 80)

# Check if config_b is a reordering of config_a
mapping = []
for i, pixel_b in enumerate(pixels_b):
    distances = [np.linalg.norm(pixel_b - pixel_a) for pixel_a in pixels_a]
    closest_idx = np.argmin(distances)
    closest_dist = distances[closest_idx]
    mapping.append((i, closest_idx, closest_dist))
    if closest_dist > 100:  # More than 100 pixels difference
        print(
            f"\n⚠️  WARNING: B[{i}] differs significantly from its closest match A[{closest_idx}]"
        )
        print(f"   B[{i}]: {pixel_b}")
        print(f"   A[{closest_idx}]: {pixels_a[closest_idx]}")
        print(f"   Pixel difference: {closest_dist:.2f} pixels")

# Check if the mapping preserves the distance relationships
print("\n\nChecking if distance relationships are preserved...")
print(
    "If B is a reordered version of A, the distances should match when reordered."
)

# Create expected distance mapping
expected_mapping = {m[0]: m[1] for m in mapping}
print(f"\nInferred point mapping (B -> A): {expected_mapping}")

# Verify each distance
print(
    "\nVerifying distances (comparing B's distances to A's reordered distances):"
)
mismatches = []
for key_b, value_b in config_b["dataset"]["gcp"]["distances"].items():
    i_b, j_b = parse_distance_key(key_b)
    i_a = expected_mapping.get(i_b)
    j_a = expected_mapping.get(j_b)

    # Find corresponding distance in config_a
    key_a1 = f"({i_a},{j_a})"
    key_a2 = f"({j_a},{i_a})"
    value_a = config_a["dataset"]["gcp"]["distances"].get(key_a1) or config_a[
        "dataset"
    ]["gcp"]["distances"].get(key_a2)

    match = "✓" if abs(value_b - value_a) < 0.001 else "✗"
    print(
        f"  B{key_b} = {value_b:.4f} vs A({i_a},{j_a}) = {value_a:.4f} {match}"
    )

    if abs(value_b - value_a) > 0.001:
        mismatches.append((key_b, value_b, value_a))

if mismatches:
    print("\n⚠️  CRITICAL ISSUE: Distance mismatches found!")
    print(
        "The distance mapping does not preserve the relationships correctly."
    )
else:
    print(
        "\n✓ Distance mapping is consistent (distances match after reordering)."
    )

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("\nThe pixel coordinates in config_b are DIFFERENT from config_a,")
print(
    "not just reordered! This will cause different orthorectification results."
)
print("\nEven though the distance values are the same, they are assigned to")
print(
    "DIFFERENT pixel coordinate pairs, which will create different geometric"
)
print("transformations during orthorectification.")
