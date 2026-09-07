# ruff: noqa: E501
"""Real-time visualization and video generator for OTV across resolutions."""

import argparse
import asyncio
import math
import subprocess
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

from awive.algorithms.otv import (
    compute_velocity,
    draw_vectors,
    get_angle,
    get_magnitude,
)
from awive.config import Config
from awive.loader import make_loader
from awive.preprocess.correct_image import Formatter


class OTVVisualizerStream:
    """Processes frames and overlays real-time OTV velocimetry tracking."""

    def __init__(
        self,
        config: Config,
        target_shape: tuple[int, int],  # (width, height)
        name: str,
        scale: float,
    ) -> None:
        self.name = name
        self.scale = scale
        self.target_shape = target_shape
        self.scaled_cfg = config.scale_for_resolution(
            target_shape[0], target_shape[1], 3840, 2160
        )
        self.formatter = Formatter(
            self.scaled_cfg.dataset, self.scaled_cfg.preprocessing
        )
        self.detector = cv2.FastFeatureDetector_create()
        self.otv_cfg = self.scaled_cfg.otv
        self.ppm = self.scaled_cfg.preprocessing.ppm

        self.prev_frame = None
        self.prev_kps = []
        self.traj_start_kps = []
        self.traj_start_idx = []
        self.masks = []
        self.total_trajectories = 0
        self.current_mean_vel = 0.0
        self.frame_idx = 0

    def process_frame(
        self, raw_4k_frame: np.ndarray, fps: float = 30.0
    ) -> np.ndarray:
        """Track features on frame and return annotated visualization."""
        # 1. Resize input video frame if scale != 1.0
        if self.scale == 1.0:
            frame_in = raw_4k_frame
        else:
            frame_in = cv2.resize(raw_4k_frame, self.target_shape)

        # 2. Preprocess (lens undistort + orthorectify + crop ROI)
        curr_frame = self.formatter.apply(frame_in.copy())
        curr_kps = []
        recent_velocities = []

        # 3. Detect FAST features
        detected_kps = list(self.detector.detect(curr_frame, None))

        keypoints_to_add = min(
            self.otv_cfg.max_features - len(self.prev_kps), len(detected_kps)
        )
        if keypoints_to_add > 0:
            self.traj_start_idx.extend([self.frame_idx] * keypoints_to_add)
            if self.prev_frame is None:
                self.prev_kps.extend(detected_kps[:keypoints_to_add])
                self.traj_start_kps.extend(detected_kps[:keypoints_to_add])
            else:
                self.prev_kps.extend(detected_kps[-keypoints_to_add:])
                self.traj_start_kps.extend(detected_kps[-keypoints_to_add:])

        vis_frame = cv2.cvtColor(curr_frame, cv2.COLOR_GRAY2BGR)

        # 4. Predict keypoints with Lucas-Kanade
        if self.prev_frame is not None and len(self.prev_kps) > 0:
            pts2, kps_status, _ = cv2.calcOpticalFlowPyrLK(
                self.prev_frame,
                curr_frame,
                cv2.KeyPoint_convert(self.prev_kps),
                None,
                winSize=(self.otv_cfg.lk.winsize, self.otv_cfg.lk.winsize),
                maxLevel=self.otv_cfg.lk.max_level,
                criteria=(
                    cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                    self.otv_cfg.lk.max_count,
                    self.otv_cfg.lk.epsilon,
                ),
            )
            curr_kps = [cv2.KeyPoint(pt[0], pt[1], 1.0) for pt in pts2]

            k = 0
            for i in range(len(self.prev_kps)):
                if kps_status[i]:
                    mag = get_magnitude(self.prev_kps[i], curr_kps[i])
                    max_dist = self.otv_cfg.lk.max_level * (
                        2 * self.otv_cfg.lk.radius + 1
                    )
                    angle = get_angle(self.prev_kps[i], curr_kps[i])
                    if angle < 0:
                        angle += 360
                    valid_disp = (mag <= max_dist) and (
                        angle == 0
                        or angle == 360
                        or (
                            self.otv_cfg.partial_min_angle
                            <= angle
                            <= self.otv_cfg.partial_max_angle
                        )
                    )
                    if valid_disp:
                        self.prev_kps[k] = self.prev_kps[i]
                        curr_kps[k] = curr_kps[i]
                        self.traj_start_kps[k] = self.traj_start_kps[i]
                        self.traj_start_idx[k] = self.traj_start_idx[i]
                        k += 1
                        continue

                # Trajectory ended - validate trajectory
                tot_mag = get_magnitude(self.traj_start_kps[i], curr_kps[i])
                tot_angle = get_angle(self.traj_start_kps[i], curr_kps[i])
                if tot_angle < 0:
                    tot_angle += 360
                if tot_mag >= self.otv_cfg.final_min_distance and (
                    tot_angle == 0
                    or tot_angle == 360
                    or (
                        self.otv_cfg.final_min_angle
                        <= tot_angle
                        <= self.otv_cfg.final_max_angle
                    )
                ):
                    v = compute_velocity(
                        self.traj_start_kps[i],
                        curr_kps[i],
                        (1.0 / self.ppm),
                        self.frame_idx - self.traj_start_idx[i],
                        fps,
                    )
                    recent_velocities.append(v)
                    self.total_trajectories += 1

            self.prev_kps = self.prev_kps[:k]
            curr_kps = curr_kps[:k]
            self.traj_start_kps = self.traj_start_kps[:k]
            self.traj_start_idx = self.traj_start_idx[:k]

            if recent_velocities:
                self.current_mean_vel = float(np.mean(recent_velocities))

            # Draw vectors overlay
            vis_frame = draw_vectors(
                vis_frame, self.prev_kps, curr_kps, self.masks
            )

        self.prev_frame = curr_frame.copy()
        if curr_kps:
            self.prev_kps = curr_kps
        self.frame_idx += 1

        return vis_frame


def create_annotated_card(
    frame: np.ndarray,
    title: str,
    kps_count: int,
    trajs: int,
    vel: float,
    target_size: tuple[int, int] = (640, 640),
) -> np.ndarray:
    """Resize to target size and overlay professional HUD banner."""
    card = cv2.resize(frame, target_size)

    # Semi-transparent top HUD header
    hud_h = 75
    overlay = card.copy()
    cv2.rectangle(overlay, (0, 0), (target_size[0], hud_h), (20, 24, 30), -1)
    cv2.addWeighted(overlay, 0.75, card, 0.25, 0, card)

    # Title
    cv2.putText(
        card,
        title,
        (15, 28),
        cv2.FONT_HERSHEY_DUPLEX,
        0.75,
        (0, 240, 255),
        2,
        cv2.LINE_AA,
    )

    # Stats line
    stats_text = (
        f"KPs: {kps_count:4d}  |  Trajs: {trajs:5d}  |  Vel: {vel:.2f} m/s"
    )
    cv2.putText(
        card,
        stats_text,
        (15, 58),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )

    # Border
    cv2.rectangle(
        card, (0, 0), (target_size[0] - 1, target_size[1] - 1), (60, 60, 60), 1
    )
    return card


def build_comparison_video(
    config_path: Path = Path("/root/.config/nflow/awive.yaml"),
    num_frames: int = 90,
    output_video: Path = Path("experiments/otv_realtime_comparison.mp4"),
) -> None:
    """Generate 2x2 comparison video across 4K, 1080p, 720p, 480p."""
    base_cfg = Config.from_fp(config_path)
    loader = make_loader(base_cfg.dataset)

    streams = [
        OTVVisualizerStream(
            base_cfg, (3840, 2160), "4K Ultra HD (3840x2160)", 1.0
        ),
        OTVVisualizerStream(
            base_cfg, (1920, 1080), "1080p Full HD (1920x1080)", 0.5
        ),
        OTVVisualizerStream(
            base_cfg, (1280, 720), "720p HD (1280x720)", 1280 / 3840
        ),
        OTVVisualizerStream(
            base_cfg, (854, 480), "480p SD (854x480)", 854 / 3840
        ),
    ]

    # Video writer for 2x2 grid (1280 x 1280)
    grid_w, grid_h = 1280, 1280
    output_video.parent.mkdir(parents=True, exist_ok=True)
    temp_avi = output_video.with_suffix(".avi")
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    fps = loader.fps or 30.0
    writer = cv2.VideoWriter(str(temp_avi), fourcc, fps, (grid_w, grid_h))

    print(
        f"Processing {num_frames} frames from {base_cfg.dataset.video_fp} "
        "across 4 resolutions..."
    )
    t0 = time.time()

    for idx in range(num_frames):
        if not loader.has_images():
            break
        raw_frame = loader.read()
        if raw_frame is None:
            break

        cards = []
        for s in streams:
            vis = s.process_frame(raw_frame, fps=fps)
            card = create_annotated_card(
                vis,
                s.name,
                len(s.prev_kps),
                s.total_trajectories,
                s.current_mean_vel,
                target_size=(640, 640),
            )
            cards.append(card)

        # Assemble 2x2 grid
        top_row = np.hstack([cards[0], cards[1]])
        bot_row = np.hstack([cards[2], cards[3]])
        grid = np.vstack([top_row, bot_row])

        writer.write(grid)
        if (idx + 1) % 15 == 0 or idx == num_frames - 1:
            rate = (idx + 1) / (time.time() - t0)
            print(f"  Rendered frame {idx + 1}/{num_frames} ({rate:.1f} FPS)...")

    writer.release()
    loader.end()

    # Convert to web-playable MP4 with H.264
    print("Transcoding to fast H.264 MP4 for web and IDE playback...")

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(temp_avi),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "fast",
        "-crf",
        "23",
        str(output_video),
    ]
    subprocess.run(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )
    if temp_avi.exists():
        temp_avi.unlink()

    print(f"Comparison video successfully generated at: {output_video}")


# ---------------------------------------------------------------------------
# Live Web Stream Server (MJPEG)
# ---------------------------------------------------------------------------

_frame_lock = threading.Lock()
_latest_frames: dict[str, bytes] = {}
_is_running = True


def _video_processing_worker(config_path: Path) -> None:
    """Loop through video and update JPEG stream buffers."""
    base_cfg = Config.from_fp(config_path)

    while _is_running:
        loader = make_loader(base_cfg.dataset)
        fps = loader.fps or 30.0

        streams = [
            OTVVisualizerStream(
                base_cfg, (3840, 2160), "4K Ultra HD (3840x2160)", 1.0
            ),
            OTVVisualizerStream(
                base_cfg, (1920, 1080), "1080p Full HD (1920x1080)", 0.5
            ),
            OTVVisualizerStream(
                base_cfg, (1280, 720), "720p HD (1280x720)", 1280 / 3840
            ),
            OTVVisualizerStream(
                base_cfg, (854, 480), "480p SD (854x480)", 854 / 3840
            ),
        ]

        while _is_running and loader.has_images():
            raw_frame = loader.read()
            if raw_frame is None:
                break

            t0 = time.time()
            cards = []
            single_jpegs = {}
            for s, key in zip(
                streams, ["4k", "1080p", "720p", "480p"], strict=True
            ):
                vis = s.process_frame(raw_frame, fps=fps)
                card = create_annotated_card(
                    vis,
                    s.name,
                    len(s.prev_kps),
                    s.total_trajectories,
                    s.current_mean_vel,
                    target_size=(640, 640),
                )
                cards.append(card)
                _, buf = cv2.imencode(
                    ".jpg", card, [cv2.IMWRITE_JPEG_QUALITY, 80]
                )
                single_jpegs[key] = buf.tobytes()

            # 2x2 grid
            top_row = np.hstack([cards[0], cards[1]])
            bot_row = np.hstack([cards[2], cards[3]])
            grid = np.vstack([top_row, bot_row])
            # Resize grid to 960x960 for snappy web streaming
            grid_disp = cv2.resize(grid, (960, 960))
            _, grid_buf = cv2.imencode(
                ".jpg", grid_disp, [cv2.IMWRITE_JPEG_QUALITY, 80]
            )

            with _frame_lock:
                _latest_frames["grid"] = grid_buf.tobytes()
                _latest_frames.update(single_jpegs)

            # Cap stream to roughly match video FPS
            elapsed = time.time() - t0
            sleep_time = max(0.01, (1.0 / fps) - elapsed)
            time.sleep(sleep_time)

        loader.end()


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Real-Time OTV Velocimetry Across Resolutions</title>
  <style>
    body {
      margin: 0;
      padding: 20px;
      background: #0d1117;
      color: #e6edf3;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    h1 {
      margin: 0 0 8px 0;
      font-size: 22px;
      color: #58a6ff;
    }
    p.subtitle {
      margin: 0 0 16px 0;
      color: #8b949e;
      font-size: 14px;
    }
    .controls {
      margin-bottom: 16px;
      display: flex;
      gap: 10px;
    }
    button {
      background: #21262d;
      color: #c9d1d9;
      border: 1px solid #30363d;
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      font-size: 13px;
      transition: all 0.2s;
    }
    button:hover {
      background: #30363d;
      color: #ffffff;
      border-color: #8b949e;
    }
    button.active {
      background: #1f6feb;
      color: #ffffff;
      border-color: #58a6ff;
    }
    .stream-container {
      background: #161b22;
      padding: 10px;
      border-radius: 8px;
      border: 1px solid #30363d;
      box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    }
    img#stream {
      display: block;
      max-width: 90vw;
      max-height: 80vh;
      border-radius: 4px;
    }
    .legend {
      margin-top: 14px;
      display: flex;
      gap: 20px;
      font-size: 13px;
      color: #8b949e;
    }
    .legend span {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
    }
  </style>
</head>
<body>
  <h1>Live Optical Tracking Velocimetry (OTV)</h1>
  <p class="subtitle">Real-time comparison across resolutions on video_rimac.mp4</p>

  <div class="controls">
    <button class="active" onclick="setMode('grid')">2x2 Grid (All Resolutions)</button>
    <button onclick="setMode('4k')">4K UHD (3840x2160)</button>
    <button onclick="setMode('1080p')">1080p Full HD</button>
    <button onclick="setMode('720p')">720p HD</button>
    <button onclick="setMode('480p')">480p SD</button>
  </div>

  <div class="stream-container">
    <img id="stream" src="/stream?mode=grid" alt="Live OTV Stream">
  </div>

  <div class="legend">
    <span><span class="dot" style="background:#58a6ff"></span> Vectors: Velocity Colormap (Blue: Slow, Red: Fast)</span>
    <span><span class="dot" style="background:#3fb950"></span> Metric Grid: ppm = 100 px/m invariant</span>
  </div>

  <script>
    function setMode(mode) {
      document.querySelectorAll('button').forEach(b => b.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById('stream').src = '/stream?mode=' + mode + '&t=' + Date.now();
    }
  </script>
</body>
</html>
"""


class LiveStreamHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for live MJPEG streaming and web UI."""

    def do_GET(self) -> None:
        """Handle GET requests for web dashboard and MJPEG stream."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        mode = params.get("mode", ["grid"])[0]

        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        if parsed.path == "/stream":
            self.send_response(200)
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=frame"
            )
            self.end_headers()
            try:
                while _is_running:
                    with _frame_lock:
                        frame_bytes = _latest_frames.get(
                            mode
                        ) or _latest_frames.get("grid")

                    if frame_bytes:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n\r\n")
                        self.wfile.write(frame_bytes)
                        self.wfile.write(b"\r\n")
                    time.sleep(0.03)
            except (ConnectionResetError, BrokenPipeError):
                pass
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, log_fmt: str, *args: object) -> None:
        """Suppress standard HTTP request logging."""
        pass


def start_live_web_server(
    config_path: Path = Path("/root/.config/nflow/awive.yaml"),
    port: int = 8080,
) -> None:
    """Launch background OTV processor and live HTTP server."""
    # Start video processing in background daemon thread
    worker = threading.Thread(
        target=_video_processing_worker, args=(config_path,), daemon=True
    )
    worker.start()

    server = ThreadingHTTPServer(("0.0.0.0", port), LiveStreamHandler)
    print("=" * 70)
    print(f" LIVE OTV STREAMING SERVER RUNNING")
    print(f" Open in your browser:  http://localhost:{port}")
    print(f" (Or use your server IP / forwarded port {port})")
    print(" Press Ctrl+C to stop the server.")
    print("=" * 70)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="OTV Real-time Video Comparison Generator & Live Streamer"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("/root/.config/nflow/awive.yaml"),
        help="Path to awive config file",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Launch live interactive web browser stream",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for live web stream server (default: 8080)",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=90,
        help="Number of frames to render for video export (default 90 = 3 seconds)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/otv_realtime_comparison.mp4"),
        help="Path to save output video (when not in --serve mode)",
    )
    args = parser.parse_args()

    if args.serve:
        start_live_web_server(config_path=args.config, port=args.port)
    else:
        build_comparison_video(
            config_path=args.config,
            num_frames=args.frames,
            output_video=args.output,
        )
