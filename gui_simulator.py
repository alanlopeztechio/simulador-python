import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import threading
import os
import json
import webbrowser
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from simulator import LogSimulator, PredefinedUseCases, BatchSimulator


class SimulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🚚 Simulador de Cadena de Frío - RFID")
        self.root.geometry("1100x850")
        self.root.resizable(True, True)
        
        # Variables
        self.output_dir = tk.StringVar(value="use_cases_output")
        self.num_samples_per_case = tk.IntVar(value=1)
        self.use_real_routes = tk.BooleanVar(value=False)
        self.generate_plots = tk.BooleanVar(value=True)
        self.generate_maps = tk.BooleanVar(value=True)
        
        # Configuración de los 3 casos de uso
        self.case_configs = {
            1: {
                'enabled': tk.BooleanVar(value=True),
                'name': 'Cadena Frío Farmacéutica',
                'samples': tk.IntVar(value=1)
            },
            2: {
                'enabled': tk.BooleanVar(value=True),
                'name': 'Alimentos Perecederos',
                'samples': tk.IntVar(value=1)
            },
            3: {
                'enabled': tk.BooleanVar(value=True),
                'name': 'Químicos Industriales',
                'samples': tk.IntVar(value=1)
            }
        }
        
        self.is_generating = False
        self.generated_files = {}  # Almacena los archivos generados por caso
        
        self._create_widgets()
        self._load_existing_files()  # Cargar archivos existentes al iniciar
        
    def _create_widgets(self):
        """Crea todos los widgets de la interfaz"""
        
        # ===== HEADER =====
        header_frame = tk.Frame(self.root, bg="#2E86AB", pady=15)
        header_frame.pack(fill=tk.X)
        
        title_label = tk.Label(
            header_frame,
            text="🚚 SIMULADOR DE CADENA DE FRÍO CON RFID 🌡️",
            font=("Arial", 18, "bold"),
            bg="#2E86AB",
            fg="white"
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            header_frame,
            text="Generador de datos simulados con distribuciones estadísticas",
            font=("Arial", 10),
            bg="#2E86AB",
            fg="white"
        )
        subtitle_label.pack()
        
        # ===== SCROLLABLE CONTAINER =====
        # Crear un canvas con scrollbar
        canvas_container = tk.Frame(self.root)
        canvas_container.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(canvas_container, highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        
        # Frame scrollable dentro del canvas
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Empaquetar canvas y scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Habilitar scroll con la rueda del mouse
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # ===== MAIN CONTAINER (ahora dentro del frame scrollable) =====
        main_container = tk.Frame(scrollable_frame, padx=20, pady=20)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # ===== CONFIGURACIÓN GENERAL =====
        general_frame = tk.LabelFrame(
            main_container,
            text="⚙️ Configuración General",
            font=("Arial", 12, "bold"),
            padx=15,
            pady=15
        )
        general_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Output Directory
        dir_frame = tk.Frame(general_frame)
        dir_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(dir_frame, text="📁 Carpeta de salida:", font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Entry(dir_frame, textvariable=self.output_dir, width=40, font=("Arial", 10)).pack(side=tk.LEFT, padx=10)
        tk.Button(
            dir_frame,
            text="Explorar...",
            command=self._browse_directory,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT)
        
        # Opciones
        options_frame = tk.Frame(general_frame)
        options_frame.pack(fill=tk.X, pady=10)
        
        tk.Checkbutton(
            options_frame,
            text="📈 Generar gráficas de análisis",
            variable=self.generate_plots,
            font=("Arial", 10)
        ).pack(anchor=tk.W, pady=2)
        
        tk.Checkbutton(
            options_frame,
            text="🗺️ Generar mapas interactivos",
            variable=self.generate_maps,
            font=("Arial", 10)
        ).pack(anchor=tk.W, pady=2)
        
        tk.Checkbutton(
            options_frame,
            text="🛣️ Usar rutas reales (OpenStreetMap)",
            variable=self.use_real_routes,
            font=("Arial", 10)
        ).pack(anchor=tk.W, pady=2)
        
        # ===== CASOS DE USO =====
        cases_frame = tk.LabelFrame(
            main_container,
            text="📦 Casos de Uso - Configuración de Muestras",
            font=("Arial", 12, "bold"),
            padx=15,
            pady=10
        )
        cases_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Obtener casos de uso predefinidos
        use_cases = PredefinedUseCases.get_all_cases()
        
        for i, use_case in enumerate(use_cases, 1):
            self._create_case_widget(cases_frame, i, use_case)
        
        # ===== BOTONES DE ACCIÓN =====
        button_frame = tk.Frame(main_container)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.generate_btn = tk.Button(
            button_frame,
            text="🚀 GENERAR SIMULACIONES",
            command=self._start_generation,
            bg="#2E86AB",
            fg="white",
            font=("Arial", 14, "bold"),
            height=2,
            cursor="hand2"
        )
        self.generate_btn.pack(fill=tk.X, pady=5)
        
        tk.Button(
            button_frame,
            text="📂 Abrir carpeta de salida",
            command=self._open_output_folder,
            bg="#757575",
            fg="white",
            font=("Arial", 10, "bold"),
            cursor="hand2"
        ).pack(fill=tk.X, pady=5)
        
        # ===== BARRA DE PROGRESO =====
        progress_frame = tk.Frame(main_container)
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.progress_label = tk.Label(
            progress_frame,
            text="Listo para generar simulaciones",
            font=("Arial", 10)
        )
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode='indeterminate',
            length=800
        )
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # ===== LOG OUTPUT =====
        log_frame = tk.LabelFrame(
            main_container,
            text="📋 Registro de Actividad",
            font=("Arial", 10, "bold"),
            padx=10,
            pady=10
        )
        log_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.log_text = tk.Text(
            log_frame,
            height=6,
            font=("Courier", 9),
            bg="#f5f5f5",
            wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # ===== VISOR DE RESULTADOS =====
        viewer_frame = tk.LabelFrame(
            main_container,
            text="👁️ Visor de Resultados Generados",
            font=("Arial", 10, "bold"),
            padx=10,
            pady=10
        )
        viewer_frame.pack(fill=tk.X, pady=(10, 0))
        
        self._create_viewer_panel(viewer_frame)
        
    def _create_case_widget(self, parent, case_num, use_case):
        """Crea un widget para configurar un caso de uso específico"""
        case_frame = tk.Frame(parent, relief=tk.GROOVE, borderwidth=2, padx=10, pady=10)
        case_frame.pack(fill=tk.X, pady=5)
        
        # Header del caso
        header = tk.Frame(case_frame)
        header.pack(fill=tk.X)
        
        # Checkbox para habilitar/deshabilitar
        tk.Checkbutton(
            header,
            text=f"Caso {case_num}: {use_case.name}",
            variable=self.case_configs[case_num]['enabled'],
            font=("Arial", 11, "bold")
        ).pack(side=tk.LEFT)
        
        # Detalles del caso
        details_frame = tk.Frame(case_frame)
        details_frame.pack(fill=tk.X, pady=5)
        
        details_text = f"""📍 Ruta: {use_case.start_location_name} → {use_case.end_location_name}
⏱️ Duración: {use_case.expected_duration_hours:.1f} hrs | 🌡️ Rango: [{use_case.lower_temp}°C, {use_case.upper_temp}°C] | 📊 Distribución: {use_case.distribution_type.upper()}
📝 {use_case.description}"""
        
        tk.Label(
            details_frame,
            text=details_text,
            font=("Arial", 9),
            justify=tk.LEFT,
            fg="#555555"
        ).pack(anchor=tk.W)
        
        # Configuración de muestras
        samples_frame = tk.Frame(case_frame)
        samples_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(
            samples_frame,
            text="Número de muestras (JSONs) a generar:",
            font=("Arial", 9)
        ).pack(side=tk.LEFT)
        
        tk.Spinbox(
            samples_frame,
            from_=1,
            to=50,
            textvariable=self.case_configs[case_num]['samples'],
            width=10,
            font=("Arial", 10)
        ).pack(side=tk.LEFT, padx=10)
        
    def _create_viewer_panel(self, parent):
        """Crea el panel para visualizar los resultados generados"""
        # Frame de selección
        selection_frame = tk.Frame(parent)
        selection_frame.pack(fill=tk.X, pady=5)
        
        # Selector de caso de uso
        tk.Label(selection_frame, text="📦 Caso de uso:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.case_selector = ttk.Combobox(selection_frame, state="readonly", width=30, font=("Arial", 9))
        self.case_selector.pack(side=tk.LEFT, padx=5)
        self.case_selector.bind("<<ComboboxSelected>>", self._on_case_selected)
        
        # Selector de muestra JSON
        tk.Label(selection_frame, text="📄 Muestra:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.sample_selector = ttk.Combobox(selection_frame, state="readonly", width=40, font=("Arial", 9))
        self.sample_selector.pack(side=tk.LEFT, padx=5)
        self.sample_selector.bind("<<ComboboxSelected>>", self._on_sample_selected)
        
        # Botones de acción
        action_frame = tk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(
            action_frame,
            text="📊 Ver Gráficas",
            command=self._view_plot,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            action_frame,
            text="🗺️ Ver Mapa",
            command=self._view_map,
            bg="#2196F3",
            fg="white",
            font=("Arial", 10, "bold"),
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            action_frame,
            text="📄 Ver JSON",
            command=self._view_json,
            bg="#FF9800",
            fg="white",
            font=("Arial", 10, "bold"),
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            action_frame,
            text="� Abrir Carpeta",
            command=self._open_sample_folder,
            bg="#9C27B0",
            fg="white",
            font=("Arial", 10, "bold"),
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            action_frame,
            text="�🔄 Actualizar Lista",
            command=self._load_existing_files,
            bg="#757575",
            fg="white",
            font=("Arial", 10, "bold"),
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        # Panel de información del archivo seleccionado
        info_frame = tk.LabelFrame(parent, text="ℹ️ Información del Archivo", font=("Arial", 9, "bold"))
        info_frame.pack(fill=tk.X, pady=10)
        
        self.info_text = tk.Text(info_frame, height=5, font=("Courier", 9), bg="#f9f9f9", wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def _load_existing_files(self):
        """Carga los archivos existentes en el directorio de salida"""
        output_dir = self.output_dir.get()
        self.generated_files = {}
        
        if not os.path.exists(output_dir):
            self._log("⚠️ El directorio de salida no existe todavía")
            return
        
        # Buscar carpetas de casos
        for item in os.listdir(output_dir):
            item_path = os.path.join(output_dir, item)
            if os.path.isdir(item_path) and item.startswith("case_"):
                # Extraer número de caso y nombre
                parts = item.split("_", 2)
                if len(parts) >= 3:
                    case_num = parts[1]
                    case_name = parts[2].replace("_", " ").title()
                    
                    # Buscar carpetas de muestras dentro del caso
                    sample_folders = []
                    for sample_item in os.listdir(item_path):
                        sample_path = os.path.join(item_path, sample_item)
                        if os.path.isdir(sample_path) and sample_item.startswith("sample_"):
                            # Buscar archivos dentro de la carpeta de la muestra
                            json_file = None
                            plot_file = None
                            map_file = None
                            
                            for file in os.listdir(sample_path):
                                file_path = os.path.join(sample_path, file)
                                if file.endswith(".json"):
                                    json_file = file_path
                                elif file.endswith(".png"):
                                    plot_file = file_path
                                elif file.endswith(".html"):
                                    map_file = file_path
                            
                            if json_file:
                                sample_folders.append({
                                    'json': json_file,
                                    'plot': plot_file,
                                    'map': map_file,
                                    'name': sample_item,
                                    'folder': sample_path
                                })
                    
                    # Ordenar las muestras por nombre
                    sample_folders.sort(key=lambda x: x['name'])
                    
                    if sample_folders:
                        self.generated_files[f"Caso {case_num}: {case_name}"] = sample_folders
        
        # Actualizar selector de casos
        case_names = list(self.generated_files.keys())
        self.case_selector['values'] = case_names
        
        if case_names:
            self.case_selector.current(0)
            self._on_case_selected(None)
            self._log(f"✓ Cargados {len(case_names)} caso(s) con archivos generados")
        else:
            self.sample_selector['values'] = []
            self._log("⚠️ No se encontraron archivos generados")
    
    def _on_case_selected(self, event):
        """Maneja la selección de un caso de uso"""
        case_name = self.case_selector.get()
        if case_name and case_name in self.generated_files:
            samples = self.generated_files[case_name]
            sample_names = [s['name'] for s in samples]
            self.sample_selector['values'] = sample_names
            if sample_names:
                self.sample_selector.current(0)
                self._on_sample_selected(None)
    
    def _on_sample_selected(self, event):
        """Maneja la selección de una muestra específica"""
        case_name = self.case_selector.get()
        sample_name = self.sample_selector.get()
        
        if case_name and sample_name and case_name in self.generated_files:
            samples = self.generated_files[case_name]
            selected_sample = next((s for s in samples if s['name'] == sample_name), None)
            
            if selected_sample:
                # Mostrar información del archivo
                self.info_text.delete(1.0, tk.END)
                
                info = f"📁 Muestra: {sample_name}\n"
                info += f"� Carpeta: {selected_sample['folder']}\n\n"
                
                # Leer datos del JSON
                try:
                    with open(selected_sample['json'], 'r') as f:
                        data = json.load(f)
                    
                    info += f"🏷️  EPC: {data.get('EPC', 'N/A')}\n"
                    info += f"🏷️  TID: {data.get('TID', 'N/A')}\n"
                    info += f"📊 Muestras de datos: {len(data.get('loggedData', []))}\n"
                    
                    config = data.get('configuration', {})
                    info += f"⏱️  Intervalo: {config.get('logIntervalInSeconds', 0)}s\n"
                    info += f"🌡️  Rango: [{config.get('temperatureLowerLimit', 0)}°C, {config.get('temperatureUpperLimit', 0)}°C]\n"
                    
                    alarms = data.get('alarms', {})
                    if alarms.get('alarmAny'):
                        info += f"⚠️  ALARMAS DETECTADAS!\n"
                        if alarms.get('alarmLowTemperature'):
                            info += f"   ❄️ Temperatura baja\n"
                        if alarms.get('alarmHighTemperature'):
                            info += f"   🔥 Temperatura alta\n"
                    else:
                        info += f"✅ Sin alarmas\n"
                    
                    info += f"\n� JSON: {'✓' if selected_sample['json'] else '✗'}\n"
                    info += f"�📊 Gráfica: {'✓' if selected_sample['plot'] else '✗'}\n"
                    info += f"🗺️  Mapa: {'✓' if selected_sample['map'] else '✗'}\n"
                    
                except Exception as e:
                    info += f"\n❌ Error al leer JSON: {str(e)}"
                
                self.info_text.insert(1.0, info)
    
    def _view_plot(self):
        """Muestra la gráfica interactiva de Matplotlib en una ventana emergente"""
        case_name = self.case_selector.get()
        sample_name = self.sample_selector.get()
        
        if not case_name or not sample_name:
            messagebox.showwarning("Selección requerida", "Por favor selecciona un caso y una muestra.")
            return
        
        samples = self.generated_files.get(case_name, [])
        selected_sample = next((s for s in samples if s['name'] == sample_name), None)
        
        if selected_sample and selected_sample['json']:
            if os.path.exists(selected_sample['json']):
                self._show_interactive_plot_window(selected_sample['json'], sample_name)
                self._log(f"📊 Mostrando gráfica interactiva: {sample_name}")
            else:
                messagebox.showerror("Archivo no encontrado", "El archivo JSON no existe.")
        else:
            messagebox.showinfo("Datos no disponibles", "No se encontró el archivo JSON para generar la gráfica.")
    
    def _show_interactive_plot_window(self, json_path, title):
        """Crea una ventana emergente con gráfica interactiva de Matplotlib"""
        plot_window = tk.Toplevel(self.root)
        plot_window.title(f"📊 Gráfica Interactiva - {title}")
        plot_window.geometry("1600x1000")
        
        # Frame principal
        main_frame = tk.Frame(plot_window)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_frame = tk.Frame(main_frame, bg="#4CAF50", pady=10)
        title_frame.pack(fill=tk.X)
        
        tk.Label(
            title_frame,
            text=f"📊 Análisis Completo Interactivo - {title}",
            font=("Arial", 14, "bold"),
            bg="#4CAF50",
            fg="white"
        ).pack()
        
        # Botones de acción
        button_frame = tk.Frame(main_frame, pady=10)
        button_frame.pack(fill=tk.X)
        
        tk.Label(
            button_frame,
            text="� Puedes hacer zoom, pan, y guardar la gráfica usando los botones de la barra de herramientas de Matplotlib",
            font=("Arial", 9, "italic"),
            fg="#555555"
        ).pack(side=tk.LEFT, padx=10)
        
        tk.Button(
            button_frame,
            text="❌ Cerrar",
            command=plot_window.destroy,
            bg="#757575",
            fg="white",
            font=("Arial", 10, "bold")
        ).pack(side=tk.RIGHT, padx=5)
        
        # Frame con scroll para el canvas de Matplotlib
        canvas_frame = tk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Crear canvas con scrollbars
        canvas_container = tk.Canvas(canvas_frame, bg="white")
        scrollbar_y = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas_container.yview)
        scrollbar_x = tk.Scrollbar(canvas_frame, orient="horizontal", command=canvas_container.xview)
        
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        canvas_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Frame scrollable para la gráfica
        scrollable_frame = tk.Frame(canvas_container)
        canvas_container.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        try:
            # Cargar datos del JSON
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            # Recrear el simulador desde el JSON para generar la gráfica
            self._log(f"   Cargando datos y generando gráfica interactiva...")
            
            # Extraer datos del JSON
            from datetime import datetime
            timestamps = [datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00')) for d in data['loggedData']]
            temperatures = [d['tempInC'] for d in data['loggedData']]
            
            config = data['configuration']
            lower_temp = config['temperatureLowerLimit']
            upper_temp = config['temperatureUpperLimit']
            
            # Crear figura de Matplotlib (similar a la del simulator.py)
            import matplotlib
            matplotlib.use('TkAgg')
            
            from matplotlib.figure import Figure
            import matplotlib.dates as mdates
            from scipy import stats
            import numpy as np
            
            fig = Figure(figsize=(18, 12), dpi=100)
            gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
            
            # 1. Temperatura vs Tiempo
            ax1 = fig.add_subplot(gs[0, :])
            ax1.plot(timestamps, temperatures, marker='o', linestyle='-', linewidth=2, markersize=4, color='#2E86AB')
            ax1.axhline(y=lower_temp, color='blue', linestyle='--', linewidth=2, label=f'Límite inferior ({lower_temp}°C)', alpha=0.7)
            ax1.axhline(y=upper_temp, color='red', linestyle='--', linewidth=2, label=f'Límite superior ({upper_temp}°C)', alpha=0.7)
            ax1.fill_between(timestamps, lower_temp, upper_temp, alpha=0.2, color='green', label='Rango seguro')
            
            # Marcar violaciones
            violations_low = [(timestamps[i], temperatures[i]) for i in range(len(temperatures)) if temperatures[i] < lower_temp]
            violations_high = [(timestamps[i], temperatures[i]) for i in range(len(temperatures)) if temperatures[i] > upper_temp]
            
            if violations_low:
                ax1.scatter([v[0] for v in violations_low], [v[1] for v in violations_low], 
                           color='blue', s=100, marker='v', zorder=5, label='Violación baja')
            if violations_high:
                ax1.scatter([v[0] for v in violations_high], [v[1] for v in violations_high], 
                           color='red', s=100, marker='^', zorder=5, label='Violación alta')
            
            ax1.set_xlabel('Tiempo', fontsize=12, fontweight='bold')
            ax1.set_ylabel('Temperatura (°C)', fontsize=12, fontweight='bold')
            ax1.set_title(f'Monitoreo de Temperatura\nEPC: {data["EPC"]}', fontsize=14, fontweight='bold')
            ax1.grid(True, alpha=0.3, linestyle='--')
            ax1.legend(loc='best')
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            fig.autofmt_xdate()
            
            # 2. Histograma y Distribución
            ax2 = fig.add_subplot(gs[1, 0])
            counts, bins, patches = ax2.hist(temperatures, bins=25, density=True, alpha=0.7, 
                                            color='skyblue', edgecolor='black', linewidth=1.2)
            
            for i, patch in enumerate(patches):
                temp = (bins[i] + bins[i+1]) / 2
                if temp < lower_temp:
                    patch.set_facecolor('lightblue')
                elif temp > upper_temp:
                    patch.set_facecolor('lightcoral')
                else:
                    patch.set_facecolor('lightgreen')
            
            x_range = np.linspace(min(temperatures), max(temperatures), 100)
            mean = np.mean(temperatures)
            std = np.std(temperatures)
            pdf = stats.norm.pdf(x_range, mean, std)
            ax2.plot(x_range, pdf, 'r-', linewidth=3, label=f'Normal(μ={mean:.1f}, σ={std:.1f})')
            
            ax2.axvline(x=lower_temp, color='blue', linestyle='--', linewidth=2, alpha=0.7)
            ax2.axvline(x=upper_temp, color='red', linestyle='--', linewidth=2, alpha=0.7)
            ax2.set_xlabel('Temperatura (°C)', fontsize=11, fontweight='bold')
            ax2.set_ylabel('Densidad', fontsize=11, fontweight='bold')
            ax2.set_title('Distribución de Temperaturas', fontsize=12, fontweight='bold')
            ax2.legend()
            ax2.grid(True, alpha=0.3, linestyle='--')
            
            # 3. Box Plot
            ax3 = fig.add_subplot(gs[1, 1])
            box = ax3.boxplot(temperatures, vert=True, patch_artist=True,
                             boxprops=dict(facecolor='lightblue', linewidth=2),
                             whiskerprops=dict(linewidth=2),
                             capprops=dict(linewidth=2),
                             medianprops=dict(color='darkblue', linewidth=2))
            ax3.axhline(y=lower_temp, color='blue', linestyle='--', linewidth=2, label='Límite inferior', alpha=0.7)
            ax3.axhline(y=upper_temp, color='red', linestyle='--', linewidth=2, label='Límite superior', alpha=0.7)
            ax3.set_ylabel('Temperatura (°C)', fontsize=11, fontweight='bold')
            ax3.set_title('Box Plot de Temperaturas', fontsize=12, fontweight='bold')
            ax3.legend()
            ax3.grid(True, alpha=0.3, axis='y', linestyle='--')
            
            # 4. Q-Q Plot
            ax4 = fig.add_subplot(gs[1, 2])
            stats.probplot(temperatures, dist="norm", plot=ax4)
            ax4.set_title('Q-Q Plot (Normal)', fontsize=12, fontweight='bold')
            ax4.grid(True, alpha=0.3, linestyle='--')
            
            # 5. Serie temporal con media móvil
            ax5 = fig.add_subplot(gs[2, 0])
            ax5.plot(timestamps, temperatures, 'o-', label='Temperatura', alpha=0.6)
            
            # Calcular media móvil
            window = min(5, len(temperatures))
            if len(temperatures) >= window:
                moving_avg = np.convolve(temperatures, np.ones(window)/window, mode='valid')
                moving_timestamps = timestamps[window-1:]
                ax5.plot(moving_timestamps, moving_avg, 'r-', linewidth=2, label=f'Media móvil ({window} puntos)')
            
            ax5.axhline(y=lower_temp, color='blue', linestyle='--', alpha=0.5)
            ax5.axhline(y=upper_temp, color='red', linestyle='--', alpha=0.5)
            ax5.set_xlabel('Tiempo', fontsize=11, fontweight='bold')
            ax5.set_ylabel('Temperatura (°C)', fontsize=11, fontweight='bold')
            ax5.set_title('Serie Temporal con Media Móvil', fontsize=12, fontweight='bold')
            ax5.legend()
            ax5.grid(True, alpha=0.3, linestyle='--')
            ax5.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            
            # 6. Estadísticas
            ax6 = fig.add_subplot(gs[2, 1:])
            ax6.axis('off')
            
            violations_count = len(violations_low) + len(violations_high)
            compliance_rate = ((len(temperatures) - violations_count) / len(temperatures)) * 100
            
            stats_text = f"""
            {'='*70}
            REPORTE DE SIMULACIÓN
            {'='*70}
            
            EPC: {data['EPC']}
            TID: {data['TID']}
            
            TEMPERATURAS
            {'─'*70}
            Media: {np.mean(temperatures):.2f}°C
            Mediana: {np.median(temperatures):.2f}°C
            Desviación Estándar: {np.std(temperatures):.2f}°C
            Mínima: {min(temperatures):.2f}°C
            Máxima: {max(temperatures):.2f}°C
            Rango permitido: [{lower_temp}°C, {upper_temp}°C]
            
            ALARMAS Y CUMPLIMIENTO
            {'─'*70}
            ⚠️  Violaciones totales: {violations_count} ({(violations_count/len(temperatures)*100):.1f}%)
            ❄️  Temperaturas bajo límite: {len(violations_low)}
            🔥 Temperaturas sobre límite: {len(violations_high)}
            ✓  Tasa de cumplimiento: {compliance_rate:.1f}%
            
            MUESTRAS
            {'─'*70}
            Total de muestras: {len(temperatures)}
            Intervalo: {config['logIntervalInSeconds']}s
            {'='*70}
            """
            
            ax6.text(0.05, 0.95, stats_text, transform=ax6.transAxes,
                    fontsize=9, verticalalignment='top', fontfamily='monospace',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.6, pad=1))
            
            fig.suptitle(f'ANÁLISIS COMPLETO INTERACTIVO', fontsize=16, fontweight='bold', y=0.995)
            
            # Integrar figura en Tkinter
            canvas_plot = FigureCanvasTkAgg(fig, master=scrollable_frame)
            canvas_plot.draw()
            canvas_plot.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Agregar toolbar de navegación de matplotlib
            from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
            toolbar = NavigationToolbar2Tk(canvas_plot, scrollable_frame)
            toolbar.update()
            
            # Configurar scrollregion
            scrollable_frame.update_idletasks()
            canvas_container.configure(scrollregion=canvas_container.bbox("all"), 
                                      yscrollcommand=scrollbar_y.set,
                                      xscrollcommand=scrollbar_x.set)
            
            self._log(f"   ✓ Gráfica interactiva generada exitosamente")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar la gráfica:\n{str(e)}")
            self._log(f"   ❌ Error al generar gráfica: {str(e)}")
            plot_window.destroy()
    
    def _view_map(self):
        """Muestra el mapa en una ventana emergente con navegador integrado"""
        case_name = self.case_selector.get()
        sample_name = self.sample_selector.get()
        
        if not case_name or not sample_name:
            messagebox.showwarning("Selección requerida", "Por favor selecciona un caso y una muestra.")
            return
        
        samples = self.generated_files.get(case_name, [])
        selected_sample = next((s for s in samples if s['name'] == sample_name), None)
        
        if selected_sample and selected_sample['map']:
            if os.path.exists(selected_sample['map']):
                self._show_map_window(selected_sample['map'], sample_name)
                self._log(f"🗺️ Mostrando mapa: {os.path.basename(selected_sample['map'])}")
            else:
                messagebox.showerror("Archivo no encontrado", "El mapa no existe.")
        else:
            messagebox.showinfo("Mapa no disponible", "No se generó un mapa para esta muestra.")
    
    def _show_map_window(self, map_path, title):
        """Crea una ventana emergente para mostrar el mapa interactivo"""
        map_window = tk.Toplevel(self.root)
        map_window.title(f"🗺️ Mapa Interactivo - {title}")
        map_window.geometry("1200x800")
        
        # Frame principal
        main_frame = tk.Frame(map_window)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_frame = tk.Frame(main_frame, bg="#2196F3", pady=10)
        title_frame.pack(fill=tk.X)
        
        tk.Label(
            title_frame,
            text=f"🗺️ Mapa de Ruta Interactivo - {title}",
            font=("Arial", 14, "bold"),
            bg="#2196F3",
            fg="white"
        ).pack()
        
        # Botones de acción
        button_frame = tk.Frame(main_frame, pady=10)
        button_frame.pack(fill=tk.X)
        
        tk.Button(
            button_frame,
            text="🌐 Abrir en Navegador",
            command=lambda: webbrowser.open('file://' + os.path.abspath(map_path)),
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="💾 Guardar Como...",
            command=lambda: self._save_map_as(map_path),
            bg="#FF9800",
            fg="white",
            font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="❌ Cerrar",
            command=map_window.destroy,
            bg="#757575",
            fg="white",
            font=("Arial", 10, "bold")
        ).pack(side=tk.RIGHT, padx=5)
        
        # Instrucciones
        info_frame = tk.Frame(main_frame, bg="#E3F2FD", pady=5)
        info_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(
            info_frame,
            text="💡 Haz clic en el botón '🌐 Abrir en Navegador' para ver el mapa interactivo completo con todas las funcionalidades de zoom y navegación.",
            font=("Arial", 9),
            bg="#E3F2FD",
            wraplength=1100,
            justify=tk.LEFT
        ).pack(pady=5)
        
        # Frame para mostrar información del mapa
        content_frame = tk.Frame(main_frame, bg="white")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Leer y mostrar información del HTML
        try:
            with open(map_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            info_text = tk.Text(content_frame, font=("Courier", 10), wrap=tk.WORD, height=25)
            info_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
            
            scrollbar = tk.Scrollbar(content_frame, command=info_text.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            info_text.config(yscrollcommand=scrollbar.set)
            
            # Mostrar información sobre el mapa
            info = f"""{'='*80}
MAPA INTERACTIVO DE RUTA - {title}
{'='*80}

📍 Archivo: {os.path.basename(map_path)}
📂 Ruta completa: {map_path}
📏 Tamaño: {os.path.getsize(map_path) / 1024:.2f} KB

{'─'*80}
CARACTERÍSTICAS DEL MAPA:
{'─'*80}

✓ Mapa interactivo basado en OpenStreetMap
✓ Visualización de ruta completa con puntos de muestreo
✓ Marcadores de inicio (verde) y fin (rojo)
✓ Colores por temperatura:
  • Verde: Temperatura dentro del rango seguro
  • Rojo: Temperatura por encima del límite superior
  • Azul: Temperatura por debajo del límite inferior

✓ Funcionalidades interactivas:
  • Zoom in/out con botones o rueda del mouse
  • Navegación arrastrando el mapa
  • Popups informativos al hacer clic en puntos
  • Medición de temperatura en cada punto de la ruta

{'─'*80}
INSTRUCCIONES DE USO:
{'─'*80}

1. Haz clic en '🌐 Abrir en Navegador' para ver el mapa completo
2. En el navegador, puedes:
   • Hacer clic en cualquier punto de la ruta para ver detalles
   • Usar zoom para explorar áreas específicas
   • Hacer clic en los marcadores para información detallada
   • Mover el mapa arrastrando con el mouse

3. El mapa es completamente interactivo y muestra:
   • Temperatura en cada punto de medición
   • Hora de cada registro
   • Coordenadas GPS exactas
   • Estado de alarmas si las hubiera

{'='*80}

Para una mejor experiencia, abre el mapa en tu navegador predeterminado.
"""
            
            info_text.insert(1.0, info)
            info_text.config(state=tk.DISABLED)
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el mapa:\n{str(e)}")
            map_window.destroy()
    
    def _save_map_as(self, map_path):
        """Guarda una copia del mapa en otra ubicación"""
        new_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
            initialfile=os.path.basename(map_path)
        )
        if new_path:
            import shutil
            shutil.copy2(map_path, new_path)
            messagebox.showinfo("Guardado", f"Mapa guardado en:\n{new_path}")
    
    def _view_json(self):
        """Abre el archivo JSON en el editor predeterminado"""
        case_name = self.case_selector.get()
        sample_name = self.sample_selector.get()
        
        if not case_name or not sample_name:
            messagebox.showwarning("Selección requerida", "Por favor selecciona un caso y una muestra.")
            return
        
        samples = self.generated_files.get(case_name, [])
        selected_sample = next((s for s in samples if s['name'] == sample_name), None)
        
        if selected_sample:
            if os.path.exists(selected_sample['json']):
                os.startfile(selected_sample['json'])
                self._log(f"📄 Abriendo JSON: {os.path.basename(selected_sample['json'])}")
            else:
                messagebox.showerror("Archivo no encontrado", "El archivo JSON no existe.")
    
    def _open_sample_folder(self):
        """Abre la carpeta de la muestra seleccionada en el explorador"""
        case_name = self.case_selector.get()
        sample_name = self.sample_selector.get()
        
        if not case_name or not sample_name:
            messagebox.showwarning("Selección requerida", "Por favor selecciona un caso y una muestra.")
            return
        
        samples = self.generated_files.get(case_name, [])
        selected_sample = next((s for s in samples if s['name'] == sample_name), None)
        
        if selected_sample and selected_sample.get('folder'):
            if os.path.exists(selected_sample['folder']):
                os.startfile(selected_sample['folder'])
                self._log(f"📂 Abriendo carpeta: {os.path.basename(selected_sample['folder'])}")
            else:
                messagebox.showerror("Carpeta no encontrada", "La carpeta de la muestra no existe.")
        else:
            messagebox.showerror("Error", "No se pudo encontrar la carpeta de la muestra.")
    
    def _browse_directory(self):
        """Abre un diálogo para seleccionar la carpeta de salida"""
        directory = filedialog.askdirectory(initialdir=self.output_dir.get())
        if directory:
            self.output_dir.set(directory)
            
    def _open_output_folder(self):
        """Abre la carpeta de salida en el explorador de archivos"""
        output_path = self.output_dir.get()
        if os.path.exists(output_path):
            os.startfile(output_path)
        else:
            messagebox.showwarning("Carpeta no encontrada", f"La carpeta '{output_path}' no existe todavía.")
    
    def _log(self, message):
        """Agrega un mensaje al log"""
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def _start_generation(self):
        """Inicia el proceso de generación en un hilo separado"""
        if self.is_generating:
            messagebox.showwarning("Generación en proceso", "Ya hay una generación en curso.")
            return
        
        # Validar que al menos un caso esté habilitado
        if not any(config['enabled'].get() for config in self.case_configs.values()):
            messagebox.showerror("Error", "Debe habilitar al menos un caso de uso.")
            return
        
        # Confirmar generación
        total_jsons = sum(
            config['samples'].get() for config in self.case_configs.values() 
            if config['enabled'].get()
        )
        
        response = messagebox.askyesno(
            "Confirmar generación",
            f"Se generarán {total_jsons} archivos JSON.\n"
            f"¿Desea continuar?"
        )
        
        if not response:
            return
        
        # Iniciar generación en thread separado
        self.is_generating = True
        self.generate_btn.config(state=tk.DISABLED, text="⏳ Generando...")
        self.progress_bar.start(10)
        
        thread = threading.Thread(target=self._generate_simulations, daemon=True)
        thread.start()
    
    def _generate_simulations(self):
        """Genera las simulaciones según la configuración"""
        try:
            output_dir = self.output_dir.get()
            os.makedirs(output_dir, exist_ok=True)
            
            self._log("="*60)
            self._log("🚀 INICIANDO GENERACIÓN DE SIMULACIONES")
            self._log("="*60)
            
            use_cases = PredefinedUseCases.get_all_cases()
            total_generated = 0
            
            for case_num, use_case in enumerate(use_cases, 1):
                config = self.case_configs[case_num]
                
                if not config['enabled'].get():
                    self._log(f"⏭️  Caso {case_num} deshabilitado, omitiendo...")
                    continue
                
                num_samples = config['samples'].get()
                
                self._log(f"\n{'─'*60}")
                self._log(f"📦 CASO {case_num}: {use_case.name}")
                self._log(f"   Generando {num_samples} muestra(s)...")
                self._log(f"{'─'*60}")
                
                for sample_num in range(1, num_samples + 1):
                    try:
                        # Generar EPC y TID únicos
                        epc = f"5201F250{case_num:02d}{sample_num:04d}"
                        tid = f"E2C24500200{case_num:03d}{sample_num:08d}"
                        
                        # Crear simulador
                        simulator = LogSimulator.from_use_case(
                            use_case=use_case,
                            epc=epc,
                            tid=tid,
                            use_real_route=self.use_real_routes.get()
                        )
                        
                        # Generar datos
                        self._log(f"   [{sample_num}/{num_samples}] Generando datos para EPC: {epc}...")
                        data = simulator.generate()
                        
                        # Crear subcarpeta para el caso
                        case_dir = os.path.join(output_dir, f"case_{case_num}_{use_case.name.replace(' ', '_').lower()}")
                        
                        # Crear carpeta específica para esta muestra
                        sample_dir = os.path.join(case_dir, f"sample_{sample_num:03d}_EPC_{epc}")
                        os.makedirs(sample_dir, exist_ok=True)
                        
                        # Guardar JSON
                        json_filename = os.path.join(sample_dir, f"sample_{sample_num:03d}_EPC_{epc}.json")
                        simulator.save_to_file(json_filename)
                        self._log(f"      ✓ JSON guardado: {os.path.basename(json_filename)}")
                        
                        # Generar mapa si está habilitado
                        if self.generate_maps.get():
                            map_filename = os.path.join(sample_dir, f"map_{sample_num:03d}_EPC_{epc}.html")
                            simulator.generate_map(map_filename)
                            self._log(f"      ✓ Mapa guardado: {os.path.basename(map_filename)}")
                        
                        # Generar gráfica si está habilitado
                        if self.generate_plots.get():
                            plot_filename = os.path.join(sample_dir, f"plot_{sample_num:03d}_EPC_{epc}.png")
                            # No mostrar la gráfica, solo guardarla
                            import matplotlib
                            matplotlib.use('Agg')  # Backend sin GUI
                            simulator.plot_results(save_path=plot_filename)
                            self._log(f"      ✓ Gráfica guardada: {os.path.basename(plot_filename)}")
                        
                        total_generated += 1
                        
                    except Exception as e:
                        self._log(f"      ❌ Error en muestra {sample_num}: {str(e)}")
            
            self._log(f"\n{'='*60}")
            self._log(f"✅ GENERACIÓN COMPLETADA EXITOSAMENTE")
            self._log(f"   Total de archivos JSON generados: {total_generated}")
            self._log(f"   Carpeta de salida: {output_dir}")
            self._log(f"{'='*60}\n")
            
            # Recargar archivos generados
            self.root.after(0, self._load_existing_files)
            
            # Mostrar mensaje de éxito
            self.root.after(0, lambda: messagebox.showinfo(
                "Generación completada",
                f"✅ Se generaron {total_generated} simulaciones exitosamente.\n\n"
                f"📁 Revisa los archivos en:\n{output_dir}\n\n"
                f"Usa el panel 'Visor de Resultados' para explorar los archivos generados."
            ))
            
        except Exception as e:
            self._log(f"\n❌ ERROR CRÍTICO: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror(
                "Error",
                f"Ocurrió un error durante la generación:\n{str(e)}"
            ))
        
        finally:
            # Restaurar interfaz
            self.is_generating = False
            self.root.after(0, self._reset_ui)
    
    def _reset_ui(self):
        """Restaura la interfaz después de la generación"""
        self.generate_btn.config(state=tk.NORMAL, text="🚀 GENERAR SIMULACIONES")
        self.progress_bar.stop()
        self.progress_label.config(text="Generación completada")


def main():
    """Función principal para ejecutar la GUI"""
    root = tk.Tk()
    app = SimulatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
