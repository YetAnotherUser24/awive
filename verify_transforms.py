"""Verify if config_c produces the same orthorectification as config_a."""
import yaml
import numpy as np
import cv2

def load_config(filepath):
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def calculate_meters_from_distances(distances_dict):
    """Calculate meter coordinates using MDS (same as in config.py)"""
    def di(i, j):
        key1 = f"({i},{j})"
        key2 = f"({j},{i})"
        return distances_dict.get(key1) or distances_dict.get(key2)
    
    d = np.array([
        [0, di(0, 1), di(0, 2), di(0, 3)],
        [di(1, 0), 0, di(1, 2), di(1, 3)],
        [di(2, 0), di(2, 1), 0, di(2, 3)],
        [di(3, 0), di(3, 1), di(3, 2), 0],
    ])
    
    dim = 2
    n = d.shape[0]
    h = np.eye(n) - np.ones((n, n)) / n
    d_squared = d**2
    b = -0.5 * h @ d_squared @ h
    eigvals, eigvecs = np.linalg.eig(b)
    idx = np.argsort(eigvals)[::-1]
    eigvals = eigvals[idx][:dim]
    eigvecs = eigvecs[:, idx][:, :dim]
    l_result = np.diag(np.sqrt(np.abs(eigvals)))
    x = eigvecs @ l_result
    x[:, 0] *= -1
    return x

def get_perspective_transform(config, ppm=100):
    """Get the perspective transform matrix for a config"""
    pixels = np.array(config['dataset']['gcp']['pixels'], dtype=np.float32)
    meters = calculate_meters_from_distances(config['dataset']['gcp']['distances'])
    meters = meters.astype(np.float32) * ppm
    
    return cv2.getPerspectiveTransform(pixels, meters), pixels, meters

# Load all configs
config_a = load_config('config_awive_a.yaml')
config_b_corrected = load_config('config_awive_b_corrected.yaml')
config_c = load_config('config_awive_c.yaml')

print("=" * 80)
print("ORTHORECTIFICATION TRANSFORM VERIFICATION")
print("=" * 80)

# Get transforms
M_a, pixels_a, meters_a = get_perspective_transform(config_a)
M_b, pixels_b, meters_b = get_perspective_transform(config_b_corrected)
M_c, pixels_c, meters_c = get_perspective_transform(config_c)

print("\nConfig A - Pixel to Meter mapping:")
for i in range(4):
    print(f"  [{pixels_a[i,0]:7.1f}, {pixels_a[i,1]:7.1f}] -> [{meters_a[i,0]:10.4f}, {meters_a[i,1]:10.4f}]")

print("\nConfig B Corrected - Pixel to Meter mapping:")
for i in range(4):
    print(f"  [{pixels_b[i,0]:7.1f}, {pixels_b[i,1]:7.1f}] -> [{meters_b[i,0]:10.4f}, {meters_b[i,1]:10.4f}]")

print("\nConfig C - Pixel to Meter mapping:")
for i in range(4):
    print(f"  [{pixels_c[i,0]:7.1f}, {pixels_c[i,1]:7.1f}] -> [{meters_c[i,0]:10.4f}, {meters_c[i,1]:10.4f}]")

# Test if transforms produce the same output for test points
print("\n" + "=" * 80)
print("TRANSFORM COMPARISON")
print("=" * 80)

# Create test points across the image
test_points = np.array([
    [811, 265],    # Original A[0]
    [455, 437],    # Original A[1]
    [2562, 2095],  # Original A[2]
    [3578, 1041],  # Original A[3]
    [1000, 1000],  # Center-ish point
    [2000, 1500],  # Another test point
], dtype=np.float32)

def transform_points(points, M):
    """Transform points using perspective transform"""
    points_homogeneous = np.column_stack([points, np.ones(len(points))])
    transformed = np.array([np.dot(pt, M.T) for pt in points_homogeneous])
    transformed = transformed[:, :2] / transformed[:, 2:3]
    return transformed

result_a = transform_points(test_points, M_a)
result_b = transform_points(test_points, M_b)
result_c = transform_points(test_points, M_c)

print("\nTransforming test points:")
print("\nTest Point       -> Config A Output      | Config B Output      | Config C Output")
print("-" * 95)

max_diff_b = 0
max_diff_c = 0

for i, pt in enumerate(test_points):
    diff_b = np.linalg.norm(result_a[i] - result_b[i])
    diff_c = np.linalg.norm(result_a[i] - result_c[i])
    max_diff_b = max(max_diff_b, diff_b)
    max_diff_c = max(max_diff_c, diff_c)
    
    match_b = "✓" if diff_b < 0.01 else "✗"
    match_c = "✓" if diff_c < 0.01 else "✗"
    
    print(f"[{pt[0]:6.0f},{pt[1]:6.0f}] -> "
          f"[{result_a[i,0]:9.2f},{result_a[i,1]:9.2f}] | "
          f"[{result_b[i,0]:9.2f},{result_b[i,1]:9.2f}] {match_b} | "
          f"[{result_c[i,0]:9.2f},{result_c[i,1]:9.2f}] {match_c}")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

print(f"\nMax difference between Config A and Config B_corrected: {max_diff_b:.6f}")
print(f"Max difference between Config A and Config C: {max_diff_c:.6f}")

if max_diff_b < 0.01:
    print("\n✓ Config B_corrected produces IDENTICAL results to Config A")
else:
    print(f"\n✗ Config B_corrected differs from Config A by up to {max_diff_b:.2f} units")

if max_diff_c < 0.01:
    print("✓ Config C produces IDENTICAL results to Config A")
else:
    print(f"✗ Config C differs from Config A by up to {max_diff_c:.2f} units")

print("\n" + "=" * 80)
print("EXPLANATION")
print("=" * 80)

if max_diff_c >= 0.01:
    print("""
The MDS algorithm has inherent ambiguities (reflection, rotation, translation).
When we reorder the distance matrix, MDS reconstructs a coordinate system that
might be reflected or rotated compared to the original.

This means config_c will NOT produce the same orthorectification output as
config_a, even though it uses the same pixel locations.

The key insight: GCP ordering DOES matter because MDS reconstruction is not
invariant to distance matrix reordering. The algorithm produces a specific
coordinate system based on the structure of the distance matrix.

To get identical results, configs must have not just the same pixel locations
and distances, but also the SAME distance matrix structure (which means the
same point ordering or a very specific permutation that preserves the MDS
output).
""")
else:
    print("""
All configs produce identical orthorectification results! The GCP ordering
doesn't affect the final output as long as pixel coordinates and distance
assignments are correct.
""")
