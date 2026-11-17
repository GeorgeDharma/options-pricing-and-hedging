"""Original implementation of standard option formulas; currency is USD.

Rates and volatilities are decimal annual inputs. Vega/rho are per percentage
point; theta is per calendar day. Hedge simulations require zero dividends.
"""

from dataclasses import dataclass, replace
import math
import numpy as np
from scipy.special import ndtr
from scipy.optimize import brentq
from scipy.stats import t as student_t


@dataclass(frozen=True)
class Option:
    spot: float = 36.0
    strike: float = 40.0
    years: float = 1.0
    rate: float = 0.06
    dividend: float = 0.0
    volatility: float = 0.20
    kind: str = "put"

    def __post_init__(self):
        if self.spot <= 0 or self.strike <= 0 or self.years < 0 or self.volatility < 0:
            raise ValueError(
                "Spot and strike must be positive; time and volatility nonnegative."
            )
        if not all(
            math.isfinite(x)
            for x in [
                self.spot,
                self.strike,
                self.years,
                self.rate,
                self.dividend,
                self.volatility,
            ]
        ):
            raise ValueError("All option inputs must be finite.")
        if self.kind not in ("put", "call"):
            raise ValueError("kind must be put or call")


def payoff(spot, strike, kind):
    return np.maximum((np.asarray(spot) - strike) * (1 if kind == "call" else -1), 0)


def price(option, spot=None, years=None):
    """Return the European option value per unit for the supplied spot and time."""
    s = np.asarray(option.spot if spot is None else spot, dtype=float)
    t = option.years if years is None else years
    if t < 0 or np.any(s <= 0):
        raise ValueError("Remaining time must be nonnegative and spot positive.")
    if t == 0:
        return payoff(s, option.strike, option.kind)
    k, r, q, v = option.strike, option.rate, option.dividend, option.volatility
    if v == 0:
        return np.exp(-r * t) * payoff(s * np.exp((r - q) * t), k, option.kind)
    d1 = (np.log(s / k) + (r - q + v * v / 2) * t) / (v * np.sqrt(t))
    d2 = d1 - v * np.sqrt(t)
    if option.kind == "call":
        return s * np.exp(-q * t) * ndtr(d1) - k * np.exp(-r * t) * ndtr(d2)
    return k * np.exp(-r * t) * ndtr(-d2) - s * np.exp(-q * t) * ndtr(-d1)


def delta(option, spot=None, years=None):
    """Return the long-option price sensitivity per one-dollar spot change."""
    s = np.asarray(option.spot if spot is None else spot, dtype=float)
    t = option.years if years is None else years
    if t <= 0 or option.volatility <= 0:
        raise ValueError("Delta requires positive time and volatility.")
    d1 = (
        np.log(s / option.strike)
        + (option.rate - option.dividend + option.volatility**2 / 2) * t
    ) / (option.volatility * np.sqrt(t))
    return np.exp(-option.dividend * t) * (ndtr(d1) - (option.kind == "put"))


def greeks(o):
    """Return analytical risks; vega/rho are per percentage point and theta per day."""
    if o.years <= 0 or o.volatility <= 0:
        raise ValueError("Greeks require positive time and volatility.")
    s, k, t, r, q, v = o.spot, o.strike, o.years, o.rate, o.dividend, o.volatility
    d1 = (math.log(s / k) + (r - q + v * v / 2) * t) / (v * math.sqrt(t))
    d2 = d1 - v * math.sqrt(t)
    phi = math.exp(-d1 * d1 / 2) / math.sqrt(2 * math.pi)
    sign = 1 if o.kind == "call" else -1
    theta = (
        -s * math.exp(-q * t) * phi * v / (2 * math.sqrt(t))
        - sign * r * k * math.exp(-r * t) * ndtr(sign * d2)
        + sign * q * s * math.exp(-q * t) * ndtr(sign * d1)
    )
    return {
        "delta": float(delta(o)),
        "gamma": math.exp(-q * t) * phi / (s * v * math.sqrt(t)),
        "vega": s * math.exp(-q * t) * phi * math.sqrt(t) / 100,
        "theta": theta / 365,
        "rho": sign * k * t * math.exp(-r * t) * ndtr(sign * d2) / 100,
    }


def finite_greeks(o):
    """Check analytical sensitivities through small input changes and repricing."""
    hs = o.spot * 1e-4
    hv = hr = 1e-4
    ht = 1 / 3650
    p = float(price(o))
    bump = lambda name, h: float(price(replace(o, **{name: getattr(o, name) + h})))
    return {
        "delta": (bump("spot", hs) - bump("spot", -hs)) / (2 * hs),
        "gamma": (bump("spot", hs) - 2 * p + bump("spot", -hs)) / hs**2,
        "vega": (bump("volatility", hv) - bump("volatility", -hv)) / (2 * hv) / 100,
        "theta": -(bump("years", ht) - bump("years", -ht)) / (2 * ht) / 365,
        "rho": (bump("rate", hr) - bump("rate", -hr)) / (2 * hr) / 100,
    }


def tree_price(o, steps):
    """Cox-Ross-Rubinstein tree; European exercise only."""
    if not isinstance(steps, int) or steps < 1:
        raise ValueError("steps must be a positive integer")
    if o.years == 0 or o.volatility == 0:
        return float(price(o))
    dt = o.years / steps
    u = math.exp(o.volatility * math.sqrt(dt))
    d = 1 / u
    p = (math.exp((o.rate - o.dividend) * dt) - d) / (u - d)
    if not 0 <= p <= 1:
        raise ValueError("Tree probability is invalid; increase the step count.")
    terminal = o.spot * np.exp((2 * np.arange(steps + 1) - steps) * math.log(u))
    v = payoff(terminal, o.strike, o.kind)
    disc = math.exp(-o.rate * dt)
    for _ in range(steps):
        v = disc * ((1 - p) * v[:-1] + p * v[1:])
    return float(v[0])


def monte_carlo(o, pairs=100000, seed=42):
    """Antithetic terminal sampling; independent pairs determine the CI."""
    if pairs < 2:
        raise ValueError("At least two independent pairs are required.")
    z = np.random.default_rng(seed).standard_normal(pairs)
    drift = (o.rate - o.dividend - o.volatility**2 / 2) * o.years
    shock = o.volatility * math.sqrt(o.years) * z
    x = (
        0.5
        * (
            payoff(o.spot * np.exp(drift + shock), o.strike, o.kind)
            + payoff(o.spot * np.exp(drift - shock), o.strike, o.kind)
        )
        * math.exp(-o.rate * o.years)
    )
    se = float(x.std(ddof=1) / math.sqrt(pairs))
    mean = float(x.mean())
    half = float(student_t.ppf(0.975, pairs - 1)) * se
    return {
        "pairs": pairs,
        "paths": 2 * pairs,
        "price": mean,
        "standard_error": se,
        "ci_low": mean - half,
        "ci_high": mean + half,
    }


def implied_volatility(o, premium):
    """Invert a European price; reject quotes outside strict arbitrage bounds."""
    lower = float(price(replace(o, volatility=0)))
    upper = (
        o.spot * math.exp(-o.dividend * o.years)
        if o.kind == "call"
        else o.strike * math.exp(-o.rate * o.years)
    )
    if o.years <= 0 or not math.isfinite(premium) or not lower < premium < upper:
        raise ValueError("Premium must lie strictly inside European price bounds.")
    return brentq(
        lambda v: float(price(replace(o, volatility=v))) - premium, 1e-9, 10, xtol=1e-13
    )


def simulate(
    o,
    paths=30000,
    steps=252,
    seed=1010,
    realised_vol=None,
    jump_intensity=0.0,
    jump_mean=-0.10,
    jump_sd=0.15,
):
    """Risk-neutral GBM or compensated lognormal jumps, sampled exactly at grid dates.

    jump_mean is mean LOG jump, not mean percentage loss. Conditional on N jumps,
    their log sum is Normal(N*mean, sqrt(N)*sd). The compensator preserves E[S_T].
    """
    if o.dividend != 0:
        raise ValueError(
            "The hedge experiment is specified for a non-dividend-paying asset."
        )
    if paths < 1 or steps < 1 or jump_intensity < 0 or jump_sd < 0:
        raise ValueError("Invalid simulation sizes or jump parameters.")
    v = o.volatility if realised_vol is None else realised_vol
    if v < 0:
        raise ValueError("Realised volatility cannot be negative.")
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((paths, steps))
    dt = o.years / steps
    drift = o.rate - 0.5 * v * v
    logs = drift * dt + v * math.sqrt(dt) * z
    if jump_intensity:
        j_rng = np.random.default_rng(seed + 1)
        n = j_rng.poisson(jump_intensity * dt, size=z.shape)
        jumps = n * jump_mean + np.sqrt(n) * jump_sd * j_rng.standard_normal(z.shape)
        kappa = math.exp(jump_mean + jump_sd**2 / 2) - 1
        logs += jumps - jump_intensity * kappa * dt
    s = np.empty((paths, steps + 1))
    s[:, 0] = o.spot
    s[:, 1:] = o.spot * np.exp(np.cumsum(logs, axis=1))
    return s


def hedge(o, paths, interval=1, cost_bps=5.0, units=10000, trace_index=None):
    """Terminal P&L for selling units options and holding the long-option delta.

    Negative holdings are short shares. Borrowing/lending use the same rate.
    A proportional half-spread is charged on initial, subsequent and final trades.
    No outside cash is added. interval=None leaves the premium invested unhedged.
    """
    if o.dividend != 0 or cost_bps < 0 or units <= 0:
        raise ValueError(
            "Require zero dividends, nonnegative costs and positive units."
        )
    if interval is not None and (not isinstance(interval, int) or interval < 1):
        raise ValueError("interval must be a positive integer or None")
    if (
        paths.ndim != 2
        or paths.shape[1] < 2
        or np.any(paths <= 0)
        or not np.allclose(paths[:, 0], o.spot)
    ):
        raise ValueError("Paths must be positive and begin at option spot.")
    n, cols = paths.shape
    steps = cols - 1
    dt = o.years / steps
    cost_rate = cost_bps / 10000
    cash = np.full(n, float(price(o)) * units)
    h = np.zeros(n)
    cost_fv = np.zeros(n)
    cost_paid = np.zeros(n)
    turnover = np.zeros(n)
    trace = []
    for day in range(steps + 1):
        s = paths[:, day]
        t = o.years - day * dt
        cash_before = cash.copy()
        interest = np.zeros(n) if day == 0 else cash * np.expm1(o.rate * dt)
        cash += interest
        if day:
            cost_fv *= math.exp(o.rate * dt)
        old = h.copy()
        if day == steps:
            h = np.zeros(n)
        elif interval is not None and day % interval == 0:
            h = units * delta(o, s, t)
        qty = h - old
        traded = np.abs(qty) * s
        cost = traded * cost_rate
        cash -= qty * s + cost
        cost_fv += cost
        cost_paid += cost
        turnover += traded
        liability = (
            payoff(s, o.strike, o.kind) * units
            if day == steps
            else price(o, s, t) * units
        )
        settlement = liability if day == steps else np.zeros(n)
        cash -= settlement
        if trace_index is not None:
            i = trace_index
            trace.append(
                {
                    "day": day,
                    "spot": float(s[i]),
                    "years_left": t,
                    "cash_open": float(cash_before[i]),
                    "interest": float(interest[i]),
                    "shares_before": float(old[i]),
                    "trade_shares": float(qty[i]),
                    "shares_after": float(h[i]),
                    "trading_cost": float(cost[i]),
                    "option_settlement": float(settlement[i]),
                    "cash_close": float(cash[i]),
                    "stock_value": float(h[i] * s[i]),
                    "option_liability": float(liability[i]) if day < steps else 0.0,
                    "net_value": float(
                        cash[i] + h[i] * s[i] - (liability[i] if day < steps else 0)
                    ),
                }
            )
    return {
        "pnl": cash,
        "gross_pnl": cash + cost_fv,
        "cost_future_value": cost_fv,
        "cost_paid": cost_paid,
        "turnover": turnover,
        "trace": trace,
    }


def distribution(x):
    """Summarise terminal P&L, including the average of the worst five percent."""
    x = np.asarray(x)
    tail = np.sort(x)[: max(1, int(math.ceil(0.05 * len(x))))]
    se = float(x.std(ddof=1) / math.sqrt(len(x)))
    return {
        "mean": float(x.mean()),
        "std": float(x.std(ddof=1)),
        "p05": float(np.quantile(x, 0.05)),
        "tail_mean": float(tail.mean()),
        "mean_se": se,
        "mean_ci_low": float(x.mean() - 1.96 * se),
        "mean_ci_high": float(x.mean() + 1.96 * se),
    }
