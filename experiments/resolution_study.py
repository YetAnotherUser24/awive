"""Comprehensive evaluation of OTV velocimetry across video resolutions."""

import argparse
import json
import time
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from awive.algorithms.otv import OTV
from awive.algorithms.water_flow import get_water_flow
from awive.config import Config
from awive.loader import Loader, make_loader
from awive.preprocess.correct_image import Formatter


class MemoryLoader(Loader):
    """Memory-buffered frame loader for deterministic resolution benchmarks."""

    def __init__(self, frames: list[np.ndarray], fps: float = 30.0) -> None:
        """Initialize memory loader."""
        self.frames = frames
        self.fps = fps
        self.total_frames = len(frames) + 10
        self._index = 0
        self._width = frames[0].shape[1]
        self._height = frames[0].shape[0]

    @property
    def width(self) -> int:
        """Get frame width."""
        return self._width

    @property
    def height(self) -> int:
        """Get frame height."""
        return self._height

    def has_images(self) -> bool:
        """Check whether more frames are available."""
        return self._index < len(self.frames)

    def read(self) -> np.ndarray | None:
        """Read next frame from memory buffer."""
        if self._index >= len(self.frames):
            return None
        img = self.frames[self._index]
        self._index += 1
        return img

    def end(self) -> None:
        """Free resources."""
        pass


def run_resolution_study(
    config_path: Path,
    num_frames: int = 90,
    output_plot: Path = Path("experiments/resolution_comparison_rimac.png"),
    output_json: Path = Path("experiments/resolution_comparison_rimac.json"),
) -> dict:
    """Run OTV across multiple resolutions and compare metrics."""
    base_cfg = Config.from_fp(config_path)

    # 1. Load initial frames at native 4K
    print(f"Loading {num_frames} frames from {base_cfg.dataset.video_fp}...")
    loader = make_loader(base_cfg.dataset)
    frames_4k: list[np.ndarray] = []
    for _ in range(num_frames):
        if loader.has_images():
            frame = loader.read()
            if frame is not None:
                frames_4k.append(frame)
    loader.end()
    actual_frames = len(frames_4k)
    print(f"Loaded {actual_frames} frames (native 4K: {frames_4k[0].shape}).")

    resolutions = [
        {
            "name": "4K (3840x2160)",
            "width": 3840,
            "height": 2160,
            "scale": 1.0,
        },
        {
            "name": "1080p (1920x1080)",
            "width": 1920,
            "height": 1080,
            "scale": 0.5,
        },
        {
            "name": "720p (1280x720)",
            "width": 1280,
            "height": 720,
            "scale": 1280 / 3840,
        },
        {
            "name": "480p (854x480)",
            "width": 854,
            "height": 480,
            "scale": 854 / 3840,
        },
    ]

    results = {}
    ref_flow = None
    ref_vel = None

    for res in resolutions:
        name = res["name"]
        w, h = res["width"], res["height"]
        scale = res["scale"]
        print(f"\nEvaluating: {name} (scale: {scale:.3f})...")

        # Scale config calibration (GCPs and camera intrinsics)
        scaled_cfg = base_cfg.scale_for_resolution(w, h, 3840, 2160)

        # Prepare frames
        if scale == 1.0:
            res_frames = frames_4k
        else:
            res_frames = [cv2.resize(f, (w, h)) for f in frames_4k]

        t0 = time.time()
        formatter = Formatter(scaled_cfg.dataset, scaled_cfg.preprocessing)
        prev_gray = formatter.apply(res_frames[0].copy())

        # Feature detector diagnostics
        fast = cv2.FastFeatureDetector_create()
        initial_features = len(fast.detect(prev_gray, None))

        depths_positions = scaled_cfg.water_flow.profile.depths_array[:, :2]
        valid_depths = np.array(
            [p for p in depths_positions if p[0] > 0 and p[1] > 0]
        )

        mem_loader = MemoryLoader(res_frames[1:], fps=loader.fps or 30.0)
        otv = OTV(
            config_=scaled_cfg,
            prev_gray=prev_gray,
            formatter=formatter,
            lines=valid_depths[:, 1].tolist(),
        )

        otv_stats = otv.run(mem_loader, show_video=False)
        total_time = time.time() - t0
        fps = actual_frames / total_time

        # Extract per-region velocities
        sorted_keys = sorted(otv_stats.keys(), key=int)
        vels = [float(otv_stats[k]["velocity"]) for k in sorted_keys]
        counts = [int(otv_stats[k]["count"]) for k in sorted_keys]
        positions = [float(otv_stats[k]["position"]) for k in sorted_keys]

        # Calculate water flow
        wlevel = 0.8  # nominal depth level
        depths_m = scaled_cfg.water_flow.profile.depths_meters(
            ppm=scaled_cfg.preprocessing.ppm,
            resolution=scaled_cfg.preprocessing.resolution,
        )
        water_flow = float(
            get_water_flow(
                depths=depths_m,
                vels=np.array(vels, dtype=float),
                old_depth=scaled_cfg.water_flow.profile.height,
                roughness=scaled_cfg.water_flow.roughness,
                current_depth=wlevel,
            )
        )

        valid_vels = [v for v in vels if v > 0]
        mean_velocity = float(np.mean(valid_vels)) if valid_vels else 0.0
        total_trajectories = sum(counts)

        if ref_flow is None:
            ref_flow = water_flow
            ref_vel = mean_velocity
            flow_diff_pct = 0.0
            vel_diff_pct = 0.0
        else:
            flow_diff_pct = ((water_flow - ref_flow) / ref_flow) * 100.0
            vel_diff_pct = ((mean_velocity - ref_vel) / ref_vel) * 100.0

        results[name] = {
            "resolution": [w, h],
            "scale": scale,
            "fps": fps,
            "total_time_s": total_time,
            "initial_features": initial_features,
            "total_trajectories": total_trajectories,
            "mean_velocity_mps": mean_velocity,
            "vel_diff_pct": vel_diff_pct,
            "water_flow_m3s": water_flow,
            "flow_diff_pct": flow_diff_pct,
            "velocities": vels,
            "counts": counts,
            "positions_px": positions,
        }

        print(f"  FPS: {fps:.1f} | Runtime: {total_time:.2f}s")
        print(
            f"  Features: {initial_features} | "
            f"Trajectories: {total_trajectories}"
        )
        print(f"  Mean Vel: {mean_velocity:.3f} m/s ({vel_diff_pct:+.1f}%)")
        print(f"  Water Flow: {water_flow:.3f} m³/s ({flow_diff_pct:+.1f}%)")

    # Print summary table
    print("\n" + "=" * 88)
    print("                      MULTI-RESOLUTION BENCHMARK SUMMARY")
    print("=" * 88)
    hdr = (
        f"{'Resolution':<18} | {'FPS':<6} | {'Mean Vel':<10} | "
        f"{'Vel Diff':<9} | {'Flow (m³/s)':<11} | {'Flow Diff':<10} | "
        f"{'Trajs':<7}"
    )
    print(hdr)
    print("-" * 88)
    for name, r in results.items():
        print(
            f"{name:<18} | "
            f"{r['fps']:<6.1f} | "
            f"{r['mean_velocity_mps']:<10.3f} | "
            f"{r['vel_diff_pct']:>+7.1f}% | "
            f"{r['water_flow_m3s']:<11.3f} | "
            f"{r['flow_diff_pct']:>+8.1f}% | "
            f"{r['total_trajectories']:<7}"
        )
    print("=" * 88)

    # Save JSON report
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved metrics JSON to: {output_json}")

    # Generate 4-panel diagnostic plot
    generate_comparison_plot(results, base_cfg.preprocessing.ppm, output_plot)
    print(f"Saved comparison plot to: {output_plot}")

    return results


def generate_comparison_plot(
    results: dict, ppm: float, output_path: Path
) -> None:
    """Generate diagnostic multi-panel figure comparing resolutions."""
    res_names = list(results.keys())
    short_labels = ["4K", "1080p", "720p", "480p"]
    flows = [results[k]["water_flow_m3s"] for k in res_names]
    flow_diffs = [results[k]["flow_diff_pct"] for k in res_names]
    vels_mean = [results[k]["mean_velocity_mps"] for k in res_names]
    trajs = [results[k]["total_trajectories"] for k in res_names]
    features = [results[k]["initial_features"] for k in res_names]
    fps_vals = [results[k]["fps"] for k in res_names]

    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        "OTV Velocimetry Resolution Sensitivity Study (video_rimac.mp4)",
        fontsize=16,
        fontweight="bold",
    )

    # Panel 1: Water Flow & Error vs Resolution
    ax1 = axs[0, 0]
    color1 = "#1f77b4"
    ax1.plot(
        short_labels,
        flows,
        marker="o",
        linewidth=2.5,
        color=color1,
        label="Water Flow (m³/s)",
    )
    ax1.set_ylabel("Water Flow (m³/s)", color=color1, fontsize=12)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.grid(True, alpha=0.3)
    ax1.set_title(
        "Water Flow & Relative Error vs Resolution",
        fontsize=13,
        fontweight="semibold",
    )

    ax1_twin = ax1.twinx()
    color2 = "#d62728"
    ax1_twin.plot(
        short_labels,
        flow_diffs,
        marker="s",
        linestyle="--",
        linewidth=2,
        color=color2,
        label="Relative Deviation (%)",
    )
    ax1_twin.set_ylabel(
        "Relative Deviation from 4K (%)", color=color2, fontsize=12
    )
    ax1_twin.tick_params(axis="y", labelcolor=color2)
    for i, txt in enumerate(flow_diffs):
        ax1_twin.annotate(
            f"{txt:+.1f}%",
            (short_labels[i], flow_diffs[i]),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontweight="bold",
            color=color2,
        )

    # Panel 2: Cross-Sectional Velocity Profiles across River Transect
    ax2 = axs[0, 1]
    palette = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"]
    positions_px = results[res_names[0]]["positions_px"]
    positions_meters = [p / ppm for p in positions_px]

    for (_name, r), c, lbl in zip(
        results.items(), palette, short_labels, strict=True
    ):
        ax2.plot(
            positions_meters,
            r["velocities"],
            marker="o",
            markersize=4,
            linewidth=2,
            label=lbl,
            color=c,
        )
    ax2.set_xlabel("Cross-Section Position across River (meters)", fontsize=11)
    ax2.set_ylabel("Surface Velocity (m/s)", fontsize=11)
    ax2.set_title(
        "Transect Velocity Distribution across Width",
        fontsize=13,
        fontweight="semibold",
    )
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper left")

    # Panel 3: Trajectory & Feature Count
    ax3 = axs[1, 0]
    x_pos = np.arange(len(short_labels))
    width = 0.35
    ax3.bar(
        x_pos - width / 2,
        features,
        width,
        label="FAST Features Detected",
        color="#4c72b0",
    )
    ax3.bar(
        x_pos + width / 2,
        trajs,
        width,
        label="Valid Trajectories Tracked",
        color="#55a868",
    )
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(short_labels)
    ax3.set_ylabel("Count", fontsize=11)
    ax3.set_title(
        "Feature & Trajectory Density", fontsize=13, fontweight="semibold"
    )
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    # Panel 4: Processing Speed & Throughput
    ax4 = axs[1, 1]
    ax4.bar(short_labels, fps_vals, color="#8172b3", width=0.5)
    for i, val in enumerate(fps_vals):
        ax4.text(
            i, val + 0.5, f"{val:.1f} FPS", ha="center", fontweight="bold"
        )
    ax4.set_ylabel("Throughput (Frames / Second)", fontsize=11)
    ax4.set_title(
        "Processing Speed (Throughput)", fontsize=13, fontweight="semibold"
    )
    ax4.set_ylim(0, max(fps_vals) * 1.2)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multi-resolution evaluation for OTV."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("awive.yaml"),
        help="Path to awive.yaml config",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=90,
        help="Number of frames to evaluate (default: 90 frames = 3 seconds)",
    )
    parser.add_argument(
        "--output-plot",
        type=Path,
        default=Path("experiments/resolution_comparison_rimac.png"),
        help="Output path for comparison plot",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("experiments/resolution_comparison_rimac.json"),
        help="Output path for metrics JSON",
    )
    parser.add_argument(
        "--plot-only",
        action="store_true",
        help="Regenerate plot from existing JSON without re-running OTV",
    )
    args = parser.parse_args()

    if args.plot_only and args.output_json.exists():
        print(f"Loading cached metrics from {args.output_json}...")
        with open(args.output_json) as f:
            cached_results = json.load(f)
        base_cfg = Config.from_fp(args.config)
        generate_comparison_plot(
            cached_results, base_cfg.preprocessing.ppm, args.output_plot
        )
        print(f"Regenerated plot at {args.output_plot}")
    else:
        run_resolution_study(
            config_path=args.config,
            num_frames=args.frames,
            output_plot=args.output_plot,
            output_json=args.output_json,
        )
