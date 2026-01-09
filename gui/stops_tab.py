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
import tkintermapview

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.route import RouteConfig, RoutePoint
from models.segment import SegmentMetadata
from models.sensor import SensorConfig
from db.database import DatabaseManager


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
        
        # Create main container with left and right panels
        main_container = tk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Left panel: Scrollable content (origin, destination, segments, sensors)
        left_panel = tk.Frame(main_container)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollable canvas for left panel
        self.canvas = tk.Canvas(left_panel)
        self.scrollbar = tk.Scrollbar(left_panel, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Right panel: Map widget
        right_panel = tk.Frame(main_container, width=400, relief=tk.SUNKEN, borderwidth=2)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5, pady=5)
        right_panel.pack_propagate(False)
        
        # Map widget
        self.map_widget = tkintermapview.TkinterMapView(right_panel, corner_radius=0)
        self.map_widget.pack(fill=tk.BOTH, expand=True)
        
        # Set initial position (Los Angeles area)
        self.map_widget.set_position(34.0522, -118.2437)
        self.map_widget.set_zoom(10)
        
        # Data storage
        self.segment_frames = []
        self.sensor_checkboxes = []
        self.available_sensors = []  # List of SensorConfig objects
        
        # Cache for used EPCs/TIDs (optimización para evitar consultas repetidas a BD)
        self.used_epcs_cache = set()
        self.used_tids_cache = set()
        self._load_used_identifiers_cache()
        
        # Map markers
        self.origin_marker = None
        self.destination_marker = None
        self.segment_markers = []  # List of markers for segments/waypoints
        
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
        self.origin_name_var = tk.StringVar(value="Origin")

        def set_origin_coords(lat, lon):
            self.origin_lat_var.set(lat)
            self.origin_lng_var.set(lon)
            # Guardar el nombre de la ubicación seleccionada
            selected_text = self.origin_search.get_text()
            if selected_text:
                self.origin_name_var.set(selected_text)
            self._update_map_markers()
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
        self.dest_name_var = tk.StringVar(value="Destination")

        def set_destination_coords(lat, lon):
            self.dest_lat_var.set(lat)
            self.dest_lng_var.set(lon)
            # Guardar el nombre de la ubicación seleccionada
            selected_text = self.destination_search.get_text()
            if selected_text:
                self.dest_name_var.set(selected_text)
            self._update_map_markers()
            print(f"Destino actualizado: {lat}, {lon}")
        
        self.destination_search = LocationSearchWidget(dest_frame, on_select_callback=set_destination_coords)
        self.destination_search.grid(row=0, column=1, columnspan=3, sticky="w")
        tk.Label(dest_frame, text="Location :").grid(row=0, column=0, sticky=tk.E)
        
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

    def _update_map_markers(self):
        """Update map markers for origin, destination, and segments."""
        try:
            origin_lat = self.origin_lat_var.get()
            origin_lng = self.origin_lng_var.get()
            dest_lat = self.dest_lat_var.get()
            dest_lng = self.dest_lng_var.get()
            
            # Remove existing markers
            if self.origin_marker:
                self.origin_marker.delete()
            if self.destination_marker:
                self.destination_marker.delete()
            for marker in self.segment_markers:
                marker.delete()
            self.segment_markers.clear()
            
            # Collect all points for center calculation
            all_lats = [origin_lat, dest_lat]
            all_lngs = [origin_lng, dest_lng]
            
            # Add origin marker (green)
            self.origin_marker = self.map_widget.set_marker(
                origin_lat, origin_lng, 
                text="Origin",
                marker_color_circle="green",
                marker_color_outside="darkgreen"
            )
            
            # Add destination marker (red)
            self.destination_marker = self.map_widget.set_marker(
                dest_lat, dest_lng,
                text="Destination", 
                marker_color_circle="red",
                marker_color_outside="darkred"
            )
            
            # Add segment markers (blue/orange)
            for i, segment_data in enumerate(self.segment_frames, start=1):
                seg_lat = segment_data["latitude"].get()
                seg_lng = segment_data["longitude"].get()
                seg_desc = segment_data["description"].get()
                
                all_lats.append(seg_lat)
                all_lngs.append(seg_lng)
                
                # Create marker for segment (blue)
                marker = self.map_widget.set_marker(
                    seg_lat, seg_lng,
                    text=f"Waypoint {i}",
                    marker_color_circle="blue",
                    marker_color_outside="darkblue"
                )
                self.segment_markers.append(marker)
            
            # Calculate center point from all markers
            center_lat = sum(all_lats) / len(all_lats)
            center_lng = sum(all_lngs) / len(all_lngs)
            
            # Set map position to center
            self.map_widget.set_position(center_lat, center_lng)
            
            # Adjust zoom to fit all markers
            lat_diff = max(all_lats) - min(all_lats)
            lng_diff = max(all_lngs) - min(all_lngs)
            max_diff = max(lat_diff, lng_diff)
            
            if max_diff < 0.1:
                zoom_level = 12
            elif max_diff < 0.5:
                zoom_level = 10
            elif max_diff < 1:
                zoom_level = 9
            elif max_diff < 2:
                zoom_level = 8
            elif max_diff < 5:
                zoom_level = 7
            else:
                zoom_level = 6
                
            self.map_widget.set_zoom(zoom_level)
            
        except Exception as e:
            print(f"Error updating map markers: {e}")
    
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
        desc_var = tk.StringVar(value=f"Waypoint {index}")
        tk.Entry(data_frame, textvariable=desc_var, width=50).grid(row=0, column=1, columnspan=3, sticky=tk.W, padx=5)
        
        # Row 1: Location Search
        tk.Label(data_frame, text="Location:").grid(row=1, column=0, sticky=tk.E)
        lat_var = tk.DoubleVar(value=34.0522)
        lng_var = tk.DoubleVar(value=-118.2437)
        name_var = tk.StringVar(value=f"Waypoint {index}")
        
        def set_segment_coords(lat, lon):
            lat_var.set(lat)
            lng_var.set(lon)
            # Guardar el nombre de la ubicación seleccionada
            selected_text = location_search.get_text()
            if selected_text:
                name_var.set(selected_text)
                desc_var.set(selected_text)  # También actualizar la descripción
            self._update_map_markers()
            print(f"Segment {index} updated: {lat}, {lon}")
        
        location_search = LocationSearchWidget(data_frame, on_select_callback=set_segment_coords)
        location_search.grid(row=1, column=1, columnspan=3, sticky="w", padx=5)
        
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
            "location_search": location_search,
            "name": name_var,
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
        self._update_map_markers()
    
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
        """Add a new sensor with unique EPC/TID verification."""
        # Generar sensor verificando contra la base de datos y cache local
        sensor = self._generate_unique_sensor()
        if sensor is None:
            messagebox.showerror(
                "Error",
                "No se pudo generar un sensor único. Verifica la conexión a la base de datos."
            )
            return
        
        # Agregar a cache local
        self.used_epcs_cache.add(sensor.epc)
        self.used_tids_cache.add(sensor.tid)
        
        self.available_sensors.append(sensor)
        
        # Get current index for this sensor
        current_index = len(self.available_sensors) - 1
        
        # Create checkbox frame
        frame = tk.Frame(self.sensors_list_frame, relief=tk.GROOVE, borderwidth=1, padx=5, pady=3)
        frame.pack(fill=tk.X, pady=2)
        
        # Sensor info
        info_text = f"{sensor.get_display_name()} - EPC: {sensor.epc}, TID: {sensor.tid}"
        tk.Label(frame, text=info_text, font=("Arial", 9)).pack(side=tk.LEFT)
        
        # Edit/Delete buttons
        btn_frame = tk.Frame(frame)
        btn_frame.pack(side=tk.RIGHT)
        tk.Button(btn_frame, text="Edit", command=lambda idx=current_index: self._edit_sensor(idx),
                 bg="#2196F3", fg="white", font=("Arial", 8), width=5).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Delete", command=lambda f=frame, idx=current_index: self._remove_sensor(f, idx),
                 bg="#E53935", fg="white", font=("Arial", 8), width=5).pack(side=tk.LEFT, padx=2)
    
    def _edit_sensor(self, index):
        """Edit sensor configuration with duplicate checking."""
        if 0 <= index < len(self.available_sensors):
            sensor = self.available_sensors[index]
            original_epc = sensor.epc
            original_tid = sensor.tid
            
            # Simple dialog for editing
            dialog = tk.Toplevel(self)
            dialog.title(f"Edit {sensor.get_display_name()}")
            dialog.geometry("400x300")
            
            tk.Label(dialog, text="EPC:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
            epc_var = tk.StringVar(value=sensor.epc)
            tk.Entry(dialog, textvariable=epc_var, width=30).grid(row=0, column=1, padx=10, pady=5)
            
            tk.Label(dialog, text="TID:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
            tid_var = tk.StringVar(value=sensor.tid)
            tk.Entry(dialog, textvariable=tid_var, width=30).grid(row=1, column=1, padx=10, pady=5)
            
            tk.Label(dialog, text="Name:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
            name_var = tk.StringVar(value=sensor.name or "")
            tk.Entry(dialog, textvariable=name_var, width=30).grid(row=2, column=1, padx=10, pady=5)
            
            # Status label for warnings
            status_label = tk.Label(dialog, text="", fg="orange", font=("Arial", 8))
            status_label.grid(row=3, column=0, columnspan=2, pady=5)
            
            def save():
                new_epc = epc_var.get().strip()
                new_tid = tid_var.get().strip()
                
                # Verificar duplicados solo si cambió el valor
                if new_epc != original_epc and self._is_identifier_used(new_epc, 'epc', exclude_sensor=sensor):
                    messagebox.showerror("Error", f"El EPC '{new_epc}' ya está en uso en la base de datos.")
                    return
                
                if new_tid != original_tid and self._is_identifier_used(new_tid, 'tid', exclude_sensor=sensor):
                    messagebox.showerror("Error", f"El TID '{new_tid}' ya está en uso en la base de datos.")
                    return
                
                # Actualizar cache si cambió
                if new_epc != original_epc:
                    self.used_epcs_cache.discard(original_epc)
                    self.used_epcs_cache.add(new_epc)
                if new_tid != original_tid:
                    self.used_tids_cache.discard(original_tid)
                    self.used_tids_cache.add(new_tid)
                
                sensor.epc = new_epc
                sensor.tid = new_tid
                sensor.name = name_var.get() if name_var.get() else None
                self._refresh_sensor_list()
                dialog.destroy()
            
            tk.Button(dialog, text="Save", command=save, bg="#4CAF50", fg="white").grid(row=4, column=0, columnspan=2, pady=10)
    
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
        current_index = len(self.available_sensors) - 1
        frame = tk.Frame(self.sensors_list_frame, relief=tk.GROOVE, borderwidth=1, padx=5, pady=3)
        frame.pack(fill=tk.X, pady=2)
        
        info_text = f"{sensor.get_display_name()} - EPC: {sensor.epc}, TID: {sensor.tid}"
        tk.Label(frame, text=info_text, font=("Arial", 9)).pack(side=tk.LEFT)
        
        btn_frame = tk.Frame(frame)
        btn_frame.pack(side=tk.RIGHT)
        tk.Button(btn_frame, text="Edit", command=lambda idx=current_index: self._edit_sensor(idx),
                 bg="#2196F3", fg="white", font=("Arial", 8), width=5).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Delete", command=lambda f=frame, idx=current_index: self._remove_sensor(f, idx),
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
            name=self.origin_name_var.get(),
            latitude=self.origin_lat_var.get(),
            longitude=self.origin_lng_var.get(),
            point_type="origin",
            timestamp=origin_time,
        )
        
        # Destination (arrival time will be calculated with real API data during generation)
        from datetime import timedelta
        from geopy.distance import geodesic
        
        # Use simple distance-based estimation for now
        # The real API duration will be used during simulation generation
        distance_km = geodesic(
            (self.origin_lat_var.get(), self.origin_lng_var.get()),
            (self.dest_lat_var.get(), self.dest_lng_var.get())
        ).kilometers
        estimated_hours = distance_km / 60.0
        arrival_time = origin_time + timedelta(hours=estimated_hours)
        
        config.destination = RoutePoint(
            name=self.dest_name_var.get(),
            latitude=self.dest_lat_var.get(),
            longitude=self.dest_lng_var.get(),
            point_type="destination",
            timestamp=arrival_time,
        )
        
        # Waypoints and segments
        for segment_data in self.segment_frames:
            # Create waypoint for this segment
            waypoint = RoutePoint(
                name=segment_data["name"].get(),
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


# Helper functions para StopsTab - Verificación de EPCs/TIDs
def _load_used_identifiers_cache(self):
    """Carga el cache de EPCs/TIDs usados desde la base de datos.
    
    Esta función se ejecuta una sola vez al inicializar la UI para
    optimizar las verificaciones posteriores.
    """
    try:
        with DatabaseManager() as db:
            self.used_epcs_cache = set(db.get_used_epcs())
            self.used_tids_cache = set(db.get_used_tids())
            print(f"✓ Cache cargado: {len(self.used_epcs_cache)} EPCs, {len(self.used_tids_cache)} TIDs en uso")
    except Exception as e:
        print(f"⚠ No se pudo cargar cache de BD: {e}")
        print("  Continuando sin verificación de base de datos...")
        self.used_epcs_cache = set()
        self.used_tids_cache = set()


def _is_identifier_used(self, identifier: str, id_type: str, exclude_sensor=None) -> bool:
    """Verifica si un EPC o TID ya está en uso.
    
    Args:
        identifier: EPC o TID a verificar
        id_type: 'epc' o 'tid'
        exclude_sensor: Sensor a excluir de la verificación (para edición)
    
    Returns:
        True si está en uso, False si está disponible
    """
    # Verificar en sensores locales primero
    for sensor in self.available_sensors:
        if sensor == exclude_sensor:
            continue
        if id_type == 'epc' and sensor.epc == identifier:
            return True
        if id_type == 'tid' and sensor.tid == identifier:
            return True
    
    # Verificar en cache de base de datos
    if id_type == 'epc':
        return identifier in self.used_epcs_cache
    else:
        return identifier in self.used_tids_cache


def _generate_unique_sensor(self) -> Optional[SensorConfig]:
    """Genera un sensor con EPC y TID únicos.
    
    Verifica contra la base de datos y sensores locales para garantizar
    que no haya duplicados.
    
    Returns:
        SensorConfig con identificadores únicos o None si hay error
    """
    try:
        # Recargar cache para asegurar datos frescos
        with DatabaseManager() as db:
            self.used_epcs_cache = set(db.get_used_epcs())
            self.used_tids_cache = set(db.get_used_tids())
        
        # Encontrar el siguiente índice disponible
        index = 1
        max_attempts = 10000  # Prevenir bucle infinito
        
        while index < max_attempts:
            # Generar EPC y TID con el índice actual
            test_epc = f"5201F250300{index:05d}"
            test_tid = f"E2C24500200005668{index:07d}"
            
            # Verificar si están disponibles (no en cache ni en sensores locales)
            epc_available = not self._is_identifier_used(test_epc, 'epc')
            tid_available = not self._is_identifier_used(test_tid, 'tid')
            
            if epc_available and tid_available:
                # Encontramos un índice disponible
                sensor = SensorConfig.generate_default(index)
                print(f"✓ Sensor único generado: índice {index}, EPC: {test_epc}")
                return sensor
            
            index += 1
        
        # Si llegamos aquí, no encontramos índice disponible
        messagebox.showwarning(
            "Advertencia",
            f"No se encontró un índice disponible después de {max_attempts} intentos."
        )
        return None
        
    except Exception as e:
        print(f"✗ Error generando sensor único: {e}")
        # En caso de error, generar con índice basado en cantidad local
        # (modo fallback sin verificación de BD)
        index = len(self.available_sensors) + 1
        sensor = SensorConfig.generate_default(index)
        print(f"⚠ Usando modo fallback: índice {index}")
        return sensor


def _refresh_cache_from_db(self):
    """Refresca el cache de EPCs/TIDs desde la base de datos.
    
    Útil para actualizar después de operaciones que modifican la BD.
    """
    try:
        with DatabaseManager() as db:
            self.used_epcs_cache = set(db.get_used_epcs())
            self.used_tids_cache = set(db.get_used_tids())
            print(f"✓ Cache actualizado: {len(self.used_epcs_cache)} EPCs, {len(self.used_tids_cache)} TIDs")
    except Exception as e:
        print(f"⚠ No se pudo actualizar cache: {e}")


# Agregar los métodos a la clase StopsTab
StopsTab._load_used_identifiers_cache = _load_used_identifiers_cache
StopsTab._is_identifier_used = _is_identifier_used
StopsTab._generate_unique_sensor = _generate_unique_sensor
StopsTab._refresh_cache_from_db = _refresh_cache_from_db


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
