"""
Save Configurations Tab - Persist and load route configurations.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
from datetime import datetime
from typing import Optional
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.route import RouteConfig, RoutePoint
from models.segment import SegmentMetadata
from models.distribution import Distribution
from models.sensor import SensorConfig


class ConfigTab(tk.Frame):
    """Tab 4: Save Configurations - Save and load complete route configurations."""
    
    def __init__(self, parent, stops_tab, distributions_tab):
        super().__init__(parent)
        self.stops_tab = stops_tab
        self.distributions_tab = distributions_tab
        self.config_dir = "saved_configurations"
        
        # Ensure directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        self._build_ui()
        self.refresh_config_list()
    
    def _build_ui(self):
        """Build the UI."""
        # Title
        title_frame = tk.Frame(self, pady=10)
        title_frame.pack(fill=tk.X, padx=10)
        tk.Label(title_frame, text="Save Configurations", 
                font=("Arial", 14, "bold")).pack()
        
        # Save options
        save_frame = tk.LabelFrame(self, text="Save Options", 
                                   font=("Arial", 10, "bold"), padx=10, pady=10)
        save_frame.pack(fill=tk.X, padx=10, pady=5)
        
        btn_container = tk.Frame(save_frame)
        btn_container.pack(fill=tk.X)
        
        tk.Button(btn_container, text="Save Route Configuration", 
                 command=self._save_route_config,
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                 width=25).pack(side=tk.LEFT, padx=5, pady=5)
        
        tk.Button(btn_container, text="Save Distribution Configuration", 
                 command=self._save_distribution_config,
                 bg="#2196F3", fg="white", font=("Arial", 10, "bold"),
                 width=25).pack(side=tk.LEFT, padx=5, pady=5)
        
        tk.Button(btn_container, text="Save Sensors Configuration", 
                 command=self._save_sensors_config,
                 bg="#FF9800", fg="white", font=("Arial", 10, "bold"),
                 width=25).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Saved configurations list
        list_frame = tk.LabelFrame(self, text="Saved Configurations List", 
                                   font=("Arial", 10, "bold"), padx=10, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Listbox with scrollbar
        scroll_frame = tk.Frame(list_frame)
        scroll_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(scroll_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.config_listbox = tk.Listbox(scroll_frame, yscrollcommand=scrollbar.set,
                                         font=("Arial", 9), height=15)
        self.config_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.config_listbox.yview)
        
        # Action buttons
        action_frame = tk.Frame(list_frame)
        action_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(action_frame, text="Load", command=self._load_config,
                 bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text="Delete", command=self._delete_config,
                 bg="#E53935", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text="Refresh", command=self.refresh_config_list,
                 bg="#2196F3", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
    
    def _save_route_config(self):
        """Save complete route configuration (route + distributions + sensors)."""
        route_config = self.stops_tab.get_route_config()
        if not route_config:
            return
        
        # Apply distributions
        if not self.distributions_tab.apply_distributions_to_route(route_config):
            return
        
        # Ask for filename
        filename = filedialog.asksaveasfilename(
            initialdir=self.config_dir,
            title="Save Route Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        # Serialize to JSON
        config_dict = self._route_config_to_dict(route_config)
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, default=str)
            messagebox.showinfo("Success", f"Configuration saved to:\n{filename}")
            self.refresh_config_list()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save configuration:\n{str(e)}")
    
    def _save_distribution_config(self):
        """Save only distribution configurations."""
        distributions = self.distributions_tab.get_all_distributions()
        if not distributions:
            messagebox.showwarning("No Distributions", "No distributions configured to save.")
            return
        
        filename = filedialog.asksaveasfilename(
            initialdir=self.config_dir,
            title="Save Distribution Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump({"distributions": distributions}, f, indent=2)
                messagebox.showinfo("Success", f"Distributions saved to:\n{filename}")
                self.refresh_config_list()
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save:\n{str(e)}")
    
    def _save_sensors_config(self):
        """Save only sensor configurations."""
        route_config = self.stops_tab.get_route_config()
        if not route_config or not route_config.sensors:
            messagebox.showwarning("No Sensors", "No sensors configured to save.")
            return
        
        sensors_dict = {"sensors": [self._sensor_to_dict(s) for s in route_config.sensors]}
        
        filename = filedialog.asksaveasfilename(
            initialdir=self.config_dir,
            title="Save Sensors Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(sensors_dict, f, indent=2)
                messagebox.showinfo("Success", f"Sensors saved to:\n{filename}")
                self.refresh_config_list()
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save:\n{str(e)}")
    
    def _load_config(self):
        """Load selected configuration."""
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a configuration to load.")
            return
        
        filename = self.config_listbox.get(selection[0]).split(" - ")[0]
        filepath = os.path.join(self.config_dir, filename)
        
        if not os.path.exists(filepath):
            messagebox.showerror("File Not Found", f"Configuration file not found:\n{filepath}")
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            # Determine type and load
            if "route_name" in config_dict:
                # Full route configuration
                messagebox.showinfo("Load", "Full route loading will be implemented in next phase.\n"
                                          "Configuration structure validated successfully.")
            elif "distributions" in config_dict:
                messagebox.showinfo("Load", "Distribution loading will be implemented in next phase.")
            elif "sensors" in config_dict:
                messagebox.showinfo("Load", "Sensors loading will be implemented in next phase.")
            else:
                messagebox.showwarning("Unknown Format", "Unknown configuration format.")
                
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load configuration:\n{str(e)}")
    
    def _delete_config(self):
        """Delete selected configuration."""
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a configuration to delete.")
            return
        
        filename = self.config_listbox.get(selection[0]).split(" - ")[0]
        filepath = os.path.join(self.config_dir, filename)
        
        if messagebox.askyesno("Confirm Delete", f"Delete configuration:\n{filename}?"):
            try:
                os.remove(filepath)
                messagebox.showinfo("Success", "Configuration deleted.")
                self.refresh_config_list()
            except Exception as e:
                messagebox.showerror("Delete Error", f"Failed to delete:\n{str(e)}")
    
    def refresh_config_list(self):
        """Refresh the list of saved configurations."""
        self.config_listbox.delete(0, tk.END)
        
        if not os.path.exists(self.config_dir):
            return
        
        files = [f for f in os.listdir(self.config_dir) if f.endswith('.json')]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(self.config_dir, x)), reverse=True)
        
        for filename in files:
            filepath = os.path.join(self.config_dir, filename)
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            display_text = f"{filename} - Created: {mtime.strftime('%Y-%m-%d %H:%M')}"
            self.config_listbox.insert(tk.END, display_text)
    
    def _route_config_to_dict(self, config: RouteConfig) -> dict:
        """Convert RouteConfig to dictionary for JSON serialization."""
        return {
            "route_name": config.route_name,
            "route_description": config.route_description,
            "origin": self._route_point_to_dict(config.origin),
            "destination": self._route_point_to_dict(config.destination),
            "waypoints": [self._route_point_to_dict(wp) for wp in config.waypoints],
            "segments": [self._segment_to_dict(seg) for seg in config.segments],
            "sensors": [self._sensor_to_dict(sensor) for sensor in config.sensors],
            "log_interval_seconds": config.log_interval_seconds,
            "use_real_routes": config.use_real_routes,
            "transport_mode": config.transport_mode,
        }
    
    def _route_point_to_dict(self, point: RoutePoint) -> dict:
        """Convert RoutePoint to dict."""
        return {
            "name": point.name,
            "latitude": point.latitude,
            "longitude": point.longitude,
            "point_type": point.point_type,
            "timestamp": point.timestamp.isoformat() if point.timestamp else None,
        }
    
    def _segment_to_dict(self, segment: SegmentMetadata) -> dict:
        """Convert SegmentMetadata to dict."""
        return {
            "description": segment.description,
            "segment_type": segment.segment_type,
            "estimated_stop_time_minutes": segment.estimated_stop_time_minutes,
            "distributions": [self._distribution_to_dict(d) for d in segment.distributions],
            "blend_strategy": segment.blend_strategy,
            "alarm_lower_temp": segment.alarm_lower_temp,
            "alarm_upper_temp": segment.alarm_upper_temp,
            "apply_smoothing": segment.apply_smoothing,
            "smoothing_phi": segment.smoothing_phi,
        }
    
    def _distribution_to_dict(self, dist: Distribution) -> dict:
        """Convert Distribution to dict."""
        return {
            "type": dist.type,
            "mode": dist.mode,
            "mean_temp": dist.mean_temp,
            "std_dev": dist.std_dev,
            "beta_alpha": dist.beta_alpha,
            "beta_beta": dist.beta_beta,
            "lower_temp": dist.lower_temp,
            "upper_temp": dist.upper_temp,
            "weight": dist.weight,
            "ambient_temp": dist.ambient_temp,
            "relative_offset_pct": dist.relative_offset_pct,
        }
    
    def _sensor_to_dict(self, sensor: SensorConfig) -> dict:
        """Convert SensorConfig to dict."""
        return {
            "epc": sensor.epc,
            "tid": sensor.tid,
            "name": sensor.name,
            "logger_mode": sensor.logger_mode,
            "battery_present": sensor.battery_present,
            "battery_voltage_min": sensor.battery_voltage_min,
            "battery_voltage_max": sensor.battery_voltage_max,
            "led_enabled": sensor.led_enabled,
            "led_mode": sensor.led_mode,
            "led_off_time_seconds": sensor.led_off_time_seconds,
            "led_on_time_milliseconds": sensor.led_on_time_milliseconds,
            "anti_tamper_enabled": sensor.anti_tamper_enabled,
            "anti_tamper_polarity": sensor.anti_tamper_polarity,
            "log_interval_seconds": sensor.log_interval_seconds,
            "log_delayed_start_samples": sensor.log_delayed_start_samples,
        }


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Config Tab Test")
    root.geometry("800x600")
    
    # Mock tabs
    class MockStopsTab:
        def get_route_config(self):
            from models.route import RouteConfig, RoutePoint
            from datetime import datetime
            config = RouteConfig(route_name="Test", route_description="Test Desc")
            config.origin = RoutePoint("O", 34.0, -118.0, "origin", datetime.now())
            config.destination = RoutePoint("D", 36.0, -119.0, "destination", datetime.now())
            return config
    
    class MockDistTab:
        def apply_distributions_to_route(self, config):
            return True
        def get_all_distributions(self):
            return []
    
    tab = ConfigTab(root, MockStopsTab(), MockDistTab())
    tab.pack(fill=tk.BOTH, expand=True)
    
    root.mainloop()
