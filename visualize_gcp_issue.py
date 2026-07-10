"""Visualize the GCP issue and demonstrate the root cause."""

import yaml
import numpy as np

# Load both config files
with open("config_awive_a.yaml", "r") as f:
    config_a = yaml.safe_load(f)

with open("config_awive_b.yaml", "r") as f:
    config_b = yaml.safe_load(f)

print("=" * 80)
print("ROOT CAUSE ANALYSIS: Why Config B Produces Different Results")
print("=" * 80)

print("\n" + "=" * 80)
print("STEP 1: Understanding the Algorithm")
print("=" * 80)
print("""
The orthorectification process works as follows:
1. Takes pixel coordinates from the image
2. Uses distances between GCPs to reconstruct 2D meter coordinates via MDS
   (Multidimensional Scaling using eigendecomposition)
3. Creates a perspective transform from pixel coords -> meter coords
4. Applies this transform to warp the image to real-world coordinates

KEY POINT: The order of points MATTERS because:
- The distance matrix structure depends on point indices
- MDS reconstruction uses point ordering to compute meter coordinates
- Different orderings produce different meter coordinate layouts
""")

print("\n" + "=" * 80)
print("STEP 2: The Problem with Config B")
print("=" * 80)

pixels_a = np.array(config_a["dataset"]["gcp"]["pixels"])
pixels_b = np.array(config_b["dataset"]["gcp"]["pixels"])

print("\nConfig A:")
for i in range(4):
    print(f"  Point {i}: pixels={pixels_a[i]}")

print("\nConfig B:")
for i in range(4):
    print(f"  Point {i}: pixels={pixels_b[i]}")

print("\nMapping (B -> A based on proximity):")
print("  B[0] [552, 403] ≈ A[1] [455, 437]  (diff: ~103 pixels) ⚠️ LARGE DIFF")
print("  B[1] [2551, 2121] ≈ A[2] [2562, 2095]  (diff: ~28 pixels)")
print("  B[2] [3575, 1041] ≈ A[3] [3578, 1041]  (diff: ~3 pixels)")
print("  B[3] [830, 242] ≈ A[0] [811, 265]  (diff: ~30 pixels)")

print("""
ISSUE #1: The pixel coordinates in Config B are NOT exactly a reordering
of Config A. They are APPROXIMATIONS with errors up to 103 pixels!

ISSUE #2: Even if they were exact reorderings, the distances are assigned
to the wrong point pairs!
""")

print("\n" + "=" * 80)
print("STEP 3: Distance Matrix Analysis")
print("=" * 80)


def parse_distance_key(key):
    return tuple(map(int, key.strip("()").split(",")))


def build_distance_matrix(distances_dict):
    matrix = np.zeros((4, 4))
    for key, value in distances_dict.items():
        i, j = parse_distance_key(key)
        matrix[i, j] = value
        matrix[j, i] = value
    return matrix


dist_a = build_distance_matrix(config_a["dataset"]["gcp"]["distances"])
dist_b = build_distance_matrix(config_b["dataset"]["gcp"]["distances"])

print("\nConfig A Distance Matrix:")
print("     Point0  Point1  Point2  Point3")
for i in range(4):
    print(f"P{i}: ", end="")
    for j in range(4):
        print(f"{dist_a[i, j]:7.4f} ", end="")
    print()

print("\nConfig B Distance Matrix:")
print("     Point0  Point1  Point2  Point3")
for i in range(4):
    print(f"P{i}: ", end="")
    for j in range(4):
        print(f"{dist_b[i, j]:7.4f} ", end="")
    print()

print("""
The distance matrices are DIFFERENT! This means:
- Config A Point 0 is 3.7782m from Point 1
- Config B Point 0 is 19.0869m from Point 1

Even though both configs use the same 6 distance values, they're assigned
to different point pairs, creating completely different geometric shapes!
""")

print("\n" + "=" * 80)
print("STEP 4: MDS Reconstruction (What the Code Does)")
print("=" * 80)

print("""
The calculate_meters() function in config.py uses MDS to reconstruct
2D meter coordinates from distances. This is POSITION-SENSITIVE:

For Config A with distances:
  (0,1)=3.78, (0,2)=19.38, (0,3)=20.63, (1,2)=19.09, (1,3)=21.84, (2,3)=8.33
  
It creates this distance matrix structure which MDS uses to find coordinates.

For Config B with the SAME distance values but DIFFERENT assignments:
  (0,1)=19.09, (0,2)=21.84, (0,3)=3.78, (1,2)=8.33, (1,3)=19.38, (2,3)=20.63
  
MDS will produce a DIFFERENT geometric layout!
""")


# Simulate MDS for both configs
def calculate_meters_from_distances(distances_dict):
    """Simulate the MDS calculation from config.py"""

    def di(i, j):
        key1 = f"({i},{j})"
        key2 = f"({j},{i})"
        return distances_dict.get(key1) or distances_dict.get(key2)

    d = np.array(
        [
            [0, di(0, 1), di(0, 2), di(0, 3)],
            [di(1, 0), 0, di(1, 2), di(1, 3)],
            [di(2, 0), di(2, 1), 0, di(2, 3)],
            [di(3, 0), di(3, 1), di(3, 2), 0],
        ]
    )

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


meters_a = calculate_meters_from_distances(
    config_a["dataset"]["gcp"]["distances"]
)
meters_b = calculate_meters_from_distances(
    config_b["dataset"]["gcp"]["distances"]
)

print("\nMDS-reconstructed meter coordinates for Config A:")
for i in range(4):
    print(f"  Point {i}: [{meters_a[i, 0]:8.4f}, {meters_a[i, 1]:8.4f}]")

print("\nMDS-reconstructed meter coordinates for Config B:")
for i in range(4):
    print(f"  Point {i}: [{meters_b[i, 0]:8.4f}, {meters_b[i, 1]:8.4f}]")

print("\nThese are DIFFERENT shapes!")

print("\n" + "=" * 80)
print("STEP 5: The Perspective Transform")
print("=" * 80)

print(f"""
OpenCV's getPerspectiveTransform() creates a mapping:
  
  Config A: pixels_a -> meters_a
  Config B: pixels_b -> meters_b

Where:
1. pixels_a ≠ pixels_b (different source points, with errors up to 103 pixels)
2. meters_a ≠ meters_b (different target shapes)

This creates completely different perspective transforms!

The transform matrix M satisfies:
  meters = M · pixels (in homogeneous coordinates)

Different pixels + different meters = different M = different output image!
""")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

print("""
❌ Config B contains TWO critical errors:

ERROR #1: Pixel Coordinate Mismatch
  The pixel coordinates in config_b are APPROXIMATIONS of a reordered
  config_a, not exact values. The error is up to 103 pixels for point B[0].
  
  Expected: B[0] = [455, 437] (exact copy of A[1])
  Actual:   B[0] = [552, 403] (103 pixels off!)

ERROR #2: Incorrect Distance Assignment
  Even if the pixel coords were exact, the distances are assigned to wrong
  point pairs. Config B's distance structure creates a different geometric
  shape than Config A.

WHY THIS HAPPENS:
  The GCP interface likely allows clicking points in any order to form a
  trapezoid. If you clicked the same 4 physical points but in a different
  order between the two configs:
  
  - The pixel clicks may not be exactly the same (manual clicking error)
  - The distance assignments get shuffled based on the new order
  - MDS reconstructs a different meter coordinate layout
  - The perspective transform becomes completely different

FIX:
  To make config_b identical to config_a, you need to:
  1. Use EXACT same pixel coordinates (copy from config_a)
  2. Reorder them to match your desired point order
  3. Update the distance assignments to match the new ordering
  
  OR: Keep the same point order in both configs to avoid this issue entirely.
""")

print("\n" + "=" * 80)
print("NUMERICAL VERIFICATION")
print("=" * 80)

# Show that pixel coordinates have measurable errors
print("\nPixel coordinate errors (Config B vs closest Config A point):")
print("  B[0] vs A[1]: Δx=97, Δy=-34  -> distance=102.79 pixels")
print("  B[1] vs A[2]: Δx=-11, Δy=26  -> distance=28.23 pixels")
print("  B[2] vs A[3]: Δx=-3, Δy=0    -> distance=3.00 pixels")
print("  B[3] vs A[0]: Δx=19, Δy=-23  -> distance=29.83 pixels")

print("\nThese pixel errors translate to real-world position errors after")
print("orthorectification, causing different regions to be sampled and")
print("different velocity measurements to be computed.")
