import argparse
import datetime as dt
import json
import logging
from pathlib import Path

import numpy as np
import yaml

import awive.config
from awive.algorithms.otv import run_otv
from awive.algorithms.water_flow import get_simplest_water_flow, get_water_flow

AWIVE_FP = Path("/root/.config/nflow/awive.yaml")
LOG = logging.getLogger(__name__)


def _write_output_file(
    data: dict,
    output_fp: Path,
    output_format: str | None,
) -> None:
    """Persist computed velocimetry data in YAML or JSON format."""
    selected_format = (
        output_format.lower() if output_format is not None else ""
    )
    if not selected_format:
        selected_format = (
            "json" if output_fp.suffix.lower() == ".json" else "yaml"
        )

    if selected_format not in {"yaml", "json"}:
        msg = (
            f"Unsupported output format: {selected_format}. "
            "Use 'yaml' or 'json'."
        )
        raise ValueError(msg)

    output_fp.parent.mkdir(parents=True, exist_ok=True)
    with output_fp.open("w", encoding="utf-8") as f:
        if selected_format == "json":
            json.dump(data, f, indent=2)
        else:
            yaml.safe_dump(data, f, sort_keys=False)


def process_video(
    awive_fp: Path,
    area: float,
    ts: dt.datetime | None = None,
    wlevel: float | None = None,
    output_fp: Path = Path("/root/awive/data.yaml"),
    output_format: str | None = None,
    show_video: bool = False,
) -> None:
    """Process video.

    Args:
        awive_fp: Path to the awive config file.
        area: Area of the water flow.
        ts: Timestamp of the data. If None, use current time.
        wlevel: Current water level. If None, use simplest water flow calc.
        output_fp: Output file path where data is persisted.
        output_format: Output format. If None, infer from file extension.
        show_video: Whether to display video during processing.
    """
    ts = ts if ts is not None else dt.datetime.now(dt.UTC)
    raw: dict
    raw, _ = run_otv(awive_fp, show_video=show_video)
    velocimetry = [
        d.get("velocity", "-") for _, d in raw.items() if isinstance(d, dict)
    ]

    current_water_depth = wlevel
    if current_water_depth is None:
        water_flow: float = get_simplest_water_flow(area=area, velocities=raw)
    else:
        awive_cfg = awive.config.Config.from_fp(awive_fp)
        depths = awive_cfg.water_flow.profile.depths_meters(
            awive_cfg.preprocessing.ppm,
            awive_cfg.preprocessing.resolution,
        )
        water_flow: float = get_water_flow(
            depths=depths,
            vels=np.array(velocimetry, dtype=float),
            old_depth=awive_cfg.water_flow.profile.height,
            roughness=awive_cfg.water_flow.roughness,
            current_depth=current_water_depth,
        )

    velocimetry_array = [float(v) for v in velocimetry]
    print(f"Water flow: {water_flow:.3f} m³/s")
    water_flow_array = float(water_flow)
    data_save = {
        "timestamp": ts.isoformat(),
        "velocimetry": velocimetry_array,
        "water_flow": water_flow_array,
    }

    _write_output_file(
        data=data_save,
        output_fp=output_fp,
        output_format=output_format,
    )


def velocimetry(
    awive_fp: Path,
    video_fp: Path,
    ts: dt.datetime | None = None,
    wlevel: float | None = None,
    resolution: float = 1.0,
    output_fp: Path = Path("/root/awive/data.yaml"),
    output_format: str | None = None,
    show_video: bool = False,
) -> None:
    """Process video."""
    # Replace the video path in the awive config file
    awive_cfg = awive.config.Config.from_fp(awive_fp)
    awive_cfg.dataset.video_fp = video_fp
    awive_cfg.preprocessing.resolution = resolution
    awive_fp.write_text(yaml.dump(awive_cfg.model_dump(mode="json"), indent=4))

    process_video(
        awive_fp=awive_fp,
        area=awive_cfg.water_flow.area,
        ts=ts,
        wlevel=wlevel,
        output_fp=output_fp,
        output_format=output_format,
        show_video=show_video,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video_fp", type=Path, help="Path to the video file")
    parser.add_argument(
        "--wlevel",
        type=float,
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="Display video during processing",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("/root/awive/data.yaml"),
        help="Output file path for velocimetry results",
    )
    parser.add_argument(
        "--output-format",
        choices=["yaml", "json"],
        default=None,
        help="Output format. If omitted, inferred from output file extension",
    )
    args = parser.parse_args()
    velocimetry(
        awive_fp=AWIVE_FP,
        video_fp=args.video_fp,
        wlevel=args.wlevel,
        output_fp=args.output_file,
        output_format=args.output_format,
        show_video=args.video,
    )
