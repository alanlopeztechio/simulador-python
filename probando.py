import tkinter as tk
from tkinter import ttk
import requests
import threading
from typing import List, Dict
import itertools


class BookSearchApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Gutendex Book Search")
        self.setup_window()

        # Variables de estado
        self.search_timer = None
        self.selected_book_data = {}
        self.loading = False
        self.spinner_cycle = itertools.cycle(["|", "/", "-", "\\"])  # animación simple

        # --- UI ---
        main_frame = tk.Frame(root, padx=20, pady=20, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True)

        lbl_title = tk.Label(main_frame, text="Buscador de Libros (Gutendex)",
                             font=("Segoe UI", 16, "bold"), bg='#f0f0f0', fg='#333')
        lbl_title.pack(pady=(0, 20))

        lbl_search = tk.Label(main_frame, text="Escribe el título o autor:", bg='#f0f0f0')
        lbl_search.pack(anchor="w")

        # === FILA COMBOBOX + BOTÓN ===
        row_frame = tk.Frame(main_frame, bg="#f0f0f0")
        row_frame.pack(fill="x", pady=5)

        self.combo_var = tk.StringVar()
        self.search_box = ttk.Combobox(row_frame, textvariable=self.combo_var, width=40)
        self.search_box.pack(side="left", padx=(0, 10), ipady=3)

        self.search_button = ttk.Button(row_frame, text="Buscar", command=self.search_button_clicked)
        self.search_button.pack(side="left")

        # Bind: autocompletado
        # self.search_box.bind('<KeyRelease>', self.on_key_release)
        self.search_box.bind('<<ComboboxSelected>>', self.on_select)

        # Spinner (animación de carga)
        self.status_label = tk.Label(main_frame, text="Listo para buscar", fg="grey",
                                     bg='#f0f0f0', font=("Consolas", 9))
        self.status_label.pack(pady=5)

        # Detalles
        self.result_text = tk.Text(main_frame, height=10, width=60, state='disabled',
                                   bg='white', relief='flat', font=("Consolas", 10))
        self.result_text.pack(pady=20)

    # -------------------------------------------------------------------
    # CONFIGURACIÓN DE LA VENTANA
    # -------------------------------------------------------------------
    def setup_window(self):
        width, height = 500, 450
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.configure(bg='#f0f0f0')

    # -------------------------------------------------------------------
    # SPINNER (ANIMACIÓN)
    # -------------------------------------------------------------------
    def start_spinner(self):
        self.loading = True
        self.animate_spinner()

    def stop_spinner(self):
        self.loading = False
        self.status_label.config(text="Listo", fg="grey")

    def animate_spinner(self):
        if self.loading:
            frame = next(self.spinner_cycle)
            self.status_label.config(text=f"Buscando... {frame}", fg="blue")
            self.root.after(120, self.animate_spinner)

    # -------------------------------------------------------------------
    # AUTOCOMPLETE (cuando escribe)
    # -------------------------------------------------------------------
    def on_key_release(self, event):
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return'):
            return

        query = self.combo_var.get()

        if len(query) < 3:
            return

        if self.search_timer:
            self.root.after_cancel(self.search_timer)

        self.search_timer = self.root.after(600, lambda: self.start_search_thread(query))

    # -------------------------------------------------------------------
    # BOTÓN BUSCAR
    # -------------------------------------------------------------------
    def search_button_clicked(self):
        query = self.combo_var.get().strip()
        if query:
            self.start_search_thread(query)

    # -------------------------------------------------------------------
    # HILO PARA BUSCAR
    # -------------------------------------------------------------------
    def start_search_thread(self, query):
        self.start_spinner()
        threading.Thread(target=self.fetch_books, args=(query,), daemon=True).start()

    # -------------------------------------------------------------------
    # CONSULTA A LA API
    # -------------------------------------------------------------------
    def fetch_books(self, query):
        try:
            url = f"https://gutendex.com/books/?search={query}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            results = data.get('results', [])
            self.book_map = {}
            display_values = []

            for book in results[:10]:
                title = book.get('title', 'Sin título')
                authors = ", ".join([a['name'] for a in book.get('authors', [])])
                display_str = f"{title} | {authors}"

                self.book_map[display_str] = book
                display_values.append(display_str)

            self.root.after(0, lambda: self.update_combo_values(display_values))

        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(text="❌ Error de conexión", fg="red"))

        finally:
            self.root.after(0, self.stop_spinner)

    # -------------------------------------------------------------------
    # ACTUALIZAR COMBOBOX
    # -------------------------------------------------------------------
    def update_combo_values(self, values: List[str]):
        if not values:
            self.status_label.config(text="No se encontraron resultados", fg="orange")
        else:
            self.search_box['values'] = values
            self.search_box.event_generate('<Down>')
            self.status_label.config(text="Resultados listos", fg="green")

    # -------------------------------------------------------------------
    # SELECCIÓN DE RESULTADO
    # -------------------------------------------------------------------
    def on_select(self, event):
        selected_text = self.search_box.get()
        book = self.book_map.get(selected_text)

        if book:
            self.display_book_details(book)

    # -------------------------------------------------------------------
    # MOSTRAR DETALLES DEL LIBRO
    # -------------------------------------------------------------------
    def display_book_details(self, book: Dict):
        self.result_text.config(state='normal')
        self.result_text.delete(1.0, tk.END)

        info = f"""
TÍTULO: {book.get('title')}
AUTORES: {", ".join([a['name'] for a in book.get('authors', [])])}
IDIOMAS: {", ".join(book.get('languages', []))}
DESCARGAS: {book.get('download_count')}

LICENCIA: {book.get('copyright', 'Desconocido')}
        """
        self.result_text.insert(tk.END, info)
        self.result_text.config(state='disabled')


# --- MAIN ---
if __name__ == "__main__":
    root = tk.Tk()
    app = BookSearchApp(root)
    root.mainloop()
