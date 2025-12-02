# 🚚 Cold Chain Simulator - RFID Tag Data Generator

> Sistema avanzado de simulación para monitoreo de cadena de frío con tags RFID

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Production_Ready-green.svg)]()
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)]()

## 📋 Descripción

Simulador de cadena de frío que genera archivos JSON completos en formato RFID tag para monitoreo de temperatura durante transporte de productos sensibles (farmacéuticos, alimentos, químicos).

### Características Principales

✅ **Interfaz Gráfica Intuitiva** - 4 tabs para configuración completa  
✅ **Configuración Flexible** - Múltiples segmentos, sensores y distribuciones  
✅ **Generación de JSONs** - Formato RFID tag con inventarios, configuración, alarmas y datos  
✅ **Rutas Reales** - Integración con OpenStreetMap (opcional)  
✅ **Multi-Sensor** - Genera archivos separados por sensor  
✅ **Persistencia** - Guarda y carga configuraciones  

## 🚀 Inicio Rápido

### Requisitos

- Python 3.10+
- Dependencias: tkinter, numpy, scipy, geopy, folium, matplotlib, requests

### Instalación

```bash
# Clonar repositorio
git clone https://github.com/alanlopeztechio/simulador-python.git
cd simulador-python

# Instalar dependencias (si es necesario)
pip install numpy scipy geopy folium matplotlib requests
```

### Ejecución

```bash
# Con guía interactiva
py quickstart.py

# Inicio directo
py main.py
```

## 📖 Uso

### Flujo de Trabajo

1. **Stops Tab** → Configure ruta, origen, destino, segmentos y sensores
2. **Distribution Parameters Tab** → Configure distribuciones de temperatura por segmento
3. **Generate** → Click en "🚀 GENERATE SIMULATION"
4. **Results Tab** → Visualice y analice los JSONs generados

Ver [GUIA_USO.md](GUIA_USO.md) para instrucciones detalladas.

## 📁 Estructura del Proyecto

```
simulador-python/
├── models/              # Modelos de datos
├── gui/                 # Componentes UI
├── simulator.py         # Motor de simulación
├── simulator_adapter.py # Adaptador models ↔ simulator
├── main.py             # Punto de entrada
└── simulation_outputs/ # JSONs generados
```

## 🎯 Casos de Uso

### Transporte Farmacéutico
- Vacunas: -25°C a -15°C
- Medicamentos: 2°C a 8°C
- Distribución: Normal con baja desviación

### Alimentos Perecederos
- Mariscos: 0°C a 4°C
- Lácteos: 2°C a 6°C
- Distribución: Beta con sesgo hacia temperaturas bajas

### Químicos Industriales
- Reactivos: 10°C a 30°C
- Distribución: Normal con mayor variación

## 📊 Formato de Salida

Genera archivos JSON en formato RFID tag:

```json
{
  "version": "1.1.0",
  "EPC": "5201F25099990001",
  "TID": "E2C245002009999900000001",
  "inventories": [...],
  "configuration": {...},
  "arming": {...},
  "alarms": {...},
  "loggedData": [
    {
      "timestamp": "2025-11-14T16:30:58Z",
      "tempInC": 3.4,
      "tamper": false
    },
    ...
  ]
}
```

## 🛠️ Tecnologías

- **Python 3.14** - Lenguaje principal
- **Tkinter** - Interfaz gráfica
- **NumPy/SciPy** - Generación de distribuciones estadísticas
- **Geopy** - Cálculos geográficos
- **Folium** - Mapas interactivos
- **Matplotlib** - Visualización de datos
- **OpenRouteService** - Rutas reales (opcional)

## 📚 Documentación

- [GUIA_USO.md](GUIA_USO.md) - Manual de usuario completo
- [REFACTORING_README.md](REFACTORING_README.md) - Documentación técnica
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Resumen de implementación

## 🏗️ Arquitectura

**Modular y Extensible**:
- `models/` - Clases de datos (Distribution, SegmentMetadata, RouteConfig, SensorConfig)
- `gui/` - Componentes de interfaz (Stops, Distributions, Config, Results)
- `simulator_adapter.py` - Puente entre modelos nuevos y simulador existente

## ✨ Características Avanzadas

### Distribuciones de Temperatura
- **Normal** - Distribución gaussiana estándar
- **Beta** - Control de sesgo (hacia límites superior/inferior)
- **Truncnorm** - Normal estrictamente dentro de límites
- **Uniform** - Distribución uniforme

### Modos de Aplicación
- **Absolute** - Temperaturas absolutas en °C
- **Relative** - Porcentaje de offset desde temperatura ambiente

### Multi-Sensor
- Configure múltiples sensores por ruta
- Genera 1 JSON por sensor
- Cada sensor con EPC/TID único

## 🎨 Capturas

_(Agregar screenshots de la interfaz)_

## 🤝 Contribuciones

Este es un proyecto en desarrollo activo. Sugerencias y mejoras son bienvenidas.

## 📝 Licencia

MIT License - Ver LICENSE para detalles

## 👥 Autores

- Alan López (@alanlopeztechio) - Desarrollo y refactoring

## 🔄 Historial de Versiones

### v2.0.0 (Diciembre 2025) - Refactoring Completo ✅
- ✅ Arquitectura modular (models + gui packages)
- ✅ Múltiples distribuciones por segmento
- ✅ Modo absoluto y relativo
- ✅ Multi-sensor support
- ✅ Interfaz rediseñada (4 tabs)
- ✅ Generación de JSONs en formato RFID completo
- ✅ Visualizador de resultados con estadísticas

### v1.0.0 - Versión Original
- Simulador básico con interfaz
- Una distribución por segmento
- Generación de JSONs básicos

---

**Simulador de Cadena de Frío** - Generación avanzada de datos RFID para monitoreo de temperatura 🌡️
