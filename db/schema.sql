-- Schema para almacenar simulaciones de cadena de frío en Neon PostgreSQL
-- Diseñado para ser consumido por Power BI con relaciones claras

-- Tabla principal de simulaciones
CREATE TABLE IF NOT EXISTS simulations (
    id SERIAL PRIMARY KEY,
    epc VARCHAR(50) NOT NULL,
    tid VARCHAR(50) NOT NULL,
    version VARCHAR(20),
    route_name VARCHAR(255),
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

CREATE INDEX idx_simulations_epc ON simulations(epc);
CREATE INDEX idx_simulations_created_at ON simulations(created_at);
CREATE INDEX idx_simulations_route_name ON simulations(route_name);


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

CREATE INDEX idx_segments_simulation ON segments(simulation_id);


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

CREATE INDEX idx_stops_simulation ON stops(simulation_id);
CREATE INDEX idx_stops_location ON stops(latitude, longitude);


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

CREATE INDEX idx_sensor_simulation ON sensor_data(simulation_id);
CREATE INDEX idx_sensor_timestamp ON sensor_data(timestamp);
CREATE INDEX idx_sensor_tamper ON sensor_data(tamper);
CREATE INDEX idx_sensor_location ON sensor_data(latitude, longitude);


-- Vista para Power BI: Simulaciones con estadísticas completas
CREATE OR REPLACE VIEW vw_simulations_summary AS
SELECT 
    s.id,
    s.epc,
    s.tid,
    s.route_name,
    s.created_at,
    s.log_interval_seconds,
    s.temp_lower_limit,
    s.temp_upper_limit,
    s.distribution_type,
    s.total_samples,
    s.total_violations,
    s.compliance_rate,
    s.duration_hours,
    s.total_distance_km,
    s.transport_mode,
    s.arm_status,
    s.arm_timestamp,
    COUNT(DISTINCT seg.id) as segment_count,
    COUNT(DISTINCT st.id) as stop_count,
    COUNT(DISTINCT sd.id) as sensor_reading_count
FROM simulations s
LEFT JOIN segments seg ON s.id = seg.simulation_id
LEFT JOIN stops st ON s.id = st.simulation_id
LEFT JOIN sensor_data sd ON s.id = sd.simulation_id
GROUP BY s.id;


-- Vista para Power BI: Violaciones de temperatura por simulación
CREATE OR REPLACE VIEW vw_temperature_violations AS
SELECT 
    sd.simulation_id,
    s.epc,
    s.tid,
    s.route_name,
    sd.timestamp,
    sd.temp_celsius,
    sd.latitude,
    sd.longitude,
    sd.location_name,
    s.temp_lower_limit,
    s.temp_upper_limit,
    CASE 
        WHEN sd.temp_celsius < s.temp_lower_limit THEN 'Below Limit'
        WHEN sd.temp_celsius > s.temp_upper_limit THEN 'Above Limit'
        ELSE 'Normal'
    END as violation_type
FROM sensor_data sd
JOIN simulations s ON sd.simulation_id = s.id
WHERE sd.tamper = TRUE;


-- Vista para Power BI: Estadísticas por segmento
CREATE OR REPLACE VIEW vw_segment_analytics AS
SELECT 
    seg.id,
    seg.simulation_id,
    s.route_name,
    seg.segment_number,
    seg.from_lat,
    seg.from_lng,
    seg.to_lat,
    seg.to_lng,
    seg.sample_count,
    seg.observed_min,
    seg.observed_max,
    seg.observed_mean,
    seg.observed_std,
    seg.configured_lower_temp,
    seg.configured_upper_temp,
    -- Calcular distancia aproximada del segmento (en km usando fórmula haversine simplificada)
    111.32 * SQRT(
        POWER(seg.to_lat - seg.from_lat, 2) + 
        POWER((seg.to_lng - seg.from_lng) * COS(RADIANS((seg.from_lat + seg.to_lat) / 2)), 2)
    ) as segment_distance_km,
    -- Indicador de compliance del segmento
    CASE 
        WHEN seg.observed_min < seg.configured_lower_temp OR seg.observed_max > seg.configured_upper_temp 
        THEN FALSE 
        ELSE TRUE 
    END as segment_compliant
FROM segments seg
JOIN simulations s ON seg.simulation_id = s.id;


-- Vista para Power BI: Timeline de eventos por parada
CREATE OR REPLACE VIEW vw_stop_timeline AS
SELECT 
    st.id,
    st.simulation_id,
    s.route_name,
    st.stop_number,
    st.latitude,
    st.longitude,
    st.location_name,
    st.stop_type,
    st.arrivals_count,
    st.departures_count,
    st.inventory_timestamp,
    s.created_at as simulation_start
FROM stops st
JOIN simulations s ON st.simulation_id = s.id
ORDER BY st.simulation_id, st.stop_number;


-- Vista para Power BI: Datos de sensores con contexto completo
CREATE OR REPLACE VIEW vw_sensor_data_enriched AS
SELECT 
    sd.id,
    sd.simulation_id,
    s.epc,
    s.tid,
    s.route_name,
    sd.timestamp,
    sd.temp_celsius,
    sd.tamper,
    sd.temperature_status,
    sd.latitude,
    sd.longitude,
    sd.location_name,
    sd.sample_index,
    s.temp_lower_limit,
    s.temp_upper_limit,
    s.distribution_type,
    -- Calcular diferencia con límites
    sd.temp_celsius - s.temp_lower_limit as temp_above_lower_limit,
    s.temp_upper_limit - sd.temp_celsius as temp_below_upper_limit
FROM sensor_data sd
JOIN simulations s ON sd.simulation_id = s.id;



-- Comments in the tables and views for clarity
COMMENT ON TABLE simulations IS 'Main table that stores metadata for each cold chain simulation';
COMMENT ON TABLE segments IS 'Individual segments of each route with temperature statistics per segment';
COMMENT ON TABLE stops IS 'Stops and inventory points along the route';
COMMENT ON TABLE sensor_data IS 'Individual temperature readings with timestamp and GPS location';

COMMENT ON VIEW vw_simulations_summary IS 'Summary view of simulations for Power BI dashboards';
COMMENT ON VIEW vw_temperature_violations IS 'View of all detected temperature violations';
COMMENT ON VIEW vw_segment_analytics IS 'Detailed per-segment analysis with compliance metrics';
COMMENT ON VIEW vw_stop_timeline IS 'Timeline of events at each stop';
COMMENT ON VIEW vw_sensor_data_enriched IS 'Sensor data enriched with simulation context';
