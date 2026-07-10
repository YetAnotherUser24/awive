"""Create config_c with a different GCP ordering."""
import yaml

# Load config_a
with open('config_awive_a.yaml', 'r') as f:
    config_a = yaml.safe_load(f)

# Create config_c with ordering: [A2, A3, A0, A1]
# This gives us: C[0]=A[2], C[1]=A[3], C[2]=A[0], C[3]=A[1]
config_c = yaml.safe_load(open('config_awive_a.yaml', 'r').read())

# Reorder pixels: [A2, A3, A0, A1]
pixels_a = config_a['dataset']['gcp']['pixels']
config_c['dataset']['gcp']['pixels'] = [
    pixels_a[2],  # C[0] = A[2] = [2562, 2095]
    pixels_a[3],  # C[1] = A[3] = [3578, 1041]
    pixels_a[0],  # C[2] = A[0] = [811, 265]
    pixels_a[1],  # C[3] = A[1] = [455, 437]
]

# Update distances to match the new ordering
# Original A distances:
# (0,1)=3.7782, (0,2)=19.3769, (0,3)=20.6298
# (1,2)=19.0869, (1,3)=21.8399, (2,3)=8.3321

# With reordering C[0]=A[2], C[1]=A[3], C[2]=A[0], C[3]=A[1]:
# C(0,1) = A(2,3) = 8.3321
# C(0,2) = A(2,0) = 19.3769
# C(0,3) = A(2,1) = 19.0869
# C(1,2) = A(3,0) = 20.6298
# C(1,3) = A(3,1) = 21.8399
# C(2,3) = A(0,1) = 3.7782

config_c['dataset']['gcp']['distances'] = {
    "(0,1)": 8.3321,
    "(0,2)": 19.3769,
    "(0,3)": 19.0869,
    "(1,2)": 20.6298,
    "(1,3)": 21.8399,
    "(2,3)": 3.7782,
}

# Save config_c
with open('config_awive_c.yaml', 'w') as f:
    yaml.dump(config_c, f, default_flow_style=False, sort_keys=False)

print("=" * 80)
print("CONFIG_AWIVE_C GENERATED")
print("=" * 80)

print("\nGenerated: config_awive_c.yaml")
print("\nPoint ordering: [A2, A3, A0, A1]")
print("\nPixel coordinates:")
for i, pixel in enumerate(config_c['dataset']['gcp']['pixels']):
    orig_idx = [2, 3, 0, 1][i]
    print(f"  C[{i}] = A[{orig_idx}] = {pixel}")

print("\nDistances:")
for key, value in config_c['dataset']['gcp']['distances'].items():
    print(f"  {key}: {value}")

print("\n" + "=" * 80)
print("VERIFICATION")
print("=" * 80)

# Verify that the distances are correct
import numpy as np

def calculate_meters_from_distances(distances_dict):
    """Simulate the MDS calculation"""
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

meters_a = calculate_meters_from_distances(config_a['dataset']['gcp']['distances'])
meters_c = calculate_meters_from_distances(config_c['dataset']['gcp']['distances'])

print("\nMDS-reconstructed meter coordinates for Config A:")
for i in range(4):
    print(f"  A[{i}]: [{meters_a[i,0]:8.4f}, {meters_a[i,1]:8.4f}]")

print("\nMDS-reconstructed meter coordinates for Config C:")
for i in range(4):
    orig_idx = [2, 3, 0, 1][i]
    print(f"  C[{i}] (=A[{orig_idx}]): [{meters_c[i,0]:8.4f}, {meters_c[i,1]:8.4f}]")

print("\nExpected meter coordinates for Config C (reordered from A):")
reordering = [2, 3, 0, 1]
for i in range(4):
    orig_idx = reordering[i]
    print(f"  C[{i}] (=A[{orig_idx}]): [{meters_a[orig_idx,0]:8.4f}, {meters_a[orig_idx,1]:8.4f}]")

print("\nChecking if MDS reconstruction matches expected reordering...")
all_match = True
for i in range(4):
    orig_idx = reordering[i]
    expected = meters_a[orig_idx]
    actual = meters_c[i]
    diff = np.linalg.norm(expected - actual)
    match = "✓" if diff < 0.01 else "✗"
    print(f"  C[{i}]: diff={diff:.6f} {match}")
    if diff >= 0.01:
        all_match = False

if all_match:
    print("\n✓ SUCCESS: Config C will produce identical results to Config A!")
else:
    print("\n⚠️ WARNING: Something went wrong with the distance mapping.")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
config_awive_c.yaml has been created with a different GCP ordering.

All three configs (A, B_corrected, C) should produce IDENTICAL orthorectified
images because they:
1. Use the same physical pixel locations (just numbered differently)
2. Have correctly mapped distances for their respective orderings
3. Will reconstruct the same geometric shape through MDS

The order of GCP points does NOT matter for the final result, as long as:
- Pixel coordinates are exact (no clicking errors)
- Distance assignments match the point ordering
""")
