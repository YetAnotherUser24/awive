"""
Statistical Analysis of Water Flow Calculations

This script performs comprehensive statistical analysis on water flow estimations
from multiple video fragments, including descriptive statistics, distribution analysis,
correlation studies, and time series analysis.
"""

from pathlib import Path

import matplotlib

matplotlib.use(
    "Agg"
)  # Headless non-interactive backend for server environments
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from scipy import stats
from scipy.stats import probplot

from awive.algorithms.water_flow import (
    get_simplest_water_flow,
    get_water_flow,
)
from awive.config import Depth

try:
    import seaborn as sns
except ImportError:
    sns = None


class WaterFlowStatisticalAnalyzer:
    """Statistical analyzer for water flow calculations."""

    def __init__(
        self, velocities_path: Path, depths: list[Depth], ppm: float = 262
    ):
        self.velocities_path = velocities_path
        self.depths = depths
        self.ppm = ppm
        self.velocity_dict = yaml.safe_load(velocities_path.open())

        # Data containers
        self.simple_flows = {}
        self.detailed_flows = {}
        self.velocities_by_fragment = {}
        self.velocities_by_position = {}

        # Calculate flows
        self._calculate_flows()
        self._organize_data()

    def _calculate_flows(self):
        """Calculate both simple and detailed water flows for all fragments."""
        for key, vels in self.velocity_dict.items():
            # Simple water flow estimation
            simple_flow = get_simplest_water_flow(area=12.3, velocities=vels)
            self.simple_flows[key] = simple_flow

            # Detailed water flow estimation
            vels_array = np.array([v["velocity"] for v in vels.values()])
            depths_array = np.array(
                [[depth.z, depth.y / self.ppm] for depth in self.depths]
            )

            detailed_flow = get_water_flow(
                vels=vels_array,
                depths=depths_array,
                roughness=8,
                old_depth=2.0,
                current_depth=2.0,
            )
            self.detailed_flows[key] = detailed_flow

    def _organize_data(self):
        """Organize velocity data by fragment and position for analysis."""
        # Organize velocities by fragment
        for fragment, vels in self.velocity_dict.items():
            self.velocities_by_fragment[fragment] = [
                v["velocity"] for v in vels.values()
            ]

        # Organize velocities by position across all fragments
        positions = set()
        for vels in self.velocity_dict.values():
            positions.update(vels.keys())

        for pos in positions:
            self.velocities_by_position[pos] = []
            for fragment_vels in self.velocity_dict.values():
                if pos in fragment_vels:
                    self.velocities_by_position[pos].append(
                        fragment_vels[pos]["velocity"]
                    )

    def descriptive_statistics(self) -> dict:
        """Calculate descriptive statistics for flows and velocities."""
        simple_flows_array = np.array(list(self.simple_flows.values()))
        detailed_flows_array = np.array(list(self.detailed_flows.values()))

        # All velocities combined
        all_velocities = []
        for vels in self.velocities_by_fragment.values():
            all_velocities.extend(vels)
        all_velocities = np.array(all_velocities)

        stats_dict = {
            "simple_flows": {
                "mean": np.mean(simple_flows_array),
                "median": np.median(simple_flows_array),
                "std": np.std(simple_flows_array),
                "min": np.min(simple_flows_array),
                "max": np.max(simple_flows_array),
                "cv": np.std(simple_flows_array) / np.mean(simple_flows_array),
                "q25": np.percentile(simple_flows_array, 25),
                "q75": np.percentile(simple_flows_array, 75),
                "iqr": np.percentile(simple_flows_array, 75)
                - np.percentile(simple_flows_array, 25),
            },
            "detailed_flows": {
                "mean": np.mean(detailed_flows_array),
                "median": np.median(detailed_flows_array),
                "std": np.std(detailed_flows_array),
                "min": np.min(detailed_flows_array),
                "max": np.max(detailed_flows_array),
                "cv": np.std(detailed_flows_array)
                / np.mean(detailed_flows_array),
                "q25": np.percentile(detailed_flows_array, 25),
                "q75": np.percentile(detailed_flows_array, 75),
                "iqr": np.percentile(detailed_flows_array, 75)
                - np.percentile(detailed_flows_array, 25),
            },
            "velocities": {
                "mean": np.mean(all_velocities),
                "median": np.median(all_velocities),
                "std": np.std(all_velocities),
                "min": np.min(all_velocities),
                "max": np.max(all_velocities),
                "cv": np.std(all_velocities) / np.mean(all_velocities),
                "q25": np.percentile(all_velocities, 25),
                "q75": np.percentile(all_velocities, 75),
                "iqr": np.percentile(all_velocities, 75)
                - np.percentile(all_velocities, 25),
            },
        }

        return stats_dict

    def normality_tests(self) -> dict:
        """Perform normality tests on flow data."""
        simple_flows_array = np.array(list(self.simple_flows.values()))
        detailed_flows_array = np.array(list(self.detailed_flows.values()))

        # Shapiro-Wilk test
        simple_shapiro = stats.shapiro(simple_flows_array)
        detailed_shapiro = stats.shapiro(detailed_flows_array)

        # Kolmogorov-Smirnov test
        simple_ks = stats.kstest(
            simple_flows_array,
            "norm",
            args=(np.mean(simple_flows_array), np.std(simple_flows_array)),
        )
        detailed_ks = stats.kstest(
            detailed_flows_array,
            "norm",
            args=(np.mean(detailed_flows_array), np.std(detailed_flows_array)),
        )

        return {
            "simple_flows": {
                "shapiro_stat": simple_shapiro.statistic,
                "shapiro_p": simple_shapiro.pvalue,
                "ks_stat": simple_ks.statistic,
                "ks_p": simple_ks.pvalue,
                "is_normal_shapiro": simple_shapiro.pvalue > 0.05,
                "is_normal_ks": simple_ks.pvalue > 0.05,
            },
            "detailed_flows": {
                "shapiro_stat": detailed_shapiro.statistic,
                "shapiro_p": detailed_shapiro.pvalue,
                "ks_stat": detailed_ks.statistic,
                "ks_p": detailed_ks.pvalue,
                "is_normal_shapiro": detailed_shapiro.pvalue > 0.05,
                "is_normal_ks": detailed_ks.pvalue > 0.05,
            },
        }

    def correlation_analysis(self) -> dict:
        """Analyze correlations between simple and detailed flows."""
        simple_flows_array = np.array(list(self.simple_flows.values()))
        detailed_flows_array = np.array(list(self.detailed_flows.values()))

        # Pearson correlation
        pearson_corr, pearson_p = stats.pearsonr(
            simple_flows_array, detailed_flows_array
        )

        # Spearman correlation
        spearman_corr, spearman_p = stats.spearmanr(
            simple_flows_array, detailed_flows_array
        )

        # Kendall's tau
        kendall_corr, kendall_p = stats.kendalltau(
            simple_flows_array, detailed_flows_array
        )

        return {
            "pearson": {"correlation": pearson_corr, "p_value": pearson_p},
            "spearman": {"correlation": spearman_corr, "p_value": spearman_p},
            "kendall": {"correlation": kendall_corr, "p_value": kendall_p},
        }

    def velocity_position_analysis(self) -> dict:
        """Analyze velocity patterns across positions."""
        position_stats = {}

        for pos, velocities in self.velocities_by_position.items():
            if len(velocities) > 1:
                velocities = np.array(velocities)
                position_stats[pos] = {
                    "mean": np.mean(velocities),
                    "std": np.std(velocities),
                    "cv": np.std(velocities) / np.mean(velocities),
                    "min": np.min(velocities),
                    "max": np.max(velocities),
                    "range": np.max(velocities) - np.min(velocities),
                    "count": len(velocities),
                }

        return position_stats

    def time_series_analysis(self) -> dict:
        """Analyze temporal trends in flow data."""
        fragments = sorted(self.simple_flows.keys())
        simple_flows_series = [self.simple_flows[f] for f in fragments]
        detailed_flows_series = [self.detailed_flows[f] for f in fragments]

        # Linear trend analysis
        x = np.arange(len(fragments))

        # Simple flows trend
        simple_slope, simple_intercept, simple_r, simple_p, simple_se = (
            stats.linregress(x, simple_flows_series)
        )

        # Detailed flows trend
        (
            detailed_slope,
            detailed_intercept,
            detailed_r,
            detailed_p,
            detailed_se,
        ) = stats.linregress(x, detailed_flows_series)

        # Autocorrelation (lag-1)
        simple_autocorr = np.corrcoef(
            simple_flows_series[:-1], simple_flows_series[1:]
        )[0, 1]
        detailed_autocorr = np.corrcoef(
            detailed_flows_series[:-1], detailed_flows_series[1:]
        )[0, 1]

        return {
            "simple_flows": {
                "slope": simple_slope,
                "intercept": simple_intercept,
                "r_squared": simple_r**2,
                "p_value": simple_p,
                "standard_error": simple_se,
                "lag1_autocorr": simple_autocorr,
            },
            "detailed_flows": {
                "slope": detailed_slope,
                "intercept": detailed_intercept,
                "r_squared": detailed_r**2,
                "p_value": detailed_p,
                "standard_error": detailed_se,
                "lag1_autocorr": detailed_autocorr,
            },
        }

    def generate_report(self) -> str:
        """Generate a comprehensive statistical report."""
        desc_stats = self.descriptive_statistics()
        normality = self.normality_tests()
        correlation = self.correlation_analysis()
        position_analysis = self.velocity_position_analysis()
        time_analysis = self.time_series_analysis()

        report = []
        report.append("=" * 80)
        report.append("WATER FLOW STATISTICAL ANALYSIS REPORT")
        report.append("=" * 80)
        report.append("")

        # Dataset overview
        report.append("DATASET OVERVIEW:")
        report.append(f"Number of fragments: {len(self.velocity_dict)}")
        report.append(
            f"Number of measurement positions: {len(next(iter(self.velocity_dict.values())))}"
        )
        report.append(
            f"Total velocity measurements: {sum(len(v) for v in self.velocity_dict.values())}"
        )
        report.append("")

        # Descriptive Statistics
        report.append("DESCRIPTIVE STATISTICS:")
        report.append("-" * 40)

        for flow_type, stats in desc_stats.items():
            report.append(f"\n{flow_type.replace('_', ' ').title()}:")
            report.append(f"  Mean:              {stats['mean']:.4f}")
            report.append(f"  Median:            {stats['median']:.4f}")
            report.append(f"  Standard Deviation: {stats['std']:.4f}")
            report.append(f"  Coefficient of Variation: {stats['cv']:.4f}")
            report.append(f"  Minimum:           {stats['min']:.4f}")
            report.append(f"  Maximum:           {stats['max']:.4f}")
            report.append(f"  25th Percentile:   {stats['q25']:.4f}")
            report.append(f"  75th Percentile:   {stats['q75']:.4f}")
            report.append(f"  Interquartile Range: {stats['iqr']:.4f}")

        # Normality Tests
        report.append("\n\nNORMALITY TESTS:")
        report.append("-" * 40)

        for flow_type, tests in normality.items():
            report.append(f"\n{flow_type.replace('_', ' ').title()}:")
            report.append(f"  Shapiro-Wilk test:")
            report.append(f"    Statistic: {tests['shapiro_stat']:.4f}")
            report.append(f"    p-value:   {tests['shapiro_p']:.4f}")
            report.append(f"    Normal:    {tests['is_normal_shapiro']}")
            report.append(f"  Kolmogorov-Smirnov test:")
            report.append(f"    Statistic: {tests['ks_stat']:.4f}")
            report.append(f"    p-value:   {tests['ks_p']:.4f}")
            report.append(f"    Normal:    {tests['is_normal_ks']}")

        # Correlation Analysis
        report.append("\n\nCORRELATION ANALYSIS (Simple vs Detailed Flows):")
        report.append("-" * 40)

        for method, corr_data in correlation.items():
            report.append(f"  {method.title()} correlation:")
            report.append(f"    Coefficient: {corr_data['correlation']:.4f}")
            report.append(f"    p-value:     {corr_data['p_value']:.4f}")
            significance = (
                "significant"
                if corr_data["p_value"] < 0.05
                else "not significant"
            )
            report.append(f"    Significance: {significance}")

        # Velocity Position Analysis
        report.append("\n\nVELOCITY ANALYSIS BY POSITION:")
        report.append("-" * 40)

        for pos, pos_stats in position_analysis.items():
            report.append(f"\nPosition {pos}:")
            report.append(f"  Mean velocity:     {pos_stats['mean']:.4f}")
            report.append(f"  Standard deviation: {pos_stats['std']:.4f}")
            report.append(f"  Coefficient of variation: {pos_stats['cv']:.4f}")
            report.append(f"  Range:             {pos_stats['range']:.4f}")
            report.append(f"  Measurements:      {pos_stats['count']}")

        # Time Series Analysis
        report.append("\n\nTEMPORAL TREND ANALYSIS:")
        report.append("-" * 40)

        for flow_type, trend_data in time_analysis.items():
            report.append(f"\n{flow_type.replace('_', ' ').title()}:")
            report.append(f"  Linear trend slope: {trend_data['slope']:.6f}")
            report.append(
                f"  R-squared:         {trend_data['r_squared']:.4f}"
            )
            report.append(f"  p-value:           {trend_data['p_value']:.4f}")
            trend_direction = (
                "increasing" if trend_data["slope"] > 0 else "decreasing"
            )
            significance = (
                "significant"
                if trend_data["p_value"] < 0.05
                else "not significant"
            )
            report.append(
                f"  Trend:             {trend_direction} ({significance})"
            )
            report.append(
                f"  Lag-1 autocorrelation: {trend_data['lag1_autocorr']:.4f}"
            )

        # Summary and Conclusions
        report.append("\n\nSUMMARY AND CONCLUSIONS:")
        report.append("-" * 40)

        # Flow comparison
        simple_mean = desc_stats["simple_flows"]["mean"]
        detailed_mean = desc_stats["detailed_flows"]["mean"]
        diff_percent = abs(simple_mean - detailed_mean) / simple_mean * 100

        report.append(
            f"• Average difference between simple and detailed flows: {diff_percent:.1f}%"
        )

        # Variability assessment
        simple_cv = desc_stats["simple_flows"]["cv"]
        detailed_cv = desc_stats["detailed_flows"]["cv"]

        report.append(
            f"• Simple flow coefficient of variation: {simple_cv:.3f}"
        )
        report.append(
            f"• Detailed flow coefficient of variation: {detailed_cv:.3f}"
        )

        if simple_cv < 0.1:
            report.append("• Simple flows show low variability (CV < 0.1)")
        elif simple_cv < 0.3:
            report.append(
                "• Simple flows show moderate variability (0.1 ≤ CV < 0.3)"
            )
        else:
            report.append("• Simple flows show high variability (CV ≥ 0.3)")

        # Correlation strength
        pearson_corr = correlation["pearson"]["correlation"]
        if abs(pearson_corr) > 0.8:
            corr_strength = "very strong"
        elif abs(pearson_corr) > 0.6:
            corr_strength = "strong"
        elif abs(pearson_corr) > 0.4:
            corr_strength = "moderate"
        else:
            corr_strength = "weak"

        report.append(
            f"• Correlation between simple and detailed flows: {corr_strength} (r = {pearson_corr:.3f})"
        )

        # Temporal stability
        simple_trend_p = time_analysis["simple_flows"]["p_value"]
        detailed_trend_p = time_analysis["detailed_flows"]["p_value"]

        if simple_trend_p > 0.05 and detailed_trend_p > 0.05:
            report.append(
                "• Flow measurements show temporal stability (no significant trends)"
            )
        else:
            report.append(
                "• Flow measurements show temporal variability (significant trends detected)"
            )

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def create_visualizations(self, output_dir: Path | None = None):
        """Create comprehensive visualizations of the flow analysis."""
        if output_dir is None:
            output_dir = Path("flow_analysis_plots")
        output_dir.mkdir(exist_ok=True)

        # Set style
        if "seaborn-v0_8" in plt.style.available:
            plt.style.use("seaborn-v0_8")
        if sns is not None:
            sns.set_palette("husl")

        # 1. Flow comparison histogram
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        simple_flows = list(self.simple_flows.values())
        detailed_flows = list(self.detailed_flows.values())

        ax1.hist(
            simple_flows,
            bins=15,
            alpha=0.7,
            label="Simple Flows",
            color="skyblue",
        )
        ax1.set_xlabel("Flow (cubic units/second)")
        ax1.set_ylabel("Frequency")
        ax1.set_title("Distribution of Simple Water Flows")
        ax1.grid(True, alpha=0.3)

        ax2.hist(
            detailed_flows,
            bins=15,
            alpha=0.7,
            label="Detailed Flows",
            color="lightcoral",
        )
        ax2.set_xlabel("Flow (cubic units/second)")
        ax2.set_ylabel("Frequency")
        ax2.set_title("Distribution of Detailed Water Flows")
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(
            output_dir / "flow_distributions.png", dpi=300, bbox_inches="tight"
        )
        plt.close()

        # 2. Scatter plot: Simple vs Detailed flows
        plt.figure(figsize=(10, 8))
        plt.scatter(simple_flows, detailed_flows, alpha=0.7, s=100)

        # Add regression line
        z = np.polyfit(simple_flows, detailed_flows, 1)
        p = np.poly1d(z)
        plt.plot(simple_flows, p(simple_flows), "r--", alpha=0.8, linewidth=2)

        plt.xlabel("Simple Flow (cubic units/second)")
        plt.ylabel("Detailed Flow (cubic units/second)")
        plt.title("Simple vs Detailed Water Flow Correlation")
        plt.grid(True, alpha=0.3)

        # Add correlation info
        corr = self.correlation_analysis()["pearson"]["correlation"]
        plt.text(
            0.05,
            0.95,
            f"Pearson r = {corr:.3f}",
            transform=plt.gca().transAxes,
            fontsize=12,
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
        )

        plt.savefig(
            output_dir / "flow_correlation.png", dpi=300, bbox_inches="tight"
        )
        plt.close()

        # 3. Time series plot
        fragments = sorted(self.simple_flows.keys())
        fragment_numbers = [int(f.split("_")[1]) for f in fragments]
        simple_series = [self.simple_flows[f] for f in fragments]
        detailed_series = [self.detailed_flows[f] for f in fragments]

        plt.figure(figsize=(14, 8))
        plt.plot(
            fragment_numbers,
            simple_series,
            "o-",
            label="Simple Flow",
            linewidth=2,
            markersize=6,
        )
        plt.plot(
            fragment_numbers,
            detailed_series,
            "s-",
            label="Detailed Flow",
            linewidth=2,
            markersize=6,
        )

        plt.xlabel("Fragment Number")
        plt.ylabel("Flow (cubic units/second)")
        plt.title("Water Flow Time Series Analysis")
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.savefig(
            output_dir / "flow_time_series.png", dpi=300, bbox_inches="tight"
        )
        plt.close()

        # 4. Velocity box plots by position
        position_data = []
        position_labels = []

        for pos, velocities in self.velocities_by_position.items():
            if len(velocities) > 1:
                position_data.append(velocities)
                position_labels.append(f"Position {pos}")

        plt.figure(figsize=(12, 8))
        box_plot = plt.boxplot(
            position_data, tick_labels=position_labels, patch_artist=True
        )

        # Color the boxes
        if sns is not None:
            colors = sns.color_palette("Set3", len(position_data))
        else:
            colors = [
                plt.cm.Set3(i / max(1, len(position_data)))
                for i in range(len(position_data))
            ]
        for patch, color in zip(box_plot["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        plt.xlabel("Position")
        plt.ylabel("Velocity (units/second)")
        plt.title("Velocity Distribution by Position")
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(
            output_dir / "velocity_by_position.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close()

        # 5. Combined statistical summary plot
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

        # Q-Q plots for normality assessment
        probplot(simple_flows, dist="norm", plot=ax1)
        ax1.set_title("Q-Q Plot: Simple Flows")
        ax1.grid(True, alpha=0.3)

        probplot(detailed_flows, dist="norm", plot=ax2)
        ax2.set_title("Q-Q Plot: Detailed Flows")
        ax2.grid(True, alpha=0.3)

        # Residuals plot
        predicted = np.polyval(
            np.polyfit(simple_flows, detailed_flows, 1), simple_flows
        )
        residuals = np.array(detailed_flows) - predicted

        ax3.scatter(predicted, residuals, alpha=0.7)
        ax3.axhline(y=0, color="r", linestyle="--")
        ax3.set_xlabel("Predicted Detailed Flow")
        ax3.set_ylabel("Residuals")
        ax3.set_title("Residuals Plot")
        ax3.grid(True, alpha=0.3)

        # Flow differences
        differences = np.array(detailed_flows) - np.array(simple_flows)
        ax4.hist(differences, bins=15, alpha=0.7, color="lightgreen")
        ax4.axvline(
            x=np.mean(differences),
            color="red",
            linestyle="--",
            label=f"Mean difference: {np.mean(differences):.3f}",
        )
        ax4.set_xlabel("Detailed - Simple Flow")
        ax4.set_ylabel("Frequency")
        ax4.set_title("Distribution of Flow Differences")
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(
            output_dir / "statistical_diagnostics.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close()

        print(f"Visualizations saved to: {output_dir.absolute()}")


def main():
    """Main execution function."""
    velocities_path = Path("velocities.yaml")
    depths = [
        Depth(x=768, y=523, z=3),
        Depth(x=1013, y=739, z=4),
        Depth(x=1282, y=853, z=3),
        Depth(x=1608, y=1250, z=3),
        Depth(x=1856, y=1441, z=3),
    ]

    # Create analyzer
    analyzer = WaterFlowStatisticalAnalyzer(velocities_path, depths)

    # Generate and print report
    report = analyzer.generate_report()
    print(report)

    # Save report to file
    report_path = Path("water_flow_statistical_report.txt")
    report_path.write_text(report)
    print(f"\nDetailed report saved to: {report_path.absolute()}")

    # Create visualizations
    try:
        analyzer.create_visualizations()
    except ImportError as e:
        print(
            f"\nNote: Could not create visualizations due to missing dependencies: {e}"
        )
        print("Install matplotlib and seaborn to generate plots:")
        print("pip install matplotlib seaborn")


if __name__ == "__main__":
    main()
