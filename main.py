"""
Cold Chain Simulator - Refactored Version
Main entry point for the application.
"""

import tkinter as tk
from gui.main_window import SimulatorGUI

if __name__ == "__main__":
    root = tk.Tk()
    app = SimulatorGUI(root)
    root.mainloop()
