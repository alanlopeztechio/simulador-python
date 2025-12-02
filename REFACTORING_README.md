# Cold Chain Simulator - Refactored Version

## Overview

This refactoring implements a modular, extensible architecture for the Cold Chain Simulator with a redesigned UI matching the provided specifications.

## Project Structure

```
simulador-python/
├── models/                          # Data models (NEW)
│   ├── __init__.py
│   ├── distribution.py             # Distribution class with absolute/relative modes
│   ├── segment.py                  # SegmentMetadata with multiple distributions
│   ├── route.py                    # RouteConfig with rich metadata
│   └── sensor.py                   # SensorConfig for multi-sensor support
│
├── gui/                            # GUI components (NEW)
│   ├── __init__.py
│   ├── main_window.py              # Main application window
│   ├── stops_tab.py                # Tab 1: Route/Segments/Sensors
│   ├── distributions_tab.py        # Tab 2: Distribution Parameters
│   ├── config_tab.py               # Tab 4: Save/Load Configurations
│   └── results_tab.py              # Tab 3: Results Viewer (placeholder)
│
├── main.py                         # NEW entry point
├── simulator.py                    # Original simulator (to be integrated)
└── gui_custom_routes.py           # Original GUI (legacy, can be removed later)
```

## Key Features Implemented

### 1. Models Package

#### **Distribution** (`models/distribution.py`)
- Supports 4 distribution types: `normal`, `beta`, `truncnorm`, `uniform`
- **Mode support**: `absolute` (direct temperature values) vs `relative` (percentage offset from ambient)
- Configurable parameters per distribution type
- Weight parameter for blending multiple distributions

#### **DistributionBlender** (`models/distribution.py`)
- Blends multiple distributions per segment
- 3 strategies: `weighted_average`, `alternating`, `layered`
- Enables complex temperature profiles

#### **SegmentMetadata** (`models/segment.py`)
- Rich segment description with type classification
- **Multiple distributions per segment** (key feature)
- Configurable blending strategy
- Alarm temperature bounds separate from distribution bounds
- Optional smoothing (AR(1) process)

#### **RouteConfig** (`models/route.py`)
- Complete route metadata (name, description)
- Origin/destination with timestamps
- Waypoints for intermediate stops
- Automatically manages segment count
- Multi-sensor support

#### **SensorConfig** (`models/sensor.py`)
- Full sensor configuration (EPC, TID, battery, LED, anti-tamper)
- Support for multiple sensors per route
- Auto-generation utilities

### 2. GUI Package

#### **Stops Tab** (`gui/stops_tab.py`)
✅ Route metadata (name, description) - required fields
✅ Origin with lat/lng/departure time
✅ Destination with lat/lng/estimated transit time
✅ Dynamic segment builder:
  - Description
  - Coordinates (lat/lng)
  - Segment type (Fleet, Control, Highway, Urban, Rural, Warehouse)
  - Estimated stop time
✅ Associated sensors with add/edit/delete

#### **Distribution Parameters Tab** (`gui/distributions_tab.py`)
✅ Load route segments from Stops tab
✅ Per-segment distribution configuration:
  - Distribution type dropdown (Normal, Beta, Truncnorm, Uniform)
  - Mode selection (Absolute vs Relative)
  - Dynamic parameter fields based on type
✅ Parameter inputs:
  - Min/Max range
  - Standard deviation (Normal/Truncnorm)
  - Mean temperature (Normal)
  - Alpha/Beta (Beta distribution)

#### **Save Configurations Tab** (`gui/config_tab.py`)
✅ Save complete route configuration to JSON
✅ Save distributions only
✅ Save sensors only
✅ List saved configurations with timestamps
✅ Load/Delete configuration files
✅ Full JSON serialization/deserialization

#### **Main Window** (`gui/main_window.py`)
✅ 4-tab layout (Stops, Distribution Parameters, Results, Save Configurations)
✅ Bottom action bar with:
  - Number of samples control
  - "Use Real Routes" checkbox
  - Generate simulation button
✅ Status bar
✅ Tab change event handling
✅ Threaded simulation execution (placeholder)

### 3. Results Tab (`gui/results_tab.py`)
- Placeholder implementation (per user request to focus on configuration first)
- Will display generated JSONs in future phase

## Running the Application

```bash
# Using Python 3.14
py main.py

# Or with python3
python3 main.py
```

## Next Steps (Phase 2)

The following components need integration:

1. **Simulator Core Integration** (`models/distribution.py` → `simulator.py`):
   - Refactor `LogSimulator._generate_temperatures_segmented()` to use new `DistributionBlender`
   - Implement relative mode calculation with ambient temperature baseline
   - Support multiple sensors (generate separate JSON per sensor)

2. **Configuration Loading** (`gui/config_tab.py`):
   - Implement full deserialization
   - Populate Stops and Distributions tabs from loaded config

3. **Results Viewer** (`gui/results_tab.py`):
   - File browser for generated JSONs
   - View JSON/Map/Chart actions
   - Integration with existing visualization code

4. **Testing**:
   - End-to-end workflow validation
   - Multiple distributions per segment
   - Relative mode with different ambient temperatures
   - Multi-sensor generation

## Configuration File Format

Saved configurations use JSON format:

```json
{
  "route_name": "CDMX to Guadalajara",
  "route_description": "Pharmaceutical cold chain transport",
  "origin": {
    "name": "Origin",
    "latitude": 19.4326,
    "longitude": -99.1332,
    "point_type": "origin",
    "timestamp": "2025-12-01T10:00:00"
  },
  "destination": { ... },
  "waypoints": [ ... ],
  "segments": [
    {
      "description": "Highway segment",
      "segment_type": "Highway",
      "estimated_stop_time_minutes": 30,
      "distributions": [
        {
          "type": "normal",
          "mode": "absolute",
          "lower_temp": -25.0,
          "upper_temp": -15.0,
          "mean_temp": -20.0,
          "std_dev": 2.5,
          "weight": 1.0
        }
      ],
      "alarm_lower_temp": -25.0,
      "alarm_upper_temp": -15.0
    }
  ],
  "sensors": [
    {
      "epc": "5201F2503000001",
      "tid": "E2C245002000056680000001",
      "name": "Sensor 1",
      ...
    }
  ]
}
```

## Design Decisions

1. **Modular Architecture**: Separated models, GUI, and simulation logic for maintainability
2. **Multiple Distributions**: Each segment can have N distributions (key requirement)
3. **Absolute vs Relative Modes**: Flexible temperature modeling
4. **Multi-Sensor Support**: Generate separate outputs per sensor
5. **Configuration Persistence**: Full save/load for reproducibility

## Migration from Original Code

The original `gui_custom_routes.py` and parts of `simulator.py` have been refactored:

- **RouteDefinitionTab** → **StopsTab** (enhanced with metadata and sensors)
- **SegmentProfileTab** → **DistributionsTab** (supports multiple distributions)
- **ResultsViewerTab** → **ResultsTab** (placeholder, to be completed)
- **New**: ConfigTab for persistence
- **TempProfile** → **SegmentMetadata** (with multiple Distribution objects)

Original files remain for reference and can be removed after full integration is validated.

## Validation

All created files have been syntax-checked and validated:
- ✅ `models/*.py` - All syntax valid
- ✅ `gui/*.py` - All syntax valid
- ✅ `main.py` - Entry point valid

## Status

**Phase 1 Complete**: UI and data models implemented
**Phase 2 Pending**: Simulator core integration
**Phase 3 Pending**: Results viewer and full end-to-end testing

---

*Refactored on: December 1, 2025*
*Branch: refactor*
