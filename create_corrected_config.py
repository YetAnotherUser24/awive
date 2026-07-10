"""Create a corrected version of config_b that properly reorders config_a."""

import yaml

# Load config_a
with open("config_awive_a.yaml", "r") as f:
    config_a = yaml.safe_load(f)

# Create config_b_corrected with proper reordering
# Mapping: B[0]=A[1], B[1]=A[2], B[2]=A[3], B[3]=A[0]
config_b_corrected = yaml.safe_load(open("config_awive_a.yaml", "r").read())

# Reorder pixels: [A1, A2, A3, A0]
pixels_a = config_a["dataset"]["gcp"]["pixels"]
config_b_corrected["dataset"]["gcp"]["pixels"] = [
    pixels_a[1],  # B[0] = A[1] = [455, 437]
    pixels_a[2],  # B[1] = A[2] = [2562, 2095]
    pixels_a[3],  # B[2] = A[3] = [3578, 1041]
    pixels_a[0],  # B[3] = A[0] = [811, 265]
]

# Update distances to match the new ordering
# Original A distances:
# (0,1)=3.7782, (0,2)=19.3769, (0,3)=20.6298
# (1,2)=19.0869, (1,3)=21.8399, (2,3)=8.3321

# With reordering B[0]=A[1], B[1]=A[2], B[2]=A[3], B[3]=A[0]:
# B(0,1) = A(1,2) = 19.0869
# B(0,2) = A(1,3) = 21.8399
# B(0,3) = A(1,0) = 3.7782
# B(1,2) = A(2,3) = 8.3321
# B(1,3) = A(2,0) = 19.3769
# B(2,3) = A(3,0) = 20.6298

config_b_corrected["dataset"]["gcp"]["distances"] = {
    "(0,1)": 19.0869,
    "(0,2)": 21.8399,
    "(0,3)": 3.7782,
    "(1,2)": 8.3321,
    "(1,3)": 19.3769,
    "(2,3)": 20.6298,
}

# Save corrected config
with open("config_awive_b_corrected.yaml", "w") as f:
    yaml.dump(config_b_corrected, f, default_flow_style=False, sort_keys=False)

print("=" * 80)
print("CORRECTED CONFIG_B GENERATED")
print("=" * 80)

print("\nGenerated: config_awive_b_corrected.yaml")
print("\nThis config has:")
print("  1. EXACT pixel coordinates from config_a (no approximations)")
print("  2. Correct distance assignments for the reordered points")
print("\nCorrected pixel coordinates:")
for i, pixel in enumerate(config_b_corrected["dataset"]["gcp"]["pixels"]):
    print(f"  Point {i}: {pixel}")

print("\n" + "=" * 80)
print("COMPARISON: Current config_b vs Corrected config_b")
print("=" * 80)

config_b = yaml.safe_load(open("config_awive_b.yaml", "r").read())

print("\nCurrent config_b pixels (INCORRECT):")
for i, pixel in enumerate(config_b["dataset"]["gcp"]["pixels"]):
    print(f"  Point {i}: {pixel}")

print("\nCorrected config_b pixels (SHOULD BE):")
for i, pixel in enumerate(config_b_corrected["dataset"]["gcp"]["pixels"]):
    print(f"  Point {i}: {pixel}")

print("\nDifferences:")
import numpy as np

for i in range(4):
    curr = np.array(config_b["dataset"]["gcp"]["pixels"][i])
    corr = np.array(config_b_corrected["dataset"]["gcp"]["pixels"][i])
    diff = curr - corr
    dist = np.linalg.norm(diff)
    if dist > 0.1:
        print(
            f"  Point {i}: Δx={diff[0]}, Δy={diff[1]}, distance={dist:.2f} pixels ⚠️"
        )
    else:
        print(f"  Point {i}: Identical ✓")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print("""
Replace config_awive_b.yaml with config_awive_b_corrected.yaml to fix the issue.

The corrected version:
- Uses exact pixel coordinates from config_a (no manual clicking errors)
- Has proper distance assignments for the reordered points
- Will produce the SAME orthorectified output as config_a

Note: If the order of GCP points is meaningful in your workflow (e.g., for
labeling or visualization), then reordering is fine. But the pixel coordinates
MUST be exact copies, not approximations from re-clicking the interface.
""")
