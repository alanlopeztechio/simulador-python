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
    origin_departure_date DATE,  -- Solo fecha (día/mes/año)
    
    -- Punto de destino
    destination_name VARCHAR(255),
    destination_latitude DECIMAL(10, 6),
    destination_longitude DECIMAL(10, 6),
    destination_arrival_date DATE,  -- Solo fecha (día/mes/año)
    
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
    
    -- Relación con ruta (la compañía se obtiene a través de la ruta)
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


-- ============================================================
-- VISTA ÚNICA CONSOLIDADA PARA POWER BI
-- ============================================================

-- Vista única con TODA la información de la base de datos
-- NOTA: Esta vista tiene UNA FILA POR CADA LECTURA DE SENSOR
-- Incluye información completa de simulación, ruta, compañía, sensor, segmento y parada
CREATE OR REPLACE VIEW vw_powerbi_master AS
SELECT 
    -- ========== DATOS DE SENSOR (NIVEL DE DETALLE) ==========
    sd.id as sensor_reading_id,
    sd.timestamp as reading_timestamp,
    sd.temp_celsius,
    sd.tamper,
    sd.temperature_status,
    sd.latitude as sensor_latitude,
    sd.longitude as sensor_longitude,
    sd.location_name as sensor_location_name,
    sd.sample_index,
    
    -- ========== SIMULACIÓN ==========
    s.id as simulation_id,
    s.epc,
    s.tid,
    s.version,
    s.created_at as simulation_date,
    s.arm_status,
    s.arm_timestamp,
    
    -- Configuración de simulación
    s.log_interval_seconds,
    s.log_number_of_samples,
    s.temp_lower_limit,
    s.temp_upper_limit,
    s.distribution_type,
    s.use_real_route,
    s.transport_mode,
    
    -- Estadísticas de simulación
    s.total_samples,
    s.total_violations,
    s.compliance_rate,
    s.duration_hours,
    s.total_distance_km,
    
    -- ========== COMPAÑÍA ==========
    c.id as company_id,
    c.name as company_name,
    c.description as company_description,
    c.contact_email as company_email,
    c.contact_phone as company_phone,
    c.created_at as company_created_at,
    
    -- ========== RUTA ==========
    r.id as route_id,
    s.route_name,
    r.route_description,
    r.origin_name,
    r.origin_latitude,
    r.origin_longitude,
    r.origin_departure_date,
    r.destination_name,
    r.destination_latitude,
    r.destination_longitude,
    r.destination_arrival_date,
    r.transport_mode as route_transport_mode,
    r.use_real_routes as route_use_real_routes,
    r.log_interval_seconds as route_log_interval,
    r.created_at as route_created_at,
    
    -- ========== ANÁLISIS DE TEMPERATURA ==========
    CASE 
        WHEN sd.temp_celsius < s.temp_lower_limit THEN 'Violación Frío'
        WHEN sd.temp_celsius > s.temp_upper_limit THEN 'Violación Calor'
        ELSE 'Normal'
    END as temp_analysis,
    
    sd.temp_celsius - s.temp_lower_limit as deviation_from_lower,
    s.temp_upper_limit - sd.temp_celsius as deviation_from_upper,
    
    -- ========== CAMPOS CALCULADOS ==========
    CASE 
        WHEN s.compliance_rate >= 95 THEN 'Excelente'
        WHEN s.compliance_rate >= 85 THEN 'Bueno'
        WHEN s.compliance_rate >= 70 THEN 'Regular'
        ELSE 'Deficiente'
    END as compliance_category,
    
    CASE 
        WHEN s.total_violations = 0 THEN 'Sin Violaciones'
        WHEN s.total_violations <= 5 THEN 'Pocas Violaciones'
        WHEN s.total_violations <= 20 THEN 'Violaciones Moderadas'
        ELSE 'Muchas Violaciones'
    END as violation_level,
    
    -- ========== DIMENSIONES TEMPORALES (SIMULACIÓN) ==========
    EXTRACT(YEAR FROM s.created_at) as sim_year,
    EXTRACT(MONTH FROM s.created_at) as sim_month,
    EXTRACT(DAY FROM s.created_at) as sim_day,
    EXTRACT(QUARTER FROM s.created_at) as sim_quarter,
    TO_CHAR(s.created_at, 'YYYY-MM') as sim_year_month,
    TO_CHAR(s.created_at, 'YYYY-MM-DD') as sim_date,
    
    -- ========== DIMENSIONES TEMPORALES (LECTURA SENSOR) ==========
    EXTRACT(YEAR FROM sd.timestamp) as reading_year,
    EXTRACT(MONTH FROM sd.timestamp) as reading_month,
    EXTRACT(DAY FROM sd.timestamp) as reading_day,
    EXTRACT(HOUR FROM sd.timestamp) as reading_hour,
    EXTRACT(MINUTE FROM sd.timestamp) as reading_minute,
    EXTRACT(QUARTER FROM sd.timestamp) as reading_quarter,
    EXTRACT(DOW FROM sd.timestamp) as reading_day_of_week_number,
    EXTRACT(WEEK FROM sd.timestamp) as reading_week_number,
    TO_CHAR(sd.timestamp, 'YYYY-MM-DD') as reading_date,
    TO_CHAR(sd.timestamp, 'HH24:MI:SS') as reading_time,
    TO_CHAR(sd.timestamp, 'Day') as reading_day_of_week,
    TO_CHAR(sd.timestamp, 'Month') as reading_month_name
    
FROM sensor_data sd
INNER JOIN simulations s ON sd.simulation_id = s.id
LEFT JOIN routes r ON s.route_id = r.id
LEFT JOIN companies c ON r.company_id = c.id;

COMMENT ON VIEW vw_powerbi_master IS 'Vista única consolidada con TODOS los datos: cada fila es una lectura de sensor con información completa de simulación, ruta y compañía. Contiene todas las coordenadas GPS de cada punto';
