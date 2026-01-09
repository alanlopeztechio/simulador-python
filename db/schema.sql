-- Schema para almacenar simulaciones de cadena de frío en Neon PostgreSQL
-- Diseñado para ser consumido por Power BI con relaciones claras

-- ============================================================
-- TABLAS DE CONFIGURACIÓN (Compañías y Rutas)
-- ============================================================

-- Tabla de compañías
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);

-- Tabla de rutas guardadas
CREATE TABLE IF NOT EXISTS routes (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    route_name VARCHAR(255) NOT NULL,
    route_description TEXT,
    
    -- Punto de origen
    origin_name VARCHAR(255),
    origin_latitude DECIMAL(10, 6),
    origin_longitude DECIMAL(10, 6),
    origin_departure_time TIME,
    
    -- Punto de destino
    destination_name VARCHAR(255),
    destination_latitude DECIMAL(10, 6),
    destination_longitude DECIMAL(10, 6),
    destination_arrival_time TIME,
    
    -- Waypoints (guardados como JSON)
    waypoints_json TEXT, -- Array de waypoints en formato JSON
    
    -- Segments metadata (guardados como JSON)
    segments_json TEXT, -- Array de segmentos en formato JSON
    
    -- Sensores asociados (guardados como JSON)
    sensors_json TEXT, -- Array de sensores en formato JSON
    
    -- Configuración de simulación
    log_interval_seconds INTEGER DEFAULT 300,
    use_real_routes BOOLEAN DEFAULT FALSE,
    transport_mode VARCHAR(50) DEFAULT 'driving-car',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_route_per_company UNIQUE (company_id, route_name)
);

CREATE INDEX IF NOT EXISTS idx_routes_company ON routes(company_id);
CREATE INDEX IF NOT EXISTS idx_routes_name ON routes(route_name);

-- ============================================================
-- TABLAS DE SIMULACIONES
-- ============================================================

-- Tabla principal de simulaciones
CREATE TABLE IF NOT EXISTS simulations (
    id SERIAL PRIMARY KEY,
    epc VARCHAR(50) NOT NULL,
    tid VARCHAR(50) NOT NULL,
    version VARCHAR(20),
    
    -- Relación con compañía y ruta
    company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    route_id INTEGER REFERENCES routes(id) ON DELETE SET NULL,
    route_name VARCHAR(255), -- Nombre de la ruta en el momento de la simulación
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Configuración de la simulación
    log_interval_seconds INTEGER,
    log_number_of_samples INTEGER,
    temp_lower_limit DECIMAL(10, 2),
    temp_upper_limit DECIMAL(10, 2),
    distribution_type VARCHAR(50),
    
    -- Timestamps de armado
    arm_status VARCHAR(50),
    arm_timestamp TIMESTAMP,
    
    -- Estadísticas generales
    total_samples INTEGER,
    total_violations INTEGER,
    compliance_rate DECIMAL(5, 2),
    duration_hours DECIMAL(10, 2),
    total_distance_km DECIMAL(10, 2),
    
    -- Metadata adicional
    use_real_route BOOLEAN DEFAULT FALSE,
    transport_mode VARCHAR(50),
    
    -- Índices para búsquedas frecuentes
    CONSTRAINT unique_simulation UNIQUE (epc, tid, created_at)
);

CREATE INDEX IF NOT EXISTS idx_simulations_epc ON simulations(epc);
CREATE INDEX IF NOT EXISTS idx_simulations_created_at ON simulations(created_at);
CREATE INDEX IF NOT EXISTS idx_simulations_route_name ON simulations(route_name);


-- Tabla de segmentos (tramos entre waypoints)
CREATE TABLE IF NOT EXISTS segments (
    id SERIAL PRIMARY KEY,
    simulation_id INTEGER REFERENCES simulations(id) ON DELETE CASCADE,
    segment_number INTEGER NOT NULL,
    
    -- Coordenadas del segmento
    from_lat DECIMAL(10, 6),
    from_lng DECIMAL(10, 6),
    to_lat DECIMAL(10, 6),
    to_lng DECIMAL(10, 6),
    
    -- Muestras asignadas al segmento
    sample_start INTEGER,
    sample_end INTEGER,
    sample_count INTEGER,
    
    -- Estadísticas observadas de temperatura
    observed_min DECIMAL(10, 2),
    observed_max DECIMAL(10, 2),
    observed_mean DECIMAL(10, 2),
    observed_std DECIMAL(10, 2),
    
    -- Configuración del segmento
    configured_lower_temp DECIMAL(10, 2),
    configured_upper_temp DECIMAL(10, 2),
    configured_distribution VARCHAR(50),
    
    CONSTRAINT unique_segment UNIQUE (simulation_id, segment_number)
);

CREATE INDEX IF NOT EXISTS idx_segments_simulation ON segments(simulation_id);


-- Tabla de inventarios/paradas
CREATE TABLE IF NOT EXISTS stops (
    id SERIAL PRIMARY KEY,
    simulation_id INTEGER REFERENCES simulations(id) ON DELETE CASCADE,
    stop_number INTEGER NOT NULL,
    
    -- Ubicación
    latitude DECIMAL(10, 6),
    longitude DECIMAL(10, 6),
    location_name VARCHAR(255),
    
    -- Tipo de parada
    stop_type VARCHAR(50), -- 'origin', 'waypoint', 'destination'
    
    -- Contadores de eventos
    arrivals_count INTEGER DEFAULT 0,
    departures_count INTEGER DEFAULT 0,
    
    -- Timestamp del inventario
    inventory_timestamp TIMESTAMP,
    
    CONSTRAINT unique_stop UNIQUE (simulation_id, stop_number)
);

CREATE INDEX IF NOT EXISTS idx_stops_simulation ON stops(simulation_id);
CREATE INDEX IF NOT EXISTS idx_stops_location ON stops(latitude, longitude);


-- Tabla de datos sensorizados (lecturas de temperatura)
CREATE TABLE IF NOT EXISTS sensor_data (
    id BIGSERIAL PRIMARY KEY,
    simulation_id INTEGER REFERENCES simulations(id) ON DELETE CASCADE,
    
    -- Timestamp de la lectura
    timestamp TIMESTAMP NOT NULL,
    
    -- Datos del sensor
    temp_celsius DECIMAL(10, 2) NOT NULL,
    tamper BOOLEAN DEFAULT FALSE,
    temperature_status VARCHAR(50), -- 'Normal', 'Cold Violation', 'Heat Violation'
    
    -- Ubicación GPS
    latitude DECIMAL(10, 6),
    longitude DECIMAL(10, 6),
    location_name VARCHAR(255),
    
    -- Metadata adicional
    sample_index INTEGER,
    
    CONSTRAINT unique_sensor_reading UNIQUE (simulation_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_sensor_simulation ON sensor_data(simulation_id);
CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_sensor_tamper ON sensor_data(tamper);
CREATE INDEX IF NOT EXISTS idx_sensor_location ON sensor_data(latitude, longitude);


-- Comments in the tables for clarity
COMMENT ON TABLE simulations IS 'Main table that stores metadata for each cold chain simulation';
COMMENT ON TABLE segments IS 'Individual segments of each route with temperature statistics per segment';
COMMENT ON TABLE stops IS 'Stops and inventory points along the route';
COMMENT ON TABLE sensor_data IS 'Individual temperature readings with timestamp and GPS location';
