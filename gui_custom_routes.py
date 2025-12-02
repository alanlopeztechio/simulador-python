import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import threading
import os
import json
import matplotlib.pyplot as plt
from simulator import LogSimulator, TempProfile

class RouteDefinitionTab(tk.Frame):
    """Tab 1: Route Definition (Geometry)"""
    def __init__(self, parent):
        super().__init__(parent)
        
        # Scrollable canvas for the entire tab
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
        
        # --- Content ---
        
        # 1. Origin
        self.origin_frame = tk.LabelFrame(self.scrollable_frame, text="🟢 Origin", font=("Arial", 10, "bold"), padx=10, pady=10)
        self.origin_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.origin_name = tk.StringVar(value="CDMX - Warehouse")
        self.origin_lat = tk.DoubleVar(value=19.4326)
        self.origin_lng = tk.DoubleVar(value=-99.1332)
        
        self._create_point_inputs(self.origin_frame, self.origin_name, self.origin_lat, self.origin_lng)
        
        # 2. Intermediate Stops
        self.stops_frame = tk.LabelFrame(self.scrollable_frame, text="🛑 Intermediate Stops", font=("Arial", 10, "bold"), padx=10, pady=10)
        self.stops_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.stops_container = tk.Frame(self.stops_frame)
        self.stops_container.pack(fill=tk.BOTH, expand=True)
        
        self.stop_entries = []
        
        tk.Button(self.stops_frame, text="➕ Add Stop", command=self._add_stop, bg="#4CAF50", fg="white").pack(pady=5)
        
        # 3. Final Destination
        self.dest_frame = tk.LabelFrame(self.scrollable_frame, text="🏁 Final Destination", font=("Arial", 10, "bold"), padx=10, pady=10)
        self.dest_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.dest_name = tk.StringVar(value="Guadalajara - Downtown")
        self.dest_lat = tk.DoubleVar(value=20.6597)
        self.dest_lng = tk.DoubleVar(value=-103.3496)
        
        self._create_point_inputs(self.dest_frame, self.dest_name, self.dest_lat, self.dest_lng)

    def _create_point_inputs(self, parent, name_var, lat_var, lng_var):
        tk.Label(parent, text="Name:").grid(row=0, column=0, sticky=tk.E)
        tk.Entry(parent, textvariable=name_var, width=30).grid(row=0, column=1, columnspan=3, sticky=tk.W, padx=5)
        
        tk.Label(parent, text="Lat:").grid(row=1, column=0, sticky=tk.E)
        tk.Entry(parent, textvariable=lat_var, width=12).grid(row=1, column=1, padx=5)
        
        tk.Label(parent, text="Lng:").grid(row=1, column=2, sticky=tk.E)
        tk.Entry(parent, textvariable=lng_var, width=12).grid(row=1, column=3, padx=5)

    def _add_stop(self):
        index = len(self.stop_entries) + 1
        frame = tk.Frame(self.stops_container, relief=tk.GROOVE, borderwidth=1, padx=5, pady=5)
        frame.pack(fill=tk.X, pady=2)
        
        name_var = tk.StringVar(value=f"Stop {index}")
        lat_var = tk.DoubleVar(value=0.0)
        lng_var = tk.DoubleVar(value=0.0)
        
        tk.Label(frame, text=f"#{index}", font=("Arial", 9, "bold")).grid(row=0, column=0, rowspan=2, padx=5)
        
        self._create_point_inputs(frame, name_var, lat_var, lng_var)
        
        btn_del = tk.Button(frame, text="❌", command=lambda f=frame: self._remove_stop(f), bg="#E53935", fg="white", width=3)
        btn_del.grid(row=0, column=4, rowspan=2, padx=5)
        
        entry = {
            "frame": frame,
            "name": name_var,
            "lat": lat_var,
            "lng": lng_var
        }
        self.stop_entries.append(entry)

    def _remove_stop(self, frame):
        for entry in self.stop_entries:
            if entry["frame"] == frame:
                entry["frame"].destroy()
                self.stop_entries.remove(entry)
                break
        # Renumber
        for i, entry in enumerate(self.stop_entries):
            for widget in entry["frame"].winfo_children():
                if isinstance(widget, tk.Label) and widget.cget("text").startswith("#"):
                    widget.config(text=f"#{i+1}")

    def get_route_points(self):
        """Returns list of dictionaries with info for each ordered point"""
        points = []
        # Origen
        points.append({
            "name": self.origin_name.get(),
            "lat": self.origin_lat.get(),
            "lng": self.origin_lng.get(),
            "type": "origin"
        })
        # Paradas
        for entry in self.stop_entries:
            points.append({
                "name": entry["name"].get(),
                "lat": entry["lat"].get(),
                "lng": entry["lng"].get(),
                "type": "stop"
            })
        # Destino
        points.append({
            "name": self.dest_name.get(),
            "lat": self.dest_lat.get(),
            "lng": self.dest_lng.get(),
            "type": "destination"
        })
        return points


class SegmentProfileTab(tk.Frame):
    """Tab 2: Segment Profile (Thermal Configuration)"""
    def __init__(self, parent, route_tab, generate_callback):
        super().__init__(parent)
        self.route_tab = route_tab
        self.generate_callback = generate_callback
        self.segment_widgets = []
        
        # Top controls
        top_frame = tk.Frame(self, pady=10)
        top_frame.pack(fill=tk.X, padx=10)
        
        tk.Button(top_frame, text="🔄 Load Route Segments", command=self.load_segments, bg="#2196F3", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        # Scrollable area for segments
        self.canvas = tk.Canvas(self)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bottom controls (Generation)
        bottom_frame = tk.Frame(self, pady=10, bg="#f0f0f0")
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Global extra configuration
        self.num_samples = tk.IntVar(value=1)
        tk.Label(bottom_frame, text="Samples (JSONs):").pack(side=tk.LEFT, padx=5)
        tk.Spinbox(bottom_frame, from_=1, to=50, textvariable=self.num_samples, width=5).pack(side=tk.LEFT, padx=5)
        
        self.use_real_routes = tk.BooleanVar(value=False)
        tk.Checkbutton(bottom_frame, text="Use Real Routes (OSM)", variable=self.use_real_routes).pack(side=tk.LEFT, padx=10)
        
        tk.Button(bottom_frame, text="🚀 GENERATE SIMULATION", command=self._on_generate, bg="#FF5722", fg="white", font=("Arial", 12, "bold")).pack(side=tk.RIGHT, padx=10)

    def load_segments(self):
        # Clear existing
        for w in self.segment_widgets:
            w["frame"].destroy()
        self.segment_widgets.clear()
        
        points = self.route_tab.get_route_points()
        if len(points) < 2:
            messagebox.showwarning("Warning", "Define at least Origin and Destination in Tab 1.")
            return
            
        # Create segments (Point i -> Point i+1)
        for i in range(len(points) - 1):
            p_start = points[i]
            p_end = points[i+1]
            
            frame = tk.LabelFrame(self.scrollable_frame, text=f"Segment {i+1}: {p_start['name']} ➡ {p_end['name']}", font=("Arial", 9, "bold"), padx=10, pady=10)
            frame.pack(fill=tk.X, pady=5)
            
            min_var = tk.DoubleVar(value=0.0)
            max_var = tk.DoubleVar(value=10.0)
            dist_var = tk.StringVar(value="normal")
            
            tk.Label(frame, text="Temp Min:").grid(row=0, column=0, padx=5)
            tk.Entry(frame, textvariable=min_var, width=8).grid(row=0, column=1, padx=5)
            
            tk.Label(frame, text="Temp Max:").grid(row=0, column=2, padx=5)
            tk.Entry(frame, textvariable=max_var, width=8).grid(row=0, column=3, padx=5)
            
            tk.Label(frame, text="Distribution:").grid(row=0, column=4, padx=5)
            ttk.Combobox(frame, textvariable=dist_var, values=["normal", "beta", "truncnorm", "uniform"], state="readonly", width=10).grid(row=0, column=5, padx=5)
            
            self.segment_widgets.append({
                "frame": frame,
                "min": min_var,
                "max": max_var,
                "dist": dist_var
            })
            
    def get_segment_profiles(self):
        profiles = []
        for w in self.segment_widgets:
            profiles.append({
                "lower_temp": w["min"].get(),
                "upper_temp": w["max"].get(),
                "distribution_type": w["dist"].get()
            })
        return profiles

    def _on_generate(self):
        if not self.segment_widgets:
            messagebox.showwarning("Warning", "No segments loaded. Please press 'Load Route Segments'.")
            return
        self.generate_callback()


class ResultsViewerTab(tk.Frame):
    """Tab 3: Results Viewer"""
    def __init__(self, parent, output_dir):
        super().__init__(parent)
        self.output_dir = output_dir
        self.generated_files = {}
        
        # Controls
        ctrl_frame = tk.Frame(self, pady=10)
        ctrl_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(ctrl_frame, text="Case:").pack(side=tk.LEFT)
        self.case_cb = ttk.Combobox(ctrl_frame, state="readonly", width=30)
        self.case_cb.pack(side=tk.LEFT, padx=5)
        self.case_cb.bind("<<ComboboxSelected>>", self._on_case_selected)
        
        tk.Label(ctrl_frame, text="Sample:").pack(side=tk.LEFT, padx=(10,0))
        self.sample_cb = ttk.Combobox(ctrl_frame, state="readonly", width=30)
        self.sample_cb.pack(side=tk.LEFT, padx=5)
        self.sample_cb.bind("<<ComboboxSelected>>", self._on_sample_selected)
        
        tk.Button(ctrl_frame, text="🔄 Refresh", command=self.load_files).pack(side=tk.LEFT, padx=10)
        
        # Actions
        btn_frame = tk.Frame(self, pady=5)
        btn_frame.pack(fill=tk.X, padx=10)
        
        tk.Button(btn_frame, text="📄 View JSON", command=self._open_json).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🗺️ View Map", command=self._open_map).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="📊 View Chart", command=self._open_plot).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="📂 Open Folder", command=self._open_folder).pack(side=tk.LEFT, padx=5)
        
        # Info Text
        self.info_text = tk.Text(self, height=15, bg="#f5f5f5", font=("Courier", 9))
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.load_files()

    def load_files(self):
        self.generated_files = {}
        if not os.path.exists(self.output_dir):
            return
            
        for item in os.listdir(self.output_dir):
            path = os.path.join(self.output_dir, item)
            if os.path.isdir(path) and item.startswith("case_"):
                samples = []
                for s_item in os.listdir(path):
                    s_path = os.path.join(path, s_item)
                    if os.path.isdir(s_path) and s_item.startswith("sample_"):
                        # Find files
                        json_f = next((os.path.join(s_path, f) for f in os.listdir(s_path) if f.endswith(".json") and f.startswith("sample_")), None)
                        map_f = next((os.path.join(s_path, f) for f in os.listdir(s_path) if f.endswith(".html")), None)
                        plot_f = next((os.path.join(s_path, f) for f in os.listdir(s_path) if f.endswith(".png")), None)
                        
                        if json_f:
                            samples.append({
                                "name": s_item,
                                "path": s_path,
                                "json": json_f,
                                "map": map_f,
                                "plot": plot_f
                            })
                if samples:
                    self.generated_files[item] = sorted(samples, key=lambda x: x["name"])
        
        self.case_cb["values"] = list(self.generated_files.keys())
        if self.generated_files:
            self.case_cb.current(0)
            self._on_case_selected(None)

    def _on_case_selected(self, event):
        case = self.case_cb.get()
        if case in self.generated_files:
            samples = [s["name"] for s in self.generated_files[case]]
            self.sample_cb["values"] = samples
            if samples:
                self.sample_cb.current(0)
                self._on_sample_selected(None)

    def _on_sample_selected(self, event):
        self.info_text.delete(1.0, tk.END)
        sample = self._get_current_sample()
        if sample:
            # Read JSON info
            try:
                with open(sample["json"], "r") as f:
                    data = json.load(f)
                
                txt = f"EPC: {data.get('EPC')}\n"
                txt += f"TID: {data.get('TID')}\n"
                txt += f"Points: {len(data.get('loggedData', []))}\n"
                txt += f"Route: {sample['path']}\n"
                self.info_text.insert(tk.END, txt)
            except Exception as e:
                self.info_text.insert(tk.END, f"Error reading JSON: {e}")

    def _get_current_sample(self):
        case = self.case_cb.get()
        s_name = self.sample_cb.get()
        if case in self.generated_files:
            for s in self.generated_files[case]:
                if s["name"] == s_name:
                    return s
        return None

    def _open_json(self):
        s = self._get_current_sample()
        if s and s["json"]: os.startfile(s["json"])

    def _open_map(self):
        s = self._get_current_sample()
        if s and s["map"]: os.startfile(s["map"])

    def _open_plot(self):
        s = self._get_current_sample()
        if s and s["plot"]: os.startfile(s["plot"])

    def _open_folder(self):
        s = self._get_current_sample()
        if s: os.startfile(s["path"])


class SimulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Custom Routes Simulator")
        self.root.geometry("1000x800")
        
        self.output_dir = "use_cases_output"
        
        # Notebook
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tabs
        self.tab1 = RouteDefinitionTab(self.notebook)
        self.notebook.add(self.tab1, text="1. Route Definition")
        
        self.tab2 = SegmentProfileTab(self.notebook, self.tab1, self.start_generation)
        self.notebook.add(self.tab2, text="2. Segment Profile")
        
        self.tab3 = ResultsViewerTab(self.notebook, self.output_dir)
        self.notebook.add(self.tab3, text="3. Results")
        
        # Bind tab change to auto-load segments if switching to tab 2
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, event):
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 1: # Tab 2
            self.tab2.load_segments()

    def start_generation(self):
        # Gather data
        points = self.tab1.get_route_points()
        profiles_data = self.tab2.get_segment_profiles()
        
        waypoints = [(p["lat"], p["lng"]) for p in points]
        
        # Convert profiles to TempProfile objects
        profiles = []
        for p in profiles_data:
            profiles.append(TempProfile(
                lower_temp=p["lower_temp"],
                upper_temp=p["upper_temp"],
                distribution_type=p["distribution_type"]
            ))
            
        num_samples = self.tab2.num_samples.get()
        use_real = self.tab2.use_real_routes.get()
        
        # Run in thread
        threading.Thread(target=self._run_simulation, args=(waypoints, profiles, num_samples, use_real)).start()

    def _run_simulation(self, waypoints, profiles, num_samples, use_real):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            case_dir = os.path.join(self.output_dir, f"case_custom_{timestamp}")
            os.makedirs(case_dir, exist_ok=True)
            
            for i in range(num_samples):
                epc = f"CUSTOM{i+1:04d}"
                sim = LogSimulator.from_waypoints(
                    epc=epc,
                    tid=epc,
                    waypoints=waypoints,
                    segment_profiles=profiles,
                    use_real_route=use_real,
                    # Global fallbacks (taken from first segment or defaults)
                    lower_temp=profiles[0].lower_temp if profiles else 0,
                    upper_temp=profiles[0].upper_temp if profiles else 10,
                    distribution_type=profiles[0].distribution_type if profiles else "normal"
                )
                sim.generate()
                
                # Save
                sample_dir = os.path.join(case_dir, f"sample_{i+1:03d}_{epc}")
                os.makedirs(sample_dir, exist_ok=True)
                sim.save_to_file(os.path.join(sample_dir, f"sample_{epc}.json"))
                sim.generate_map(os.path.join(sample_dir, "map.html"))
                
                # Plot
                plt.figure()
                sim.plot_results(save_path=os.path.join(sample_dir, "plot.png"))
                plt.close()
                
            messagebox.showinfo("Success", f"{num_samples} simulations generated in:\n{case_dir}")
            
            # Refresh viewer
            self.root.after(0, self.tab3.load_files)
            
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = SimulatorGUI(root)
    root.mainloop()
