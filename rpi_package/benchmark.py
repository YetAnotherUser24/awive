"""Zero-heavy-dependency benchmark runner for Raspberry Pi Zero 2 W.

Tests the existing `velocimetry` function 100% as-is across native resolution
test videos, using stdlib `resource` and `time` to measure peak RAM and FPS.
No pandas, no matplotlib.
"""

from __future__ import annotations

import argparse
import csv
import resource
import time
from pathlib import Path

import yaml

from awive.algorithms.velocimetry import velocimetry

PROFILES = [
    {
        "id": "1080p_fhd",
        "label": "1080p FHD",
        "video": "videos/video_1080p.mp4",
        "config": "configs/awive_1080p.yaml",
        "width": 1920,
        "height": 1080,
    },
    {
        "id": "720p_default",
        "label": "720p HD Default",
        "video": "videos/video_720p.mp4",
        "config": "configs/awive_720p_default.yaml",
        "width": 1280,
        "height": 720,
    },
    {
        "id": "720p_tuned",
        "label": "720p HD Tuned",
        "video": "videos/video_720p.mp4",
        "config": "configs/awive_720p_tuned.yaml",
        "width": 1280,
        "height": 720,
    },
    {
        "id": "480p_tuned",
        "label": "480p SD Tuned",
        "video": "videos/video_480p.mp4",
        "config": "configs/awive_480p_tuned.yaml",
        "width": 854,
        "height": 480,
    },
    {
        "id": "360p_tuned",
        "label": "360p Low Tuned",
        "video": "videos/video_360p.mp4",
        "config": "configs/awive_360p_tuned.yaml",
        "width": 640,
        "height": 360,
    },
]


def get_peak_ram_mb() -> float:
    """Return peak resident memory (RSS) in megabytes."""
    # On Linux ru_maxrss is in kilobytes
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main() -> None:
    parser = argparse.ArgumentParser(description="RPi Zero 2 W Velocimetry Benchmark")
    parser.add_argument(
        "--wlevel",
        type=float,
        default=0.32,
        help="Water level (default: 0.32m for sample point 01)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("rpi_zero_results.csv"),
        help="CSV results file",
    )
    args = parser.parse_args()

    results = []

    print("=" * 80)
    print("🍓 Raspberry Pi Zero 2 W Velocimetry Capability Benchmark")
    print("   Testing `velocimetry()` as-is across native resolutions")
    print(f"   Initial Baseline RAM: {get_peak_ram_mb():.1f} MB")
    print("=" * 80)

    for p in PROFILES:
        cfg_path = Path(p["config"])
        vid_path = Path(p["video"])

        if not cfg_path.exists() or not vid_path.exists():
            print(f"⚠️  Skipping {p['label']}: missing {cfg_path} or {vid_path}")
            continue

        print(f"\n▶️  Running {p['label']:18s} ({p['width']}x{p['height']})...")

        t0 = time.perf_counter()
        try:
            velocimetry(
                awive_fp=cfg_path,
                video_fp=vid_path,
                wlevel=args.wlevel,
            )
            elapsed = time.perf_counter() - t0
            peak_ram = get_peak_ram_mb()

            # Read result from data.yaml
            flow_val = 0.0
            vel_count = 0
            for p_yaml in [Path("data.yaml"), Path("/root/awive/data.yaml")]:
                if p_yaml.exists():
                    with open(p_yaml) as f:
                        d = yaml.safe_load(f)
                        flow_val = float(d.get("water_flow", 0.0))
                        vel_count = len(d.get("velocimetry", []))
                    break

            fps = 90.0 / max(elapsed, 1e-6)  # 90 frames test clip
            latency_ms = (elapsed / 90.0) * 1000.0

            print(
                f"   ✅ Done in {elapsed:.2f}s | {fps:.1f} FPS | "
                f"{latency_ms:.1f} ms/frame | Peak RAM: {peak_ram:.1f} MB | "
                f"Flow: {flow_val:.2f} m³/s"
            )

            results.append(
                {
                    "profile": p["id"],
                    "label": p["label"],
                    "width": p["width"],
                    "height": p["height"],
                    "elapsed_sec": round(elapsed, 3),
                    "fps": round(fps, 2),
                    "latency_ms": round(latency_ms, 1),
                    "peak_ram_mb": round(peak_ram, 1),
                    "water_flow": round(flow_val, 3),
                    "velocimetry_points": vel_count,
                }
            )
        except Exception as e:
            print(f"   ❌ Error during {p['label']}: {e}")

    # Write results CSV
    if results:
        fieldnames = list(results[0].keys())
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print("\n" + "=" * 80)
        print(f"📊 Benchmark Summary saved to: {args.output}")
        print("=" * 80)
        print(f"{'Profile':20s} {'Resolution':12s} {'Time (s)':10s} {'FPS':8s} {'Latency':12s} {'Peak RAM':10s}")
        print("-" * 80)
        for r in results:
            print(
                f"{r['label']:20s} {str(r['width'])+'x'+str(r['height']):12s} "
                f"{r['elapsed_sec']:<10.2f} {r['fps']:<8.1f} "
                f"{str(r['latency_ms'])+' ms':<12s} {str(r['peak_ram_mb'])+' MB':<10s}"
            )
        print("=" * 80)


if __name__ == "__main__":
    main()
