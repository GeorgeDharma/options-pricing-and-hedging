import unittest
import numpy as np
from options.engine import Option, simulate, hedge
from options.trade_band import band_paths


class ExecutionBandTests(unittest.TestCase):
    def test_calendar_controls_match_existing_cash_ledger(self):
        contract = Option(36, 40, 1, 0.06, 0, 0.20, "put")
        paths = simulate(contract, paths=24, steps=30, seed=72)
        pnl, fees, _, trade_counts, ledger = band_paths(contract, paths, 1000, 5)
        for policy, interval in [(0, 1), (1, 5)]:
            expected = hedge(contract, paths, interval, 5, 1000)
            np.testing.assert_allclose(pnl[policy], expected["pnl"], atol=1e-8)
            np.testing.assert_allclose(fees[policy], expected["cost_paid"], atol=1e-8)
        self.assertEqual(ledger[-1]["held_shares"], 0)
        self.assertAlmostEqual(ledger[-1]["after_trade_cash"], pnl[3, 0])
        self.assertLessEqual(trade_counts[4].mean(), trade_counts[2].mean())
