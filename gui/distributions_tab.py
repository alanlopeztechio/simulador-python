"""
Distribution Parameters Tab - Configure multiple distributions per segment.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.route import RouteConfig
from models.segment import SegmentMetadata
from models.distribution import Distribution


class DistributionsTab(tk.Frame):
    """Tab 2: Distribution Parameters.
    
    Based on UI design image 2, supports:
    - Multiple distributions per segment
    - Distribution type selection (Normal, Beta, Truncnorm, Uniform)
    - Mode selection (Absolute vs Relative)
    - Parameter configuration per distribution type
    """
    
    DISTRIBUTION_TYPES = ["normal", "beta", "truncnorm", "uniform"]
    DISTRIBUTION_MODES = ["absolute", "relative"]
    BLEND_STRATEGIES = ["weighted_average", "alternating", "layered"]
    
    def __init__(self, parent, routes_tab):
        super().__init__(parent)
        self.routes_tab = routes_tab
        self.segment_distribution_widgets = []  # List of segment widgets, each containing distribution widgets
        
        # Scrollable canvas
        self.canvas = tk.Canvas(self)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build initial UI."""
        container = self.scrollable_frame
        
        # Header with regenerate button
        header_frame = tk.Frame(container, pady=10)
        header_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(header_frame, text="Route-Based Distributions", 
                font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        
        tk.Button(header_frame, text="Regenerate Distributions", 
                 command=self.regenerate_from_route,
                 bg="#2196F3", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(header_frame, text="Add Manual Distribution", 
                 command=self._add_manual_distribution,
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=5)
        
        # Container for segments
        self.segments_dist_container = tk.Frame(container)
        self.segments_dist_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Initial message
        tk.Label(self.segments_dist_container, 
                text="Click 'Regenerate Distributions' to load route segments from Rutas tab",
                font=("Arial", 10), fg="gray").pack(pady=20)
    
    def regenerate_from_route(self):
        """Load route configuration and generate distribution UI for each segment."""
        route_config = self.routes_tab.get_route_config()
        if not route_config:
            messagebox.showinfo("Info", "Selecciona una ruta en la pestaña de Rutas primero.")
            return
        
        # Clear existing
        for widget in self.segments_dist_container.winfo_children():
            widget.destroy()
        self.segment_distribution_widgets.clear()
        
        # Ensure segments exist
        route_config.ensure_segments()
        
        if not route_config.segments:
            tk.Label(self.segments_dist_container, 
                    text="No segments found. Please add segments in the Rutas tab.",
                    font=("Arial", 10), fg="red").pack(pady=20)
            return
        
        # Create UI for each segment
        for i, segment in enumerate(route_config.segments):
            self._create_segment_distribution_widget(i, segment, route_config)
    
    def _create_segment_distribution_widget(self, segment_index: int, segment: SegmentMetadata, route_config: RouteConfig):
        """Create distribution configuration widget for a segment."""
        # Main segment frame
        seg_frame = tk.LabelFrame(self.segments_dist_container, 
                                  text=f"Distribution Name {segment_index + 1}",
                                  font=("Arial", 10, "bold"), padx=10, pady=10,
                                  relief=tk.GROOVE, borderwidth=2)
        seg_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Segment info header
        info_frame = tk.Frame(seg_frame)
        info_frame.pack(fill=tk.X, pady=5)
        
        points = route_config.get_all_points()
        from_point = points[segment_index] if segment_index < len(points) else None
        to_point = points[segment_index + 1] if segment_index + 1 < len(points) else None
        
        from_name = from_point.name if from_point else "Unknown"
        to_name = to_point.name if to_point else "Unknown"
        
        tk.Label(info_frame, text=f"From: Origin A  To: Segment B",
                font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Label(info_frame, text=f" | Type: {segment.segment_type}",
                font=("Arial", 9), fg="blue").pack(side=tk.LEFT)
        
        # Distribution type selector
        type_frame = tk.Frame(seg_frame)
        type_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(type_frame, text="Distribution Type:").pack(side=tk.LEFT, padx=5)
        dist_type_var = tk.StringVar(value="Normal")
        dist_type_combo = ttk.Combobox(type_frame, textvariable=dist_type_var,
                                       values=["Normal", "Beta", "Truncnorm", "Uniform"],
                                       state="readonly", width=15)
        dist_type_combo.pack(side=tk.LEFT, padx=5)
        
        # Mode of Application
        tk.Label(type_frame, text="Mode of Application:").pack(side=tk.LEFT, padx=20)
        mode_var = tk.StringVar(value="absolute")
        tk.Radiobutton(type_frame, text="Absolute Mode", variable=mode_var, 
                      value="absolute").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(type_frame, text="Relative Mode", variable=mode_var, 
                      value="relative").pack(side=tk.LEFT, padx=5)
        
        # Parameters frame (changes based on distribution type)
        params_frame = tk.Frame(seg_frame, relief=tk.SUNKEN, borderwidth=1, padx=10, pady=10)
        params_frame.pack(fill=tk.X, pady=5)
        
        # Param variables
        param_vars = {
            "min_range": tk.DoubleVar(value=0.0),
            "max_range": tk.DoubleVar(value=10.0),
            "std_dev": tk.DoubleVar(value=2.0),
            "beta_alpha": tk.DoubleVar(value=2.0),
            "beta_beta": tk.DoubleVar(value=5.0),
            "mean_temp": tk.DoubleVar(value=5.0),
        }
        
        def update_params_ui(*args):
            """Update parameter fields based on selected distribution type."""
            for widget in params_frame.winfo_children():
                widget.destroy()
            
            dist_type = dist_type_var.get().lower()
            
            # Common: Min/Max Range
            tk.Label(params_frame, text="Minimum Range:").grid(row=0, column=0, sticky=tk.W, pady=2)
            tk.Entry(params_frame, textvariable=param_vars["min_range"], width=10).grid(row=0, column=1, padx=5, pady=2)
            
            tk.Label(params_frame, text="Maximum Range:").grid(row=0, column=2, sticky=tk.W, pady=2, padx=(20, 0))
            tk.Entry(params_frame, textvariable=param_vars["max_range"], width=10).grid(row=0, column=3, padx=5, pady=2)
            
            if dist_type == "normal" or dist_type == "truncnorm":
                tk.Label(params_frame, text="Standard Deviation:").grid(row=1, column=0, sticky=tk.W, pady=2)
                tk.Entry(params_frame, textvariable=param_vars["std_dev"], width=10).grid(row=1, column=1, padx=5, pady=2)
                
                if dist_type == "normal":
                    tk.Label(params_frame, text="Mean Temperature:").grid(row=1, column=2, sticky=tk.W, pady=2, padx=(20, 0))
                    tk.Entry(params_frame, textvariable=param_vars["mean_temp"], width=10).grid(row=1, column=3, padx=5, pady=2)
            
            elif dist_type == "beta":
                tk.Label(params_frame, text="Alpha:").grid(row=1, column=0, sticky=tk.W, pady=2)
                tk.Entry(params_frame, textvariable=param_vars["beta_alpha"], width=10).grid(row=1, column=1, padx=5, pady=2)
                
                tk.Label(params_frame, text="Beta:").grid(row=1, column=2, sticky=tk.W, pady=2, padx=(20, 0))
                tk.Entry(params_frame, textvariable=param_vars["beta_beta"], width=10).grid(row=1, column=3, padx=5, pady=2)
        
        # Bind distribution type change
        dist_type_combo.bind("<<ComboboxSelected>>", update_params_ui)
        update_params_ui()  # Initial setup
        
        # Action buttons
        btn_frame = tk.Frame(seg_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(btn_frame, text="Edit Distribution", 
                 bg="#2196F3", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Delete distribution", 
                 bg="#E53935", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        
        # Store widget reference
        widget_data = {
            "frame": seg_frame,
            "segment_index": segment_index,
            "segment": segment,
            "dist_type_var": dist_type_var,
            "mode_var": mode_var,
            "param_vars": param_vars,
        }
        self.segment_distribution_widgets.append(widget_data)
    
    def _add_manual_distribution(self):
        """Add a standalone distribution not tied to route segments."""
        messagebox.showinfo("Manual Distribution", 
                          "Manual distribution addition will be implemented in future version.\n"
                          "For now, please use route segments.")
    
    def apply_distributions_to_route(self, route_config: RouteConfig) -> bool:
        """Apply configured distributions to RouteConfig segments.
        
        Args:
            route_config: RouteConfig to update with distribution configurations
            
        Returns:
            True if successful, False otherwise
        """
        if len(self.segment_distribution_widgets) != len(route_config.segments):
            messagebox.showerror("Configuration Error", 
                               f"Distribution count mismatch: {len(self.segment_distribution_widgets)} distributions "
                               f"vs {len(route_config.segments)} segments")
            return False
        
        for widget_data in self.segment_distribution_widgets:
            seg_index = widget_data["segment_index"]
            if seg_index >= len(route_config.segments):
                continue
            
            segment = route_config.segments[seg_index]
            
            # Build Distribution object
            dist_type = widget_data["dist_type_var"].get().lower()
            mode = widget_data["mode_var"].get()
            params = widget_data["param_vars"]
            
            distribution = Distribution(
                type=dist_type,
                mode=mode,
                lower_temp=params["min_range"].get(),
                upper_temp=params["max_range"].get(),
                std_dev=params["std_dev"].get(),
                mean_temp=params["mean_temp"].get() if dist_type in ["normal", "truncnorm"] else None,
                beta_alpha=params["beta_alpha"].get(),
                beta_beta=params["beta_beta"].get(),
                weight=1.0,
            )
            
            # Clear existing distributions and add new one
            segment.distributions.clear()
            segment.distributions.append(distribution)
            
            # Set alarm bounds
            segment.alarm_lower_temp = params["min_range"].get()
            segment.alarm_upper_temp = params["max_range"].get()
        
        return True
    
    def get_all_distributions(self) -> List[dict]:
        """Get all configured distributions as list of dicts.
        
        Returns:
            List of distribution configurations
        """
        distributions = []
        for widget_data in self.segment_distribution_widgets:
            dist_type = widget_data["dist_type_var"].get().lower()
            mode = widget_data["mode_var"].get()
            params = widget_data["param_vars"]
            
            distributions.append({
                "segment_index": widget_data["segment_index"],
                "type": dist_type,
                "mode": mode,
                "min_range": params["min_range"].get(),
                "max_range": params["max_range"].get(),
                "std_dev": params["std_dev"].get(),
                "mean_temp": params["mean_temp"].get(),
                "beta_alpha": params["beta_alpha"].get(),
                "beta_beta": params["beta_beta"].get(),
            })
        
        return distributions


if __name__ == "__main__":
    # Test the tab
    root = tk.Tk()
    root.title("Distributions Tab Test")
    root.geometry("900x700")
    
    # Mock stops tab
    class MockStopsTab:
        def get_route_config(self):
            from models.route import RouteConfig, RoutePoint
            from models.segment import SegmentMetadata
            from datetime import datetime
            
            config = RouteConfig(
                route_name="Test Route",
                route_description="Test Description",
            )
            config.origin = RoutePoint("Origin", 34.0, -118.0, "origin", datetime.now())
            config.destination = RoutePoint("Dest", 36.0, -119.0, "destination", datetime.now())
            config.segments = [
                SegmentMetadata("Seg 1", "highway", 30),
                SegmentMetadata("Seg 2", "urban", 15),
            ]
            return config
    
    mock_stops = MockStopsTab()
    tab = DistributionsTab(root, mock_stops)
    tab.pack(fill=tk.BOTH, expand=True)
    
    root.mainloop()
