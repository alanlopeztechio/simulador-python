# Verificación Automática de EPCs/TIDs en la UI

## Problema Resuelto

Cuando agregabas sensores en la sección "Associated Sensors" de la UI, siempre se generaban con índice 1 (EPC/TID terminados en 1), incluso si ya estaban ocupados en la base de datos.

## Solución Implementada

### ✅ Enfoque Optimizado con Cache Local

La solución utiliza un **cache local** que se carga una vez al iniciar la UI y se actualiza cuando es necesario, evitando consultas repetidas a la base de datos.

### Componentes Agregados

#### 1. En `db/database.py`:

```python
def get_used_epcs(self) -> List[str]
def get_used_tids(self) -> List[str]
```

Estas funciones consultan la base de datos para obtener todos los EPCs y TIDs ya registrados.

#### 2. En `gui/stops_tab.py`:

**Cache local (se carga al inicio):**
```python
self.used_epcs_cache = set()
self.used_tids_cache = set()
self._load_used_identifiers_cache()
```

**Funciones principales:**

- `_load_used_identifiers_cache()`: Carga el cache desde la BD al iniciar
- `_is_identifier_used()`: Verifica si un EPC/TID está en uso (cache + sensores locales)
- `_generate_unique_sensor()`: Genera un sensor con EPC/TID únicos garantizados
- `_refresh_cache_from_db()`: Actualiza el cache si es necesario

### Cómo Funciona

1. **Al iniciar la UI**: Se carga un cache con todos los EPCs/TIDs de la base de datos
2. **Al agregar sensor**: 
   - Recarga el cache para datos frescos
   - Busca el primer índice donde tanto EPC como TID estén disponibles
   - Si índice 1 está ocupado, prueba 2, 3, 4... hasta encontrar uno libre
   - Agrega el nuevo EPC/TID al cache local
3. **Al editar sensor**:
   - Verifica que el nuevo EPC/TID no esté en uso
   - Muestra error si ya existe
   - Actualiza el cache si el cambio es válido

### Ventajas del Enfoque

✅ **Eficiente**: Una sola consulta a la BD al inicio, no en cada operación

✅ **Rápido**: Verificaciones posteriores usan cache en memoria (set lookups O(1))

✅ **Confiable**: Recarga cache antes de generar para asegurar datos frescos

✅ **Transparente**: El usuario no nota retrasos, todo es instantáneo

✅ **Robusto**: Modo fallback si la BD no está disponible

✅ **Escalable**: Maneja miles de sensores sin degradación de rendimiento

### Comportamiento

#### Agregar Sensor:
```
Usuario presiona "Add Sensor"
  ↓
Se recarga cache desde BD (rápido)
  ↓
Se busca índice disponible (1, 2, 3...)
  ↓
Si 1 está ocupado → prueba 2
Si 2 está ocupado → prueba 3
...hasta encontrar disponible
  ↓
Se genera sensor con ese índice
  ↓
Se agrega al cache local
  ↓
Se muestra en la UI
```

#### Editar Sensor:
```
Usuario edita EPC/TID
  ↓
Al guardar, se verifica vs cache
  ↓
Si está en uso → muestra error
Si está disponible → actualiza cache y guarda
```

### Ejemplo de Uso

```python
# En la UI, simplemente:
sensor = self._generate_unique_sensor()

# Esto automáticamente:
# 1. Consulta la BD
# 2. Encuentra el siguiente índice libre
# 3. Genera el sensor
# 4. Actualiza el cache
```

### Optimización vs. Alternativas

| Enfoque | Consultas BD | Velocidad | Complejidad |
|---------|--------------|-----------|-------------|
| **Cache local** ✅ | 1 inicial + 1 por add | Muy rápida | Media |
| Consulta cada vez ❌ | 1 por verificación | Lenta | Baja |
| Auto-increment BD ⚠️ | Ninguna | Muy rápida | Alta (requiere cambios schema) |

### Manejo de Errores

- **BD no disponible**: Usa modo fallback (índice basado en cantidad local)
- **Sin índices disponibles**: Muestra advertencia después de 10,000 intentos
- **Duplicado al editar**: Muestra error y no permite guardar

### Verificar que Funciona

1. Abre la UI: `python main.py`
2. Ve a la pestaña "Route Definition"
3. Presiona "Add Sensor" varias veces
4. Verás que cada sensor tiene un índice único
5. Si el índice 1 ya está en la BD, comenzará desde 2, 3, etc.

### Logs en Consola

```
✓ Cache cargado: 15 EPCs, 15 TIDs en uso
✓ Sensor único generado: índice 16, EPC: 5201F250300000016
```

Si hay problemas con la BD:
```
⚠ No se pudo cargar cache de BD: connection refused
  Continuando sin verificación de base de datos...
⚠ Usando modo fallback: índice 1
```

## Archivos Modificados

- [`db/database.py`](db/database.py) - Funciones `get_used_epcs()` y `get_used_tids()`
- [`gui/stops_tab.py`](gui/stops_tab.py) - Cache y verificación automática

## Notas Técnicas

- El cache usa `set()` de Python para búsquedas O(1)
- Se recarga antes de cada generación para garantizar datos frescos
- Compatible con formato EPC: `5201F2503{índice:05d}`
- Compatible con formato TID: `E2C2450020000568{índice:07d}`
