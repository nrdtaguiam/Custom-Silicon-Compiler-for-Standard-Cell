# Standard Cell Characterization Engine ("Silicon Compiler")

This subdirectory contains the automated characterization engine for the CMOS Inverter cell. The engine sweeps the inverter circuit across a multidimensional grid of input slews and load capacitances to build standard Liberty (`.lib`) files and detailed timing matrices.

---

## 📂 Project Structure

- **[inv_template.spice]**: A parametric SPICE template containing the inverter schematic under test (DUT) with placeholder tokens for input slew (`{{INPUT_SLEW}}`) and output load capacitance (`{{LOAD_CAP}}`).
- **[characterize.py]**: The Python execution orchestrator that manages sweeps, substitutes placeholders, executes ngspice inside WSL, and manages temporary simulation artifacts.
- **[wave_parser.py]**: The mathematical waveform engine that loads tabular data from ngspice, dynamically detects rising/falling input transitions, and performs linear interpolation to extract exact 10%, 50%, and 90% crossovers.
- **[generate_lib.py]**: The database compiler that compiles the characterization matrices into standard formats.

---

## ⚙️ Environment Requirements

- **Host (Windows)**: Python 3.x with standard libraries (`argparse`, `subprocess`, `json`, `os`, `sys`).
- **Simulation Environment (WSL)**: WSL distribution with `ngspice` installed and executable on the command line.
  *(Install inside WSL: `sudo apt-get update && sudo apt-get install -y ngspice`)*

---

## ⚡ Execution Instructions

Run the simulation controller from the root directory of the repository:

### 1. Default Run (5x5 Sweep Grid, 1.8V VDD)
Sweeps slews from **10ps to 200ps** and load capacitances from **5fF to 50fF**:
```bash
python src/cell_char/characterize.py
```

### 2. Custom Sweeps (Dynamic CLI Arguments)
Customize the sweep grid, VDD supply voltage, and range bounds:
```bash
python src/cell_char/characterize.py --grid-size 3 --vdd 1.2 --slew-min 20e-12 --slew-max 100e-12 --cap-min 5e-15 --cap-max 25e-15
```

### Options:
- `--slew-min`, `--slew-max`: Slew rate limits in seconds (e.g., `10e-12` for 10ps).
- `--cap-min`, `--cap-max`: Load capacitance limits in Farads (e.g., `5e-15` for 5fF).
- `--grid-size`: Resolution $N$ of the $N \times N$ sweep grid (default: `5`).
- `--vdd`: VDD voltage supply value (default: `1.8`).
- `--skip-check`: Skip WSL and ngspice presence verification checks.

---

## 🧮 Characterization Logic

### Crossover Definitions
For a supply voltage of $V_{DD}$, the engine calculates timing thresholds as:
- **10% Threshold**: $0.1 \times V_{DD}$
- **50% Threshold**: $0.5 \times V_{DD}$
- **90% Threshold**: $0.9 \times V_{DD}$

### Waveform Calculations
1. **Dynamic Crossover Windowing**:
   The parser scans the input waveform `v(in)` to detect when it crosses $50\%$ VDD. It defines local analysis windows dynamically around the detected rising and falling input edges, ensuring robustness against changing pulse widths or delays.
2. **Linear Interpolation**:
   To achieve sub-timestep accuracy, the exact crossing time $T_x$ is interpolated between simulation data points $(t_1, v_1)$ and $(t_2, v_2)$:
   $$T_x = t_1 + (t_2 - t_1) \times \frac{V_{\text{target}} - v_1}{v_2 - v_1}$$

3. **Metrics Extracted**:
   - `cell_fall`: propagation delay of output falling (50% input rising $\rightarrow$ 50% output falling).
   - `cell_rise`: propagation delay of output rising (50% input falling $\rightarrow$ 50% output rising).
   - `fall_transition`: transition time of output falling (90% output $\rightarrow$ 10% output).
   - `rise_transition`: transition time of output rising (10% output $\rightarrow$ 90% output).

---

## 📈 Generated Outputs

After a successful run, the compiler outputs:
1. **[char_report.md]**: Markdown tables showing calculated values (in picoseconds) for each of the 4 delay metrics across the sweep grid.
2. **[inverter.lib]**: Synopsys Liberty (.lib) library formatted using standard `table_lookup` templates. Values are automatically scaled (`ns` for delays, `pF` for capacitances) to meet Liberty specification standards.
