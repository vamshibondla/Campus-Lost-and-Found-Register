"""Chart generation module for Campus Lost-and-Found Register."""

import logging

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except ImportError:
    _HAS_MPL = False


def generate_charts(summary: dict, output_file: str = "campus_summary_charts.png") -> bool:
    if not _HAS_MPL:
        logger.warning("Matplotlib not installed. Run 'pip install matplotlib' to export charts.")
        return False

    if summary["total"] == 0:
        logger.info("No records available to plot.")
        return False

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 5))

    # 1. Category Bar Chart with value labels
    cats = list(summary["by_category"].keys())
    counts = list(summary["by_category"].values())
    bars = ax1.bar(cats, counts, color="#2b5c8f")
    ax1.set_title("Items by Category")
    ax1.set_ylabel("Count")
    ax1.tick_params(axis="x", rotation=30)
    ax1.bar_label(bars, padding=2)

    # 2. Resolution Status Pie Chart
    ax2.pie([summary["open"], summary["claimed"]], labels=["Open", "Claimed"],
            autopct="%1.1f%%", colors=["#e07a5f", "#81b29a"], startangle=90)
    ax2.set_title("Open vs. Claimed Status")

    # 3. Top Hotspot Locations
    locs = list(summary["by_location"].keys())
    loc_counts = list(summary["by_location"].values())
    loc_bars = ax3.barh(locs, loc_counts, color="#3d405b")
    ax3.set_title("Top Campus Hotspots")
    ax3.set_xlabel("Reports")
    ax3.invert_yaxis()
    ax3.bar_label(loc_bars, padding=3)

    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    return True