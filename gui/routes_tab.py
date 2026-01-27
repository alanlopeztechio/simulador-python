"""
Routes Tab - Complete route management with integrated editor.
Create, edit, and manage routes linked to companies with full configuration.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import json
from datetime import datetime, time
import threading
import requests
import itertools
import tkintermapview

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.route import RouteConfig, RoutePoint
from models.segment import SegmentMetadata
from models.sensor import SensorConfig
from models.company import Company
from db.database import DatabaseManager


class LocationSearchWidget(tk.Frame):
    """Widget for searching and selecting locations using Nominatim (OpenStreetMap)."""
    
    _last_request_time = 0  # Class variable to track last request time
    
    def __init__(self, parent, on_select_callback=None):
        super().__init__(parent)
        self.on_select_callback = on_select_callback
        self.loading = False
        self.spinner_cycle = itertools.cycle(["|", "/", "-", "\\"])
        
        # Search entry
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self, textvariable=self.search_var, width=30, font=("Arial", 9))
        self.search_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        # Search button
        self.search_btn = tk.Button(self, text="🔍", command=self._search,
                                    font=("Arial", 9), bg="#2196F3", fg="white")
        self.search_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Results combobox
        self.results_var = tk.StringVar()
        self.results_combo = ttk.Combobox(self, textvariable=self.results_var,
                                         state='readonly', width=40, font=("Arial", 9))
        self.results_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.results_combo.bind('<<ComboboxSelected>>', self._on_result_selected)
        
        # Status label
        self.status_label = tk.Label(self, text="", font=("Arial", 8), fg="gray")
        self.status_label.pack(side=tk.LEFT)
        
        # Store coordinates for each result
        self.results_coords = {}
    
    def _search(self):
        """Start search in background thread."""
        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Búsqueda", "Por favor ingresa una ubicación para buscar.")
            return
        
        self.loading = True
        self.status_label.config(text="Buscando...", fg="blue")
        threading.Thread(target=self._fetch_locations, args=(query,), daemon=True).start()
    
    def _fetch_locations(self, query):
        """Fetch locations from OpenRouteService API."""
        try:
            api_key = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjMwYWY3NzRhN2U1YjRkMWRhMDdhNDRmYzM4ZDBkMmYwIiwiaCI6Im11cm11cjY0In0="
            
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
            
            results = []
            coords = {}
            
            for f in features:
                props = f.get("properties", {})
                geom = f.get("geometry", {})
                
                label = props.get("label")
                if label and geom.get("coordinates"):
                    results.append(label)
                    lng, lat = geom["coordinates"]
                    coords[label] = (lat, lng)
            
            self.after(0, self._update_results, results, coords)
            
        except Exception as e:
            self.after(0, messagebox.showerror, "Error", f"Error en búsqueda: {e}")
        finally:
            self.after(0, self._stop_loading)
    
    def _update_results(self, results, coords):
        """Update combobox with search results."""
        self.results_coords = coords
        self.results_combo['values'] = results
        if results:
            self.results_combo.current(0)
            self.status_label.config(text=f"{len(results)} resultados", fg="green")
        else:
            self.status_label.config(text="Sin resultados", fg="orange")
    
    def _stop_loading(self):
        """Stop loading indicator."""
        self.loading = False
    
    def _on_result_selected(self, event):
        """Handle result selection."""
        selected = self.results_var.get()
        if selected and selected in self.results_coords:
            lat, lng = self.results_coords[selected]
            if self.on_select_callback:
                self.on_select_callback(lat, lng)
            self.status_label.config(text="✓ Ubicación seleccionada", fg="green")
    
    def get_text(self):
        """Get the selected location text."""
        return self.results_var.get() or self.search_var.get()
    
    def set_text(self, text):
        """Set the search entry text."""
        self.search_var.set(text)
        self.results_var.set(text)
        self.results_combo['values'] = [text] if text else []
        if text:
            self.results_combo.current(0)


class RoutesTab(tk.Frame):
    """Tab for complete route management with integrated editor."""
    
    SEGMENT_TYPES = ["Fleet", "Control", "Highway", "Urban", "Rural", "Warehouse"]
    
    def __init__(self, parent, companies_tab):
        super().__init__(parent)
        
        self.companies_tab = companies_tab
        self.db = None
        self.routes = []
        self.selected_company_id = None
        self.current_route = None
        self.editing_mode = False
        
        # Data storage for editor
        self.segment_frames = []
        
        # Map markers
        self.origin_marker = None
        self.destination_marker = None
        self.segment_markers = []
        
        # Create UI
        self._create_ui()
    
    def _create_ui(self):
        """Create the complete UI with list and editor."""
        main_paned = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)
        
        # LEFT PANEL
        left_panel = tk.Frame(main_paned, width=300)
        main_paned.add(left_panel, minsize=250)
        self._create_routes_list(left_panel)
        
        # RIGHT PANEL
        right_panel = tk.Frame(main_paned)
        main_paned.add(right_panel, minsize=700)
        self._create_route_editor(right_panel)
        
        self._refresh_companies()
    
    def _create_routes_list(self, parent):
        """Create routes list panel."""
        company_frame = tk.LabelFrame(parent, text="Compañía", font=("Arial", 10, "bold"), padx=10, pady=10)
        company_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.company_var = tk.StringVar()
        self.company_combo = ttk.Combobox(company_frame, textvariable=self.company_var,
                                         state='readonly', font=("Arial", 9), width=25)
        self.company_combo.pack(fill=tk.X, pady=(0, 5))
        self.company_combo.bind('<<ComboboxSelected>>', self._on_company_select)
        
        tk.Button(company_frame, text="🔄 Refrescar", command=self._refresh_companies,
                 font=("Arial", 8)).pack(fill=tk.X)
        
        routes_frame = tk.LabelFrame(parent, text="Rutas", font=("Arial", 10, "bold"), padx=10, pady=10)
        routes_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        list_frame = tk.Frame(routes_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.routes_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Arial", 9))
        self.routes_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.routes_listbox.yview)
        
        self.routes_listbox.bind('<<ListboxSelect>>', self._on_route_select)
        
        btn_frame = tk.Frame(routes_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        tk.Button(btn_frame, text="➕ Nueva", command=self._new_route,
                 bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(fill=tk.X, pady=1)
        tk.Button(btn_frame, text="✏️ Editar", command=self._edit_route,
                 bg="#FF9800", fg="white", font=("Arial", 9, "bold")).pack(fill=tk.X, pady=1)
        tk.Button(btn_frame, text="🗑️ Eliminar", command=self._delete_route,
                 bg="#f44336", fg="white", font=("Arial", 9, "bold")).pack(fill=tk.X, pady=1)
    
    def _create_route_editor(self, parent):
        """Create route editor panel with map."""
        editor_paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL)
        editor_paned.pack(fill=tk.BOTH, expand=True)
        
        # Form panel (scrollable)
        form_container = tk.Frame(editor_paned)
        editor_paned.add(form_container, minsize=400)
        
        form_canvas = tk.Canvas(form_container)
        form_scrollbar = tk.Scrollbar(form_container, orient="vertical", command=form_canvas.yview)
        self.form_frame = tk.Frame(form_canvas)
        
        self.form_frame.bind("<Configure>", lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all")))
        form_canvas.create_window((0, 0), window=self.form_frame, anchor="nw")
        form_canvas.configure(yscrollcommand=form_scrollbar.set)
        
        form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        form_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Map panel
        map_container = tk.Frame(editor_paned, relief=tk.SUNKEN, borderwidth=2)
        editor_paned.add(map_container, minsize=400)
        
        self.map_widget = tkintermapview.TkinterMapView(map_container, corner_radius=0)
        self.map_widget.pack(fill=tk.BOTH, expand=True)
        self.map_widget.set_position(34.0522, -118.2437)
        self.map_widget.set_zoom(10)
        
        self._build_editor_form()
    
    def _build_editor_form(self):
        """Build the route editor form."""
        container = self.form_frame
        
        # Title
        title_frame = tk.Frame(container, bg="#1976D2", pady=10)
        title_frame.pack(fill=tk.X)
        
        self.editor_title_label = tk.Label(title_frame, text="Editor de Ruta",
                                          font=("Arial", 14, "bold"), bg="#1976D2", fg="white")
        self.editor_title_label.pack()
        
        # Save button
        save_frame = tk.Frame(container, bg="#f0f0f0", pady=15)
        save_frame.pack(fill=tk.X)
        
        tk.Button(save_frame, text="💾 GUARDAR RUTA", command=self._save_route,
                 bg="#1976D2", fg="white", font=("Arial", 12, "bold"),
                 height=2, width=25).pack()
        
        # Route metadata
        metadata_frame = tk.LabelFrame(container, text="Información de la Ruta",
                                      font=("Arial", 10, "bold"), padx=10, pady=10)
        metadata_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(metadata_frame, text="Nombre:*", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.route_name_var = tk.StringVar()
        tk.Entry(metadata_frame, textvariable=self.route_name_var, width=40,
                font=("Arial", 9)).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        tk.Label(metadata_frame, text="Descripción:", font=("Arial", 9)).grid(row=1, column=0, sticky=tk.W, pady=2)
        self.route_desc_var = tk.StringVar()
        tk.Entry(metadata_frame, textvariable=self.route_desc_var, width=40,
                font=("Arial", 9)).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        tk.Label(metadata_frame, text="Modo de Transporte:*", font=("Arial", 9)).grid(row=2, column=0, sticky=tk.W, pady=2)
        self.transport_mode_var = tk.StringVar(value="driving-car")
        transport_combo = ttk.Combobox(metadata_frame, textvariable=self.transport_mode_var,
                                      values=["driving-car", "flight"],
                                      state="readonly", width=20, font=("Arial", 9))
        transport_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Help text for transport modes
        tk.Label(metadata_frame, text="🚗 Terrestre | ✈️ Aéreo", 
                font=("Arial", 8), fg="gray").grid(row=3, column=1, sticky=tk.W, padx=5)
        
        # Origin
        origin_frame = tk.LabelFrame(container, text="Origen",
                                    font=("Arial", 10, "bold"), padx=10, pady=10)
        origin_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.origin_lat_var = tk.DoubleVar(value=34.0522)
        self.origin_lng_var = tk.DoubleVar(value=-118.2437)
        self.origin_name_var = tk.StringVar(value="Origen")
        
        def set_origin_coords(lat, lng):
            self.origin_lat_var.set(lat)
            self.origin_lng_var.set(lng)
            text = self.origin_search.get_text()
            if text:
                self.origin_name_var.set(text)
            self._update_map_markers()
        
        tk.Label(origin_frame, text="Ubicación:").grid(row=0, column=0, sticky=tk.E)
        self.origin_search = LocationSearchWidget(origin_frame, on_select_callback=set_origin_coords)
        self.origin_search.grid(row=0, column=1, columnspan=3, sticky="w", pady=2)
        
        # Destination
        dest_frame = tk.LabelFrame(container, text="Destino",
                                  font=("Arial", 10, "bold"), padx=10, pady=10)
        dest_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.dest_lat_var = tk.DoubleVar(value=36.7783)
        self.dest_lng_var = tk.DoubleVar(value=-119.4179)
        self.dest_name_var = tk.StringVar(value="Destino")
        
        def set_dest_coords(lat, lng):
            self.dest_lat_var.set(lat)
            self.dest_lng_var.set(lng)
            text = self.dest_search.get_text()
            if text:
                self.dest_name_var.set(text)
            self._update_map_markers()
        
        tk.Label(dest_frame, text="Ubicación:").grid(row=0, column=0, sticky=tk.E)
        self.dest_search = LocationSearchWidget(dest_frame, on_select_callback=set_dest_coords)
        self.dest_search.grid(row=0, column=1, columnspan=3, sticky="w", pady=2)
        
        # Segments
        segments_frame = tk.LabelFrame(container, text="Segmentos (Waypoints)",
                                      font=("Arial", 10, "bold"), padx=10, pady=10)
        segments_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.segments_container = tk.Frame(segments_frame)
        self.segments_container.pack(fill=tk.BOTH, expand=True)
        
        tk.Button(segments_frame, text="➕ Agregar Segmento", command=self._add_segment,
                 bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(pady=5)
        
        self._set_editor_state(False)
    
    def _add_segment(self):
        """Add a new segment/waypoint."""
        index = len(self.segment_frames) + 1
        
        frame = tk.Frame(self.segments_container, relief=tk.GROOVE, borderwidth=2, padx=10, pady=10)
        frame.pack(fill=tk.X, pady=5)
        
        header = tk.Frame(frame)
        header.pack(fill=tk.X)
        tk.Label(header, text=f"Waypoint {index}", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        tk.Button(header, text="❌", command=lambda: self._remove_segment(frame),
                 bg="#f44336", fg="white", font=("Arial", 8, "bold")).pack(side=tk.RIGHT)
        
        data = tk.Frame(frame)
        data.pack(fill=tk.X, pady=5)
        
        tk.Label(data, text="Descripción:").grid(row=0, column=0, sticky=tk.W)
        desc_var = tk.StringVar(value=f"Waypoint {index}")
        tk.Entry(data, textvariable=desc_var, width=35).grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=5)
        
        lat_var = tk.DoubleVar(value=35.0)
        lng_var = tk.DoubleVar(value=-118.0)
        name_var = tk.StringVar(value=f"Waypoint {index}")
        
        def set_coords(lat, lng):
            lat_var.set(lat)
            lng_var.set(lng)
            text = search.get_text()
            if text:
                name_var.set(text)
                desc_var.set(text)
            self._update_map_markers()
        
        tk.Label(data, text="Ubicación:").grid(row=1, column=0, sticky=tk.E)
        search = LocationSearchWidget(data, on_select_callback=set_coords)
        search.grid(row=1, column=1, columnspan=2, sticky="w", padx=5, pady=2)
        
        tk.Label(data, text="Tipo:").grid(row=2, column=0, sticky=tk.E)
        type_var = tk.StringVar(value="Highway")
        ttk.Combobox(data, textvariable=type_var, values=self.SEGMENT_TYPES,
                    state="readonly", width=15).grid(row=2, column=1, sticky=tk.W, padx=5)
        
        tk.Label(data, text="Tiempo de Parada (min):").grid(row=3, column=0, sticky=tk.E)
        stop_var = tk.IntVar(value=30)
        tk.Entry(data, textvariable=stop_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5)
        
        self.segment_frames.append({
            "frame": frame,
            "description": desc_var,
            "latitude": lat_var,
            "longitude": lng_var,
            "name": name_var,
            "type": type_var,
            "stop_time": stop_var,
            "search": search
        })
        
        self._update_map_markers()
    
    def _remove_segment(self, frame_widget):
        """Remove a segment."""
        for seg_data in self.segment_frames:
            if seg_data["frame"] == frame_widget:
                self.segment_frames.remove(seg_data)
                frame_widget.destroy()
                self._update_map_markers()
                break
    
    def _update_map_markers(self):
        """Update map markers."""
        try:
            if self.origin_marker:
                self.origin_marker.delete()
            if self.destination_marker:
                self.destination_marker.delete()
            for marker in self.segment_markers:
                marker.delete()
            self.segment_markers.clear()
            
            all_lats = []
            all_lngs = []
            
            orig_lat = self.origin_lat_var.get()
            orig_lng = self.origin_lng_var.get()
            all_lats.append(orig_lat)
            all_lngs.append(orig_lng)
            self.origin_marker = self.map_widget.set_marker(orig_lat, orig_lng, text="Origen",
                                                            marker_color_circle="green")
            
            dest_lat = self.dest_lat_var.get()
            dest_lng = self.dest_lng_var.get()
            all_lats.append(dest_lat)
            all_lngs.append(dest_lng)
            self.destination_marker = self.map_widget.set_marker(dest_lat, dest_lng, text="Destino",
                                                                 marker_color_circle="red")
            
            for i, seg in enumerate(self.segment_frames, 1):
                lat = seg["latitude"].get()
                lng = seg["longitude"].get()
                all_lats.append(lat)
                all_lngs.append(lng)
                marker = self.map_widget.set_marker(lat, lng, text=f"W{i}",
                                                   marker_color_circle="blue")
                self.segment_markers.append(marker)
            
            if all_lats and all_lngs:
                center_lat = sum(all_lats) / len(all_lats)
                center_lng = sum(all_lngs) / len(all_lngs)
                self.map_widget.set_position(center_lat, center_lng)
                
                lat_diff = max(all_lats) - min(all_lats)
                lng_diff = max(all_lngs) - min(all_lngs)
                max_diff = max(lat_diff, lng_diff)
                
                zoom = 12 if max_diff < 0.1 else (10 if max_diff < 0.5 else (9 if max_diff < 1 else (8 if max_diff < 2 else 7)))
                self.map_widget.set_zoom(zoom)
                
        except Exception as e:
            print(f"Error updating markers: {e}")
    
    def _refresh_companies(self):
        """Refresh companies list."""
        try:
            self.companies_tab.load_companies()
            companies = self.companies_tab.get_all_companies()
            self.company_combo['values'] = [c.name for c in companies]
            if companies:
                self.company_combo.current(0)
                self._on_company_select(None)
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando compañías: {e}")
    
    def _on_company_select(self, event):
        """Handle company selection."""
        company_name = self.company_var.get()
        if not company_name:
            return
        
        companies = self.companies_tab.get_all_companies()
        for company in companies:
            if company.name == company_name:
                self.selected_company_id = company.id
                break
        
        self._load_routes()
    
    def _load_routes(self):
        """Load routes for selected company."""
        if not self.selected_company_id:
            return
        
        try:
            if not self.db:
                self.db = DatabaseManager()
                self.db.connect()
            
            routes_data = self.db.get_routes_by_company(self.selected_company_id)
            self.routes = [RouteConfig.from_dict(r) for r in routes_data]
            
            self.routes_listbox.delete(0, tk.END)
            for route in self.routes:
                self.routes_listbox.insert(tk.END, route.route_name)
            
            print(f"✓ Cargadas {len(self.routes)} rutas")
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando rutas: {e}")
    
    def _on_route_select(self, event):
        """Handle route selection in list."""
        selection = self.routes_listbox.curselection()
        if selection:
            index = selection[0]
            self.current_route = self.routes[index]
    
    def _new_route(self):
        """Create new route."""
        if not self.selected_company_id:
            messagebox.showwarning("Compañía", "Selecciona una compañía primero.")
            return
        
        self.editing_mode = False
        self.current_route = None
        self._clear_editor()
        self._set_editor_state(True)
        self.editor_title_label.config(text="Nueva Ruta")
    
    def _edit_route(self):
        """Edit selected route."""
        if not self.current_route:
            messagebox.showwarning("Selección", "Selecciona una ruta para editar.")
            return
        
        self.editing_mode = True
        self._load_route_to_editor(self.current_route)
        self._set_editor_state(True)
        self.editor_title_label.config(text=f"Editando: {self.current_route.route_name}")
    
    def _delete_route(self):
        """Delete selected route."""
        if not self.current_route:
            messagebox.showwarning("Selección", "Selecciona una ruta para eliminar.")
            return
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar '{self.current_route.route_name}'?"):
            try:
                self.db.delete_route(self.current_route.id)
                messagebox.showinfo("Éxito", "Ruta eliminada.")
                self._load_routes()
                self._clear_editor()
            except Exception as e:
                messagebox.showerror("Error", f"Error eliminando: {e}")
    
    def _save_route(self):
        """Save route to database."""
        if not self.selected_company_id:
            messagebox.showerror("Error", "No hay compañía seleccionada.")
            return
        
        route_name = self.route_name_var.get().strip()
        if not route_name:
            messagebox.showwarning("Validación", "El nombre de la ruta es requerido.")
            return
        
        try:
            origin = RoutePoint(
                name=self.origin_name_var.get(),
                latitude=self.origin_lat_var.get(),
                longitude=self.origin_lng_var.get(),
                point_type="origin"
            )
            
            destination = RoutePoint(
                name=self.dest_name_var.get(),
                latitude=self.dest_lat_var.get(),
                longitude=self.dest_lng_var.get(),
                point_type="destination"
            )
            
            waypoints = []
            segments = []
            for seg_data in self.segment_frames:
                wp = RoutePoint(
                    name=seg_data["name"].get(),
                    latitude=seg_data["latitude"].get(),
                    longitude=seg_data["longitude"].get(),
                    point_type="waypoint"
                )
                waypoints.append(wp)
                
                seg = SegmentMetadata(
                    description=seg_data["description"].get(),
                    segment_type=seg_data["type"].get(),
                    estimated_stop_time_minutes=seg_data["stop_time"].get()
                )
                segments.append(seg)
            
            route = RouteConfig(
                company_id=self.selected_company_id,
                route_name=route_name,
                route_description=self.route_desc_var.get(),
                origin=origin,
                destination=destination,
                waypoints=waypoints,
                segments=segments,
                sensors=[],  # Sensors are now managed in simulation tab
                transport_mode=self.transport_mode_var.get()
            )
            
            route_dict = route.to_dict()
            
            if self.editing_mode and self.current_route:
                self.db.update_route(self.current_route.id, route_dict)
                messagebox.showinfo("Éxito", "Ruta actualizada correctamente.")
            else:
                route_id = self.db.create_route(route_dict)
                messagebox.showinfo("Éxito", f"Ruta guardada con ID: {route_id}")
            
            self._load_routes()
            self._clear_editor()
            self._set_editor_state(False)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando ruta: {e}")
            print(f"Error details: {e}")
    
    def _clear_editor(self):
        """Clear editor fields."""
        self.route_name_var.set("")
        self.route_desc_var.set("")
        self.transport_mode_var.set("driving-car")
        self.origin_name_var.set("Origen")
        self.origin_lat_var.set(34.0522)
        self.origin_lng_var.set(-118.2437)
        self.dest_name_var.set("Destino")
        self.dest_lat_var.set(36.7783)
        self.dest_lng_var.set(-119.4179)
        
        for seg in self.segment_frames:
            seg["frame"].destroy()
        self.segment_frames.clear()
        
        self._update_map_markers()
    
    def _load_route_to_editor(self, route: RouteConfig):
        """Load route data into editor."""
        self._clear_editor()
        
        self.route_name_var.set(route.route_name)
        self.route_desc_var.set(route.route_description)
        self.transport_mode_var.set(route.transport_mode or "driving-car")
        
        if route.origin:
            self.origin_name_var.set(route.origin.name)
            self.origin_lat_var.set(route.origin.latitude)
            self.origin_lng_var.set(route.origin.longitude)
            # Update search widget text
            self.origin_search.set_text(route.origin.name)
        
        if route.destination:
            self.dest_name_var.set(route.destination.name)
            self.dest_lat_var.set(route.destination.latitude)
            self.dest_lng_var.set(route.destination.longitude)
            # Update search widget text
            self.dest_search.set_text(route.destination.name)
        
        # Load waypoints and segments
        for i, wp in enumerate(route.waypoints):
            self._add_segment()
            seg_data = self.segment_frames[-1]
            seg_data["name"].set(wp.name)
            seg_data["description"].set(wp.name)
            seg_data["latitude"].set(wp.latitude)
            seg_data["longitude"].set(wp.longitude)
            # Update search widget for waypoint
            if "search" in seg_data:
                seg_data["search"].set_text(wp.name)
        
        # Load segment metadata
        for i, seg in enumerate(route.segments):
            if i < len(self.segment_frames):
                self.segment_frames[i]["type"].set(seg.segment_type)
                self.segment_frames[i]["stop_time"].set(seg.estimated_stop_time_minutes)
                if seg.description:
                    self.segment_frames[i]["description"].set(seg.description)
        
        self._update_map_markers()
    
    def _set_editor_state(self, enabled: bool):
        """Enable/disable editor."""
        pass
    
    def get_selected_route(self):
        """Get currently selected route."""
        return self.current_route
    
    def get_route_config(self):
        """Get currently selected route config (alias for compatibility)."""
        return self.current_route
    
    def __del__(self):
        """Cleanup."""
        if self.db:
            try:
                self.db.disconnect()
            except:
                pass
