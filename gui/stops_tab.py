"""
Stops Tab - Route management with segments and sensors.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import List, Optional
import threading
import requests
import sys
import os
import itertools

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.route import RouteConfig, RoutePoint
from models.segment import SegmentMetadata
from models.sensor import SensorConfig


class StopsTab(tk.Frame):
    """Tab 1: Route Definition - Stops, Segments, and Sensors.
    
    Based on UI design image 1, includes:
    - Route metadata (name, description)
    - Origin with lat/lng/departure time
    - Destination with lat/lng/arrival time  
    - Segments (1+) with description/lat/lng/type/estimated stop time
    - Associated sensors
    """
    
    SEGMENT_TYPES = ["Fleet", "Control", "Highway", "Urban", "Rural", "Warehouse"]
    
    def __init__(self, parent):
        super().__init__(parent)
        
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
        
        # Data storage
        self.segment_frames = []
        self.sensor_checkboxes = []
        self.available_sensors = []  # List of SensorConfig objects
        
        self._build_ui()

    def _build_ui(self):
        """Build the complete UI layout."""
        container = self.scrollable_frame

        self.loading = False
        self.spinner_cycle = itertools.cycle(["|", "/", "-", "\\"])
        
        # === ROUTE METADATA ===
        metadata_frame = tk.LabelFrame(container, text="Route Metadata", 
                                       font=("Arial", 10, "bold"), padx=10, pady=10)
        metadata_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(metadata_frame, text="Route Name:", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.route_name_var = tk.StringVar(value="")
        tk.Entry(metadata_frame, textvariable=self.route_name_var, width=50, 
                font=("Arial", 9)).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        tk.Label(metadata_frame, text="*", fg="red").grid(row=0, column=2)
        
        tk.Label(metadata_frame, text="Route Description:", font=("Arial", 9)).grid(row=1, column=0, sticky=tk.W, pady=2)
        self.route_desc_var = tk.StringVar(value="")
        tk.Entry(metadata_frame, textvariable=self.route_desc_var, width=50,
                font=("Arial", 9)).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        tk.Label(metadata_frame, text="*", fg="red").grid(row=1, column=2)
        
        # === ORIGIN ===
        origin_frame = tk.LabelFrame(container, text="Origin", 
                                     font=("Arial", 10, "bold"), padx=10, pady=10)
        origin_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.origin_lat_var = tk.DoubleVar(value=34.0522)
        self.origin_lng_var = tk.DoubleVar(value=-118.2437)
        self.origin_time_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M"))

        def set_origin_coords(lat, lon):
            self.origin_lat_var.set(lat)
            self.origin_lng_var.set(lon)
            print(f"Origen actualizado: {lat}, {lon}")

        self.origin_search = LocationSearchWidget(origin_frame, on_select_callback=set_origin_coords)
        self.origin_search.grid(row=0, column=1, columnspan=3, sticky="w")
        tk.Label(origin_frame, text="Location :").grid(row=0, column=0, sticky=tk.E)
        
        tk.Label(origin_frame, text="Departure Time:").grid(row=1, column=0, sticky=tk.E)
        tk.Entry(origin_frame, textvariable=self.origin_time_var, width=20).grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=5)
        tk.Label(origin_frame, text="(YYYY-MM-DD HH:MM)", font=("Arial", 8), fg="gray").grid(row=1, column=3, sticky=tk.W)
        
        # === DESTINATION ===
        dest_frame = tk.LabelFrame(container, text="Destination", 
                                   font=("Arial", 10, "bold"), padx=10, pady=10)
        dest_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.dest_lat_var = tk.DoubleVar(value=36.7783)
        self.dest_lng_var = tk.DoubleVar(value=-119.4179)
        self.dest_time_var = tk.StringVar(value="")

        def set_destination_coords(lat, lon):
            self.dest_lat_var.set(lat)
            self.dest_lng_var.set(lon)
            print(f"Destino actualizado: {lat}, {lon}")
        
        self.destination_search = LocationSearchWidget(dest_frame, on_select_callback=set_destination_coords)
        self.destination_search.grid(row=0, column=1, columnspan=3, sticky="w")
        tk.Label(dest_frame, text="Location :").grid(row=0, column=0, sticky=tk.E)
        
        # tk.Label(dest_frame, text="Latitude:").grid(row=0, column=0, sticky=tk.E)
        # tk.Entry(dest_frame, textvariable=self.dest_lat_var, width=15).grid(row=0, column=1, padx=5)
        
        # tk.Label(dest_frame, text="Longitude:").grid(row=0, column=2, sticky=tk.E)
        # tk.Entry(dest_frame, textvariable=self.dest_lng_var, width=15).grid(row=0, column=3, padx=5)
        
        tk.Label(dest_frame, text="Estimated Transit Time (minutes):").grid(row=1, column=0, sticky=tk.E)
        self.est_transit_var = tk.IntVar(value=60)
        tk.Entry(dest_frame, textvariable=self.est_transit_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        # === SEGMENTS ===
        segments_frame = tk.LabelFrame(container, text="Segments", 
                                       font=("Arial", 10, "bold"), padx=10, pady=10)
        segments_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.segments_container = tk.Frame(segments_frame)
        self.segments_container.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = tk.Frame(segments_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="Add Segment", command=self._add_segment, 
                 bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        # === ASSOCIATED SENSORS ===
        sensors_frame = tk.LabelFrame(container, text="Associated Sensors", 
                                      font=("Arial", 10, "bold"), padx=10, pady=10)
        sensors_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(sensors_frame, text="Add Sensor", command=self._add_sensor,
                 bg="#2196F3", fg="white", font=("Arial", 9)).pack(side=tk.TOP, anchor=tk.W, pady=5)
        
        self.sensors_list_frame = tk.Frame(sensors_frame)
        self.sensors_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Add one default segment
        self._add_segment()
        
        # Add default sensor
        self._add_sensor()

    def start_spinner(self):
        self.loading = True
        self.animate_spinner()

    def animate_spinner(self):
        if self.loading:
            frame = next(self.spinner_cycle)
            self.status_label.config(text=f"Loading... {frame}", fg="blue")
            self.after(120, self.animate_spinner)

    def stop_spinner(self):
        self.loading = False
        self.status_label.config(text="Listo", fg="grey")

    def _search_button_clicked(self):
        query = self.combo_route_origin.get().strip()
        if query:
            self._start_search_thread(query)
    
    def _start_search_thread(self, query):
        self.start_spinner()
        threading.Thread(target=self._fetch_directions, args=(query,), daemon=True).start()


    def _fetch_directions(self, query):
        try:
            api_key = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjMwYWY3NzRhN2U1YjRkMWRhMDdhNDRmYzM4ZDBkMmYwIiwiaCI6Im11cm11cjY0In0="  # <-- pon aquí tu API KEY real
            url = "https://api.openrouteservice.org/geocode/search"
            params = {
            "api_key": api_key,
            "text": query,
            "size": 10
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            features = data.get("features", [])

            suggestions = []
            for f in features:
                props = f.get("properties", {})
                label = props.get("label")
                if label:
                    suggestions.append(label)
            self.after(0, self._update_combobox_values, suggestions)

        except Exception as e:
            self.after(0, messagebox.showerror, "Error", f"Failed to fetch directions: {e}")

        finally:
            self.after(0, self.stop_spinner)
    
    def _update_combobox_values(self, values):
        self.search_box["values"] = values
        if values:
            self.search_box.set(values[0])

    
    def _add_segment(self):
        """Add a new segment to the route."""
        index = len(self.segment_frames) + 1
        
        frame = tk.Frame(self.segments_container, relief=tk.GROOVE, borderwidth=2, padx=10, pady=10)
        frame.pack(fill=tk.X, pady=5)
        
        # Header
        header_frame = tk.Frame(frame)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text=f"Segment {index}", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(header_frame, text="Delete", command=lambda: self._remove_segment(frame),
                 bg="#E53935", fg="white", font=("Arial", 8)).pack(side=tk.RIGHT)
        
        # Segment data
        data_frame = tk.Frame(frame)
        data_frame.pack(fill=tk.X, pady=5)
        
        # Row 0: Description
        tk.Label(data_frame, text="Segment Description:").grid(row=0, column=0, sticky=tk.W)
        desc_var = tk.StringVar(value=f"First leg of the journey")
        tk.Entry(data_frame, textvariable=desc_var, width=50).grid(row=0, column=1, columnspan=3, sticky=tk.W, padx=5)
        
        # Row 1: Coordinates
        tk.Label(data_frame, text="Latitude:").grid(row=1, column=0, sticky=tk.E)
        lat_var = tk.DoubleVar(value=34.0522)
        tk.Entry(data_frame, textvariable=lat_var, width=12).grid(row=1, column=1, padx=5)
        
        tk.Label(data_frame, text="Longitude:").grid(row=1, column=2, sticky=tk.E)
        lng_var = tk.DoubleVar(value=-118.2437)
        tk.Entry(data_frame, textvariable=lng_var, width=12).grid(row=1, column=3, padx=5)
        
        # Row 2: Segment Type
        tk.Label(data_frame, text="Segment Type:").grid(row=2, column=0, sticky=tk.E)
        type_var = tk.StringVar(value="Fleet")
        type_combo = ttk.Combobox(data_frame, textvariable=type_var, 
                                  values=self.SEGMENT_TYPES, state="readonly", width=15)
        type_combo.grid(row=2, column=1, sticky=tk.W, padx=5)
        
        # Row 3: Estimated Stop Time
        tk.Label(data_frame, text="Estimated Stop Time (minutes):").grid(row=2, column=2, sticky=tk.E)
        stop_time_var = tk.IntVar(value=60)
        tk.Entry(data_frame, textvariable=stop_time_var, width=10).grid(row=2, column=3, sticky=tk.W, padx=5)
        
        # Store references
        segment_data = {
            "frame": frame,
            "description": desc_var,
            "latitude": lat_var,
            "longitude": lng_var,
            "type": type_var,
            "stop_time": stop_time_var,
        }
        self.segment_frames.append(segment_data)
        
        self._renumber_segments()
    
    def _remove_segment(self, frame):
        """Remove a segment from the route."""
        for segment_data in self.segment_frames:
            if segment_data["frame"] == frame:
                segment_data["frame"].destroy()
                self.segment_frames.remove(segment_data)
                break
        self._renumber_segments()
    
    def _renumber_segments(self):
        """Update segment numbering after add/remove."""
        for i, segment_data in enumerate(self.segment_frames, start=1):
            # Update header label
            for widget in segment_data["frame"].winfo_children():
                if isinstance(widget, tk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, tk.Label) and "Segment" in child.cget("text"):
                            child.config(text=f"Segment {i}")
                            break
    
    def _add_sensor(self):
        """Add a new sensor."""
        index = len(self.available_sensors) + 1
        sensor = SensorConfig.generate_default(index)
        self.available_sensors.append(sensor)
        
        # Create checkbox frame
        frame = tk.Frame(self.sensors_list_frame, relief=tk.GROOVE, borderwidth=1, padx=5, pady=3)
        frame.pack(fill=tk.X, pady=2)
        
        # Sensor info
        info_text = f"{sensor.get_display_name()} - EPC: {sensor.epc}, TID: {sensor.tid}"
        tk.Label(frame, text=info_text, font=("Arial", 9)).pack(side=tk.LEFT)
        
        # Edit/Delete buttons
        btn_frame = tk.Frame(frame)
        btn_frame.pack(side=tk.RIGHT)
        tk.Button(btn_frame, text="Edit", command=lambda: self._edit_sensor(index-1),
                 bg="#2196F3", fg="white", font=("Arial", 8), width=5).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Delete", command=lambda: self._remove_sensor(frame, index-1),
                 bg="#E53935", fg="white", font=("Arial", 8), width=5).pack(side=tk.LEFT, padx=2)
    
    def _edit_sensor(self, index):
        """Edit sensor configuration."""
        if 0 <= index < len(self.available_sensors):
            sensor = self.available_sensors[index]
            # Simple dialog for editing
            dialog = tk.Toplevel(self)
            dialog.title(f"Edit {sensor.get_display_name()}")
            dialog.geometry("400x250")
            
            tk.Label(dialog, text="EPC:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
            epc_var = tk.StringVar(value=sensor.epc)
            tk.Entry(dialog, textvariable=epc_var, width=30).grid(row=0, column=1, padx=10, pady=5)
            
            tk.Label(dialog, text="TID:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
            tid_var = tk.StringVar(value=sensor.tid)
            tk.Entry(dialog, textvariable=tid_var, width=30).grid(row=1, column=1, padx=10, pady=5)
            
            tk.Label(dialog, text="Name:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
            name_var = tk.StringVar(value=sensor.name or "")
            tk.Entry(dialog, textvariable=name_var, width=30).grid(row=2, column=1, padx=10, pady=5)
            
            def save():
                sensor.epc = epc_var.get()
                sensor.tid = tid_var.get()
                sensor.name = name_var.get() if name_var.get() else None
                self._refresh_sensor_list()
                dialog.destroy()
            
            tk.Button(dialog, text="Save", command=save, bg="#4CAF50", fg="white").grid(row=3, column=0, columnspan=2, pady=10)
    
    def _remove_sensor(self, frame, index):
        """Remove a sensor."""
        if 0 <= index < len(self.available_sensors):
            self.available_sensors.pop(index)
            frame.destroy()
            self._refresh_sensor_list()
    
    def _refresh_sensor_list(self):
        """Refresh sensor display."""
        for widget in self.sensors_list_frame.winfo_children():
            widget.destroy()
        
        # Rebuild sensor list
        temp_sensors = self.available_sensors.copy()
        self.available_sensors.clear()
        for sensor in temp_sensors:
            self.available_sensors.append(sensor)
            self._add_sensor_display(sensor)
    
    def _add_sensor_display(self, sensor):
        """Add sensor to display without creating new sensor."""
        index = len(self.available_sensors) - 1
        frame = tk.Frame(self.sensors_list_frame, relief=tk.GROOVE, borderwidth=1, padx=5, pady=3)
        frame.pack(fill=tk.X, pady=2)
        
        info_text = f"{sensor.get_display_name()} - EPC: {sensor.epc}, TID: {sensor.tid}"
        tk.Label(frame, text=info_text, font=("Arial", 9)).pack(side=tk.LEFT)
        
        btn_frame = tk.Frame(frame)
        btn_frame.pack(side=tk.RIGHT)
        tk.Button(btn_frame, text="Edit", command=lambda: self._edit_sensor(index),
                 bg="#2196F3", fg="white", font=("Arial", 8), width=5).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Delete", command=lambda: self._remove_sensor(frame, index),
                 bg="#E53935", fg="white", font=("Arial", 8), width=5).pack(side=tk.LEFT, padx=2)
    
    def get_route_config(self) -> Optional[RouteConfig]:
        """Build RouteConfig from current UI state.
        
        Returns:
            RouteConfig object or None if validation fails
        """
        # Validate required fields
        if not self.route_name_var.get().strip():
            messagebox.showerror("Validation Error", "Route Name is required")
            return None
        
        if not self.route_desc_var.get().strip():
            messagebox.showerror("Validation Error", "Route Description is required")
            return None
        
        if len(self.segment_frames) == 0:
            messagebox.showerror("Validation Error", "At least one segment is required")
            return None
        
        # Parse origin timestamp
        try:
            origin_time = datetime.strptime(self.origin_time_var.get(), "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Validation Error", "Invalid origin departure time format")
            return None
        
        # Build RouteConfig
        config = RouteConfig(
            route_name=self.route_name_var.get().strip(),
            route_description=self.route_desc_var.get().strip(),
        )
        
        # Origin
        config.origin = RoutePoint(
            name="Origin",
            latitude=self.origin_lat_var.get(),
            longitude=self.origin_lng_var.get(),
            point_type="origin",
            timestamp=origin_time,
        )
        
        # Destination (calculate arrival time based on transit estimate)
        from datetime import timedelta
        arrival_time = origin_time + timedelta(minutes=self.est_transit_var.get())
        config.destination = RoutePoint(
            name="Destination",
            latitude=self.dest_lat_var.get(),
            longitude=self.dest_lng_var.get(),
            point_type="destination",
            timestamp=arrival_time,
        )
        
        # Waypoints and segments
        for segment_data in self.segment_frames:
            # Create waypoint for this segment
            waypoint = RoutePoint(
                name=segment_data["description"].get(),
                latitude=segment_data["latitude"].get(),
                longitude=segment_data["longitude"].get(),
                point_type="waypoint",
            )
            config.waypoints.append(waypoint)
            
            # Create segment metadata
            segment = SegmentMetadata(
                description=segment_data["description"].get(),
                segment_type=segment_data["type"].get(),
                estimated_stop_time_minutes=segment_data["stop_time"].get(),
            )
            config.segments.append(segment)
        
        # Sensors
        config.sensors = self.available_sensors.copy()
        
        # Ensure segment count matches
        config.ensure_segments()
        
        return config


class LocationSearchWidget(tk.Frame):
    def __init__(self, parent, on_select_callback=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_select_callback = on_select_callback # Función a llamar al elegir una opción
        self._results_map = {} # Para guardar coordenadas ocultas: {"Dirección": [lat, lon]}
        
        # UI Components
        self.combo_var = tk.StringVar()
        self.search_box = ttk.Combobox(self, textvariable=self.combo_var, width=30)
        self.search_box.grid(row=0, column=0, padx=5, sticky="ew")
        self.search_box.bind("<<ComboboxSelected>>", self._on_selection_made)

        self.search_button = ttk.Button(self, text="🔍", width=4, command=self._start_search)
        self.search_button.grid(row=0, column=1, padx=2)

        self.status_label = tk.Label(self, text="", fg="grey", font=("Consolas", 8), width=15)
        self.status_label.grid(row=0, column=2, padx=5)

        # Configuración de Spinner
        self.spinner_cycle = itertools.cycle(["|", "/", "-", "\\"])
        self.loading = False

    def get_text(self):
        return self.combo_var.get()

    def set_text(self, text):
        self.combo_var.set(text)

    def _start_search(self):
        query = self.combo_var.get().strip()
        if not query: return
        
        self.loading = True
        self._animate_spinner()
        # Iniciar hilo
        threading.Thread(target=self._fetch_api, args=(query,), daemon=True).start()

    def _animate_spinner(self):
        if self.loading:
            self.status_label.config(text=f"Loading {next(self.spinner_cycle)}", fg="blue")
            self.after(100, self._animate_spinner)
        else:
            self.status_label.config(text="Ready", fg="green")

    def _fetch_api(self, query):
        try:
            # TU API KEY (Te recomiendo moverla a variables de entorno)
            api_key = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjMwYWY3NzRhN2U1YjRkMWRhMDdhNDRmYzM4ZDBkMmYwIiwiaCI6Im11cm11cjY0In0=" 
            url = "https://api.openrouteservice.org/geocode/search"
            params = {"api_key": api_key, "text": query, "size": 10}

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            suggestions = []
            self._results_map = {} # Limpiar mapa anterior

            for f in data.get("features", []):
                props = f.get("properties", {})
                geometry = f.get("geometry", {})
                label = props.get("label")
                coords = geometry.get("coordinates") # [lon, lat] ojo con el orden
                
                if label and coords:
                    suggestions.append(label)
                    # Guardamos lat/lon para usarlo después (OpenRouteService devuelve [lon, lat])
                    self._results_map[label] = (coords[1], coords[0]) 

            self.after(0, lambda: self._update_ui(suggestions))

        except Exception as e:
            print(f"Error API: {e}")
            self.after(0, lambda: self.status_label.config(text="Error", fg="red"))
        finally:
            self.loading = False

    def _update_ui(self, values):
        self.search_box["values"] = values
        if values:
            self.search_box.event_generate('<Down>') # Desplegar lista automáticamente

    def _on_selection_made(self, event):
        selected_text = self.combo_var.get()
        coords = self._results_map.get(selected_text)
        
        if coords and self.on_select_callback:
            # Llamamos a la función del padre pasándole (lat, lon)
            self.on_select_callback(coords[0], coords[1])

if __name__ == "__main__":
    # Test the tab
    root = tk.Tk()
    root.title("Stops Tab Test")
    root.geometry("800x600")
    
    tab = StopsTab(root)
    tab.pack(fill=tk.BOTH, expand=True)
    
    def print_config():
        config = tab.get_route_config()
        if config:
            print(f"Route: {config.route_name}")
            print(f"Segments: {len(config.segments)}")
            print(f"Sensors: {len(config.sensors)}")
    
    tk.Button(root, text="Get Config", command=print_config).pack()
    
    root.mainloop()
