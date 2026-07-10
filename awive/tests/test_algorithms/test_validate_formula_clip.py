from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from awive.algorithms.validate_formula import (
    extract_video_fragment,
    process_single_video,
)


def test_extract_video_fragment_returns_original_when_disabled(
    tmp_path: Path,
) -> None:
    """Clipping disabled should return the original video path."""
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"dummy")

    assert extract_video_fragment(video_path, None, tmp_path) == video_path
    assert extract_video_fragment(video_path, 0, tmp_path) == video_path


@patch("awive.algorithms.validate_formula.yaml.safe_load")
@patch("builtins.open", new_callable=mock_open)
@patch("awive.algorithms.validate_formula.velocimetry.velocimetry")
@patch("awive.algorithms.validate_formula.extract_video_fragment")
@patch("awive.algorithms.validate_formula.download_video_from_gdrive")
def test_process_single_video_uses_fragment_when_requested(
    mock_download: MagicMock,
    mock_extract: MagicMock,
    mock_velocimetry: MagicMock,
    mock_open_file: MagicMock,
    mock_yaml_load: MagicMock,
    tmp_path: Path,
) -> None:
    """Requested clip seconds should be passed through to velocimetry."""
    downloaded_path = tmp_path / "downloaded.mp4"
    fragment_path = tmp_path / "downloaded_clip_5s.mp4"
    mock_download.return_value = (downloaded_path, "downloaded.mp4")
    mock_extract.return_value = fragment_path
    mock_yaml_load.return_value = {
        "water_flow": 1.23,
        "velocimetry": [1.0, 2.0],
        "timestamp": "2026-04-13T12:00:00Z",
    }

    results = process_single_video(
        video_id="video-123",
        timestamp=1744545600000,
        water_level=0.37,
        temp_dir=tmp_path,
        clip_seconds=5.0,
    )

    assert results is not None
    assert len(results) == 1
    assert results[0]["calculated_flow"] == pytest.approx(1.23)
    mock_extract.assert_called_once_with(downloaded_path, 5.0, tmp_path)
    mock_velocimetry.assert_called_once()
    assert mock_velocimetry.call_args.kwargs["video_fp"] == fragment_path
