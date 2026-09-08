"""Downloader for sample benchmark videos from Google Drive."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import pandas as pd
import requests

DEFAULT_REPORTE_CSV = Path("_Reporte/Reporte.csv")
DEFAULT_FLOW_CSV = Path(
    "_Reporte/flow_validation_results_20260201_20260212_10_14_18_local_clip60s.csv"
)
DEFAULT_OUTPUT_DIR = Path("old_experiments/videos/sample_videos")
DEFAULT_CREDS_PATH = Path("credentials.json")


def get_all_report_points(
    reporte_csv: Path = DEFAULT_REPORTE_CSV,
    flow_csv: Path = DEFAULT_FLOW_CSV,
) -> list[dict]:
    """Dynamically load and map all 36 observation points from report CSVs."""
    if not reporte_csv.exists() or not flow_csv.exists():
        return []

    df_rep = pd.read_csv(reporte_csv)
    df_flow = pd.read_csv(flow_csv)
    df_rep["dt"] = pd.to_datetime(df_rep["timestamp_utc"], utc=True)
    df_flow["dt"] = pd.to_datetime(df_flow["timestamp_dt"], utc=True)

    points = []
    for idx, row in df_rep.iterrows():
        diffs = (df_flow["dt"] - row["dt"]).abs()
        nearest = diffs.idxmin()
        dt_val = row["dt"]
        dt_local = dt_val - pd.Timedelta(hours=5)
        q_ref = float(row["Q_referencia"])
        regime = (
            "Peak Flood"
            if q_ref >= 55.0
            else ("Medium Flow" if q_ref >= 38.0 else "Base Flow")
        )
        points.append(
            {
                "point": idx + 1,
                "date_local": dt_local.strftime("%Y-%m-%d %H:%M"),
                "date_slug": dt_local.strftime("%Y%m%d_%H%M"),
                "timestamp_dt": str(dt_val),
                "q_ref": q_ref,
                "q_lspiv": (
                    float(row["Q_med"])
                    if pd.notna(row["Q_med"])
                    else float("nan")
                ),
                "regime": regime,
                "video_id": str(df_flow.loc[nearest, "video_id"]),
            }
        )
    return points


SAMPLE_POINTS = get_all_report_points()


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
        raise RuntimeError("Failed to obtain OAuth2 token from service account")
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
            f"  ⚡ Already exists: {dest_path.name} "
            f"({dest_path.stat().st_size / (1024 * 1024):.1f} MB)"
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
            f"  ✅ Downloaded {dest_path.name} "
            f"({total_bytes / (1024 * 1024):.1f} MB)"
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
        default=36,
        help="Number of points to download (1-36, default: 36)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all 36 points",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--creds", type=Path, default=DEFAULT_CREDS_PATH)
    args = parser.parse_args()

    all_pts = get_all_report_points()
    count = len(all_pts) if args.all else min(args.count, len(all_pts))
    points_to_download = all_pts[:count]

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
            f"[{item['point']:02d}/{len(points_to_download):02d}] "
            f"{item['date_local']} ({item['regime']}, Q_ref={item['q_ref']:.2f} m³/s)"
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
