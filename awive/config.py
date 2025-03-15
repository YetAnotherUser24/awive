"""Configuration."""

from pydantic import BaseModel as RawBaseModel, Field
from numpy.typing import NDArray
from typing import Any
import numpy as np
import functools
import json
from pathlib import Path


class BaseModel(RawBaseModel):
    @staticmethod
    def from_fp(fp: Path):
        """Load config from json."""
        if fp.suffix != ".json":
            raise ValueError("File must be a json file")
        return Config(**json.load(fp.open()))


class GroundTruth(BaseModel):
    """Ground truth data."""

    position: list[int]
    velocity: float


class ConfigGcp(BaseModel):
    """Configurations GCP."""

    apply: bool
    pixels: list[tuple[int, int]] = Field(
        ..., alias="at least four coordinates: [[x1,y2], ..., [x4,y4]]"
    )
    meters: list[tuple[float, float]] = Field(
        default_factory=lambda: [],
        alias="at least four coordinates: [[x1,y2], ..., [x4,y4]]",
    )
    distances: dict[tuple[int, int], float] | None = Field(
        None, alias="distances in meters between the GCPs"
    )
    ground_truth: list[GroundTruth]

    @functools.cached_property
    def pixels_coordinates(self) -> NDArray:
        """Return pixel coordinates."""
        return np.array(self.pixels)

    @functools.cached_property
    def meters_coordinates(self) -> NDArray:
        """Return meters coordinates."""
        return np.array(self.meters)

    def calculate_meters(
        self, distances: dict[tuple[int, int], float]
    ) -> list[tuple[float, float]]:
        def di(i: int, j: int):
            return distances.get((i, j)) or distances.get((j, i))

        d = np.array(
            [
                [0, di(0, 1), di(0, 2), di(0, 3)],
                [di(1, 0), 0, di(1, 2), di(1, 3)],
                [di(2, 0), di(2, 1), 0, di(2, 3)],
                [di(3, 0), di(3, 1), di(3, 2), 0],
            ]
        )
        # check if nans are present
        if np.isnan(d).any():
            raise ValueError("Not all distances between GCPs are available")
        dim = 2

        # D is the distance matrix (n x n)
        n = d.shape[0]
        # Create centering matrix
        h = np.eye(n) - np.ones((n, n)) / n
        # Square the distances
        d_squared = d**2
        # Apply double centering
        b = -0.5 * h @ d_squared @ h
        # Eigen decomposition: using numpy's eig function
        eigvals, eigvecs = np.linalg.eig(b)
        # Sort eigenvalues and eigenvectors in descending order
        idx = np.argsort(eigvals)[::-1]
        eigvals = eigvals[idx][:dim]
        eigvecs = eigvecs[:, idx][:, :dim]
        # Compute coordinates using the positive eigenvalues
        l = np.diag(np.sqrt(eigvals))  # noqa: E741
        x = eigvecs @ l
        x[:, 0] *= -1
        return x.tolist()

    def model_post_init(self, __context: Any):
        if len(self.pixels) < 4:
            raise ValueError("at least four coordinates are required")
        if len(self.meters) == 0 and self.distances is None:
            raise ValueError("meters or distances must be provided")
        if len(self.meters) == 0 and self.distances is not None:
            if len(self.distances) != (
                len(self.pixels) * (len(self.pixels) - 1) / 2
            ):
                self.meters = self.calculate_meters(self.distances)
            else:
                raise ValueError(
                    "distances must have the correct number of elements"
                )

        if len(self.pixels) != len(self.meters):
            raise ValueError("pixels and meters must have the same length")


class ImageCorrection(BaseModel):
    """Configuration Image Correction."""

    apply: bool
    k1: float
    c: int
    f: float


class PreProcessing(BaseModel):
    """Configurations pre-processing."""

    rotate_image: int = Field(0, description="degrees")
    pre_roi: tuple[tuple[int, int], tuple[int, int]] = Field(
        ..., description="((x1,y1), (x2,y2))"
    )
    roi: tuple[tuple[int, int], tuple[int, int]] = Field(
        ..., description="((x1,y1), (x2,y2))"
    )
    image_correction: ImageCorrection


class Dataset(BaseModel):
    """Configuration dataset."""

    image_dataset: str
    image_number_offset: int
    image_path_prefix: str
    image_path_digits: int
    video_path: str
    width: int
    height: int
    ppm: int
    gcp: ConfigGcp


class ConfigOtvFeatures(BaseModel):
    """Config for OTV Features."""

    maxcorner: int
    qualitylevel: float
    mindistance: int
    blocksize: int


class ConfigOtvLucasKanade(BaseModel):
    """Config for OTV Lucas Kanade."""

    winsize: int
    max_level: int
    max_count: int
    epsilon: float
    flags: int
    radius: int
    min_eigen_threshold: float


class Otv(BaseModel):
    """Configuration OTV."""

    mask_path: str
    pixel_to_real: float
    partial_min_angle: float
    partial_max_angle: float
    final_min_angle: float
    final_max_angle: float
    final_min_distance: int
    max_features: int
    region_step: int
    resolution: int
    features: ConfigOtvFeatures
    lk: ConfigOtvLucasKanade
    lines: list[int]
    lines_width: int
    resize_factor: float | None = None


class ConfigStivLine(BaseModel):
    """Config for STIV line."""

    start: list[int]
    end: list[int]


class Stiv(BaseModel):
    """Configuration STIV."""

    window_shape: list[int]
    filter_window: int
    overlap: int
    ksize: int
    polar_filter_width: int
    lines: list[ConfigStivLine]
    resize_factor: float | None = None


class WaterLevel(BaseModel):
    """Configuration Water Level."""

    buffer_length: int
    roi: tuple[tuple[int, int], tuple[int, int]]
    roi2: tuple[tuple[int, int], tuple[int, int]]
    kernel_size: int


class Config(BaseModel):
    """Config class for awive."""

    dataset: Dataset
    otv: Otv
    stiv: Stiv
    preprocessing: PreProcessing
    water_level: WaterLevel | None = None
