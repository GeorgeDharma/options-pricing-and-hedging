# Run the analysis

Use **Python 3.12**. You can read the saved notebook and charts without installing Python. To calculate the results yourself, download the full project ZIP and extract it first. A notebook downloaded on its own does not include its supporting code and data.

## Windows: the simplest route

Install Python 3.12 from [python.org](https://www.python.org/downloads/). Open the extracted project folder: you should see `README.md`, `run_analysis.py` and `requirements.txt`. Click File Explorer's address bar, type `powershell` and press Enter. Run each line below in that window.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_analysis.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The first command creates a private Python environment for this project. The second installs its required packages. The third calculates the analysis. The fourth checks the financial and numerical identities. Calling the environment's Python directly avoids PowerShell activation-policy problems.

## macOS or Linux

Open a terminal in the extracted project folder, then run:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_analysis.py
.venv/bin/python -m unittest discover -s tests -v
```

If Python 3.12 is provided as `python3` on your machine, check `python3 --version` and use that command on the first line.

## Open the notebook interactively

On Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-notebook.txt
.\.venv\Scripts\python.exe -m jupyterlab
```

On macOS or Linux:

```bash
.venv/bin/python -m pip install -r requirements-notebook.txt
.venv/bin/python -m jupyterlab
```

JupyterLab opens in your browser. Open `notebooks/analysis.ipynb`. Use **Kernel → Restart Kernel and Run All Cells** to run the notebook from a clean start. The first code cell recalculates the full experiment and can take a few minutes. Wait for it to finish before reading later results.

The notebook finds the project root automatically when opened from the root folder or its `notebooks` folder. Keep the complete folder structure together.

## What changes when you run it?

The program overwrites generated tables and figures in `outputs/`. It uses bundled data, so no API keys, paid data account or network connection is required after installing dependencies. Input files and the original PDF report are not updated by the calculation. If you change assumptions, the new results will no longer necessarily match the PDF.

## Common problems

| Message or situation | What to do |
| --- | --- |
| `py` or `python3.12` is not recognised | Install Python 3.12, then open a new terminal. |
| `No module named numpy` or another dependency | Run the install command with the same `.venv` Python used to run the project. |
| `No module named rates`, `options` or `equity` | Extract the full ZIP and run the script from the folder containing `run_analysis.py`. |
| Notebook asks for a kernel | Select Python 3 from the JupyterLab session launched above. |
| The first notebook cell is busy | It is running the analysis. Avoid starting another copy; allow a few minutes. |
| GitHub cannot preview the notebook | Download the ZIP and open the notebook locally in JupyterLab. |

Pinned analysis dependencies are in `requirements.txt`. Notebook tools are separate in `requirements-notebook.txt`. See [validation notes](VALIDATION.md) for the tested environment and results.

## The complete simulation table

`outputs/simulation_pnl.csv.gz` contains the original complete path-level table in compressed form. Compression preserves every row. Python can read it directly:

```python
import pandas as pd
pnl = pd.read_csv("outputs/simulation_pnl.csv.gz")
print(pnl.head())
```

Running the analysis also creates `outputs/simulation_pnl.csv`. That larger generated copy is excluded from Git tracking. The compressed bundled copy is a snapshot of the original experiment; it is not refreshed automatically when you change assumptions.
