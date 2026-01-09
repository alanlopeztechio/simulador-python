"""
Main GUI window for the Cold Chain Simulator.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.companies_tab import CompaniesTab
from gui.routes_tab import RoutesTab
from gui.simulation_tab import SimulationTab
from gui.distributions_tab import DistributionsTab
from gui.config_tab import ConfigTab
from gui.results_tab import ResultsTab


class SimulatorGUI:
    """Main application window for the Cold Chain Simulator."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("COLD CHAIN SIMULATOR - GESTIÓN DE COMPAÑÍAS Y RUTAS")
        self.root.geometry("1400x900")
        
        # Create main notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        # 1. Companies management
        self.companies_tab = CompaniesTab(self.notebook)
        
        # 2. Routes management (needs companies_tab) - NOW WITH INTEGRATED EDITOR
        self.routes_tab = RoutesTab(self.notebook, self.companies_tab)
        
        # 3. Distributions configuration (needs routes_tab for segment info)
        self.distributions_tab = DistributionsTab(self.notebook, self.routes_tab)
        
        # 4. Simulation configuration (needs companies and routes tabs)
        self.simulation_tab = SimulationTab(self.notebook, self.companies_tab, self.routes_tab)
        
        # 5. Results viewer
        self.results_tab = ResultsTab(self.notebook, output_dir="simulation_outputs")
        
        # 6. Configuration (database settings)
        self.config_tab = ConfigTab(self.notebook, routes_tab=self.routes_tab, distributions_tab=self.distributions_tab)
        
        # Add tabs to notebook
        self.notebook.add(self.companies_tab, text="📋 Compañías")
        self.notebook.add(self.routes_tab, text="🗺️ Rutas")
        self.notebook.add(self.distributions_tab, text="📊 Distribuciones")
        self.notebook.add(self.simulation_tab, text="▶️ Simulación")
        self.notebook.add(self.results_tab, text="📈 Resultados")
        self.notebook.add(self.config_tab, text="⚙️ Configuración")
        
        # Status bar
        self._create_status_bar()
        
        # Bind tab change event
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
    
    def _create_status_bar(self):
        """Create status bar at bottom."""
        self.status_var = tk.StringVar(value="Ready")
        status_bar = tk.Label(self.root, textvariable=self.status_var, 
                             bd=1, relief=tk.SUNKEN, anchor=tk.W,
                             font=("Arial", 9))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _on_tab_changed(self, event):
        """Handle tab change events."""
        current_tab = self.notebook.index(self.notebook.select())
        
        # Update status based on active tab
        tab_names = ["Compañías", "Rutas", "Distribuciones", "Simulación", "Resultados", "Configuración"]
        if current_tab < len(tab_names):
            self.status_var.set(f"Tab activa: {tab_names[current_tab]}")


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
