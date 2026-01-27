"""
Simulation Tab - Select company and route to run simulations.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import threading
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.route import RouteConfig
from models.company import Company
from db.database import DatabaseManager


class SimulationTab(tk.Frame):
    """Tab for selecting company/route and running simulations."""
    
    def __init__(self, parent, companies_tab, routes_tab, distributions_tab=None):
        super().__init__(parent)
        
        self.companies_tab = companies_tab
        self.routes_tab = routes_tab
        self.distributions_tab = distributions_tab
        self.selected_company_id = None
        self.selected_route = None
        
        # Create UI
        self._create_ui()
    
    def _create_ui(self):
        """Create the UI components."""
        # Main container
        main_container = tk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title_frame = tk.Frame(main_container)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(title_frame, text="🚚 Configurar Simulación", 
                font=("Arial", 16, "bold")).pack(anchor=tk.W)
        tk.Label(title_frame, text="Selecciona una compañía y una ruta para ejecutar la simulación", 
                font=("Arial", 10), fg="gray").pack(anchor=tk.W)
        
        # Step 1: Select Company
        step1_frame = tk.LabelFrame(main_container, text="Paso 1: Seleccionar Compañía", 
                                   font=("Arial", 11, "bold"), padx=15, pady=15)
        step1_frame.pack(fill=tk.X, pady=(0, 15))
        
        company_select_frame = tk.Frame(step1_frame)
        company_select_frame.pack(fill=tk.X)
        
        tk.Label(company_select_frame, text="Compañía:", 
                font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.company_var = tk.StringVar()
        self.company_combo = ttk.Combobox(company_select_frame, textvariable=self.company_var,
                                         state='readonly', font=("Arial", 10), width=40)
        self.company_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.company_combo.bind('<<ComboboxSelected>>', self._on_company_select)
        
        tk.Button(company_select_frame, text="🔄 Refrescar", command=self._refresh_companies,
                 font=("Arial", 9)).pack(side=tk.LEFT)
        
        # Step 2: Select Route
        step2_frame = tk.LabelFrame(main_container, text="Paso 2: Seleccionar Ruta", 
                                   font=("Arial", 11, "bold"), padx=15, pady=15)
        step2_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        route_select_frame = tk.Frame(step2_frame)
        route_select_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(route_select_frame, text="Ruta:", 
                font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.route_var = tk.StringVar()
        self.route_combo = ttk.Combobox(route_select_frame, textvariable=self.route_var,
                                       state='readonly', font=("Arial", 10), width=40)
        self.route_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.route_combo.bind('<<ComboboxSelected>>', self._on_route_select)
        
        # Route preview
        tk.Label(step2_frame, text="Vista Previa de la Ruta:", 
                font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(5, 2))
        
        preview_frame = tk.Frame(step2_frame, relief=tk.SUNKEN, borderwidth=1)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        preview_scroll = tk.Scrollbar(preview_frame)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.route_preview_text = tk.Text(preview_frame, wrap=tk.WORD, 
                                         yscrollcommand=preview_scroll.set,
                                         font=("Courier", 9), state=tk.DISABLED, 
                                         height=12, bg="#f9f9f9")
        self.route_preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.config(command=self.route_preview_text.yview)
        
        # Step 3: Simulation Parameters
        step3_frame = tk.LabelFrame(main_container, text="Paso 3: Parámetros de Simulación", 
                                   font=("Arial", 11, "bold"), padx=15, pady=15)
        step3_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Create canvas and scrollbar for parameters
        params_canvas = tk.Canvas(step3_frame, highlightthickness=0, height=300)
        params_scrollbar = tk.Scrollbar(step3_frame, orient="vertical", command=params_canvas.yview)
        params_scrollable_frame = tk.Frame(params_canvas)
        
        params_scrollable_frame.bind(
            "<Configure>",
            lambda e: params_canvas.configure(scrollregion=params_canvas.bbox("all"))
        )
        
        params_canvas.create_window((0, 0), window=params_scrollable_frame, anchor="nw")
        params_canvas.configure(yscrollcommand=params_scrollbar.set)
        
        params_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        params_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            params_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        params_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        params_grid = tk.Frame(params_scrollable_frame)
        params_grid.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Departure date
        tk.Label(params_grid, text="Fecha de Salida:", 
                font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, pady=5, padx=(0, 10))
        
        date_frame = tk.Frame(params_grid)
        date_frame.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        from datetime import datetime
        today = datetime.now()
        
        self.departure_day_var = tk.IntVar(value=today.day)
        self.departure_month_var = tk.IntVar(value=today.month)
        self.departure_year_var = tk.IntVar(value=today.year)
        
        tk.Spinbox(date_frame, from_=1, to=31, textvariable=self.departure_day_var, 
                  width=4, font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Label(date_frame, text="/", font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Spinbox(date_frame, from_=1, to=12, textvariable=self.departure_month_var, 
                  width=4, font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Label(date_frame, text="/", font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Spinbox(date_frame, from_=2020, to=2030, textvariable=self.departure_year_var, 
                  width=6, font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Label(date_frame, text="(DD/MM/AAAA)", font=("Arial", 8), fg="gray").pack(side=tk.LEFT, padx=5)
        
        # Use real routes checkbox
        self.use_real_routes_var = tk.BooleanVar(value=True)
        self.use_real_routes_checkbox = tk.Checkbutton(params_grid, text="Usar Rutas Reales (OSM/Flight)", 
                      variable=self.use_real_routes_var,
                      font=("Arial", 9))
        self.use_real_routes_checkbox.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Secondary routes checkbox and count
        secondary_frame = tk.Frame(params_grid)
        secondary_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        self.use_secondary_routes_var = tk.BooleanVar(value=False)
        tk.Checkbutton(secondary_frame, text="Rutas Secundarias", 
                      variable=self.use_secondary_routes_var,
                      font=("Arial", 9),
                      command=self._toggle_secondary_routes).pack(side=tk.LEFT)
        
        tk.Label(secondary_frame, text="Cantidad:", font=("Arial", 9)).pack(side=tk.LEFT, padx=(10, 5))
        self.secondary_routes_count_var = tk.IntVar(value=1)
        self.secondary_routes_dropdown = ttk.Combobox(secondary_frame, 
                                                      textvariable=self.secondary_routes_count_var,
                                                      values=[1, 2, 3],
                                                      width=5,
                                                      state="disabled",
                                                      font=("Arial", 9))
        self.secondary_routes_dropdown.pack(side=tk.LEFT)
        
        # Include location names checkbox
        self.include_location_names_var = tk.BooleanVar(value=False)
        tk.Checkbutton(params_grid, text="Incluir Nombres de Ubicación", 
                      variable=self.include_location_names_var,
                      font=("Arial", 9)).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        tk.Label(params_grid, text="(Puede ralentizar la generación - requiere llamadas API)", 
                font=("Arial", 8), fg="gray").grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        
        # Reefer Sections Configuration
        tk.Label(params_grid, text="Configuración del Reefer:", 
                font=("Arial", 9, "bold")).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(10, 5))
        
        # Container for sections
        self.sections_container = tk.Frame(params_grid)
        self.sections_container.grid(row=6, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)
        
        # Track sections
        self.section_widgets = []
        
        # Add first section by default
        self._add_section()
        
        # Add section button
        add_section_btn_frame = tk.Frame(params_grid)
        add_section_btn_frame.grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        tk.Button(add_section_btn_frame, text="➕ Agregar Sección", 
                 command=self._add_section,
                 font=("Arial", 9), bg="#2196F3", fg="white").pack(side=tk.LEFT)

        
        # Action buttons
        action_frame = tk.Frame(main_container)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        
        tk.Button(action_frame, text="▶️ Ejecutar Simulación", 
                 command=self._run_simulation,
                 bg="#4CAF50", fg="white", font=("Arial", 12, "bold"),
                 height=2, width=20).pack(side=tk.LEFT, padx=(0, 10))
        
        # Info message
        info_frame = tk.Frame(main_container)
        info_frame.pack(fill=tk.X, pady=(15, 0))
        
        info_text = ("ℹ️ Información: \n"
                    "• Primero registra compañías en la pestaña 'Compañías'\n"
                    "• Luego crea rutas vinculadas a esas compañías en 'Rutas'\n"
                    "• Aquí seleccionas la compañía y ruta para ejecutar simulaciones")
        
        tk.Label(info_frame, text=info_text, 
                font=("Arial", 8), fg="#1976D2", justify=tk.LEFT,
                bg="#E3F2FD", relief=tk.RIDGE, padx=10, pady=10).pack(fill=tk.X)
        
        # Load initial data
        self._refresh_companies()
    
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
            messagebox.showerror("Error", f"Error refrescando compañías: {e}")
    
    def _on_company_select(self, event):
        """Handle company selection."""
        company_name = self.company_var.get()
        if not company_name:
            return
        
        # Find company ID
        companies = self.companies_tab.get_all_companies()
        for company in companies:
            if company.name == company_name:
                self.selected_company_id = company.id
                break
        
        # Update routes combobox for this company
        self._load_routes_for_company()
    
    def _load_routes_for_company(self):
        """Load routes for the selected company."""
        if not self.selected_company_id:
            return
        
        try:
            db = DatabaseManager()
            db.connect()
            
            routes_data = db.get_routes_by_company(self.selected_company_id)
            routes = [RouteConfig.from_dict(r) for r in routes_data]
            
            db.disconnect()
            
            # Update combobox
            self.route_combo['values'] = [r.route_name for r in routes]
            
            if routes:
                self.route_combo.current(0)
                self._on_route_select(None)
            else:
                self.route_combo.set('')
                self._clear_route_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando rutas: {e}")
    
    def _on_route_select(self, event):
        """Handle route selection."""
        route_name = self.route_var.get()
        if not route_name:
            return
        
        # Get the full route object from routes_tab
        try:
            db = DatabaseManager()
            db.connect()
            
            routes_data = db.get_routes_by_company(self.selected_company_id)
            for route_data in routes_data:
                if route_data['route_name'] == route_name:
                    self.selected_route = RouteConfig.from_dict(route_data)
                    break
            
            db.disconnect()
            
            if self.selected_route:
                self._display_route_preview()
                
                # Auto-activar "Usar Rutas Reales" si el modo es flight
                if self.selected_route.transport_mode == "flight":
                    self.use_real_routes_var.set(True)
                    self.use_real_routes_checkbox.config(state=tk.DISABLED)
                else:
                    self.use_real_routes_checkbox.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando ruta: {e}")
    
    def _display_route_preview(self):
        """Display preview of selected route."""
        if not self.selected_route:
            return
        
        route = self.selected_route
        
        preview = f"""
╔═══════════════════════════════════════════════════════════════╗
║                    RUTA: {route.route_name:<40} ║
╚═══════════════════════════════════════════════════════════════╝

Descripción: {route.route_description}

┌─────────────────────────────────────────────────────────────┐
│ ORIGEN                                                      │
└─────────────────────────────────────────────────────────────┘
  📍 {route.origin.name if route.origin else 'N/A'}
  🌐 Coords: {route.origin.latitude if route.origin else 'N/A'}, {route.origin.longitude if route.origin else 'N/A'}
  🕐 Salida: {route.origin.timestamp.strftime('%H:%M') if route.origin and route.origin.timestamp else 'N/A'}

┌─────────────────────────────────────────────────────────────┐
│ DESTINO                                                     │
└─────────────────────────────────────────────────────────────┘
  📍 {route.destination.name if route.destination else 'N/A'}
  🌐 Coords: {route.destination.latitude if route.destination else 'N/A'}, {route.destination.longitude if route.destination else 'N/A'}
  🕐 Llegada: {route.destination.timestamp.strftime('%H:%M') if route.destination and route.destination.timestamp else 'N/A'}

┌─────────────────────────────────────────────────────────────┐
│ SEGMENTOS ({len(route.segments)})                                              │
└─────────────────────────────────────────────────────────────┘
"""
        
        for i, seg in enumerate(route.segments, 1):
            preview += f"  {i}. {seg.description} ({seg.segment_type}) - {seg.estimated_stop_time_minutes} min\n"
        
        preview += f"""
┌─────────────────────────────────────────────────────────────┐
│ CONFIGURACIÓN                                               │
└─────────────────────────────────────────────────────────────┘
  ⏱️  Intervalo de log: {route.log_interval_seconds} seg
  🗺️  Rutas reales: {'Sí' if route.use_real_routes else 'No'}
  🚗 Transporte: {route.transport_mode}
"""
        
        # Agregar nota si es modo flight
        if route.transport_mode == "flight":
            preview += f"""
┌─────────────────────────────────────────────────────────────┐
│ ✈️  MODO VUELO ACTIVADO                                     │
└─────────────────────────────────────────────────────────────┘
  • "Usar Rutas Reales" se activa automáticamente
  • Cálculo de ruta geodésica (arco de gran círculo)
  • Velocidad: 850 km/h (configurable)
  • Sin dependencia de API externa
"""
        
        self.route_preview_text.config(state=tk.NORMAL)
        self.route_preview_text.delete('1.0', tk.END)
        self.route_preview_text.insert('1.0', preview)
        self.route_preview_text.config(state=tk.DISABLED)
    
    def _clear_route_preview(self):
        """Clear route preview."""
        self.route_preview_text.config(state=tk.NORMAL)
        self.route_preview_text.delete('1.0', tk.END)
        self.route_preview_text.config(state=tk.DISABLED)
    
    def _toggle_secondary_routes(self):
        """Enable/disable secondary routes dropdown."""
        if self.use_secondary_routes_var.get():
            self.secondary_routes_dropdown.config(state="readonly")
        else:
            self.secondary_routes_dropdown.config(state="disabled")
    
    def _add_section(self):
        """Add a new section input for EPCs/TIDs."""
        section_num = len(self.section_widgets) + 1
        
        # Create section frame
        section_frame = tk.Frame(self.sections_container, relief=tk.RIDGE, borderwidth=1, bg="#f0f0f0")
        section_frame.pack(fill=tk.X, pady=2, padx=5)
        
        # Section header
        header_frame = tk.Frame(section_frame, bg="#f0f0f0")
        header_frame.pack(fill=tk.X, padx=5, pady=2)
        
        tk.Label(header_frame, text=f"Sección {section_num}:", 
                font=("Arial", 9, "bold"), bg="#f0f0f0").pack(side=tk.LEFT)
        
        # Delete button (only show if more than 1 section)
        delete_btn = tk.Button(header_frame, text="🗑️ Eliminar", 
                              command=lambda: self._remove_section(section_frame),
                              font=("Arial", 8), fg="red", bg="#f0f0f0")
        if section_num > 1:
            delete_btn.pack(side=tk.RIGHT)
        
        # Input frame
        input_frame = tk.Frame(section_frame, bg="#f0f0f0")
        input_frame.pack(fill=tk.X, padx=5, pady=2)
        
        tk.Label(input_frame, text="Cantidad de Sensores:", 
                font=("Arial", 9), bg="#f0f0f0").pack(side=tk.LEFT, padx=(0, 5))
        
        sensor_count_var = tk.IntVar(value=100)
        spinbox = tk.Spinbox(input_frame, from_=1, to=10000, 
                            textvariable=sensor_count_var,
                            width=10, font=("Arial", 9))
        spinbox.pack(side=tk.LEFT)
        
        tk.Label(input_frame, text="EPCs/TIDs", 
                font=("Arial", 8), fg="gray", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        
        # Store section data
        section_data = {
            'frame': section_frame,
            'section_num': section_num,
            'sensor_count_var': sensor_count_var,
            'delete_btn': delete_btn
        }
        self.section_widgets.append(section_data)
        
        # Update section numbers
        self._update_section_numbers()
    
    def _remove_section(self, section_frame):
        """Remove a section."""
        # Find and remove the section
        for i, section_data in enumerate(self.section_widgets):
            if section_data['frame'] == section_frame:
                section_frame.destroy()
                self.section_widgets.pop(i)
                break
        
        # Update section numbers
        self._update_section_numbers()
    
    def _update_section_numbers(self):
        """Update section numbers after add/remove."""
        for i, section_data in enumerate(self.section_widgets):
            section_num = i + 1
            section_data['section_num'] = section_num
            
            # Update header label
            header_frame = section_data['frame'].winfo_children()[0]
            header_label = header_frame.winfo_children()[0]
            header_label.config(text=f"Sección {section_num}:")
            
            # Show/hide delete button based on count
            if len(self.section_widgets) > 1:
                section_data['delete_btn'].pack(side=tk.RIGHT)
            else:
                section_data['delete_btn'].pack_forget()

    
    def _run_simulation(self):
        """Run simulation with selected company and route."""
        if not self.selected_company_id:
            messagebox.showwarning("Validación", "Por favor selecciona una compañía.")
            return
        
        if not self.selected_route:
            messagebox.showwarning("Validación", "Por favor selecciona una ruta.")
            return
        
        # Validate sections
        if not self.section_widgets:
            messagebox.showwarning("Validación", "Debe haber al menos una sección.")
            return
        
        # Get section configurations
        sections_config = []
        total_sensors = 0
        for section_data in self.section_widgets:
            sensor_count = section_data['sensor_count_var'].get()
            if sensor_count <= 0:
                messagebox.showwarning("Validación", 
                                      f"La cantidad de sensores en Sección {section_data['section_num']} debe ser mayor a 0.")
                return
            sections_config.append({
                'section_id': section_data['section_num'],
                'sensor_count': sensor_count
            })
            total_sensors += sensor_count
        
        # Generate sensors for all sections
        try:
            self._generate_sensors_for_sections(sections_config)
        except Exception as e:
            messagebox.showerror("Error", f"Error generando sensores: {e}")
            return
        
        # Get parameters
        use_real = self.use_real_routes_var.get()
        use_secondary = self.use_secondary_routes_var.get()
        secondary_count = self.secondary_routes_count_var.get() if use_secondary else 0
        include_location_names = self.include_location_names_var.get()
        
        # Get departure date and set it on the route
        try:
            departure_datetime = datetime(
                self.departure_year_var.get(),
                self.departure_month_var.get(),
                self.departure_day_var.get(),
                8, 0, 0  # Default 8:00 AM departure
            )
            if self.selected_route.origin:
                self.selected_route.origin.timestamp = departure_datetime
        except ValueError as e:
            messagebox.showerror("Error", f"Fecha inválida: {e}")
            return
        
        # 💾 GUARDAR la fecha de salida en la base de datos
        try:
            db = DatabaseManager()
            db.connect()
            route_dict = self.selected_route.to_dict()
            db.update_route(self.selected_route.id, route_dict)
            db.disconnect()
            print(f"✓ Fecha de salida guardada: {departure_datetime.date()}")
        except Exception as e:
            print(f"⚠️ Error guardando fecha de salida: {e}")
        
        # Set real routes option on route config
        self.selected_route.use_real_routes = use_real
        
        # Calculate expected files
        num_sensors = len(self.selected_route.sensors) if self.selected_route.sensors else 1
        total_files = num_sensors
        if use_secondary and secondary_count > 0:
            total_files += (num_sensors * secondary_count)
        
        # Confirm generation
        departure_str = departure_datetime.strftime("%d/%m/%Y %H:%M")
        sections_info = "\n".join([f"  • Sección {s['section_id']}: {s['sensor_count']} sensores" 
                                   for s in sections_config])
        msg = (f"Generar simulación con:\n\n"
               f"Ruta: {self.selected_route.route_name}\n"
               f"Segmentos: {len(self.selected_route.segments)}\n"
               f"Secciones del Reefer: {len(sections_config)}\n{sections_info}\n"
               f"Total Sensores: {total_sensors}\n"
               f"Fecha Salida: {departure_str}\n"
               f"Rutas Reales: {'Sí' if use_real else 'No'}\n"
               f"Rutas Secundarias: {secondary_count if use_secondary else 'No'}\n"
               f"Incluir Ubicaciones: {'Sí' if include_location_names else 'No'}\n\n"
               f"Se crearán {total_files} archivo(s) JSON.")
        
        if not messagebox.askyesno("Confirmar Generación", msg):
            return
        
        # Disable button and show progress
        self.winfo_toplevel().config(cursor="wait")
        
        # Apply distributions from distributions tab if available
        if self.distributions_tab and hasattr(self.distributions_tab, 'apply_distributions_to_route'):
            print("📊 Aplicando distribuciones configuradas...")
            try:
                if not self.distributions_tab.apply_distributions_to_route(self.selected_route):
                    messagebox.showwarning("Distribuciones", 
                                          "No se pudieron aplicar las distribuciones. "
                                          "Se usarán valores por defecto.")
            except Exception as e:
                print(f"⚠️ Error aplicando distribuciones: {e}")
                messagebox.showwarning("Distribuciones", 
                                      f"Error aplicando distribuciones: {e}\n"
                                      "Se usarán valores por defecto.")
        
        # Run generation in background thread
        thread = threading.Thread(
            target=self._execute_simulation,
            args=(use_real, use_secondary, secondary_count, include_location_names, sections_config),
            daemon=True
        )
        thread.start()
    
    def _generate_sensors_for_sections(self, sections_config: list):
        """Generate sensors with section IDs.
        
        Args:
            sections_config: List of dicts with 'section_id' and 'sensor_count'
        """
        from models.sensor import SensorConfig
        from db.database import DatabaseManager
        
        # Clear existing sensors
        self.selected_route.sensors = []
        
        # Get next available EPC and TID from database
        db = DatabaseManager()
        db.connect()
        
        try:
            base_epc = db.get_next_sensor_epc()
            base_tid = db.get_next_sensor_tid()
            
            # Extract numeric parts
            epc_prefix = base_epc[:9]  # "5201F2503"
            tid_prefix = base_tid[:17]  # "E2C24500200005668"
            
            epc_num = int(base_epc[9:])
            tid_num = int(base_tid[17:])
            
            # Generate sensors for each section
            sensor_offset = 0
            for section in sections_config:
                section_id = section['section_id']
                sensor_count = section['sensor_count']
                
                for i in range(sensor_count):
                    epc = f"{epc_prefix}{epc_num + sensor_offset:07d}"
                    tid = f"{tid_prefix}{tid_num + sensor_offset:07d}"
                    
                    sensor = SensorConfig(epc=epc, tid=tid)
                    sensor.section_id = section_id  # Add section ID to sensor
                    self.selected_route.sensors.append(sensor)
                    sensor_offset += 1
            
            print(f"✓ Generados {len(self.selected_route.sensors)} sensores en {len(sections_config)} secciones")
            
        finally:
            db.disconnect()
    
    def _generate_sensors_for_simulation(self, count: int):
        """DEPRECATED: Use _generate_sensors_for_sections instead.
        
        Args:
            count: Number of sensors to generate
        """
        from models.sensor import SensorConfig
        from db.database import DatabaseManager
        
        # Clear existing sensors
        self.selected_route.sensors = []
        
        # Get next available EPC and TID from database
        db = DatabaseManager()
        db.connect()
        
        try:
            base_epc = db.get_next_sensor_epc()
            base_tid = db.get_next_sensor_tid()
            
            # Extract numeric parts
            epc_prefix = base_epc[:9]  # "5201F2503"
            tid_prefix = base_tid[:17]  # "E2C24500200005668"
            
            epc_num = int(base_epc[9:])
            tid_num = int(base_tid[17:])
            
            # Generate sensors
            for i in range(count):
                epc = f"{epc_prefix}{epc_num + i:07d}"
                tid = f"{tid_prefix}{tid_num + i:07d}"
                
                sensor = SensorConfig(epc=epc, tid=tid)
                self.selected_route.sensors.append(sensor)
            
            print(f"✓ Generados {count} sensores con EPCs desde {base_epc} hasta {self.selected_route.sensors[-1].epc}")
            
        finally:
            db.disconnect()
    
    def _execute_simulation(self, use_real_routes, use_secondary_routes, secondary_routes_count, 
                          include_location_names, sections_config):
        """Execute simulation in background thread."""
        try:
            from simulator_adapter import SimulatorAdapter
            import uuid
            
            output_dir = "simulation_outputs"
            
            # Generate unique reefer ID for this simulation (voyage)
            reefer_id = str(uuid.uuid4())
            
            # Generate simulations using the adapter
            generated_files = SimulatorAdapter.generate_simulations(
                route_config=self.selected_route,
                num_samples=1,  # One sample per execution
                use_real_routes=use_real_routes,
                use_secondary_routes=use_secondary_routes,
                secondary_routes_count=secondary_routes_count,
                output_dir=output_dir,
                include_location_names=include_location_names,
                reefer_id=reefer_id,
                sections_config=sections_config
            )
            
            # Update UI on main thread
            self.after(0, self._simulation_complete, generated_files)
            
        except Exception as e:
            import traceback
            error_details = f"{str(e)}\n\n{traceback.format_exc()}"
            self.after(0, self._simulation_error, error_details)
    
    def _simulation_complete(self, generated_files):
        """Called when simulation completes successfully."""
        self.winfo_toplevel().config(cursor="")
        
        # Save to database in BATCH (mucho más rápido)
        saved_to_db = False
        db_ids = []
        
        if isinstance(generated_files, list) and generated_files:
            try:
                from db.database import save_simulations_batch
                
                print(f"\n💾 Guardando {len(generated_files)} simulaciones en la base de datos...")
                db_ids = save_simulations_batch(generated_files, show_progress=True)
                saved_to_db = True
                
            except Exception as e:
                import traceback
                print(f"✗ Error guardando en base de datos: {e}")
                print(traceback.format_exc())
        
        # Show success message
        if isinstance(generated_files, list):
            files_list = "\n".join([f"  • {os.path.basename(f)}" for f in generated_files[:10]])
            if len(generated_files) > 10:
                files_list += f"\n  ... y {len(generated_files) - 10} más"
            
            success_msg = f"✓ Se generaron {len(generated_files)} archivo(s) de simulación:\n\n{files_list}\n\nGuardados en: simulation_outputs/"
            
            if saved_to_db:
                success_msg += f"\n\n💾 {len(db_ids)} simulación(es) guardadas en la base de datos"
                if db_ids:
                    success_msg += f"\nIDs: {', '.join(map(str, db_ids[:5]))}"
                    if len(db_ids) > 5:
                        success_msg += f" ... y {len(db_ids) - 5} más"
            
            messagebox.showinfo("Éxito", success_msg)
        else:
            messagebox.showinfo("Éxito", f"Simulación completada:\n{generated_files}")
    
    def _simulation_error(self, error_msg):
        """Called when simulation encounters an error."""
        self.winfo_toplevel().config(cursor="")
        messagebox.showerror("Error de Simulación", f"Ocurrió un error:\n\n{error_msg}")
