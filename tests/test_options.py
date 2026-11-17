import unittest
from dataclasses import replace
import numpy as np
from options.engine import *


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.o = Option()

    def test_published_case_known_value(self):
        self.assertAlmostEqual(float(price(self.o)), 3.84430779159684, places=11)

    def test_put_call_parity(self):
        for q in [0, 0.02]:
            p = replace(self.o, dividend=q)
            c = replace(p, kind="call")
            self.assertAlmostEqual(
                float(price(c) - price(p)),
                p.spot * np.exp(-q * p.years) - p.strike * np.exp(-p.rate * p.years),
                places=12,
            )

    def test_zero_volatility_and_expiry(self):
        self.assertAlmostEqual(
            float(price(replace(self.o, volatility=0))), 40 * np.exp(-0.06) - 36
        )
        self.assertEqual(float(price(replace(self.o, years=0))), 4)

    def test_invalid_option(self):
        for args in [
            {"spot": 0},
            {"volatility": -1},
            {"kind": "swap"},
            {"rate": float("nan")},
        ]:
            with self.assertRaises(ValueError):
                Option(**args)

    def test_greeks_finite_difference(self):
        for kind in ["call", "put"]:
            o = replace(self.o, kind=kind, dividend=0.02)
            for k, v in greeks(o).items():
                self.assertAlmostEqual(v, finite_greeks(o)[k], delta=2e-7)

    def test_tree_accuracy_and_probability(self):
        self.assertAlmostEqual(
            tree_price(self.o, 3200), float(price(self.o)), delta=0.001
        )
        with self.assertRaises(ValueError):
            tree_price(replace(self.o, rate=1, volatility=0.01), 1)

    def test_mc_interval_and_pair_count(self):
        a = monte_carlo(self.o, 100000)
        self.assertEqual(a["paths"], 200000)
        self.assertLess(a["ci_low"], price(self.o))
        self.assertGreater(a["ci_high"], price(self.o))
        self.assertEqual(a, monte_carlo(self.o, 100000))

    def test_iv_roundtrip(self):
        for kind in ["put", "call"]:
            for v in [0.1, 0.2, 0.6]:
                o = replace(self.o, kind=kind, volatility=v)
                self.assertAlmostEqual(
                    implied_volatility(o, float(price(o))), v, places=10
                )

    def test_iv_bounds(self):
        for p in [0, 40, np.nan]:
            with self.assertRaises(ValueError):
                implied_volatility(self.o, p)

    def test_value_monotonicity(self):
        self.assertGreater(price(replace(self.o, volatility=0.3)), price(self.o))
        self.assertLess(price(replace(self.o, spot=37)), price(self.o))


class HedgeTests(unittest.TestCase):
    def setUp(self):
        self.o = Option()
        self.paths = simulate(self.o, paths=2000, steps=252, seed=55)

    def test_unhedged_cash_identity(self):
        a = hedge(self.o, self.paths, None)
        expected = (
            price(self.o) * 10000 * np.exp(0.06)
            - payoff(self.paths[:, -1], 40, "put") * 10000
        )
        np.testing.assert_allclose(a["pnl"], expected, atol=1e-7)

    def test_cost_financing_identity(self):
        a = hedge(self.o, self.paths, 5, 5)
        b = hedge(self.o, self.paths, 5, 0)
        np.testing.assert_allclose(
            a["pnl"] + a["cost_future_value"], b["pnl"], atol=1e-7
        )

    def test_cost_linearity_and_scale(self):
        a = hedge(self.o, self.paths, 5, 5)
        b = hedge(self.o, self.paths, 5, 10)
        np.testing.assert_allclose(
            a["gross_pnl"] - 2 * a["cost_future_value"], b["pnl"], atol=1e-7
        )
        c = hedge(self.o, self.paths, 5, 5, units=100)
        np.testing.assert_allclose(c["pnl"] * 100, a["pnl"], atol=1e-7)

    def test_ledger_reconciliation_and_settlement(self):
        a = hedge(self.o, self.paths[:1], 5, 5, trace_index=0)
        for row in a["trace"]:
            expected = (
                row["cash_open"]
                + row["interest"]
                - row["trade_shares"] * row["spot"]
                - row["trading_cost"]
                - row["option_settlement"]
            )
            self.assertAlmostEqual(row["cash_close"], expected, places=8)
            self.assertAlmostEqual(
                row["shares_after"],
                row["shares_before"] + row["trade_shares"],
                places=8,
            )
        self.assertEqual(a["trace"][-1]["shares_after"], 0)
        self.assertAlmostEqual(a["trace"][-1]["net_value"], a["pnl"][0], places=8)
        self.assertGreater(a["trace"][0]["trading_cost"], 0)

    def test_no_lookahead(self):
        a = self.paths[:1].copy()
        b = a.copy()
        b[:, 101:] *= 1.2
        x = hedge(self.o, a, 5, trace_index=0)["trace"]
        y = hedge(self.o, b, 5, trace_index=0)["trace"]
        for i in range(101):
            self.assertEqual(x[i], y[i])

    def test_small_time_steps_reduce_base_dispersion(self):
        daily = hedge(self.o, self.paths, 1, 0)["pnl"]
        monthly = hedge(self.o, self.paths, 21, 0)["pnl"]
        self.assertLess(daily.std(), monthly.std())

    def test_simulation_martingale_and_reproducibility(self):
        for jump in [0, 1]:
            s = simulate(self.o, paths=30000, steps=12, seed=123, jump_intensity=jump)
            x = s[:, -1] * np.exp(-0.06)
            self.assertLess(abs(x.mean() - 36), 4 * x.std(ddof=1) / np.sqrt(len(x)))
        np.testing.assert_array_equal(
            self.paths, simulate(self.o, paths=2000, steps=252, seed=55)
        )

    def test_zero_change_hedge_has_no_interim_trade(self):
        a = hedge(self.o, self.paths[:1], 999, trace_index=0)
        self.assertTrue(all(r["trade_shares"] == 0 for r in a["trace"][1:-1]))

    def test_simulation_rejects_unmodelled_dividends(self):
        with self.assertRaises(ValueError):
            simulate(replace(self.o, dividend=0.02))

    def test_tail_definition(self):
        a = distribution(np.arange(100, dtype=float))
        self.assertEqual(a["tail_mean"], 2)


if __name__ == "__main__":
    unittest.main()
