"""Prepare self-contained Raspberry Pi Zero 2 W benchmark package.

Pre-renders native resolution test videos (1080p, 720p, 480p, 360p) and
generates corresponding pre-scaled awive YAML configs into `rpi_package/`
so that `velocimetry` can be executed directly as-is on the Pi Zero 2 W SD card.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import yaml

from awive.config import Config

DEFAULT_SOURCE_VIDEO = Path(
    "old_experiments/videos/sample_videos/pt01_20260201_1000_1KolOFV0wcm1eJ8wkXkgbdLkNT07b5sNr.mp4"
)
DEFAULT_CONFIG_PATH = Path("awive.yaml")
DEFAULT_OUTPUT_DIR = Path("rpi_package")

PROFILES = [
    {
        "id": "1080p_fhd",
        "label": "1080p FHD",
        "video_name": "video_1080p.mp4",
        "config_name": "awive_1080p.yaml",
        "width": 1920,
        "height": 1080,
        "min_dist": 8,
        "winsize": 15,
        "min_eig": 0.0010,
    },
    {
        "id": "720p_default",
        "label": "720p HD Default",
        "video_name": "video_720p.mp4",
        "config_name": "awive_720p_default.yaml",
        "width": 1280,
        "height": 720,
        "min_dist": 8,
        "winsize": 15,
        "min_eig": 0.0010,
    },
    {
        "id": "720p_tuned",
        "label": "720p HD Tuned",
        "video_name": "video_720p.mp4",
        "config_name": "awive_720p_tuned.yaml",
        "width": 1280,
        "height": 720,
        "min_dist": 3,
        "winsize": 21,
        "min_eig": 0.0005,
    },
    {
        "id": "480p_tuned",
        "label": "480p SD Tuned",
        "video_name": "video_480p.mp4",
        "config_name": "awive_480p_tuned.yaml",
        "width": 854,
        "height": 480,
        "min_dist": 2,
        "winsize": 25,
        "min_eig": 0.0005,
    },
    {
        "id": "360p_tuned",
        "label": "360p Low Tuned",
        "video_name": "video_360p.mp4",
        "config_name": "awive_360p_tuned.yaml",
        "width": 640,
        "height": 360,
        "min_dist": 2,
        "winsize": 25,
        "min_eig": 0.0005,
    },
]


def extract_raw_frames(source_video: Path, num_frames: int = 90) -> list:
    """Read a fixed number of raw frames from source video."""
    cap = cv2.VideoCapture(str(source_video))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open source video: {source_video}")

    frames = []
    while len(frames) < num_frames:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        frames.append(frame)
    cap.release()
    return frames


def render_video(
    frames: list, target_path: Path, width: int, height: int, fps: float = 30.0
) -> None:
    """Resize frames to target resolution and encode as standard H.264 MP4."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".tmp.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(temp_path), fourcc, fps, (width, height))
    for f in frames:
        resized = cv2.resize(f, (width, height), interpolation=cv2.INTER_AREA)
        out.write(resized)
    out.release()

    # Transcode to standard H.264 (yuv420p, faststart) for universal playback
    import subprocess
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(temp_path),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "fast",
        "-movflags", "+faststart",
        str(target_path),
    ]
    subprocess.run(cmd, check=True)
    temp_path.unlink(missing_ok=True)


def generate_package(
    source_video: Path = DEFAULT_SOURCE_VIDEO,
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    num_frames: int = 90,
) -> None:
    """Generate the complete rpi_package folder."""
    output_dir.mkdir(parents=True, exist_ok=True)
    videos_dir = output_dir / "videos"
    configs_dir = output_dir / "configs"
    videos_dir.mkdir(parents=True, exist_ok=True)
    configs_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(f"📦 Generating Raspberry Pi Zero 2 W Benchmark Package in: {output_dir}")
    print("=" * 80)

    print(f"\n1. Reading {num_frames} frames from source video: {source_video.name}...")
    frames = extract_raw_frames(source_video, num_frames=num_frames)
    print(f"   Loaded {len(frames)} source frames ({frames[0].shape[1]}x{frames[0].shape[0]}).")

    # Render distinct resolution video files
    rendered_resolutions: set[tuple[int, int]] = set()
    print("\n2. Encoding native resolution test video files...")
    for p in PROFILES:
        res_key = (p["width"], p["height"])
        if res_key not in rendered_resolutions:
            vid_path = videos_dir / p["video_name"]
            print(f"   • Encoding {p['video_name']} ({p['width']}x{p['height']})...")
            render_video(frames, vid_path, p["width"], p["height"])
            rendered_resolutions.add(res_key)

    # Generate pre-scaled configs
    print(f"\n3. Generating pre-scaled awive YAML configurations from {config_path.name}...")
    base_cfg = Config.from_fp(config_path)

    for p in PROFILES:
        scaled = base_cfg.scale_for_resolution(p["width"], p["height"])
        scaled.otv.final_min_distance = p["min_dist"]
        scaled.otv.lk.winsize = p["winsize"]
        scaled.otv.lk.min_eigen_threshold = p["min_eig"]

        # Ensure local relative video path in config
        scaled.dataset.video_fp = Path("videos") / p["video_name"]

        cfg_file = configs_dir / p["config_name"]
        data_dump = scaled.model_dump(mode="json")
        cfg_file.write_text(yaml.dump(data_dump, indent=4))
        print(
            f"   • {p['config_name']}: {p['width']}x{p['height']} | "
            f"dmin={p['min_dist']} | winsize={p['winsize']} | min_eig={p['min_eig']}"
        )

    # Create the standalone lightweight benchmark runner
    runner_py = output_dir / "benchmark.py"
    runner_py.write_text(
        r'''"""Zero-heavy-dependency benchmark runner for Raspberry Pi Zero 2 W.

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
'''
    )

    # Create 1-click shell runner
    run_sh = output_dir / "run_benchmark.sh"
    run_sh.write_text(
        """#!/usr/bin/env bash
set -e
echo "=================================================================="
echo "🍓 Launching Raspberry Pi Zero 2 W Velocimetry Benchmark"
echo "=================================================================="
python3 benchmark.py "$@"
"""
    )
    run_sh.chmod(0o755)

    # Create README with setup instructions
    readme_md = output_dir / "README.md"
    readme_md.write_text(
        """# Raspberry Pi Zero 2 W Benchmark Package

This package benchmarks the native resolution handling capabilities of a **Raspberry Pi Zero 2 W** (512 MB RAM) running the unmodified `awive.algorithms.velocimetry` pipeline.

## Contents
- `videos/`: Pre-rendered native resolution MP4 test video clips (1080p, 720p, 480p, 360p, 90 frames each).
- `configs/`: Pre-scaled `awive_*.yaml` configuration files matching the video dimensions.
- `benchmark.py`: Lightweight test runner (pure stdlib + cv2/numpy, zero pandas/matplotlib).
- `run_benchmark.sh`: 1-click execution script.

## Quick Start on Raspberry Pi Zero 2 W

### 1. System Setup (Run Once on the Pi)
```bash
# Install precompiled system binaries (< 1 minute, 0 MB build compilation RAM)
sudo apt update && sudo apt install -y python3-opencv python3-numpy python3-pydantic python3-yaml git

# Clone repo and set up virtual environment
git clone -b dev https://github.com/YetAnotherUser24/awive.git
cd awive
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --no-deps -e .
```

### 2. Copy Package & Run Benchmark
Copy the `rpi_package` directory to your Pi (via SD card, USB flash, or scp):
```bash
# On the Pi:
cd path/to/rpi_package
source /path/to/awive/.venv/bin/activate

# Execute 1-click benchmark
./run_benchmark.sh
```

### 3. Output
The script prints execution time, frame rate (FPS), per-frame latency, and peak resident RAM (`resource.ru_maxrss`), saving a summary to `rpi_zero_results.csv`.
"""
    )

    print(f"\n✅ Package successfully generated in: {output_dir}")
    print(f"   • Videos: {len(rendered_resolutions)} native MP4 files in {videos_dir}")
    print(f"   • Configs: {len(PROFILES)} YAML files in {configs_dir}")
    print(f"   • Runner: {runner_py}")
    print(f"   • Shell Launcher: {run_sh}")
    print(f"   • README: {readme_md}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare RPi Zero 2 W Benchmark Package")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_VIDEO)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--frames", type=int, default=90)
    args = parser.parse_args()

    generate_package(
        source_video=args.source,
        config_path=args.config,
        output_dir=args.output,
        num_frames=args.frames,
    )


if __name__ == "__main__":
    main()
