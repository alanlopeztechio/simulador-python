"""
Main GUI window for the Cold Chain Simulator.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.stops_tab import StopsTab
from gui.distributions_tab import DistributionsTab
from gui.config_tab import ConfigTab
from gui.results_tab import ResultsTab


class SimulatorGUI:
    """Main application window for the Cold Chain Simulator."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("COLD CHAIN SIMULATOR - CUSTOM ROUTES")
        self.root.geometry("1200x800")
        
        # Create main notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.stops_tab = StopsTab(self.notebook)
        self.distributions_tab = DistributionsTab(self.notebook, self.stops_tab)
        self.results_tab = ResultsTab(self.notebook, output_dir="simulation_outputs")
        self.config_tab = ConfigTab(self.notebook, self.stops_tab, self.distributions_tab)
        
        # Add tabs to notebook
        self.notebook.add(self.stops_tab, text="Stops")
        self.notebook.add(self.distributions_tab, text="Distribution Parameters")
        self.notebook.add(self.results_tab, text="Results")
        self.notebook.add(self.config_tab, text="Save Configurations")
        
        # Bottom action bar
        self._create_action_bar()
        
        # Status bar
        self._create_status_bar()
        
        # Bind tab change event
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
    
    def _create_action_bar(self):
        """Create bottom action bar with generate button."""
        action_frame = tk.Frame(self.root, bg="#f0f0f0", pady=10)
        action_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Generation controls
        control_frame = tk.Frame(action_frame, bg="#f0f0f0")
        control_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(control_frame, text="Samples (JSONs):", bg="#f0f0f0", 
                font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        self.num_samples_var = tk.IntVar(value=1)
        tk.Spinbox(control_frame, from_=1, to=50, textvariable=self.num_samples_var, 
                  width=5, font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        
        self.use_real_routes_var = tk.BooleanVar(value=False)
        real_routes_check = tk.Checkbutton(control_frame, text="Use Real Routes (OSM)", 
                      variable=self.use_real_routes_var, bg="#f0f0f0",
                      font=("Arial", 9))
        real_routes_check.pack(side=tk.LEFT, padx=10)
        
        # Add tooltip/warning for real routes
        def create_tooltip(widget, text):
            def on_enter(event):
                tooltip = tk.Toplevel()
                tooltip.wm_overrideredirect(True)
                tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                label = tk.Label(tooltip, text=text, background="#ffffe0", 
                               relief=tk.SOLID, borderwidth=1, font=("Arial", 8))
                label.pack()
                widget.tooltip = tooltip
            
            def on_leave(event):
                if hasattr(widget, 'tooltip'):
                    widget.tooltip.destroy()
            
            widget.bind('<Enter>', on_enter)
            widget.bind('<Leave>', on_leave)
        
        create_tooltip(real_routes_check, 
                      "⚠️ Real Routes require locations near roads.\n"
                      "Use the location search for best results.\n"
                      "Avoid generic coordinates far from streets.")
        
        # Secondary routes checkbox
        self.use_secondary_routes_var = tk.BooleanVar(value=False)
        secondary_check = tk.Checkbutton(control_frame, text="Secondary Routes?", 
                                        variable=self.use_secondary_routes_var, 
                                        bg="#f0f0f0",
                                        font=("Arial", 9),
                                        command=self._toggle_secondary_routes)
        secondary_check.pack(side=tk.LEFT, padx=10)
        
        # Secondary routes count dropdown
        tk.Label(control_frame, text="Count:", bg="#f0f0f0", 
                font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.secondary_routes_count_var = tk.IntVar(value=1)
        self.secondary_routes_dropdown = ttk.Combobox(control_frame, 
                                                      textvariable=self.secondary_routes_count_var,
                                                      values=[1, 2, 3],
                                                      width=5,
                                                      state="disabled",
                                                      font=("Arial", 9))
        self.secondary_routes_dropdown.pack(side=tk.LEFT, padx=5)
        
        # Include location names checkbox
        self.include_location_names_var = tk.BooleanVar(value=False)
        location_names_check = tk.Checkbutton(control_frame, text="Include Location Names", 
                                             variable=self.include_location_names_var, 
                                             bg="#f0f0f0",
                                             font=("Arial", 9))
        location_names_check.pack(side=tk.LEFT, padx=10)
        
        create_tooltip(location_names_check, 
                      "Add location names (city, street) to each data point.\n"
                      "⚠️ May slow down generation (requires API calls).")
        
        # Generate button
        tk.Button(action_frame, text="🚀 GENERATE SIMULATION", 
                 command=self.start_generation,
                 bg="#FF5722", fg="white", 
                 font=("Arial", 14, "bold"),
                 padx=20, pady=10).pack(side=tk.RIGHT, padx=20)
    
    def _create_status_bar(self):
        """Create status bar at bottom."""
        self.status_var = tk.StringVar(value="Ready")
        status_bar = tk.Label(self.root, textvariable=self.status_var, 
                             bd=1, relief=tk.SUNKEN, anchor=tk.W,
                             font=("Arial", 9))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _toggle_secondary_routes(self):
        """Enable/disable secondary routes dropdown."""
        if self.use_secondary_routes_var.get():
            self.secondary_routes_dropdown.config(state="readonly")
        else:
            self.secondary_routes_dropdown.config(state="disabled")
    
    def _on_tab_changed(self, event):
        """Handle tab change events."""
        current_tab = self.notebook.index(self.notebook.select())
        
        # Update status based on active tab
        tab_names = ["Stops", "Distribution Parameters", "Results", "Save Configurations"]
        if current_tab < len(tab_names):
            self.status_var.set(f"Active Tab: {tab_names[current_tab]}")
    
    def start_generation(self):
        """Start simulation generation process."""
        # Validate route configuration
        route_config = self.stops_tab.get_route_config()
        if not route_config:
            return
        
        # Apply distributions to route
        if not self.distributions_tab.apply_distributions_to_route(route_config):
            return
        
        # Confirm generation
        num_samples = self.num_samples_var.get()
        use_real = self.use_real_routes_var.get()
        use_secondary = self.use_secondary_routes_var.get()
        secondary_count = self.secondary_routes_count_var.get() if use_secondary else 0
        include_location_names = self.include_location_names_var.get()
        
        total_files = num_samples * len(route_config.sensors)
        if use_secondary:
            total_files += (num_samples * len(route_config.sensors) * secondary_count)
        
        msg = (f"Generate simulation with:\n\n"
               f"Route: {route_config.route_name}\n"
               f"Segments: {len(route_config.segments)}\n"
               f"Sensors: {len(route_config.sensors)}\n"
               f"Samples: {num_samples}\n"
               f"Real Routes: {'Yes' if use_real else 'No'}\n"
               f"Secondary Routes: {secondary_count if use_secondary else 'No'}\n\n"
               f"This will create {total_files} JSON file(s).")
        
        if not messagebox.askyesno("Confirm Generation", msg):
            return
        
        # Run generation in background thread
        self.status_var.set("Generating simulation...")
        self.root.config(cursor="wait")
        
        thread = threading.Thread(target=self._run_simulation, 
                                 args=(route_config, num_samples, use_real, use_secondary, secondary_count, include_location_names),
                                 daemon=True)
        thread.start()
    
    def _run_simulation(self, route_config, num_samples, use_real_routes, use_secondary_routes=False, secondary_routes_count=0, include_location_names=False):
        """Run simulation in background thread.
        
        Generates complete RFID tag JSON files using the simulator.
        """
        try:
            # Import adapter
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from simulator_adapter import SimulatorAdapter
            
            output_dir = "simulation_outputs"
            
            # Generate simulations using the adapter
            generated_files = SimulatorAdapter.generate_simulations(
                route_config=route_config,
                num_samples=num_samples,
                use_real_routes=use_real_routes,
                use_secondary_routes=use_secondary_routes,
                secondary_routes_count=secondary_routes_count,
                output_dir=output_dir,
                include_location_names=include_location_names
            )
            
            # Update UI on main thread
            self.root.after(0, self._generation_complete, generated_files)
            
        except Exception as e:
            import traceback
            error_details = f"{str(e)}\n\n{traceback.format_exc()}"
            self.root.after(0, self._generation_error, error_details)
    
    def _generation_complete(self, generated_files):
        """Called when generation completes successfully."""
        self.root.config(cursor="")
        self.status_var.set("Generation complete")
        
        # Check if auto-save to Neon is enabled
        auto_save_enabled = self.config_tab.get_auto_save_enabled()
        saved_to_neon = False
        neon_ids = []
        
        if auto_save_enabled and isinstance(generated_files, list):
            # Try to save to Neon
            try:
                from db.database import save_simulation_to_neon
                
                self.status_var.set("Saving to Neon database...")
                
                for json_file in generated_files:
                    try:
                        sim_id = save_simulation_to_neon(json_file=json_file)
                        neon_ids.append(sim_id)
                    except Exception as e:
                        print(f"Failed to save {json_file}: {e}")
                
                if neon_ids:
                    saved_to_neon = True
                    self.status_var.set(f"Generation complete - {len(neon_ids)} saved to Neon")
                
            except Exception as e:
                print(f"Auto-save to Neon failed: {e}")
                self.status_var.set("Generation complete - Neon save failed")
        
        # Show success message
        if isinstance(generated_files, list):
            files_list = "\n".join([f"  • {os.path.basename(f)}" for f in generated_files[:10]])
            if len(generated_files) > 10:
                files_list += f"\n  ... and {len(generated_files) - 10} more"
            
            success_msg = f"✓ Generated {len(generated_files)} simulation file(s):\n\n{files_list}\n\nSaved to: simulation_outputs/"
            
            if saved_to_neon:
                success_msg += f"\n\n💾 {len(neon_ids)} simulation(s) saved to Neon database"
                if neon_ids:
                    success_msg += f"\nDatabase IDs: {', '.join(map(str, neon_ids[:5]))}"
                    if len(neon_ids) > 5:
                        success_msg += f" ... and {len(neon_ids) - 5} more"
            
            messagebox.showinfo("Success", success_msg)
        else:
            messagebox.showinfo("Success", f"Simulation complete:\n{generated_files}")
        
        # Refresh results tab
        self.results_tab.refresh()
    
    def _generation_error(self, error_msg):
        """Called when generation encounters an error."""
        self.root.config(cursor="")
        self.status_var.set("Generation failed")
        messagebox.showerror("Generation Error", f"An error occurred:\n\n{error_msg}")


def main():
    """Main entry point."""
    root = tk.Tk()
    app = SimulatorGUI(root)
    
    # Center window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    root.mainloop()


if __name__ == "__main__":
    main()
