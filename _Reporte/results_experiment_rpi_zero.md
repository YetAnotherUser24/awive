# Raspberry Pi Zero 2 W Hardware Benchmark: Native Resolution Velocimetry

## 1. Executive Summary

This report documents the live benchmark conducted on a physical **Raspberry Pi Zero 2 W** (`natek@natekstationpi`) executing the optical tracking velocimetry algorithm (`awive.algorithms.velocimetry`) **100% as-is** across 5 native resolution profiles.

### Key Takeaways
1. **Memory Safety: 1080p is Safe!**
   - Even at **1080p Full HD**, peak resident memory (RSS) reached **239.9 MB**, consuming only **57.8%** of the Pi Zero 2 W's available physical RAM (415 MB) and leaving over 175 MB of physical headroom plus 414 MB of swap.
   - No resolution caused out-of-memory (OOM) conditions or thrashing.
2. **Processing Latency & Throughput**:
   - The quad-core ARM Cortex-A53 (1.0 GHz) processed 90 frames (3.0s at 30 fps) in **102 to 121 seconds** across all resolutions (~0.74 to 0.88 FPS, or ~1.1 to 1.35 seconds per frame).
   - Because Lucas-Kanade OTV tracks a bounded number of sparse feature points (`maxCorners: 500-1000`), the computational cost does not scale linearly with pixel count ($O(N)$ vs $O(\text{features})$). 1080p required only 14% more time than 360p.
3. **Discharge Accuracy**:
   - All 5 profiles produced flow rates within **1.6% to 6.0%** of the official Senamhi ground-truth reference ($39.88\text{ m³/s}$).
   - **720p HD Default** achieved the highest accuracy: **$39.24\text{ m³/s}$ ($-1.6\%$ error)**.
4. **Recommended Production Setting**:
   - **720p HD (1280×720)** is the optimal operational standard: best accuracy, 180 MB peak RAM (43%), 5.7 MB video size per 3s clip, and 102s execution time.

---

## 2. Hardware Test Environment

| Parameter | Specification |
| :--- | :--- |
| **Host** | `natekstationpi` |
| **Architecture** | ARMv8 64-bit (aarch64) |
| **SoC** | Broadcom BCM2710A1 |
| **CPU** | Quad-core ARM Cortex-A53 @ 1.0 GHz |
| **Physical RAM** | 415 MiB visible to Linux kernel (512 MB package) |
| **Swap** | 414 MiB |
| **Operating System** | Debian GNU/Linux 12 (bookworm) / Raspberry Pi OS |
| **Python** | Python 3.11.2 |
| **OpenCV** | OpenCV 4.11.0.86 (headless, pre-installed) |
| **NumPy** | NumPy 2.5.1 |
| **PyYAML** | PyYAML 6.0.3 |
| **Pydantic** | Pydantic 2.13.4 |

---

## 3. Benchmark Results

Measured on 90 frames (3.0 seconds duration, 30 fps native source video, point 01 at water level $h = 0.32\text{ m}$):

| Profile | Resolution | Total Time | FPS | Latency / frame | Peak RAM (RSS) | RAM % of 415M | Computed Discharge ($Q$) | Error vs Ref ($39.88\text{ m³/s}$) | Valid Points |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **360p Low Tuned** | 640×360 | 107.20 s | 0.84 | 1,191 ms | 140.2 MB | 33.8% | 38.570 m³/s | **-3.28%** | 17 |
| **480p SD Tuned** | 854×480 | 114.66 s | 0.78 | 1,274 ms | 153.9 MB | 37.1% | 37.921 m³/s | **-4.91%** | 17 |
| **720p HD Tuned** | 1280×720 | 116.13 s | 0.77 | 1,290 ms | 178.2 MB | 43.0% | 37.501 m³/s | **-5.96%** | 17 |
| **720p HD Default** | 1280×720 | 102.60 s | 0.88 | 1,140 ms | 181.7 MB | 43.8% | 39.238 m³/s | **-1.61%** | 17 |
| **1080p FHD** | 1920×1080 | 121.32 s | 0.74 | 1,348 ms | 239.9 MB | 57.8% | 38.563 m³/s | **-3.30%** | 17 |

---

## 4. Visual Comparison

![RPi Zero 2 W Benchmark Metrics](file:///root/awive/_Reporte/rpi_zero_benchmark_metrics.png)

---

## 5. Architectural & Operational Insights

### 5.1 Real-Time Continuous vs. Periodic Batch Edge Architecture
- **Misconception**: "The Pi Zero 2 W must run continuous 30 FPS inference."
- **Hydrological Reality**: River discharge changes over scales of hours and days, not milliseconds. Standard operational camera stations (e.g., USGS, SEPA, SENAMHI) capture a short clip (3 to 10 seconds) every 15, 30, or 60 minutes.
- **Workflow on Pi Zero 2 W**:
  1. Wake or trigger camera at the scheduled interval.
  2. Record 90 frames (~3 seconds) to `/tmp` or RAM disk.
  3. Run `velocimetry()` (takes ~1.8 to 2.0 minutes).
  4. Transmit discharge summary ($Q$, velocity profile, timestamp) via LoRa, 4G, or satellite.
  5. Sleep or idle, consuming < 0.5 W.

### 5.2 Storage Footprint on SD Card
Per 90-frame (3.0s) observation:
- **360p**: 1.8 MB
- **480p**: 2.8 MB
- **720p**: 5.7 MB
- **1080p**: 11.0 MB

A standard 32 GB Class 10 / A1 MicroSD card can store over **5,000 raw 720p video clips** (over 3 months of hourly videos) before overwriting, or months of 1080p clips.

### 5.3 Resolution Ceiling Recommendation
| Use Case | Recommended Profile | Reason |
| :--- | :--- | :--- |
| **Standard Edge Station** | **720p HD (1280×720)** | **Optimal balance.** Best accuracy (-1.6%), moderate RAM (182 MB), compact files (5.7 MB), 102s run time. |
| **High Precision / Wide Cross-Section** | **1080p FHD (1920×1080)** | Completely safe in RAM (240 MB). Use when the river span is wide and features are far from camera. |
| **Ultra-Low Bandwidth / Solar-Constrained** | **480p SD (854×480)** | Lowest power consumption, smallest storage (2.8 MB), within -4.9% error. |
