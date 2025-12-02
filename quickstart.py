"""
Quick Start Guide for the Refactored Cold Chain Simulator

Run this to launch the application with the new UI.
"""

import tkinter as tk
from tkinter import messagebox

def show_instructions():
    """Show quick start instructions."""
    instructions = """
╔══════════════════════════════════════════════════════════════╗
║   COLD CHAIN SIMULATOR - REFACTORED VERSION                 ║
║   Quick Start Guide                                         ║
╚══════════════════════════════════════════════════════════════╝

WORKFLOW:

1️⃣  STOPS TAB
   - Fill in Route Name and Description (required)
   - Configure Origin coordinates and departure time
   - Configure Destination coordinates and transit time
   - Add Segments (at least 1 required):
     • Segment Description
     • Coordinates (intermediate waypoint)
     • Segment Type (Fleet, Highway, Urban, etc.)
     • Estimated Stop Time
   - Add/Edit Sensors (at least 1 auto-created)

2️⃣  DISTRIBUTION PARAMETERS TAB
   - Click "Regenerate Distributions" to load segments from Stops tab
   - For each segment, configure:
     • Distribution Type (Normal, Beta, Truncnorm, Uniform)
     • Mode (Absolute or Relative)
     • Min/Max Range
     • Additional parameters based on distribution type

3️⃣  SAVE CONFIGURATIONS TAB (Optional)
   - Save complete route configuration for reuse
   - Save distributions only
   - Save sensors only
   - Load previously saved configurations

4️⃣  GENERATE SIMULATION
   - Bottom action bar: Set number of samples
   - Check "Use Real Routes (OSM)" if desired
   - Click "🚀 GENERATE SIMULATION"

5️⃣  RESULTS TAB
   - View generated simulation outputs
   - (Full implementation pending Phase 2)

═══════════════════════════════════════════════════════════════

FEATURES IMPLEMENTED:
✅ Route metadata (name, description)
✅ Origin/Destination with timestamps
✅ Dynamic segment management (add/remove)
✅ Multiple distributions per segment
✅ Absolute and Relative distribution modes
✅ Multi-sensor support
✅ Configuration save/load
✅ Modular architecture

PENDING (Phase 2):
⏳ Simulator core integration with new models
⏳ Multi-distribution blending in simulation
⏳ Relative mode temperature calculation
⏳ Multi-sensor JSON generation
⏳ Full results viewer functionality
⏳ Configuration loading (deserialization)

═══════════════════════════════════════════════════════════════

Press OK to launch the application...
"""
    messagebox.showinfo("Quick Start Guide", instructions)

if __name__ == "__main__":
    # Show instructions
    root = tk.Tk()
    root.withdraw()  # Hide main window temporarily
    
    show_instructions()
    
    # Launch main application
    root.destroy()
    
    from gui.main_window import main
    main()
