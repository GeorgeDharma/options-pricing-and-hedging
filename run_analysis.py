from pathlib import Path
from options.analysis import run

if __name__ == "__main__":
    r = run(Path(__file__).resolve().parent)
    print(f'European put value: ${r["option_value"]:.8f} per unit')
    for x in r["hedging"]:
        print(
            f'{x["case"]:18s} | {x["policy"]:18s} | mean {x["mean"]:10.2f} | SD {x["std"]:10.2f} | worst-5% mean {x["tail_mean"]:10.2f}'
        )
