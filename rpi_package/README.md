# Raspberry Pi Zero 2 W Benchmark Package

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
