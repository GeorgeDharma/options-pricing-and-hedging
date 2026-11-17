"""Run the prespecified pricing and hedge comparisons."""

from pathlib import Path
from dataclasses import asdict, replace
import json, platform, time
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .engine import (
    Option,
    price,
    greeks,
    finite_greeks,
    tree_price,
    monte_carlo,
    implied_volatility,
    simulate,
    hedge,
    distribution,
)


def timed(fn, repeats=5):
    """Measure median runtime in milliseconds after one warm-up call."""
    fn()  # warm up; timings exclude file loading and plotting
    times = []
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t) * 1000)
    return float(np.median(times))


def run(root):
    """Calculate the fixed pricing and hedging experiment and save its outputs."""
    root = Path(root)
    out = root / "outputs"
    out.mkdir(exist_ok=True)
    cfg = json.loads((root / "data/assumptions.json").read_text(encoding="utf-8"))
    o = Option(**cfg["option"])
    pv = float(price(o))
    g = greeks(o)
    fd = finite_greeks(o)
    pricing = [
        {
            "method": "Black–Scholes",
            "size": 0,
            "price": pv,
            "error": 0.0,
            "runtime_ms": timed(lambda: price(o)),
        }
    ]
    for n in [25, 50, 100, 200, 400, 800, 1600, 3200]:
        p = tree_price(o, n)
        pricing.append(
            {
                "method": "CRR tree",
                "size": n,
                "price": p,
                "error": p - pv,
                "runtime_ms": timed(lambda: tree_price(o, n)),
            }
        )
    mc = []
    for n in [1000, 10000, 100000, 500000]:
        row = monte_carlo(o, n, seed=cfg["mc_seed"])
        row["error"] = row["price"] - pv
        row["runtime_ms"] = timed(lambda: monte_carlo(o, n, seed=cfg["mc_seed"]), 3)
        mc.append(row)
    quote = []
    for label, premium in [
        ("Bid", cfg["illustrative_quote"]["bid"]),
        ("Mid", sum(cfg["illustrative_quote"].values()) / 2),
        ("Ask", cfg["illustrative_quote"]["ask"]),
    ]:
        iv = implied_volatility(o, premium)
        quote.append(
            {
                "side": label,
                "premium": premium,
                "implied_volatility": iv,
                "repriced": float(price(replace(o, volatility=iv))),
            }
        )
    greek_rows = [
        {
            "greek": k,
            "analytical": g[k],
            "finite_difference": fd[k],
            "difference": fd[k] - g[k],
        }
        for k in g
    ]
    scenarios = []
    for label, ds, dv in [
        ("Spot −10%", -0.1 * o.spot, 0),
        ("Spot +10%", 0.1 * o.spot, 0),
        ("Volatility +5 pp", 0, 0.05),
        ("Spot −10%, volatility +5 pp", -0.1 * o.spot, 0.05),
    ]:
        exact = (
            float(price(replace(o, spot=o.spot + ds, volatility=o.volatility + dv)))
            - pv
        )
        first = g["delta"] * ds + g["vega"] * dv * 100
        second = first + 0.5 * g["gamma"] * ds * ds
        scenarios.append(
            {
                "scenario": label,
                "spot_change": ds,
                "vol_change": dv,
                "exact": exact,
                "first_order": first,
                "with_gamma": second,
                "residual": exact - second,
            }
        )
    rows = []
    tail_sensitivity = []
    pnls = []
    journal = []
    path_checks = []
    net_arrays = {}
    policies = [
        ("Unhedged", None),
        ("Every 21 sessions", 21),
        ("Every 5 sessions", 5),
        ("Every session", 1),
    ]
    for case in cfg["simulation"]["cases"]:
        paths = simulate(
            o,
            paths=cfg["simulation"]["paths"],
            steps=252,
            seed=cfg["simulation"]["seed"],
            **case["parameters"],
        )
        discounted = paths[:, -1] * np.exp(-o.rate * o.years)
        path_checks.append(
            {
                "case": case["name"],
                "discounted_terminal_mean": float(discounted.mean()),
                "standard_error": float(discounted.std(ddof=1) / np.sqrt(len(paths))),
            }
        )
        for label, interval in policies:
            a = hedge(
                o,
                paths,
                interval,
                cfg["simulation"]["cost_bps"],
                cfg["simulation"]["units"],
                trace_index=0 if case["name"] == "Base" and interval == 5 else None,
            )
            stats = distribution(a["pnl"])
            rows.append(
                {
                    "case": case["name"],
                    "policy": label,
                    **stats,
                    "gross_mean": float(a["gross_pnl"].mean()),
                    "mean_cost_paid": float(a["cost_paid"].mean()),
                    "mean_cost_fv": float(a["cost_future_value"].mean()),
                    "mean_turnover": float(a["turnover"].mean()),
                }
            )
            if a["trace"]:
                journal = a["trace"]
            net_arrays[(case["name"], label)] = a["pnl"]
            pnls.append(
                pd.DataFrame(
                    {
                        "case": case["name"],
                        "policy": label,
                        "path_id": np.arange(len(paths)),
                        "pnl": a["pnl"],
                        "gross_pnl": a["gross_pnl"],
                        "cost_fv": a["cost_future_value"],
                    }
                )
            )
            if case["name"] == "Base":
                for bps in [0, 1, 5, 10]:
                    x = a["gross_pnl"] - a["cost_future_value"] * (
                        bps / cfg["simulation"]["cost_bps"]
                    )
                    tail_sensitivity.append(
                        {"policy": label, "cost_bps": bps, **distribution(x)}
                    )
    paired = []
    for case in cfg["simulation"]["cases"]:
        diff = (
            net_arrays[(case["name"], "Every session")]
            - net_arrays[(case["name"], "Every 5 sessions")]
        )
        paired.append(
            {
                "case": case["name"],
                "comparison": "Daily minus every 5 sessions",
                **distribution(diff),
            }
        )
    result = {
        "assumptions": cfg,
        "option_value": pv,
        "greeks": greek_rows,
        "pricing": pricing,
        "monte_carlo": mc,
        "quotes": quote,
        "scenarios": scenarios,
        "hedging": rows,
        "cost_sensitivity": tail_sensitivity,
        "paired": paired,
        "path_checks": path_checks,
        "journal": journal,
        "runtime_environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    for key in [
        "pricing",
        "greeks",
        "monte_carlo",
        "quotes",
        "scenarios",
        "hedging",
        "cost_sensitivity",
        "paired",
        "path_checks",
        "journal",
    ]:
        pd.DataFrame(result[key]).to_csv(out / (key + ".csv"), index=False)
    pd.concat(pnls, ignore_index=True).to_csv(
        out / "simulation_pnl.csv", index=False, float_format="%.10f"
    )
    (out / "results.json").write_text(json.dumps(result, indent=2))
    charts(result, out)
    return result


def charts(r, out):
    colors = ["#626B73", "#B79E8D", "#A85E3B", "#242B33"]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#242B33",
            "text.color": "#242B33",
            "axes.titleweight": "bold",
            "figure.facecolor": "white",
        }
    )
    fig, ax = plt.subplots(figsize=(9, 3.6))
    m = r["monte_carlo"]
    x = np.arange(len(m))
    ax.errorbar(
        x,
        [d["price"] for d in m],
        yerr=[d["ci_high"] - d["price"] for d in m],
        fmt="o",
        color=colors[2],
        capsize=5,
        label="Estimate and 95% interval",
    )
    ax.axhline(
        r["option_value"], color=colors[3], linestyle="--", label="Black–Scholes"
    )
    ax.set_xticks(x, [f'{d["paths"]:,}' for d in m])
    ax.set_xlabel("Simulated terminal prices (two per independent pair)")
    ax.set_ylabel("Put value ($ per unit)")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "pricing_convergence.png", dpi=180)
    plt.close(fig)
    base = [x for x in r["hedging"] if x["case"] == "Base"]
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.7))
    labels = ["Unhedged", "21 sessions", "5 sessions", "1 session"]
    axs[0].bar(labels, [x["std"] / 1000 for x in base], color=colors)
    axs[0].set_ylabel("Terminal P&L standard deviation ($000)")
    axs[1].bar(labels, [-x["tail_mean"] / 1000 for x in base], color=colors)
    axs[1].set_ylabel("Average loss in worst 5% ($000)")
    for ax in axs:
        ax.tick_params(axis="x", rotation=15)
        ax.grid(axis="y", alpha=0.15)
        ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(out / "hedge_comparison.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 3.5))
    cases = ["Base", "Higher volatility", "Jumps"]
    for j, p in enumerate(["Every 21 sessions", "Every 5 sessions", "Every session"]):
        vals = [
            -next(
                x["tail_mean"]
                for x in r["hedging"]
                if x["case"] == c and x["policy"] == p
            )
            / 1000
            for c in cases
        ]
        ax.bar(np.arange(3) + (j - 1) * 0.23, vals, 0.23, label=p, color=colors[j + 1])
    ax.set_xticks(np.arange(3), cases)
    ax.set_ylabel("Average loss in worst 5% ($000)")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(axis="y", alpha=0.15)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(out / "stress_comparison.png", dpi=180)
    plt.close(fig)
