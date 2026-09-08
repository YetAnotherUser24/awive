"""Downloader for sample benchmark videos from Google Drive."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SAMPLE_POINTS = [
    {
        "point": 1,
        "date_local": "2026-02-02 10:00",
        "date_slug": "20260202_1000",
        "timestamp_dt": "2026-02-02 15:00:17+00:00",
        "q_ref": 62.62,
        "regime": "Peak Flood",
        "video_id": "1p5098AJpcwbDUYdnOxyPqkvUoecxw3Km",
    },
    {
        "point": 2,
        "date_local": "2026-02-03 14:00",
        "date_slug": "20260203_1400",
        "timestamp_dt": "2026-02-03 19:00:17+00:00",
        "q_ref": 59.63,
        "regime": "Peak Flood",
        "video_id": "1dvQeFxORCrq1wW7QRjhHx-f81ZUM_BLp",
    },
    {
        "point": 3,
        "date_local": "2026-02-04 14:00",
        "date_slug": "20260204_1400",
        "timestamp_dt": "2026-02-04 19:00:16+00:00",
        "q_ref": 56.04,
        "regime": "High Flow",
        "video_id": "1BZdDVRGsgqirCS7iJFDUm28M_Gt6iryu",
    },
    {
        "point": 4,
        "date_local": "2026-02-05 18:00",
        "date_slug": "20260205_1800",
        "timestamp_dt": "2026-02-05 23:00:16+00:00",
        "q_ref": 46.20,
        "regime": "Medium-High Flow",
        "video_id": "1jgENkCJQTb5GvtrgP5tdUtnPcMCj5HUj",
    },
    {
        "point": 5,
        "date_local": "2026-02-01 14:00",
        "date_slug": "20260201_1400",
        "timestamp_dt": "2026-02-01 19:00:17+00:00",
        "q_ref": 42.87,
        "regime": "Medium Flow",
        "video_id": "1QE-D1iM_yxDwWnJpqvRGACmZHwv7Vezr",
    },
    {
        "point": 6,
        "date_local": "2026-02-01 10:00",
        "date_slug": "20260201_1000",
        "timestamp_dt": "2026-02-01 15:00:16+00:00",
        "q_ref": 39.88,
        "regime": "Medium Flow",
        "video_id": "1KolOFV0wcm1eJ8wkXkgbdLkNT07b5sNr",
    },
    {
        "point": 7,
        "date_local": "2026-02-05 10:00",
        "date_slug": "20260205_1000",
        "timestamp_dt": "2026-02-05 15:00:17+00:00",
        "q_ref": 37.19,
        "regime": "Recession Flow",
        "video_id": "116_vMc1N9kGHv2ukpQOzrCy_8MRur7Zg",
    },
    {
        "point": 8,
        "date_local": "2026-02-07 14:00",
        "date_slug": "20260207_1400",
        "timestamp_dt": "2026-02-07 19:00:17+00:00",
        "q_ref": 32.70,
        "regime": "Low Base Flow",
        "video_id": "16_BZLJv2-xb2TyIZ-Z6NpP5PLuKmUgE7",
    },
    {
        "point": 9,
        "date_local": "2026-02-09 10:00",
        "date_slug": "20260209_1000",
        "timestamp_dt": "2026-02-09 15:00:16+00:00",
        "q_ref": 31.50,
        "regime": "Low Base Flow",
        "video_id": "1atmk-h-4GL1psGytEB6r1hqt_L3kqB6i",
    },
    {
        "point": 10,
        "date_local": "2026-02-12 14:00",
        "date_slug": "20260212_1400",
        "timestamp_dt": "2026-02-12 19:00:17+00:00",
        "q_ref": 30.30,
        "regime": "Base Flow (Min)",
        "video_id": "1ELk1hKP3MlXsdWaCCS-QbWdTkpziWX6-",
    },
]

DEFAULT_OUTPUT_DIR = Path("old_experiments/videos/sample_videos")
DEFAULT_CREDS_PATH = Path("credentials.json")


def get_drive_token(creds_path: Path = DEFAULT_CREDS_PATH) -> str:
    """Acquire OAuth2 bearer token from service account credentials."""
    if not creds_path.exists():
        raise FileNotFoundError(f"Credentials file not found: {creds_path}")
    creds = service_account.Credentials.from_service_account_file(
        str(creds_path),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError(
            "Failed to obtain OAuth2 token from service account"
        )
    return creds.token


def download_video(
    video_id: str,
    dest_path: Path,
    token: str,
    chunk_size: int = 10 * 1024 * 1024,
) -> bool:
    """Download a video file from Google Drive via direct HTTP streaming."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists() and dest_path.stat().st_size > 1024 * 1024:
        print(
            f"  ⚡ Already exists: {dest_path.name} ({dest_path.stat().st_size / (1024 * 1024):.1f} MB)"
        )
        return True

    url = f"https://www.googleapis.com/drive/v3/files/{video_id}?alt=media"
    headers = {"Authorization": f"Bearer {token}"}

    print(f"  ⬇️  Downloading {video_id} -> {dest_path.name}...")
    try:
        with requests.get(
            url, headers=headers, stream=True, timeout=60
        ) as resp:
            resp.raise_for_status()
            total_bytes = 0
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        total_bytes += len(chunk)
        print(
            f"  ✅ Downloaded {dest_path.name} ({total_bytes / (1024 * 1024):.1f} MB)"
        )
        return True
    except Exception as err:
        print(f"  ❌ Error downloading {video_id}: {err}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download sample benchmark videos"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of points to download (1-10)",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--creds", type=Path, default=DEFAULT_CREDS_PATH)
    args = parser.parse_args()

    points_to_download = SAMPLE_POINTS[: args.count]
    print(f"Obtaining Drive API token using {args.creds}...")
    token = get_drive_token(args.creds)

    print(
        f"Downloading {len(points_to_download)} videos to {args.output_dir}:"
    )
    success_count = 0
    for item in points_to_download:
        dest_filename = (
            f"pt{item['point']:02d}_{item['date_slug']}_{item['video_id']}.mp4"
        )
        dest_path = args.output_dir / dest_filename
        item["local_path"] = str(dest_path)
        print(
            f"[{item['point']}/{len(points_to_download)}] {item['date_local']} ({item['regime']}, Q_ref={item['q_ref']} m³/s)"
        )
        if download_video(item["video_id"], dest_path, token):
            success_count += 1

    print(
        f"\nCompleted: {success_count}/{len(points_to_download)} videos ready."
    )
    if success_count < len(points_to_download):
        sys.exit(1)


if __name__ == "__main__":
    main()
