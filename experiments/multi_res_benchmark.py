"""Multi-resolution OTV benchmark on 10 representative SENAMHI observation points."""

from __future__ import annotations

import argparse
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from awive.algorithms.otv import OTV
from awive.algorithms.water_flow import get_water_flow
from awive.config import Config
from awive.preprocess.correct_image import Formatter
from experiments.download_sample_videos import SAMPLE_POINTS

DEFAULT_CONFIG_PATH = Path("awive.yaml")
DEFAULT_SAMPLE_DIR = Path("old_experiments/videos/sample_videos")
DEFAULT_LEVEL_CSV = Path("_Reporte/Senamhi_data_level.csv")
DEFAULT_REPORTE_CSV = Path("_Reporte/Reporte.csv")
DEFAULT_OUTPUT_CSV = Path(
    "experiments/output/multi_resolution_benchmark_full_36pts.csv"
)
REPORTE_DIR_CSV = Path("_Reporte/multi_resolution_benchmark_full_36pts.csv")

RESOLUTIONS_TO_EVALUATE = [
    {
        "name": "4k_default",
        "width": 3840,
        "height": 2160,
        "min_dist": 8,
        "winsize": 15,
        "min_eig": 0.001,
    },
    {
        "name": "1080p_default",
        "width": 1920,
        "height": 1080,
        "min_dist": 8,
        "winsize": 15,
        "min_eig": 0.001,
    },
    {
        "name": "720p_default",
        "width": 1280,
        "height": 720,
        "min_dist": 8,
        "winsize": 15,
        "min_eig": 0.001,
    },
    {
        "name": "720p_tuned",
        "width": 1280,
        "height": 720,
        "min_dist": 3,
        "winsize": 21,
        "min_eig": 0.0005,
    },
    {
        "name": "480p_tuned",
        "width": 854,
        "height": 480,
        "min_dist": 2,
        "winsize": 25,
        "min_eig": 0.0005,
    },
]


class MemoryLoader:
    """In-memory frame generator compatible with OTV loader interface."""

    def __init__(self, frames: list[np.ndarray], fps: float = 30.0) -> None:
        self.frames = frames
        self.fps = fps
        self.total_frames = len(frames) + 10
        self._index = 0
        self._width = frames[0].shape[1]
        self._height = frames[0].shape[0]

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def index(self) -> int:
        return self._index

    def has_images(self) -> bool:
        return self._index < len(self.frames)

    def read(self) -> np.ndarray | None:
        if self._index >= len(self.frames):
            return None
        img = self.frames[self._index]
        self._index += 1
        return img

    def end(self) -> None:
        pass


@dataclass
class PointBenchmarkResult:
    point: int
    date_local: str
    timestamp_dt: str
    regime: str
    video_id: str
    q_reference: float
    q_lspiv: float
    water_level_used: float
    res_name: str
    width: int
    height: int
    final_min_distance: int
    lk_winsize: int
    lk_min_eigen: float
    water_flow: float
    mean_velocity: float
    num_trajectories: int
    initial_features: int
    elapsed_sec: float
    fps: float
    flow_err: float
    flow_err_pct: float
    flow_err_lspiv: float


def load_sample_points_metadata(
    reporte_csv: Path = DEFAULT_REPORTE_CSV,
    level_csv: Path = DEFAULT_LEVEL_CSV,
) -> list[dict]:
    """Load sample points with aligned water levels and reference flows."""
    df_rep = pd.read_csv(reporte_csv)
    df_rep["timestamp_dt"] = pd.to_datetime(df_rep["timestamp_utc"], utc=True)

    df_lvl = pd.read_csv(level_csv)
    df_lvl["level_dt"] = pd.to_datetime(df_lvl["timestamp"], utc=True)
    df_lvl = df_lvl.sort_values("level_dt")

    enriched = []
    for sp in SAMPLE_POINTS:
        item = dict(sp)
        sp_dt = pd.to_datetime(sp["timestamp_dt"], utc=True)

        diffs_rep = (df_rep["timestamp_dt"] - sp_dt).abs()
        nearest_rep_idx = diffs_rep.idxmin()
        if (
            diffs_rep.loc[nearest_rep_idx] <= pd.Timedelta(minutes=60)
            and "Q_med" in df_rep.columns
        ):
            item["q_lspiv"] = float(df_rep.loc[nearest_rep_idx]["Q_med"])
        else:
            item["q_lspiv"] = float("nan")

        diffs = (df_lvl["level_dt"] - sp_dt).abs()
        nearest_idx = diffs.idxmin()
        if diffs.loc[nearest_idx] <= pd.Timedelta(minutes=60):
            item["water_level"] = float(df_lvl.loc[nearest_idx]["water_level"])
        else:
            item["water_level"] = 0.50

        enriched.append(item)
    return enriched


def preload_raw_frames(
    video_path: Path, num_frames: int = 90
) -> list[np.ndarray]:
    """Preload raw frames from video using OpenCV."""
    cap = cv2.VideoCapture(str(video_path))
    frames = []
    while len(frames) < num_frames:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        frames.append(frame)
    cap.release()
    return frames


def evaluate_single_resolution(
    base_cfg: Config,
    res_spec: dict,
    raw_frames: list[np.ndarray],
    water_level: float,
) -> tuple[float, float, int, int, float, float]:
    """Run OTV for one resolution spec and return metrics."""
    scaled_cfg = base_cfg.scale_for_resolution(
        res_spec["width"], res_spec["height"]
    )
    scaled_cfg.otv.final_min_distance = res_spec["min_dist"]
    scaled_cfg.otv.lk.winsize = res_spec.get("winsize", 15)
    scaled_cfg.otv.lk.min_eigen_threshold = res_spec.get("min_eig", 0.001)

    target_w = res_spec["width"]
    target_h = res_spec["height"]

    # Resize raw frames to target resolution if needed
    res_frames = []
    for f in raw_frames:
        if f.shape[1] != target_w or f.shape[0] != target_h:
            resized = cv2.resize(
                f, (target_w, target_h), interpolation=cv2.INTER_AREA
            )
            res_frames.append(resized)
        else:
            res_frames.append(f)

    formatter = Formatter(
        scaled_cfg.dataset,
        scaled_cfg.preprocessing,
        sample_image=res_frames[0],
    )
    prev_gray = formatter.apply(res_frames[0].copy())

    fast = cv2.FastFeatureDetector_create()
    initial_features = len(fast.detect(prev_gray, None))

    depths_positions = scaled_cfg.water_flow.profile.depths_array[:, :2]
    valid_depths = np.array(
        [p for p in depths_positions if p[0] > 0 and p[1] > 0]
    )

    mem_loader = MemoryLoader(res_frames[1:], fps=30.0)
    otv = OTV(
        config_=scaled_cfg,
        prev_gray=prev_gray,
        formatter=formatter,
        lines=valid_depths[:, 1].tolist(),
    )

    t0 = time.perf_counter()
    otv_stats = otv.run(mem_loader, show_video=False)
    elapsed = time.perf_counter() - t0
    fps = len(res_frames) / max(elapsed, 1e-6)

    # Extract velocities and counts
    sorted_keys = sorted(otv_stats.keys(), key=int)
    vels = [float(otv_stats[k]["velocity"]) for k in sorted_keys]
    counts = [int(otv_stats[k]["count"]) for k in sorted_keys]
    total_traj = sum(counts)
    mean_vel = float(np.mean(vels)) if vels else 0.0

    depths_m = scaled_cfg.water_flow.profile.depths_meters(
        ppm=scaled_cfg.preprocessing.ppm,
        resolution=scaled_cfg.preprocessing.resolution,
    )

    flow = float(
        get_water_flow(
            depths=depths_m,
            vels=np.array(vels, dtype=float),
            old_depth=scaled_cfg.water_flow.profile.height,
            roughness=scaled_cfg.water_flow.roughness,
            current_depth=water_level,
        )
    )

    return flow, mean_vel, total_traj, initial_features, elapsed, fps


def run_benchmark(
    frames_per_video: int = 90,
    sample_dir: Path = DEFAULT_SAMPLE_DIR,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    max_points: int = 10,
) -> pd.DataFrame:
    """Execute the multi-resolution benchmark across sample videos."""
    points = load_sample_points_metadata()[:max_points]
    base_cfg = Config.from_fp(DEFAULT_CONFIG_PATH)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    REPORTE_DIR_CSV.parent.mkdir(parents=True, exist_ok=True)

    results: list[PointBenchmarkResult] = []

    print("=" * 80)
    print(
        f"🚀 Running Multi-Resolution Benchmark ({len(points)} Points, {frames_per_video} frames/video)"
    )
    print("=" * 80)

    for pt in points:
        video_pattern = f"pt{pt['point']:02d}_*_{pt['video_id']}.mp4"
        found_videos = list(sample_dir.glob(video_pattern))
        if not found_videos:
            print(
                f"⚠️  Video not found for Point {pt['point']} ({pt['video_id']}), skipping..."
            )
            continue

        video_path = found_videos[0]
        print(
            f"\n▶️  Point {pt['point']:02d}: {pt['date_local']} | {pt['regime']} | Q_ref = {pt['q_ref']:.2f} m³/s | Level = {pt['water_level']:.2f}m"
        )
        print(f"    File: {video_path.name}")

        t_load = time.perf_counter()
        raw_frames = preload_raw_frames(
            video_path, num_frames=frames_per_video
        )
        print(
            f"    Loaded {len(raw_frames)} frames in {time.perf_counter() - t_load:.2f}s"
        )

        for r_spec in RESOLUTIONS_TO_EVALUATE:
            flow, mean_vel, num_traj, init_kps, elapsed, fps = (
                evaluate_single_resolution(
                    base_cfg, r_spec, raw_frames, pt["water_level"]
                )
            )

            err = flow - pt["q_ref"]
            err_pct = (err / pt["q_ref"]) * 100.0
            err_lspiv = (
                flow - pt["q_lspiv"]
                if not np.isnan(pt["q_lspiv"])
                else float("nan")
            )

            print(
                f"    • {r_spec['name']:14s} ({r_spec['width']}x{r_spec['height']}|dmin={r_spec['min_dist']}): "
                f"Q = {flow:6.2f} m³/s ({err_pct:+5.1f}%) | "
                f"Vel = {mean_vel:.2f} m/s | "
                f"Traj = {num_traj:5d} | "
                f"FPS = {fps:4.1f}"
            )

            results.append(
                PointBenchmarkResult(
                    point=pt["point"],
                    date_local=pt["date_local"],
                    timestamp_dt=pt["timestamp_dt"],
                    regime=pt["regime"],
                    video_id=pt["video_id"],
                    q_reference=pt["q_ref"],
                    q_lspiv=pt["q_lspiv"],
                    water_level_used=pt["water_level"],
                    res_name=r_spec["name"],
                    width=r_spec["width"],
                    height=r_spec["height"],
                    final_min_distance=r_spec["min_dist"],
                    lk_winsize=r_spec.get("winsize", 15),
                    lk_min_eigen=r_spec.get("min_eig", 0.001),
                    water_flow=flow,
                    mean_velocity=mean_vel,
                    num_trajectories=num_traj,
                    initial_features=init_kps,
                    elapsed_sec=elapsed,
                    fps=fps,
                    flow_err=err,
                    flow_err_pct=err_pct,
                    flow_err_lspiv=err_lspiv,
                )
            )

    df_results = pd.DataFrame([asdict(r) for r in results])
    df_results.to_csv(output_csv, index=False)
    mirror_csv = Path("_Reporte") / output_csv.name
    mirror_csv.parent.mkdir(parents=True, exist_ok=True)
    df_results.to_csv(mirror_csv, index=False)
    print("\n" + "=" * 80)
    print("✅ Benchmark completed! Results saved to:")
    print(f"   • {output_csv}")
    print(f"   • {mirror_csv}")
    print("=" * 80)
    return df_results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-Resolution OTV Benchmark"
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=90,
        help="Frames per video (default: 90 = 3s)",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=36,
        help="Number of observation points (1-36, default: 36)",
    )
    parser.add_argument("--sample-dir", type=Path, default=DEFAULT_SAMPLE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_CSV)
    args = parser.parse_args()

    run_benchmark(
        frames_per_video=args.frames,
        sample_dir=args.sample_dir,
        output_csv=args.output,
        max_points=args.max_points,
    )


if __name__ == "__main__":
    main()
