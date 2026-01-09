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
    
    def __init__(self, parent, companies_tab, routes_tab):
        super().__init__(parent)
        
        self.companies_tab = companies_tab
        self.routes_tab = routes_tab
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
        step3_frame.pack(fill=tk.X, pady=(0, 15))
        
        params_grid = tk.Frame(step3_frame)
        params_grid.pack(fill=tk.X)
        
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
        self.use_real_routes_var = tk.BooleanVar(value=False)
        tk.Checkbutton(params_grid, text="Usar Rutas Reales (OSM)", 
                      variable=self.use_real_routes_var,
                      font=("Arial", 9)).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
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
    
    def _run_simulation(self):
        """Run simulation with selected company and route."""
        if not self.selected_company_id:
            messagebox.showwarning("Validación", "Por favor selecciona una compañía.")
            return
        
        if not self.selected_route:
            messagebox.showwarning("Validación", "Por favor selecciona una ruta.")
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
        
        # Set real routes option on route config
        self.selected_route.use_real_routes = use_real
        
        # Calculate expected files
        num_sensors = len(self.selected_route.sensors) if self.selected_route.sensors else 1
        total_files = num_sensors
        if use_secondary and secondary_count > 0:
            total_files += (num_sensors * secondary_count)
        
        # Confirm generation
        departure_str = departure_datetime.strftime("%d/%m/%Y %H:%M")
        msg = (f"Generar simulación con:\n\n"
               f"Ruta: {self.selected_route.route_name}\n"
               f"Segmentos: {len(self.selected_route.segments)}\n"
               f"Sensores: {num_sensors}\n"
               f"Fecha Salida: {departure_str}\n"
               f"Rutas Reales: {'Sí' if use_real else 'No'}\n"
               f"Rutas Secundarias: {secondary_count if use_secondary else 'No'}\n"
               f"Incluir Ubicaciones: {'Sí' if include_location_names else 'No'}\n\n"
               f"Se crearán {total_files} archivo(s) JSON.")
        
        if not messagebox.askyesno("Confirmar Generación", msg):
            return
        
        # Disable button and show progress
        self.winfo_toplevel().config(cursor="wait")
        
        # Run generation in background thread
        thread = threading.Thread(
            target=self._execute_simulation,
            args=(use_real, use_secondary, secondary_count, include_location_names),
            daemon=True
        )
        thread.start()
    
    def _execute_simulation(self, use_real_routes, use_secondary_routes, secondary_routes_count, include_location_names):
        """Execute simulation in background thread."""
        try:
            from simulator_adapter import SimulatorAdapter
            
            output_dir = "simulation_outputs"
            
            # Generate simulations using the adapter
            generated_files = SimulatorAdapter.generate_simulations(
                route_config=self.selected_route,
                num_samples=1,  # One sample per execution
                use_real_routes=use_real_routes,
                use_secondary_routes=use_secondary_routes,
                secondary_routes_count=secondary_routes_count,
                output_dir=output_dir,
                include_location_names=include_location_names
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
        
        # Save to database
        saved_to_db = False
        db_ids = []
        
        if isinstance(generated_files, list) and generated_files:
            try:
                from db.database import save_simulation_to_neon
                
                for json_file in generated_files:
                    try:
                        sim_id = save_simulation_to_neon(json_file=json_file)
                        db_ids.append(sim_id)
                    except Exception as e:
                        print(f"Failed to save {json_file}: {e}")
                
                if db_ids:
                    saved_to_db = True
                
            except Exception as e:
                print(f"Auto-save to database failed: {e}")
        
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
