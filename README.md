# Pricing and hedging a European put

George Dharma

Can a short-option desk reduce turnover while keeping the size of poor hedge outcomes close to daily rebalancing?

A 2.5-point change in delta triggers about 84 stock trades per path, down from 249 when rebalancing daily. In the matched-volatility simulation it saves $212 of execution cost while the mean of the worst 5% of losses grows by $32.

[Open the notebook](notebooks/analysis.ipynb) · [Read the report (PDF)](docs/report.pdf) · [View the result table](outputs/band_summary.csv) · [Download ZIP](https://github.com/GeorgeDharma/options-pricing-and-hedging/archive/refs/heads/main.zip)

## Run the analysis

All model assumptions are included. The full run also writes the path-level simulation table to your computer. Use Python 3.12. Download and extract the ZIP, then follow the [Windows, macOS or Linux setup instructions](docs/RUNNING.md). In an activated environment, run these commands from the project folder.

```bash
python -m pip install -r requirements.txt
python run_analysis.py
python -m unittest discover -s tests -v
```

## Code and results

`options/engine.py` contains pricing, Greeks, path simulation and the cash ledger. `options/analysis.py` runs the price, fixed-schedule and stress tests. `options/trade_band.py` implements delta triggers. `options/band_figure.py` plots execution cost against losses.

`band_summary.csv` contains the five policies across three scenarios. `band_differences.csv` compares each path with daily hedging. `band_cash_ledger.csv` shows one complete five-point-band path. The generated `simulation_pnl.csv` contains the path-level fixed-schedule results.

## Source

QuantLib, European equity-option example. The contract inputs come from the example. Coverage, execution costs, simulated market paths and trigger rules are specific to this study.

[Original source](https://github.com/lballabio/QuantLib/blob/e4090768195f9c5b0bf8a6d0cb6802238342c50d/Examples/EquityOption/EquityOption.cpp)

[Methodology](docs/METHODOLOGY.md) · [Validation](docs/VALIDATION.md)
