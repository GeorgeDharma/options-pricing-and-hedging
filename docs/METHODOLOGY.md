# Options pricing and hedging
George Dharma

An original Python implementation of European option pricing, implied volatility
and a self-financing delta-hedging experiment. The financial question is whether
more frequent hedging reduces terminal losses enough to justify its trading costs.

## Rebalancing when delta moves

Five policies trade the same 30,000 paths within each scenario. Two follow the calendar. The other three trade when the gap between the current and desired stock hedge reaches 2.5, 5 or 10 delta points. Entry and liquidation count as trades. Funding and transaction costs enter each policy’s own cash ledger.

For the 2.5-point band, the base simulation averages 83.5 trades per path and $920 in trading costs. Daily rebalancing averages 249.3 trades and $1,132 in costs. The mean loss across the worst 5% of paths rises from $5,477 to $5,509. Each policy has its own worst 5% of paths. The separate paired analysis compares terminal cash on identical paths and estimates a $219 mean improvement for the band, with a $209 to $229 Monte Carlo interval. [Execution results](../outputs/band_summary.csv) · [Paired differences](../outputs/band_differences.csv) · [Example cash ledger](../outputs/band_cash_ledger.csv)

## Running this version

See [RUNNING.md](RUNNING.md). Open [the notebook](../notebooks/analysis.ipynb) for the worked calculation.

## Case and interpretation

- European put: spot $36, strike $40, one year, rate 6%, zero dividend yield,
  volatility 20%. Values are per option unit unless explicitly scaled.
- QuantLib's published example supplies those common inputs. Its term structures
  run from 17 May 1998 to maturity on 17 May 1999 using Actual/365 Fixed: one year.
  No current market price or live calibration is claimed.
- Sell 100 hypothetical contracts with a 100-unit multiplier. The underlying is
  a tradable, non-dividend-paying asset, with cash settlement at expiry.
- Constructed bid/ask $3.80/$3.90 demonstrate volatility inversion and spreads.
- 30,000 paths per scenario; 252 sessions; fixed seed 1010. The pricing Monte
  Carlo uses seed 42 and independent antithetic pairs for its confidence interval.
- Hedge schedules share paths within each scenario. Scenarios also share
  diffusion random numbers. Jumps use a separate seed. No paths are selected for
  performance; the ledger example is simply path 0.
- Lending and borrowing both use a continuously compounded 6% rate. Short
  shares are allowed; additional stock-borrow fees and margin constraints are
  not modelled. Every asset trade costs 5 bp of its absolute traded value,
  including entry and final liquidation. The option is sold at its analytical
  value; no option dealing spread or fee is added.
- The high-volatility scenario uses 30% realised volatility with 20% hedge
  volatility. Jump parameters are annual intensity 1, log-jump mean −0.10 and
  log-jump standard deviation 0.15; the drift includes the jump compensator.
- Risk-neutral dynamics isolate hedging errors and model mismatch. They do not
  forecast investment returns. Results are simulated, not a historical backtest.

## Files

| File | Purpose |
|---|---|
| `options/engine.py` | Analytical price and Greeks, tree, Monte Carlo, IV solver, paths and hedge cash ledger |
| `options/analysis.py` | Fixed comparisons, summaries, exports and figures |
| `data/assumptions.json` | All case parameters and input provenance |
| `outputs/results.json` | Complete machine-readable result; supports the readable report and Excel |
| `outputs/*.csv` | Pricing, sensitivities, hedge distributions and sample ledger |
| `outputs/simulation_pnl.csv` | Locally generated path-level terminal P&L, gross P&L and financed costs for the 12 fixed-schedule comparisons |
| `tests/test_options.py` | 20 financial and accounting tests |

The final workbook recalculates Black–Scholes prices, Greeks, an implied-volatility
bisection and one sample hedge ledger. Tree, Monte Carlo and hedge distribution
tables are imported Python results and are labelled accordingly. Changing the
live pricing sheet does not regenerate simulated paths. Rerun this project for
a different simulation, then regenerate the companion documents from its outputs.

## Sources and adaptation

1. QuantLib, [EquityOption example at commit e4090768195f9c5b0bf8a6d0cb6802238342c50d](https://github.com/lballabio/QuantLib/blob/e4090768195f9c5b0bf8a6d0cb6802238342c50d/Examples/EquityOption/EquityOption.cpp).
   Adopted the European example parameters and comparison of numerical methods.
   The implementation here is independent; it does not require QuantLib.
2. Goldman Sachs, [scenario examples](https://developer.gs.com/docs/gsquant/pricing-and-risk/scenarios/)
   and [risk-measure definitions](https://developer.gs.com/docs/gsquant/pricing-and-risk/measures/).
   Adapted the price–risk–shock comparison workflow. No GS service or entitlement
   is required. Risk units are explicitly defined here and may differ from GS units.
3. Bühler, Gonon, Teichmann and Wood, [Deep Hedging](https://arxiv.org/abs/1802.03042),
   and the author's [public implementation](https://github.com/hansbuehler/deephedging).
   Used as research context for measuring hedge risk together with trading costs.
   No neural-network method or source code from that repository is included.
4. Cboe, [Option EOD Summary](https://datashop.cboe.com/option-eod-summary) and
   [file layout](https://datashop.cboe.com/documents/Option_EOD_Summary_Layout.pdf).
   The sample ZIP endpoint returned HTTP 403. No rows were downloaded or used.
   A real quote study would verify contract style, settlement, bid/ask, observation
   time and a matching underlying before fitting volatility.

The Word/PDF report explains the decision in plain language. The notebook gives
the mathematical and coding detail needed to reproduce and discuss it.
