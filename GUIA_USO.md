# 🎉 Simulador de Cadena de Frío - COMPLETADO

## ✅ Sistema Completamente Funcional

El simulador ha sido completamente refactorizado y ahora genera archivos JSON en el formato RFID original exacto.

## 🚀 Cómo Usar

### Inicio Rápido

```bash
# Opción 1: Con guía interactiva
py quickstart.py

# Opción 2: Inicio directo
py main.py
```

### Flujo de Trabajo Completo

#### 1️⃣ **Tab "Stops"** - Configuración de Ruta

**Campos Requeridos** (marcados con *):
- **Route Name**: Nombre de la ruta (ej: "CDMX a Guadalajara")
- **Route Description**: Descripción del transporte (ej: "Transporte farmacéutico")

**Origin (Origen)**:
- Latitude / Longitude: Coordenadas del punto de inicio
- Departure Time: Hora de salida (formato: YYYY-MM-DD HH:MM)

**Destination (Destino)**:
- Latitude / Longitude: Coordenadas del destino final
- Estimated Transit Time: Tiempo estimado en minutos

**Segments (Segmentos)** - Al menos 1 requerido:
- Click "Add Segment" para agregar tramos
- Para cada segmento configure:
  - **Segment Description**: Descripción del tramo
  - **Latitude/Longitude**: Coordenadas del punto intermedio
  - **Segment Type**: Tipo (Fleet, Highway, Urban, Rural, Warehouse, Control)
  - **Estimated Stop Time**: Tiempo de parada en minutos

**Associated Sensors (Sensores)**:
- Por defecto se crea 1 sensor
- Click "Add Sensor" para agregar más
- Click "Edit" para modificar EPC, TID, y nombre
- Se generará 1 JSON por sensor

#### 2️⃣ **Tab "Distribution Parameters"** - Configuración Térmica

1. Click **"Regenerate Distributions"** para cargar los segmentos del Tab 1

2. Para cada segmento configure:

   **Distribution Type** (Tipo de distribución):
   - Normal: Distribución normal gaussiana
   - Beta: Distribución beta (sesgo controlado)
   - Truncnorm: Normal truncada (valores estrictamente dentro del rango)
   - Uniform: Distribución uniforme

   **Mode of Application** (Modo):
   - **Absolute Mode**: Temperaturas absolutas en °C
   - **Relative Mode**: Temperaturas como % de offset del ambiente (próximamente mejorado)

   **Parameters** (cambian según el tipo):
   - **Minimum Range**: Límite inferior de temperatura
   - **Maximum Range**: Límite superior de temperatura
   - **Standard Deviation**: Desviación estándar (Normal/Truncnorm)
   - **Mean Temperature**: Temperatura media (Normal)
   - **Alpha/Beta**: Parámetros de forma (Beta)

#### 3️⃣ **Tab "Save Configurations"** - Guardar/Cargar (Opcional)

**Guardar**:
- **Save Route Configuration**: Guarda ruta completa + distribuciones + sensores
- **Save Distribution Configuration**: Solo distribuciones
- **Save Sensors Configuration**: Solo sensores

**Cargar**:
- Selecciona una configuración de la lista
- Click "Load" (próximamente implementado completamente)
- Click "Delete" para eliminar

#### 4️⃣ **Generar Simulación**

En la barra inferior:

1. **Samples (JSONs)**: Número de archivos a generar (1-50)
2. **Use Real Routes (OSM)**: ✓ para usar rutas reales de OpenStreetMap
3. Click **"🚀 GENERATE SIMULATION"**

**Proceso**:
- Valida la configuración
- Muestra resumen (ruta, segmentos, sensores, muestras)
- Confirma generación
- Genera archivos JSON en `simulation_outputs/`

**Archivos generados**:
- Formato: `{NombreRuta}_{EPC}_{#muestra}_{timestamp}.json`
- Ejemplo: `Durango_mexico_000001_1_20251201_123045.json`

#### 5️⃣ **Tab "Results"** - Ver Resultados

**Visualizar archivos**:
- Lista automática de JSONs generados (ordenados por fecha)
- Click en archivo para ver información
- Double-click o "📄 View JSON" para abrir el archivo

**Panel de información muestra**:
- EPC, TID del sensor
- Rango de temperatura configurado
- Intervalo de muestreo
- Número de muestras
- Estado de alarmas (⚠️ si hay violaciones)

**Acciones**:
- **📄 View JSON**: Abre el archivo con el visor predeterminado
- **📊 View Stats**: Muestra estadísticas (media, mediana, desv. std, violaciones)
- **🗑️ Delete**: Elimina el archivo
- **📂 Open Folder**: Abre la carpeta de salida
- **🔄 Refresh**: Actualiza la lista

## 📋 Formato del JSON Generado

El archivo JSON sigue el formato RFID tag exacto:

```json
{
  "version": "1.1.0",
  "EPC": "5201F25099990001",
  "TID": "E2C245002009999900000001",
  "inventories": [
    {
      "readerTimestamp": "2025-11-14T16:30:58.000Z",
      "readerHost": "FX96007C1E1",
      "readerMAC": "87:CF:E6:89:47:50",
      "readerLatitude": 19.43,
      "readerLongitude": -99.13,
      ...
    }
  ],
  "configuration": {
    "logIntervalInSeconds": 300,
    "logNumberOfSamples": 71,
    "temperatureLowerLimit": 0.0,
    "temperatureUpperLimit": 10.0,
    ...
  },
  "arming": {
    "armStatus": "SUCCESSFUL",
    "armTimestamp": "2025-11-14T16:30:58Z",
    ...
  },
  "alarms": {
    "alarmAny": true,
    "alarmTemperature": true,
    "alarmTemperatureTimestamp": "2025-11-14T17:25:58.000Z",
    "alarmTemperatureValue": 10.6,
    ...
  },
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

## 🎯 Ejemplos de Uso

### Ejemplo 1: Transporte Farmacéutico

**Configuración**:
- Route: "CDMX a Guadalajara - Vacunas"
- Origin: CDMX (19.4326, -99.1332)
- Destination: Guadalajara (20.6597, -103.3496)
- Segment 1: Highway (Type: Highway, Stop: 30 min)
  - Distribution: Normal, Absolute
  - Range: -25°C to -15°C
  - Mean: -20°C, Std Dev: 2.5°C
- Sensors: 2 (para redundancia)

### Ejemplo 2: Alimentos Perecederos

**Configuración**:
- Route: "Veracruz a CDMX - Mariscos"
- Origin: Veracruz Puerto (19.1738, -96.1342)
- Destination: CDMX Mercado (19.4326, -99.1332)
- Segment 1: Fleet (Type: Fleet, Stop: 15 min)
  - Distribution: Beta, Absolute
  - Range: 0°C to 4°C
  - Alpha: 2.0, Beta: 8.0 (sesgo hacia temperaturas bajas)
- Sensors: 1

### Ejemplo 3: Químicos Industriales

**Configuración**:
- Route: "Monterrey a Querétaro"
- Segments: 2 (cambio de condiciones)
  - Segment 1 (Highway): Normal 10-30°C
  - Segment 2 (Urban): Normal 15-25°C (más controlado)
- Use Real Routes: ✓ (para precisión)

## 📊 Características Implementadas

✅ **Interfaz Completa**:
- 4 tabs funcionales (Stops, Distributions, Results, Save Configurations)
- Validación de campos requeridos
- Gestión dinámica de segmentos y sensores

✅ **Configuración Flexible**:
- Múltiples segmentos por ruta
- Múltiples sensores por ruta
- 4 tipos de distribuciones
- Modo absoluto y relativo

✅ **Generación de JSONs**:
- Formato RFID tag exacto
- Múltiples muestras
- Multi-sensor (1 JSON por sensor)
- Rutas reales con OpenStreetMap (opcional)

✅ **Visualización de Resultados**:
- Explorador de archivos
- Estadísticas de temperatura
- Detección de alarmas
- Visor de información

✅ **Persistencia**:
- Guardar configuraciones completas
- Guardar solo distribuciones
- Guardar solo sensores

## 🔧 Estructura del Proyecto

```
simulador-python/
├── models/              # Modelos de datos
│   ├── distribution.py  # Distribuciones con modo abs/rel
│   ├── segment.py       # Metadatos de segmentos
│   ├── route.py         # Configuración de ruta
│   └── sensor.py        # Configuración de sensores
│
├── gui/                 # Componentes UI
│   ├── stops_tab.py     # Tab 1: Rutas y segmentos
│   ├── distributions_tab.py  # Tab 2: Distribuciones
│   ├── results_tab.py   # Tab 3: Resultados
│   ├── config_tab.py    # Tab 4: Guardar/Cargar
│   └── main_window.py   # Ventana principal
│
├── simulator_adapter.py # Adaptador models → simulator
├── simulator.py         # Simulador original (core)
├── main.py             # Punto de entrada
└── quickstart.py       # Guía rápida
```

## 🚀 Próximas Mejoras (Opcional)

- Blending completo de múltiples distribuciones por segmento
- Modo relativo con temperaturas ambiente por segmento
- Carga completa de configuraciones guardadas
- Visualización de mapas y gráficas integrada
- Exportación a otros formatos (CSV, Excel)

## ✅ Prueba el Sistema

Ya puedes generar simulaciones reales! Ejecuta:

```bash
py main.py
```

Y sigue el flujo:
1. Configura ruta en "Stops"
2. Configura temperaturas en "Distribution Parameters"
3. Click "🚀 GENERATE SIMULATION"
4. Ve resultados en "Results"

¡Disfruta! 🎉
