"""Statistical comparison and visualization for multi-resolution SENAMHI benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Headless backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from awive.algorithms.validation_compare import calculate_metrics

DEFAULT_INPUT_CSV = Path(
    "experiments/output/multi_resolution_benchmark_10pts.csv"
)
DEFAULT_OUTPUT_PNG = Path(
    "experiments/output/multi_resolution_senamhi_comparison.png"
)
REPORTE_OUTPUT_PNG = Path("_Reporte/multi_resolution_senamhi_comparison.png")

COLOR_MAP = {
    "4k_default": "#1f77b4",  # Blue
    "1080p_default": "#2ca02c",  # Green
    "720p_default": "#aec7e8",  # Light blue
    "720p_tuned": "#ff7f0e",  # Orange
    "480p_tuned": "#d62728",  # Red
}

LABEL_MAP = {
    "4k_default": "4K UHD (3840x2160, 8px, w15)",
    "1080p_default": "1080p FHD (1920x1080, 8px, w15)",
    "720p_default": "720p HD (1280x720, 8px, w15)",
    "720p_tuned": "720p HD Tuned (1280x720, 3px, w21)",
    "480p_tuned": "480p SD Tuned (854x480, 2px, w25)",
}


def compute_resolution_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate MAE, RMSE, R2, NSE, and PBIAS for each resolution."""
    stats_list = []
    res_names = df["res_name"].unique()

    for res in res_names:
        sub = df[df["res_name"] == res].sort_values("point")
        if len(sub) == 0:
            continue

        pred = sub["water_flow"]
        actual = sub["q_reference"]
        metrics = calculate_metrics(pred, actual)

        avg_fps = sub["fps"].mean()
        avg_traj = sub["num_trajectories"].mean()
        avg_err_pct = sub["flow_err_pct"].abs().mean()

        stats_list.append(
            {
                "Resolution": LABEL_MAP.get(res, res),
                "res_code": res,
                "N": len(sub),
                "R2": metrics.r2,
                "NSE": metrics.nash_sutcliffe_efficiency,
                "MAE (m³/s)": metrics.mae,
                "RMSE (m³/s)": metrics.rmse,
                "Mean |Err| %": avg_err_pct,
                "FPS": avg_fps,
                "Avg Trajectories": avg_traj,
            }
        )

    return pd.DataFrame(stats_list)


def plot_benchmark_results(df: pd.DataFrame, output_png: Path) -> None:
    """Render 4-panel diagnostic comparison chart."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    REPORTE_OUTPUT_PNG.parent.mkdir(parents=True, exist_ok=True)

    points_df = df[df["res_name"] == df["res_name"].iloc[0]].sort_values(
        "point"
    )
    x_points = points_df["point"].values
    if len(x_points) > 20:
        x_labels = [
            f"Pt {p}\n{d[5:]}" if (p % 2 == 1 or p == len(x_points)) else ""
            for p, d in zip(points_df["point"], points_df["date_local"])
        ]
    else:
        x_labels = [
            f"Pt {p}\n({d})"
            for p, d in zip(points_df["point"], points_df["date_local"])
        ]

    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    plt.subplots_adjust(hspace=0.28, wspace=0.22)

    # -------------------------------------------------------------
    # Panel 1: Hydrograph Timeseries
    # -------------------------------------------------------------
    ax1 = axes[0, 0]
    ax1.plot(
        x_points,
        points_df["q_reference"].values,
        "k--o",
        linewidth=2.5,
        markersize=7,
        label="SENAMHI Reference",
        zorder=10,
    )

    if not points_df["q_lspiv"].isna().all():
        ax1.plot(
            x_points,
            points_df["q_lspiv"].values,
            color="#7f7f7f",
            linestyle=":",
            marker="s",
            linewidth=1.8,
            markersize=5,
            label="SENAMHI LSPIV (Report)",
            alpha=0.8,
        )

    for res, sub in df.groupby("res_name"):
        sub_sorted = sub.sort_values("point")
        ax1.plot(
            sub_sorted["point"].values,
            sub_sorted["water_flow"].values,
            marker="o",
            linewidth=2.0,
            markersize=5,
            color=COLOR_MAP.get(res, "gray"),
            label=LABEL_MAP.get(res, res),
            alpha=0.9,
        )

    ax1.set_title(
        f"A. Hydrograph Discharge Comparison across {len(x_points)} Points",
        fontsize=13,
        fontweight="bold",
    )
    ax1.set_xlabel("Observation Point & Date", fontsize=11)
    ax1.set_ylabel("Discharge $Q$ (m³/s)", fontsize=11)
    ax1.set_xticks(x_points)
    ax1.set_xticklabels(x_labels, rotation=35, ha="right", fontsize=8.5)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", framealpha=0.9, fontsize=9)

    # -------------------------------------------------------------
    # Panel 2: Parity Scatter Plot (Q_meas vs Q_ref)
    # -------------------------------------------------------------
    ax2 = axes[0, 1]
    min_val = min(df["q_reference"].min(), df["water_flow"].min()) * 0.9
    max_val = max(df["q_reference"].max(), df["water_flow"].max()) * 1.1

    ax2.plot(
        [min_val, max_val],
        [min_val, max_val],
        "k--",
        linewidth=1.5,
        label="1:1 Identity Line",
    )
    ax2.fill_between(
        [min_val, max_val],
        [min_val * 0.95, max_val * 0.95],
        [min_val * 1.05, max_val * 1.05],
        color="gray",
        alpha=0.15,
        label="±5% Margin",
    )

    for res, sub in df.groupby("res_name"):
        r2 = calculate_metrics(sub["water_flow"], sub["q_reference"]).r2
        ax2.scatter(
            sub["q_reference"],
            sub["water_flow"],
            color=COLOR_MAP.get(res, "gray"),
            label=f"{LABEL_MAP.get(res, res)} (R²={r2:.3f})",
            s=55,
            alpha=0.85,
        )

    ax2.set_title(
        "B. Parity Comparison vs SENAMHI Reference",
        fontsize=13,
        fontweight="bold",
    )
    ax2.set_xlabel("SENAMHI Reference $Q$ (m³/s)", fontsize=11)
    ax2.set_ylabel("OTV Discharge $Q$ (m³/s)", fontsize=11)
    ax2.set_xlim(min_val, max_val)
    ax2.set_ylim(min_val, max_val)
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="lower right", framealpha=0.9, fontsize=8.5)

    # -------------------------------------------------------------
    # Panel 3: Error Metrics (MAE & RMSE)
    # -------------------------------------------------------------
    ax3 = axes[1, 0]
    stats_df = compute_resolution_statistics(df)
    bar_width = 0.35
    indices = np.arange(len(stats_df))

    bars1 = ax3.bar(
        indices - bar_width / 2,
        stats_df["MAE (m³/s)"],
        bar_width,
        label="MAE (m³/s)",
        color="#4575b4",
        alpha=0.85,
    )
    bars2 = ax3.bar(
        indices + bar_width / 2,
        stats_df["RMSE (m³/s)"],
        bar_width,
        label="RMSE (m³/s)",
        color="#d73027",
        alpha=0.85,
    )

    for bar in bars1:
        yval = bar.get_height()
        ax3.text(
            bar.get_x() + bar.get_width() / 2.0,
            yval + 0.05,
            f"{yval:.2f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )
    for bar in bars2:
        yval = bar.get_height()
        ax3.text(
            bar.get_x() + bar.get_width() / 2.0,
            yval + 0.05,
            f"{yval:.2f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )

    ax3.set_title(
        "C. Error Metrics (MAE and RMSE vs Reference)",
        fontsize=13,
        fontweight="bold",
    )
    ax3.set_ylabel("Error (m³/s)", fontsize=11)
    ax3.set_xticks(indices)
    ax3.set_xticklabels(
        stats_df["Resolution"], rotation=25, ha="right", fontsize=9
    )
    ax3.set_ylim(0, max(stats_df["RMSE (m³/s)"]) * 1.3)
    ax3.grid(True, linestyle="--", alpha=0.5)
    ax3.legend(loc="upper left", framealpha=0.9, fontsize=9.5)

    # -------------------------------------------------------------
    # Panel 4: Processing Speed (FPS)
    # -------------------------------------------------------------
    ax4 = axes[1, 1]
    fps_bars = ax4.bar(
        indices,
        stats_df["FPS"],
        color=[COLOR_MAP.get(r, "#555") for r in stats_df["res_code"]],
        alpha=0.85,
        width=0.55,
    )
    ax4.axhline(
        30.0,
        color="gray",
        linestyle="--",
        linewidth=1.2,
        label="30 FPS Real-time Line",
    )

    for bar in fps_bars:
        yval = bar.get_height()
        ax4.text(
            bar.get_x() + bar.get_width() / 2.0,
            yval + 0.5,
            f"{yval:.1f} FPS",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    ax4.set_title(
        "D. Processing Throughput (Frames Per Second)",
        fontsize=13,
        fontweight="bold",
    )
    ax4.set_ylabel("Throughput (FPS)", fontsize=11)
    ax4.set_xticks(indices)
    ax4.set_xticklabels(
        stats_df["Resolution"], rotation=25, ha="right", fontsize=9
    )
    ax4.set_ylim(0, max(stats_df["FPS"]) * 1.25)
    ax4.grid(True, linestyle="--", alpha=0.5)
    ax4.legend(loc="upper left", framealpha=0.9, fontsize=9.5)

    plt.suptitle(
        f"Multi-Resolution Benchmark on {len(x_points)} SENAMHI Observation Points (OTV Velocimetry)",
        fontsize=15,
        fontweight="bold",
        y=0.99,
    )
    plt.tight_layout()
    plt.savefig(output_png, dpi=300, bbox_inches="tight")
    mirror_png = Path("_Reporte") / output_png.name
    mirror_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(mirror_png, dpi=300, bbox_inches="tight")
    plt.close()
    print(
        f"📊 Diagnostic comparison figure saved to: {output_png} and {mirror_png}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot Multi-Resolution Benchmark"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PNG)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input benchmark results file not found: {args.input}")
        return

    df = pd.read_csv(args.input)
    stats_df = compute_resolution_statistics(df)
    n_pts = df["point"].nunique()
    print("\n" + "=" * 90)
    print(f"📈 STATISTICAL SUMMARY ACROSS RESOLUTIONS ({n_pts} POINTS):")
    print("=" * 90)
    print(
        stats_df[
            [
                "Resolution",
                "R2",
                "NSE",
                "MAE (m³/s)",
                "RMSE (m³/s)",
                "Mean |Err| %",
                "FPS",
            ]
        ].to_string(index=False)
    )
    print("=" * 90)

    plot_benchmark_results(df, args.output)


if __name__ == "__main__":
    main()
