import os

def compile_database(results, output_dir):
    """
    Takes characterization sweep results and compiles them into:
    1. char_report.md (Markdown report matrix)
    2. inverter.lib (Mock Liberty .lib cell library)
    """
    report_path = os.path.join(output_dir, "char_report.md")
    lib_path = os.path.join(output_dir, "inverter.lib")
    
    # Extract sweeps
    input_slews = results['input_slews']  # in seconds
    load_caps = results['load_caps']      # in farads
    vdd = results.get('vdd', 1.8)         # VDD voltage in Volts

    # --- 1. Generate Markdown Report ---
    with open(report_path, "w") as f:
        f.write("# CMOS Inverter Characterization Report\n\n")
        f.write("This report presents the characterization results for the CMOS Inverter. ")
        f.write(f"Simulations were performed across a {len(input_slews)}x{len(load_caps)} grid of input transition slews and load capacitances at VDD = {vdd}V.\n\n")
        
        metrics_meta = [
            ('cell_rise', 'Cell Rise Delay (Low-to-High Prop Delay)', 'ps', 1e12),
            ('cell_fall', 'Cell Fall Delay (High-to-Low Prop Delay)', 'ps', 1e12),
            ('rise_transition', 'Rise Transition Time (10% to 90%)', 'ps', 1e12),
            ('fall_transition', 'Fall Transition Time (90% to 10%)', 'ps', 1e12)
        ]
        
        for key, name, unit, scale in metrics_meta:
            f.write(f"## {name} ({unit})\n\n")
            # Table Header
            headers = ["Slew \\ Load"] + [f"{c * 1e15:.2f} fF" for c in load_caps]
            f.write("| " + " | ".join(headers) + " |\n")
            f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
            
            # Table Rows
            matrix = results[key]
            for i, slew in enumerate(input_slews):
                row_vals = [f"**{slew * 1e12:.1f} ps**"] + [f"{val * scale:.2f}" for val in matrix[i]]
                f.write("| " + " | ".join(row_vals) + " |\n")
            f.write("\n")
            
    print(f"Generated Markdown characterization report at: {report_path}")

    # --- 2. Generate Liberty (.lib) File ---
    # Convert index vectors to standard Liberty units:
    # time_unit: "1ns", capacitive_load_unit: "1pf"
    # Slew in ns: index_1
    slew_ns = [s * 1e9 for s in input_slews]
    # Cap in pF: index_2
    cap_pf = [c * 1e12 for c in load_caps]
    
    slew_idx_str = ", ".join(f"{s:.6f}" for s in slew_ns)
    cap_idx_str = ", ".join(f"{c:.6f}" for c in cap_pf)
    
    def format_lib_matrix(matrix):
        # scale from seconds to ns (multiply by 1e9)
        lines = []
        for row in matrix:
            row_str = ", ".join(f"{val * 1e9:.6f}" for val in row)
            lines.append(f'            "{row_str}"')
        return ", \\\n".join(lines)

    # Use the grid steps in naming the template
    grid_res = f"{len(input_slews)}x{len(load_caps)}"
    
    lib_template = f"""library(inverter_char_lib) {{
  delay_model : table_lookup;
  in_place_val : {vdd:.2f};
  voltage_unit : "1V";
  time_unit : "1ns";
  leakage_power_unit : "1nW";
  current_unit : "1mA";
  pulling_resistance_unit : "1kohm";
  capacitive_load_unit (1,pf);

  lu_table_template(delay_template_{grid_res}) {{
    variable_1 : input_net_transition;
    variable_2 : total_output_net_cap;
    index_1 ("{slew_idx_str}");
    index_2 ("{cap_idx_str}");
  }}

  cell(INV) {{
    area : 10.0;
    
    pin(in) {{
      direction : input;
      capacitance : 0.00854; /* 8.54 fF extracted input capacitance */
    }}
    
    pin(out) {{
      direction : output;
      function : "!in";
      
      timing() {{
        related_pin : "in";
        timing_sense : negative_unate;
        
        cell_rise(delay_template_{grid_res}) {{
          values ( \\
{format_lib_matrix(results['cell_rise'])} \\
          );
        }}
        
        cell_fall(delay_template_{grid_res}) {{
          values ( \\
{format_lib_matrix(results['cell_fall'])} \\
          );
        }}
        
        rise_transition(delay_template_{grid_res}) {{
          values ( \\
{format_lib_matrix(results['rise_transition'])} \\
          );
        }}
        
        fall_transition(delay_template_{grid_res}) {{
          values ( \\
{format_lib_matrix(results['fall_transition'])} \\
          );
        }}
      }}
    }}
  }}
}}
"""

    with open(lib_path, "w") as f:
        f.write(lib_template)
        
    print(f"Generated mock Liberty library at: {lib_path}")
