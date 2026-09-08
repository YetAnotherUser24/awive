"""Plot benchmark results obtained directly from Raspberry Pi Zero 2 W."""

import csv
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

CSV_PATH = Path("/root/awive/_Reporte/rpi_zero_benchmark_results.csv")
OUT_FIG_LOCAL = Path("/root/awive/_Reporte/rpi_zero_benchmark_metrics.png")
OUT_FIG_ARTIFACT = Path("/root/.gemini/antigravity-ide/brain/71839929-c639-4701-9a89-85cec579a40f/rpi_zero_benchmark_metrics.png")

REF_FLOW = 39.88  # Senamhi reference discharge (m³/s)
TOTAL_RAM_MB = 415.0  # Physical RAM on RPi Zero 2 W
SAFE_RAM_MB = 350.0   # Safe headroom threshold

def main():
    rows = []
    with open(CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    labels = [r["label"] for r in rows]
    resolutions = [f"{r['width']}x{r['height']}" for r in rows]
    elapsed = [float(r["elapsed_sec"]) for r in rows]
    fps = [float(r["fps"]) for r in rows]
    ram = [float(r["peak_ram_mb"]) for r in rows]
    flow = [float(r["water_flow"]) for r in rows]
    flow_err = [((f - REF_FLOW) / REF_FLOW) * 100.0 for f in flow]

    x = np.arange(len(labels))
    width = 0.55

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), dpi=200)
    fig.patch.set_facecolor("#0f172a")

    # Custom styling
    for ax in axes:
        ax.set_facecolor("#1e293b")
        ax.tick_params(colors="#cbd5e1", labelsize=9)
        ax.xaxis.label.set_color("#cbd5e1")
        ax.yaxis.label.set_color("#cbd5e1")
        ax.title.set_color("#f8fafc")
        for spine in ax.spines.values():
            spine.set_color("#334155")
        ax.grid(axis="y", color="#334155", linestyle="--", alpha=0.6)

    # 1. Peak RAM Usage
    ax1 = axes[0]
    bars1 = ax1.bar(x, ram, width=width, color="#38bdf8", edgecolor="#0284c7", linewidth=1.5, zorder=3)
    ax1.axhline(TOTAL_RAM_MB, color="#ef4444", linestyle="--", linewidth=1.8, label=f"Hardware RAM ({int(TOTAL_RAM_MB)} MB)")
    ax1.axhline(SAFE_RAM_MB, color="#f59e0b", linestyle=":", linewidth=1.8, label=f"Safe Limit ({int(SAFE_RAM_MB)} MB)")
    ax1.set_title("Peak RAM Usage (MB) vs Hardware Limits", fontsize=12, fontweight="bold", pad=12)
    ax1.set_ylabel("Peak RSS (MB)", fontsize=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{l}\n({r})" for l, r in zip(labels, resolutions)], rotation=20, ha="right")
    ax1.set_ylim(0, 450)
    ax1.legend(facecolor="#0f172a", edgecolor="#334155", labelcolor="#e2e8f0", loc="upper left")

    for bar in bars1:
        yval = bar.get_height()
        pct = (yval / TOTAL_RAM_MB) * 100.0
        ax1.text(bar.get_x() + bar.get_width() / 2.0, yval + 8, f"{yval:.1f} MB\n({pct:.0f}%)",
                 ha="center", va="bottom", color="#f1f5f9", fontsize=8.5, fontweight="bold")

    # 2. Execution Time and Throughput (FPS)
    ax2 = axes[1]
    bars2 = ax2.bar(x, elapsed, width=width, color="#a855f7", edgecolor="#7e22ce", linewidth=1.5, zorder=3)
    ax2.set_title("Processing Time (90 Frames / 3s Clip)", fontsize=12, fontweight="bold", pad=12)
    ax2.set_ylabel("Elapsed Time (seconds)", fontsize=10)
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{l}\n({r})" for l, r in zip(labels, resolutions)], rotation=20, ha="right")
    ax2.set_ylim(0, max(elapsed) * 1.25)

    for bar, f_val in zip(bars2, fps):
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2.0, yval + 3, f"{yval:.1f}s\n({f_val:.2f} FPS)",
                 ha="center", va="bottom", color="#f1f5f9", fontsize=8.5, fontweight="bold")

    # 3. Water Flow Accuracy
    ax3 = axes[2]
    bars3 = ax3.bar(x, flow, width=width, color="#10b981", edgecolor="#047857", linewidth=1.5, zorder=3)
    ax3.axhline(REF_FLOW, color="#f59e0b", linestyle="--", linewidth=1.8, label=f"Senamhi Ref ({REF_FLOW:.2f} m³/s)")
    ax3.set_title("Discharge Accuracy (Q vs Ref)", fontsize=12, fontweight="bold", pad=12)
    ax3.set_ylabel("Discharge Q (m³/s)", fontsize=10)
    ax3.set_xticks(x)
    ax3.set_xticklabels([f"{l}\n({r})" for l, r in zip(labels, resolutions)], rotation=20, ha="right")
    ax3.set_ylim(30, 45)
    ax3.legend(facecolor="#0f172a", edgecolor="#334155", labelcolor="#e2e8f0", loc="lower right")

    for bar, err in zip(bars3, flow_err):
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width() / 2.0, yval + 0.4, f"{yval:.2f} m³/s\n({err:+.1f}%)",
                 ha="center", va="bottom", color="#f1f5f9", fontsize=8.5, fontweight="bold")

    fig.suptitle("Raspberry Pi Zero 2 W (Quad Cortex-A53 1.0 GHz, 512 MB RAM) - Velocimetry Benchmark",
                 fontsize=14, fontweight="bold", color="#f8fafc", y=0.98)

    plt.tight_layout()
    OUT_FIG_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_FIG_LOCAL, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    OUT_FIG_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_FIG_ARTIFACT, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Generated benchmark figure:\n  -> {OUT_FIG_LOCAL}\n  -> {OUT_FIG_ARTIFACT}")

if __name__ == "__main__":
    main()
