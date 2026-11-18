"""Self-financing delta hedges on fixed schedules or changes in theoretical delta."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .engine import Option, delta, distribution, payoff, price, simulate

POLICIES = (
    "Daily",
    "Every 5 sessions",
    "2.5-point band",
    "5-point band",
    "10-point band",
)
BANDS = (0.025, 0.05, 0.10)


def band_paths(option, paths, units=10000, cost_bps=5):
    """Return terminal cash, fees, turnover, trade count and a five-point-band journal."""
    if option.dividend != 0 or units <= 0 or cost_bps < 0:
        raise ValueError(
            "Require positive units, zero dividends and nonnegative costs."
        )
    paths = np.asarray(paths)
    if (
        paths.ndim != 2
        or paths.shape[1] < 2
        or not np.allclose(paths[:, 0], option.spot)
    ):
        raise ValueError(
            "Paths must start at the observed spot and include a future session."
        )
    path_count, columns = paths.shape
    steps = columns - 1
    dt = option.years / steps
    funding_factor = math.exp(option.rate * dt)
    cash = np.full((len(POLICIES), path_count), float(price(option)) * units)
    shares = np.zeros_like(cash)
    fees, turnover, trades = (np.zeros_like(cash) for _ in range(3))
    journal = []

    for day in range(steps + 1):
        spot = paths[:, day]
        if day:
            cash *= funding_factor
        prior_shares = shares.copy()
        if day == steps:
            shares.fill(0)
        else:
            desired = units * delta(option, spot, option.years - day * dt)
            shares[0] = desired
            if day % 5 == 0:
                shares[1] = desired
            for policy, threshold in enumerate(BANDS, start=2):
                breached = np.abs(desired - prior_shares[policy]) >= units * threshold
                shares[policy] = np.where(
                    breached | (day == 0), desired, prior_shares[policy]
                )

        quantity = shares - prior_shares
        traded_value = np.abs(quantity) * spot
        fee = traded_value * cost_bps / 10000
        cash -= quantity * spot + fee
        fees += fee
        turnover += traded_value
        trades += np.abs(quantity) > 1e-10
        if day == steps:
            cash -= units * payoff(spot, option.strike, option.kind)
        journal.append(
            dict(
                session=day,
                spot=float(spot[0]),
                held_shares=float(shares[3, 0]),
                net_trade_shares=float(quantity[3, 0]),
                trading_cost=float(fee[3, 0]),
                after_trade_cash=float(cash[3, 0]),
            )
        )
    return cash, fees, turnover, trades, journal


def run(root):
    root = Path(root)
    output = root / "outputs"
    config = json.loads((root / "data/assumptions.json").read_text(encoding="utf-8"))
    sim = config["simulation"]
    option = Option(**config["option"])
    summaries, comparisons = [], []
    for scenario in sim["cases"]:
        paths = simulate(
            option,
            paths=sim["paths"],
            steps=sim["sessions"],
            seed=sim["seed"],
            **scenario["parameters"],
        )
        pnl, fees, turnover, trades, journal = band_paths(
            option, paths, sim["units"], sim["cost_bps"]
        )
        for policy_index, policy in enumerate(POLICIES):
            result = pnl[policy_index]
            summaries.append(
                dict(
                    case=scenario["name"],
                    policy=policy,
                    **distribution(result),
                    cash_cost=fees[policy_index].mean(),
                    turnover_usd=turnover[policy_index].mean(),
                    trade_count=trades[policy_index].mean(),
                )
            )
            difference = result - pnl[0]
            average = difference.mean()
            margin = 1.96 * difference.std(ddof=1) / np.sqrt(len(difference))
            comparisons.append(
                dict(
                    case=scenario["name"],
                    policy=policy,
                    paired_mean=average,
                    ci_low=average - margin,
                    ci_high=average + margin,
                    probability_beats_daily=(difference > 0).mean(),
                )
            )
        if scenario["name"] == "Base":
            pd.DataFrame(journal).to_csv(
                output / "band_cash_ledger.csv", index=False, float_format="%.12g"
            )
    pd.DataFrame(summaries).to_csv(
        output / "band_summary.csv", index=False, float_format="%.12g"
    )
    pd.DataFrame(comparisons).to_csv(
        output / "band_differences.csv", index=False, float_format="%.12g"
    )
    return summaries
