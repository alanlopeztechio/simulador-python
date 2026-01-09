"""
Companies Tab - Manage transport companies.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.company import Company
from db.database import DatabaseManager


class CompaniesTab(tk.Frame):
    """Tab for managing transport companies."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.db = None
        self.companies = []
        self.selected_company_id = None
        
        # Create UI
        self._create_ui()
        
        # Load companies
        self.load_companies()
    
    def _create_ui(self):
        """Create the UI components."""
        # Main container
        main_container = tk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel - Company list
        left_panel = tk.Frame(main_container)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        tk.Label(left_panel, text="Compañías Registradas", 
                font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        # Companies listbox with scrollbar
        list_frame = tk.Frame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.companies_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                           font=("Arial", 10), height=20)
        self.companies_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.companies_listbox.yview)
        
        self.companies_listbox.bind('<<ListboxSelect>>', self._on_company_select)
        
        # Buttons for company list
        list_buttons = tk.Frame(left_panel)
        list_buttons.pack(fill=tk.X, pady=(5, 0))
        
        tk.Button(list_buttons, text="Nueva Compañía", command=self._new_company,
                 bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=2)
        tk.Button(list_buttons, text="Eliminar", command=self._delete_company,
                 bg="#f44336", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=2)
        tk.Button(list_buttons, text="Refrescar", command=self.load_companies,
                 bg="#2196F3", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=2)
        
        # Right panel - Company details
        right_panel = tk.Frame(main_container, relief=tk.GROOVE, borderwidth=2)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        tk.Label(right_panel, text="Detalles de Compañía", 
                font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # Form frame
        form_frame = tk.Frame(right_panel)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Name
        tk.Label(form_frame, text="Nombre de Compañía:*", 
                font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        tk.Entry(form_frame, textvariable=self.name_var, 
                font=("Arial", 10), width=40).grid(row=0, column=1, sticky=tk.W+tk.E, pady=5)
        
        # Description
        tk.Label(form_frame, text="Descripción:", 
                font=("Arial", 9, "bold")).grid(row=1, column=0, sticky=tk.W+tk.N, pady=5)
        self.description_text = tk.Text(form_frame, height=4, width=40, font=("Arial", 10))
        self.description_text.grid(row=1, column=1, sticky=tk.W+tk.E, pady=5)
        
        # Contact email
        tk.Label(form_frame, text="Email de Contacto:", 
                font=("Arial", 9, "bold")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.email_var = tk.StringVar()
        tk.Entry(form_frame, textvariable=self.email_var, 
                font=("Arial", 10), width=40).grid(row=2, column=1, sticky=tk.W+tk.E, pady=5)
        
        # Contact phone
        tk.Label(form_frame, text="Teléfono de Contacto:", 
                font=("Arial", 9, "bold")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.phone_var = tk.StringVar()
        tk.Entry(form_frame, textvariable=self.phone_var, 
                font=("Arial", 10), width=40).grid(row=3, column=1, sticky=tk.W+tk.E, pady=5)
        
        form_frame.columnconfigure(1, weight=1)
        
        # Action buttons
        button_frame = tk.Frame(right_panel)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(button_frame, text="Guardar Cambios", command=self._save_company,
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                 width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Limpiar Formulario", command=self._clear_form,
                 bg="#FF9800", fg="white", font=("Arial", 10, "bold"),
                 width=15).pack(side=tk.LEFT, padx=5)
    
    def load_companies(self):
        """Load companies from database."""
        try:
            # Connect to database
            if self.db is None:
                self.db = DatabaseManager()
                self.db.connect()
            
            # Get companies
            companies_data = self.db.get_all_companies()
            self.companies = [Company.from_dict(c) for c in companies_data]
            
            # Update listbox
            self.companies_listbox.delete(0, tk.END)
            for company in self.companies:
                self.companies_listbox.insert(tk.END, company.name)
            
            print(f"✓ Cargadas {len(self.companies)} compañías")
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando compañías: {e}")
            print(f"✗ Error: {e}")
    
    def _on_company_select(self, event):
        """Handle company selection."""
        selection = self.companies_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        company = self.companies[index]
        
        # Load company details into form
        self.selected_company_id = company.id
        self.name_var.set(company.name)
        self.description_text.delete('1.0', tk.END)
        self.description_text.insert('1.0', company.description)
        self.email_var.set(company.contact_email)
        self.phone_var.set(company.contact_phone)
    
    def _new_company(self):
        """Prepare form for new company."""
        self._clear_form()
        self.selected_company_id = None
    
    def _clear_form(self):
        """Clear the form."""
        self.name_var.set('')
        self.description_text.delete('1.0', tk.END)
        self.email_var.set('')
        self.phone_var.set('')
        self.selected_company_id = None
    
    def _save_company(self):
        """Save company to database."""
        # Validate
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Validación", "El nombre de la compañía es requerido.")
            return
        
        # Get form data
        company_data = {
            'name': name,
            'description': self.description_text.get('1.0', tk.END).strip(),
            'contact_email': self.email_var.get().strip(),
            'contact_phone': self.phone_var.get().strip()
        }
        
        try:
            if self.selected_company_id:
                # Update existing
                self.db.update_company(self.selected_company_id, company_data)
                messagebox.showinfo("Éxito", "Compañía actualizada correctamente.")
            else:
                # Create new
                company_id = self.db.create_company(company_data)
                self.selected_company_id = company_id
                messagebox.showinfo("Éxito", f"Compañía creada con ID: {company_id}")
            
            # Reload companies
            self.load_companies()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando compañía: {e}")
            print(f"✗ Error: {e}")
    
    def _delete_company(self):
        """Delete selected company."""
        selection = self.companies_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selección", "Por favor selecciona una compañía para eliminar.")
            return
        
        index = selection[0]
        company = self.companies[index]
        
        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirmar Eliminación",
            f"¿Estás seguro de eliminar la compañía '{company.name}'?\n\n"
            "Esto también eliminará todas las rutas asociadas."
        )
        
        if confirm:
            try:
                self.db.delete_company(company.id)
                messagebox.showinfo("Éxito", "Compañía eliminada correctamente.")
                self._clear_form()
                self.load_companies()
            except Exception as e:
                messagebox.showerror("Error", f"Error eliminando compañía: {e}")
    
    def get_selected_company_id(self):
        """Get the currently selected company ID."""
        selection = self.companies_listbox.curselection()
        if selection:
            return self.companies[selection[0]].id
        return None
    
    def get_all_companies(self):
        """Get all companies."""
        return self.companies
    
    def __del__(self):
        """Cleanup database connection."""
        if self.db:
            try:
                self.db.disconnect()
            except:
                pass
