import os
import subprocess
import json
import sys
import argparse

# Import wave_parser
from wave_parser import parse_simulation_data

def to_spice_string(val):
    """
    Converts a float value to a SPICE engineering notation string.
    Example: 10e-12 -> '10.0p', 5e-15 -> '5.0f'
    """
    if val >= 1:
        return f"{val:.6g}"
    elif val >= 1e-3:
        return f"{val * 1e3:.6g}m"
    elif val >= 1e-6:
        return f"{val * 1e6:.6g}u"
    elif val >= 1e-9:
        return f"{val * 1e9:.6g}n"
    elif val >= 1e-12:
        return f"{val * 1e12:.6g}p"
    elif val >= 1e-15:
        return f"{val * 1e15:.6g}f"
    else:
        return f"{val:.6g}"

def check_wsl_ngspice():
    """
    Pre-flight check to verify that WSL and ngspice are accessible on the system.
    """
    print("Performing environment checks...")
    try:
        # Check if wsl command is available and ngspice is installed inside
        res = subprocess.run(
            ["wsl", "ngspice", "--version"],
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode == 0:
            print("WSL and ngspice environment check PASSED.")
            return True
        else:
            print("Error: WSL is available, but ngspice check returned non-zero code.")
            print(f"Stdout: {res.stdout}\nStderr: {res.stderr}")
            return False
    except FileNotFoundError:
        print("Error: 'wsl' command not found on Host system PATH. Please ensure WSL is installed.")
        return False
    except Exception as e:
        print(f"Error during environment check: {e}")
        return False

def run_characterization():
    parser = argparse.ArgumentParser(description="CMOS Inverter Standard Cell Characterization Engine")
    parser.add_argument("--slew-min", type=float, default=10e-12, help="Minimum input slew in seconds (default: 10ps)")
    parser.add_argument("--slew-max", type=float, default=200e-12, help="Maximum input slew in seconds (default: 200ps)")
    parser.add_argument("--cap-min", type=float, default=5e-15, help="Minimum load cap in farads (default: 5fF)")
    parser.add_argument("--cap-max", type=float, default=50e-15, help="Maximum load cap in farads (default: 50fF)")
    parser.add_argument("--grid-size", type=int, default=5, help="Sweep grid resolution NxN (default: 5)")
    parser.add_argument("--vdd", type=float, default=1.8, help="VDD supply voltage in Volts (default: 1.8V)")
    parser.add_argument("--skip-check", action="store_true", help="Skip pre-flight WSL/ngspice checks")
    
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "inv_template.spice")
    temp_sim_path = os.path.join(script_dir, "temp_sim.spice")
    temp_out_path = os.path.join(script_dir, "temp_out.dat")
    temp_raw_path = os.path.join(script_dir, "raw_out.raw")
    
    # 1. Environment Verification
    if not args.skip_check:
        if not check_wsl_ngspice():
            print("Aborting characterization due to environment check failure.")
            sys.exit(1)

    # 2. Read Template
    if not os.path.exists(template_path):
        print(f"Error: Template file not found at {template_path}")
        sys.exit(1)
        
    with open(template_path, "r") as f:
        template_content = f.read()

    # Generate Sweep Ranges
    steps = args.grid_size
    input_slews = [args.slew_min + i * (args.slew_max - args.slew_min) / (steps - 1) for i in range(steps)]
    load_caps = [args.cap_min + i * (args.cap_max - args.cap_min) / (steps - 1) for i in range(steps)] if steps > 1 else [args.cap_min]
    if steps == 1:
        input_slews = [args.slew_min]
        load_caps = [args.cap_min]

    # Suffix strings for replacing in SPICE file
    slew_strings = [to_spice_string(s) for s in input_slews]
    cap_strings = [to_spice_string(c) for c in load_caps]

    # Initialize results structures
    results = {
        'input_slews': input_slews,
        'load_caps': load_caps,
        'vdd': args.vdd,
        'cell_rise': [[0.0]*steps for _ in range(steps)],
        'cell_fall': [[0.0]*steps for _ in range(steps)],
        'rise_transition': [[0.0]*steps for _ in range(steps)],
        'fall_transition': [[0.0]*steps for _ in range(steps)]
    }

    print("=" * 60)
    print("Starting CMOS Inverter Standard Cell Characterization Sweep")
    print(f"Sweep Grid: {steps} Input Slews x {steps} Load Capacitances = {steps*steps} Simulations")
    print(f"VDD Voltage: {args.vdd}V")
    print(f"Slew Range: {slew_strings[0]} to {slew_strings[-1]}")
    print(f"Load Cap Range: {cap_strings[0]} to {cap_strings[-1]}")
    print("=" * 60)

    # 3. Sweep Matrix
    for i, (slew_val, slew_str) in enumerate(zip(input_slews, slew_strings)):
        for j, (cap_val, cap_str) in enumerate(zip(load_caps, cap_strings)):
            sim_idx = i * steps + j + 1
            print(f"Simulation {sim_idx}/{steps*steps}: Slew={slew_str}, C_load={cap_str} ... ", end="")
            
            # Clean up old output files to prevent reading stale data
            for file_to_remove in [temp_out_path, temp_raw_path]:
                if os.path.exists(file_to_remove):
                    try:
                        os.remove(file_to_remove)
                    except Exception as e:
                        print(f"\nWarning: could not remove {file_to_remove}: {e}")

            # Substitute placeholders in SPICE template
            sim_content = template_content
            sim_content = sim_content.replace("{{INPUT_SLEW}}", slew_str)
            sim_content = sim_content.replace("{{LOAD_CAP}}", cap_str)
            sim_content = sim_content.replace("{{TEMP_OUT_FILE}}", "temp_out.dat")
            
            # Write temp sim file
            with open(temp_sim_path, "w") as f:
                f.write(sim_content)
                
            # Run simulation in WSL
            cmd = ["wsl", "ngspice", "-b", "-r", "raw_out.raw", "temp_sim.spice"]
            try:
                res = subprocess.run(
                    cmd, 
                    cwd=script_dir, 
                    capture_output=True, 
                    text=True, 
                    check=True
                )
            except subprocess.CalledProcessError as e:
                print(f"\nError running simulation: {e}")
                print(f"Stderr:\n{e.stderr}")
                sys.exit(1)
                
            # Verify simulation wrote output
            if not os.path.exists(temp_out_path):
                print(f"\nError: Simulation did not output data file at {temp_out_path}")
                print(f"Stdout:\n{res.stdout}")
                print(f"Stderr:\n{res.stderr}")
                sys.exit(1)
                
            # Parse waveforms
            try:
                metrics = parse_simulation_data(temp_out_path, vdd=args.vdd)
                
                # Store in matrix (slew is row i, load cap is column j)
                results['cell_rise'][i][j] = metrics['cell_rise']
                results['cell_fall'][i][j] = metrics['cell_fall']
                results['rise_transition'][i][j] = metrics['rise_transition']
                results['fall_transition'][i][j] = metrics['fall_transition']
                
                print("PASSED")
            except Exception as e:
                print(f"\nFAILED to parse waveform data: {e}")
                sys.exit(1)

    print("-" * 60)
    print("Sweep complete. Generating reports and Liberty database...")
    print("-" * 60)

    # 4. Import and execute compiler
    try:
        from generate_lib import compile_database
        compile_database(results, script_dir)
        print("Characterization pipeline completed successfully!")
    except Exception as e:
        print(f"Error compiling characterization databases: {e}")
        sys.exit(1)
        
    # 5. Clean up remaining temporary files
    for file_to_remove in [temp_sim_path, temp_out_path, temp_raw_path]:
        if os.path.exists(file_to_remove):
            try:
                os.remove(file_to_remove)
            except Exception as e:
                pass

if __name__ == "__main__":
    run_characterization()
