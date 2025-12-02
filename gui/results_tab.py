"""
Results Tab - View generated simulation results.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import json
import webbrowser


class ResultsTab(tk.Frame):
    """Tab 3: Results Viewer - Browse and view generated simulation JSONs."""
    
    def __init__(self, parent, output_dir="simulation_outputs"):
        super().__init__(parent)
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        self._build_ui()
        self.refresh()
    
    def _build_ui(self):
        """Build the UI."""
        # Title
        title_frame = tk.Frame(self, pady=10)
        title_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(title_frame, text="Simulation Results", 
                font=("Arial", 14, "bold")).pack(side=tk.LEFT)
        
        tk.Button(title_frame, text="🔄 Refresh", command=self.refresh,
                 bg="#2196F3", fg="white", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(title_frame, text="📂 Open Folder", command=self._open_output_folder,
                 bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=5)
        
        # Files list
        list_frame = tk.LabelFrame(self, text="Generated Files", 
                                   font=("Arial", 10, "bold"), padx=10, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Listbox with scrollbar
        scroll_frame = tk.Frame(list_frame)
        scroll_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(scroll_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.files_listbox = tk.Listbox(scroll_frame, yscrollcommand=scrollbar.set,
                                        font=("Courier", 9), height=20)
        self.files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.files_listbox.yview)
        
        self.files_listbox.bind("<Double-Button-1>", lambda e: self._view_json())
        
        # Action buttons
        action_frame = tk.Frame(list_frame)
        action_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(action_frame, text="📄 View JSON", command=self._view_json,
                 bg="#2196F3", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        tk.Button(action_frame, text="📊 View Stats", command=self._view_stats,
                 bg="#FF9800", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        tk.Button(action_frame, text="🗑️ Delete", command=self._delete_file,
                 bg="#E53935", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        # Info panel
        info_frame = tk.LabelFrame(self, text="File Information", 
                                   font=("Arial", 10, "bold"), padx=10, pady=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.info_text = tk.Text(info_frame, height=8, bg="#f5f5f5", 
                                font=("Courier", 9), wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        # Bind selection change
        self.files_listbox.bind("<<ListboxSelect>>", self._on_file_selected)
    
    def refresh(self):
        """Refresh the list of generated files."""
        self.files_listbox.delete(0, tk.END)
        self.info_text.delete(1.0, tk.END)
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            return
        
        files = [f for f in os.listdir(self.output_dir) if f.endswith('.json')]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(self.output_dir, x)), reverse=True)
        
        if not files:
            self.info_text.insert(1.0, "No simulation files found.\n\nGenerate a simulation to see results here.")
        else:
            for filename in files:
                self.files_listbox.insert(tk.END, filename)
            
            # Auto-select first file
            if files:
                self.files_listbox.selection_set(0)
                self._on_file_selected(None)
    
    def _on_file_selected(self, event):
        """Handle file selection."""
        selection = self.files_listbox.curselection()
        if not selection:
            return
        
        filename = self.files_listbox.get(selection[0])
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract info
            epc = data.get("EPC", "N/A")
            tid = data.get("TID", "N/A")
            num_samples = len(data.get("loggedData", []))
            version = data.get("version", "N/A")
            
            alarms = data.get("alarms", {})
            has_alarms = alarms.get("alarmAny", False)
            temp_alarm = alarms.get("alarmTemperature", False)
            
            config = data.get("configuration", {})
            temp_lower = config.get("temperatureLowerLimit", "N/A")
            temp_upper = config.get("temperatureUpperLimit", "N/A")
            log_interval = config.get("logIntervalInSeconds", "N/A")
            
            # Format info
            info = f"""File: {filename}
Size: {os.path.getsize(filepath) / 1024:.1f} KB
Version: {version}

SENSOR:
  EPC: {epc}
  TID: {tid}

CONFIGURATION:
  Temperature Range: {temp_lower}°C to {temp_upper}°C
  Log Interval: {log_interval}s
  Samples: {num_samples}

ALARMS:
  Status: {"⚠️ ALARM DETECTED" if has_alarms else "✓ No Alarms"}
  Temperature Alarm: {"YES" if temp_alarm else "No"}
"""
            
            if temp_alarm:
                alarm_time = alarms.get("alarmTemperatureTimestamp", "N/A")
                alarm_val = alarms.get("alarmTemperatureValue", "N/A")
                info += f"  First Alarm: {alarm_time}\n"
                info += f"  Alarm Value: {alarm_val}°C\n"
            
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, info)
            
        except Exception as e:
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, f"Error reading file:\n{str(e)}")
    
    def _view_json(self):
        """Open selected JSON file."""
        selection = self.files_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to view.")
            return
        
        filename = self.files_listbox.get(selection[0])
        filepath = os.path.join(self.output_dir, filename)
        
        # Open with default application
        try:
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", filepath])
            else:  # Linux
                subprocess.Popen(["xdg-open", filepath])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file:\n{str(e)}")
    
    def _view_stats(self):
        """Show statistics for selected file."""
        selection = self.files_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file.")
            return
        
        filename = self.files_listbox.get(selection[0])
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logged_data = data.get("loggedData", [])
            temps = [entry["tempInC"] for entry in logged_data if "tempInC" in entry]
            
            if temps:
                import statistics
                stats_text = f"""TEMPERATURE STATISTICS

Samples: {len(temps)}
Mean: {statistics.mean(temps):.2f}°C
Median: {statistics.median(temps):.2f}°C
Std Dev: {statistics.stdev(temps) if len(temps) > 1 else 0:.2f}°C
Min: {min(temps):.2f}°C
Max: {max(temps):.2f}°C

Configuration:
  Lower Limit: {data.get('configuration', {}).get('temperatureLowerLimit', 'N/A')}°C
  Upper Limit: {data.get('configuration', {}).get('temperatureUpperLimit', 'N/A')}°C

Violations:
  Below Lower: {sum(1 for t in temps if t < data.get('configuration', {}).get('temperatureLowerLimit', -999))}
  Above Upper: {sum(1 for t in temps if t > data.get('configuration', {}).get('temperatureUpperLimit', 999))}
"""
                messagebox.showinfo("Temperature Statistics", stats_text)
            else:
                messagebox.showwarning("No Data", "No temperature data found in file.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate statistics:\n{str(e)}")
    
    def _delete_file(self):
        """Delete selected file."""
        selection = self.files_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to delete.")
            return
        
        filename = self.files_listbox.get(selection[0])
        filepath = os.path.join(self.output_dir, filename)
        
        if messagebox.askyesno("Confirm Delete", f"Delete file:\n{filename}?"):
            try:
                os.remove(filepath)
                messagebox.showinfo("Success", "File deleted.")
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file:\n{str(e)}")
    
    def _open_output_folder(self):
        """Open output folder in file explorer."""
        import subprocess
        import platform
        
        output_path = os.path.abspath(self.output_dir)
        
        try:
            if platform.system() == "Windows":
                os.startfile(output_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", output_path])
            else:  # Linux
                subprocess.Popen(["xdg-open", output_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open folder:\n{str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Results Tab Test")
    root.geometry("600x400")
    
    tab = ResultsTab(root)
    tab.pack(fill=tk.BOTH, expand=True)
    
    root.mainloop()
