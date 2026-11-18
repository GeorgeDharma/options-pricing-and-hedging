"""Plot average transaction costs and tail losses on the same simulated paths."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter
import pandas as pd


def draw(output):
    output = Path(output)
    results = pd.read_csv(output / "band_summary.csv")
    results = results[results.case == "Base"].set_index("policy")
    positions = [
        ("Daily", "Daily", (5, 8)),
        ("2.5-point band", "2.5-point band", (-22, 9)),
        ("5-point band", "5-point band", (6, 7)),
        ("10-point band", "10-point band", (-24, -18)),
        ("Every 5 sessions", "Every 5 sessions", (6, -8)),
    ]
    fig, ax = plt.subplots(figsize=(8.1, 3.05), layout="constrained")
    for name, label, offset in positions:
        row = results.loc[name]
        color = "#985433" if name == "2.5-point band" else "#344a59"
        location = (row.cash_cost, -row.tail_mean)
        ax.scatter(*location, color=color, s=53)
        ax.annotate(
            label, location, xytext=offset, textcoords="offset points", fontsize=9
        )
    ax.set(
        xlabel="Mean trading cost over the year ($)",
        ylabel="Mean loss in worst 5% ($)",
        xlim=(425, 1240),
        ylim=(4800, 10200),
    )
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.grid(axis="y", color="#dfd9d2", alpha=0.65)
    ax.spines[["right", "top"]].set_visible(False)
    fig.savefig(output / "delta_band_tradeoff.png", dpi=180)
    plt.close(fig)
