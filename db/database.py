"""
Database Manager for Neon PostgreSQL
Handles connection and data persistence for cold chain simulations
"""

import os
import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv
import json

# Cargar variables de entorno
load_dotenv()


class DatabaseManager:
    """Manager para operaciones con PostgreSQL/Neon"""
    
    def __init__(self, connection_string: str = None):
        """
        Inicializa el manager de base de datos
        
        Args:
            connection_string: String de conexión a PostgreSQL/Neon
                             Si no se proporciona, se lee de la variable de entorno DATABASE_URL
        """
        self.connection_string = connection_string or os.getenv('DATABASE_URL')
        if not self.connection_string:
            raise ValueError(
                "No se proporcionó connection string. "
                "Configura la variable de entorno DATABASE_URL o pasa connection_string al constructor."
            )
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Establece conexión con la base de datos"""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            print("✓ Conexión exitosa a Neon PostgreSQL")
        except Exception as e:
            print(f"✗ Error conectando a la base de datos: {e}")
            raise
    
    def disconnect(self):
        """Cierra la conexión con la base de datos"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("✓ Conexión cerrada")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.disconnect()
    
    def initialize_schema(self, schema_file: str = None):
        """
        Inicializa el esquema de base de datos ejecutando el archivo SQL
        
        Args:
            schema_file: Ruta al archivo schema.sql. Por defecto usa db/schema.sql
        """
        if schema_file is None:
            schema_file = os.path.join(os.path.dirname(__file__), 'schema.sql')
        
        try:
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            self.cursor.execute(schema_sql)
            self.conn.commit()
            print("✓ Esquema de base de datos inicializado correctamente")
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error inicializando esquema: {e}")
            raise
    
    def insert_simulation(self, simulation_data: Dict[str, Any]) -> int:
        """
        Inserta una simulación completa en la base de datos
        
        Args:
            simulation_data: Diccionario con los datos de la simulación (formato JSON del simulador)
        
        Returns:
            ID de la simulación insertada
        """
        try:
            # Extraer datos principales
            epc = simulation_data.get('EPC')
            tid = simulation_data.get('TID')
            version = simulation_data.get('version', '1.0.0')
            config = simulation_data.get('configuration', {})
            arming = simulation_data.get('arming', {})
            alarms = simulation_data.get('alarms', {})
            logged_data = simulation_data.get('loggedData', [])
            
            # Calcular estadísticas
            total_samples = len(logged_data)
            violations = sum(1 for entry in logged_data if entry.get('tamper', False))
            compliance_rate = ((total_samples - violations) / total_samples * 100) if total_samples > 0 else 100.0
            
            # Calcular duración
            if logged_data and len(logged_data) >= 2:
                start_time = datetime.fromisoformat(logged_data[0]['timestamp'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(logged_data[-1]['timestamp'].replace('Z', '+00:00'))
                duration_hours = (end_time - start_time).total_seconds() / 3600
            else:
                duration_hours = 0.0
            
            # Extraer metadata adicional si existe
            metadata = simulation_data.get('metadata', {})
            route_name = metadata.get('route_name', 'Unknown Route')
            use_real_route = metadata.get('use_real_route', False)
            transport_mode = metadata.get('transport_mode', 'driving-car')
            total_distance_km = metadata.get('total_distance_km', 0.0)
            route_id = metadata.get('route_id')  # Puede ser None
            
            # Parse arm timestamp
            arm_timestamp_str = arming.get('armTimestamp')
            arm_timestamp = None
            if arm_timestamp_str:
                try:
                    arm_timestamp = datetime.fromisoformat(arm_timestamp_str.replace('Z', '+00:00'))
                except:
                    pass
            
            # Insertar simulación
            insert_query = """
                INSERT INTO simulations (
                    epc, tid, version, 
                    route_id, route_name,
                    log_interval_seconds, log_number_of_samples,
                    temp_lower_limit, temp_upper_limit, distribution_type,
                    arm_status, arm_timestamp,
                    total_samples, total_violations, compliance_rate,
                    duration_hours, total_distance_km,
                    use_real_route, transport_mode
                ) VALUES (
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s
                ) RETURNING id
            """
            
            self.cursor.execute(insert_query, (
                epc, tid, version,
                route_id, route_name,
                config.get('logIntervalInSeconds'),
                config.get('logNumberOfSamples'),
                config.get('temperatureLowerLimit'),
                config.get('temperatureUpperLimit'),
                metadata.get('distribution_type', 'normal'),
                arming.get('armStatus'),
                arm_timestamp,
                total_samples,
                violations,
                compliance_rate,
                duration_hours,
                total_distance_km,
                use_real_route,
                transport_mode
            ))
            
            simulation_id = self.cursor.fetchone()['id']
            print(f"✓ Simulación insertada con ID: {simulation_id}")
            
            return simulation_id
            
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error insertando simulación: {e}")
            raise
    
    def insert_segments(self, simulation_id: int, segments_data: List[Dict[str, Any]]):
        """
        Inserta los segmentos de una simulación
        
        Args:
            simulation_id: ID de la simulación
            segments_data: Lista de diccionarios con datos de segmentos
        """
        if not segments_data:
            return
        
        try:
            insert_query = """
                INSERT INTO segments (
                    simulation_id, segment_number,
                    from_lat, from_lng, to_lat, to_lng,
                    sample_start, sample_end, sample_count,
                    observed_min, observed_max, observed_mean, observed_std,
                    configured_lower_temp, configured_upper_temp, configured_distribution
                ) VALUES (
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
            """
            
            batch_data = []
            for seg in segments_data:
                from_wp = seg.get('from_waypoint', {})
                to_wp = seg.get('to_waypoint', {})
                configured = seg.get('configured', {})
                
                batch_data.append((
                    simulation_id,
                    seg.get('segment'),
                    from_wp.get('lat'),
                    from_wp.get('lng'),
                    to_wp.get('lat'),
                    to_wp.get('lng'),
                    seg.get('sample_start'),
                    seg.get('sample_end'),
                    seg.get('sample_count'),
                    seg.get('observed_min'),
                    seg.get('observed_max'),
                    seg.get('observed_mean'),
                    seg.get('observed_std'),
                    configured.get('lower_temp'),
                    configured.get('upper_temp'),
                    configured.get('distribution_type')
                ))
            
            execute_batch(self.cursor, insert_query, batch_data)
            print(f"✓ {len(batch_data)} segmentos insertados")
            
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error insertando segmentos: {e}")
            raise
    
    def insert_stops(self, simulation_id: int, inventories_data: List[Dict[str, Any]]):
        """
        Inserta las paradas/inventarios de una simulación
        
        Args:
            simulation_id: ID de la simulación
            inventories_data: Lista de diccionarios con datos de inventarios
        """
        if not inventories_data:
            return
        
        try:
            insert_query = """
                INSERT INTO stops (
                    simulation_id, stop_number,
                    latitude, longitude, location_name,
                    stop_type, arrivals_count, departures_count,
                    inventory_timestamp
                ) VALUES (
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s
                )
            """
            
            batch_data = []
            for idx, inv in enumerate(inventories_data):
                # Determinar tipo de parada
                if idx == 0:
                    stop_type = 'origin'
                elif idx == len(inventories_data) - 1:
                    stop_type = 'destination'
                else:
                    stop_type = 'waypoint'
                
                # Parse timestamp - usar readerTimestamp si no hay timestamp
                timestamp_str = inv.get('timestamp') or inv.get('readerTimestamp')
                timestamp = None
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except:
                        pass
                
                # Las coordenadas pueden estar en location{} o directamente como readerLatitude/readerLongitude
                location = inv.get('location', {})
                latitude = location.get('latitude') or inv.get('readerLatitude')
                longitude = location.get('longitude') or inv.get('readerLongitude')
                location_name = inv.get('locationName') or inv.get('locality') or f'Stop {idx+1}'
                
                batch_data.append((
                    simulation_id,
                    idx,
                    latitude,
                    longitude,
                    location_name,
                    stop_type,
                    inv.get('arrivals', 0),
                    inv.get('departures', 0),
                    timestamp
                ))
            
            execute_batch(self.cursor, insert_query, batch_data)
            print(f"✓ {len(batch_data)} paradas insertadas")
            
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error insertando paradas: {e}")
            raise
    
    def insert_sensor_data(self, simulation_id: int, logged_data: List[Dict[str, Any]], 
                          temp_lower_limit: float = None, temp_upper_limit: float = None):
        """
        Inserta los datos de sensores de una simulación
        
        Args:
            simulation_id: ID de la simulación
            logged_data: Lista de diccionarios con datos de sensores
            temp_lower_limit: Límite inferior de temperatura
            temp_upper_limit: Límite superior de temperatura
        """
        if not logged_data:
            return
        
        try:
            insert_query = """
                INSERT INTO sensor_data (
                    simulation_id, timestamp,
                    temp_celsius, tamper, temperature_status,
                    latitude, longitude, location_name,
                    sample_index
                ) VALUES (
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s
                )
            """
            
            batch_data = []
            for idx, entry in enumerate(logged_data):
                timestamp_str = entry.get('timestamp')
                timestamp = None
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except:
                        pass
                
                # Calcular temperature_status
                temp_celsius = entry.get('tempInC')
                temperature_status = 'Normal'
                if temp_celsius is not None and temp_lower_limit is not None and temp_upper_limit is not None:
                    if temp_celsius < temp_lower_limit:
                        temperature_status = 'Cold Violation'
                    elif temp_celsius > temp_upper_limit:
                        temperature_status = 'Heat Violation'
                
                batch_data.append((
                    simulation_id,
                    timestamp,
                    temp_celsius,
                    entry.get('tamper', False),
                    temperature_status,
                    entry.get('latitude'),
                    entry.get('longitude'),
                    entry.get('locationName'),
                    idx
                ))
            
            # Insertar en lotes de 1000 para mejor performance
            batch_size = 1000
            for i in range(0, len(batch_data), batch_size):
                batch = batch_data[i:i+batch_size]
                execute_batch(self.cursor, insert_query, batch)
            
            print(f"✓ {len(batch_data)} lecturas de sensores insertadas")
            
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error insertando datos de sensores: {e}")
            raise
    
    def save_simulation_complete(self, simulation_data: Dict[str, Any], 
                                 segments_data: List[Dict[str, Any]] = None,
                                 auto_commit: bool = True) -> int:
        """
        Guarda una simulación completa con todos sus datos relacionados
        
        Args:
            simulation_data: Datos de la simulación en formato JSON
            segments_data: Datos de segmentos (si están disponibles, sino se generan desde inventories)
            auto_commit: Si es True, hace commit automáticamente. Si es False, no hace commit (para batch)
        
        Returns:
            ID de la simulación insertada
        """
        try:
            # Insertar simulación principal
            simulation_id = self.insert_simulation(simulation_data)
            
            # Generar segmentos desde inventories si no se proporcionaron
            if not segments_data:
                segments_data = self._generate_segments_from_inventories(simulation_data)
            
            # Insertar segmentos
            if segments_data:
                self.insert_segments(simulation_id, segments_data)
            
            # Insertar inventarios/paradas
            inventories = simulation_data.get('inventories', [])
            if inventories:
                self.insert_stops(simulation_id, inventories)
            
            # Insertar datos de sensores
            logged_data = simulation_data.get('loggedData', [])
            if logged_data:
                config = simulation_data.get('configuration', {})
                temp_lower_limit = config.get('temperatureLowerLimit')
                temp_upper_limit = config.get('temperatureUpperLimit')
                self.insert_sensor_data(simulation_id, logged_data, temp_lower_limit, temp_upper_limit)
            
            # Solo hacer commit si auto_commit=True (modo individual)
            if auto_commit:
                self.conn.commit()
                print(f"✓ Simulación completa guardada exitosamente (ID: {simulation_id})")
            
            return simulation_id
            
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error guardando simulación completa: {e}")
            raise
    
    def _generate_segments_from_inventories(self, simulation_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Genera datos de segmentos desde los inventories del JSON.
        Cada segmento va de un inventory al siguiente.
        
        Args:
            simulation_data: Datos de la simulación en formato JSON
        
        Returns:
            Lista de diccionarios con datos de segmentos
        """
        inventories = simulation_data.get('inventories', [])
        logged_data = simulation_data.get('loggedData', [])
        config = simulation_data.get('configuration', {})
        
        if len(inventories) < 2:
            return []
        
        segments = []
        
        # Crear un segmento entre cada par de inventories consecutivos
        for i in range(len(inventories) - 1):
            from_inv = inventories[i]
            to_inv = inventories[i + 1]
            
            # Coordenadas del segmento
            from_lat = from_inv.get('readerLatitude')
            from_lng = from_inv.get('readerLongitude')
            to_lat = to_inv.get('readerLatitude')
            to_lng = to_inv.get('readerLongitude')
            
            # Determinar rango de muestras basado en loggerNextSample
            sample_start = from_inv.get('loggerNextSample', i)
            sample_end = to_inv.get('loggerNextSample', len(logged_data)) - 1
            
            # Ajustar para el último segmento
            if i == len(inventories) - 2:
                sample_end = len(logged_data) - 1
            
            # Validar rangos
            sample_start = max(0, min(sample_start, len(logged_data) - 1))
            sample_end = max(sample_start, min(sample_end, len(logged_data) - 1))
            
            # Extraer temperaturas del segmento
            segment_temps = []
            for j in range(sample_start, sample_end + 1):
                if j < len(logged_data):
                    temp = logged_data[j].get('tempInC')
                    if temp is not None:
                        segment_temps.append(temp)
            
            # Calcular estadísticas
            if segment_temps:
                import numpy as np
                observed_min = float(min(segment_temps))
                observed_max = float(max(segment_temps))
                observed_mean = float(np.mean(segment_temps))
                observed_std = float(np.std(segment_temps))
            else:
                observed_min = None
                observed_max = None
                observed_mean = None
                observed_std = None
            
            # Crear segmento
            segment = {
                "segment": i,
                "from_waypoint": {"lat": from_lat, "lng": from_lng},
                "to_waypoint": {"lat": to_lat, "lng": to_lng},
                "sample_start": sample_start,
                "sample_end": sample_end,
                "sample_count": len(segment_temps),
                "observed_min": observed_min,
                "observed_max": observed_max,
                "observed_mean": observed_mean,
                "observed_std": observed_std,
                "configured": {
                    "lower_temp": config.get('temperatureLowerLimit'),
                    "upper_temp": config.get('temperatureUpperLimit'),
                    "distribution_type": simulation_data.get('metadata', {}).get('distribution_type', 'normal')
                }
            }
            
            segments.append(segment)
        
        print(f"✓ {len(segments)} segmentos generados desde inventories")
        return segments
    
    def get_simulation_summary(self, simulation_id: int = None) -> List[Dict[str, Any]]:
        """
        Obtiene resumen de simulaciones desde la vista
        
        Args:
            simulation_id: ID específico de simulación (opcional)
        
        Returns:
            Lista de diccionarios con datos de simulaciones
        """
        try:
            if simulation_id:
                query = "SELECT * FROM vw_simulations_summary WHERE id = %s"
                self.cursor.execute(query, (simulation_id,))
            else:
                query = "SELECT * FROM vw_simulations_summary ORDER BY created_at DESC LIMIT 100"
                self.cursor.execute(query)
            
            return [dict(row) for row in self.cursor.fetchall()]
            
        except Exception as e:
            print(f"✗ Error obteniendo resumen: {e}")
            raise
    
    def get_temperature_violations(self, simulation_id: int = None) -> List[Dict[str, Any]]:
        """
        Obtiene violaciones de temperatura
        
        Args:
            simulation_id: ID específico de simulación (opcional)
        
        Returns:
            Lista de violaciones
        """
        try:
            if simulation_id:
                query = "SELECT * FROM vw_temperature_violations WHERE simulation_id = %s"
                self.cursor.execute(query, (simulation_id,))
            else:
                query = "SELECT * FROM vw_temperature_violations ORDER BY timestamp DESC LIMIT 1000"
                self.cursor.execute(query)
            
            return [dict(row) for row in self.cursor.fetchall()]
            
        except Exception as e:
            print(f"✗ Error obteniendo violaciones: {e}")
            raise
    
    def get_used_epcs(self) -> List[str]:
        """
        Obtiene todos los EPCs únicos que ya están en uso en la base de datos
        
        Returns:
            Lista de EPCs únicos utilizados
        """
        try:
            query = "SELECT DISTINCT epc FROM simulations ORDER BY epc"
            self.cursor.execute(query)
            return [row['epc'] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"✗ Error obteniendo EPCs: {e}")
            return []
    
    def get_used_tids(self) -> List[str]:
        """
        Obtiene todos los TIDs únicos que ya están en uso en la base de datos
        
        Returns:
            Lista de TIDs únicos utilizados
        """
        try:
            query = "SELECT DISTINCT tid FROM simulations ORDER BY tid"
            self.cursor.execute(query)
            return [row['tid'] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"✗ Error obteniendo TIDs: {e}")
            return []
    
    # ============================================================
    # CRUD Operations for Companies
    # ============================================================
    
    def create_company(self, company_data: Dict[str, Any]) -> int:
        """
        Create a new company
        
        Args:
            company_data: Dictionary with company fields (name, description, contact_email, contact_phone)
        
        Returns:
            ID of the created company
        """
        try:
            query = """
                INSERT INTO companies (name, description, contact_email, contact_phone)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """
            self.cursor.execute(query, (
                company_data.get('name'),
                company_data.get('description', ''),
                company_data.get('contact_email', ''),
                company_data.get('contact_phone', '')
            ))
            company_id = self.cursor.fetchone()['id']
            self.conn.commit()
            print(f"✓ Compañía creada con ID: {company_id}")
            return company_id
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error creando compañía: {e}")
            raise
    
    def get_all_companies(self) -> List[Dict[str, Any]]:
        """Get all companies"""
        try:
            query = "SELECT * FROM companies ORDER BY name"
            self.cursor.execute(query)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"✗ Error obteniendo compañías: {e}")
            return []
    
    def get_company_by_id(self, company_id: int) -> Optional[Dict[str, Any]]:
        """Get company by ID"""
        try:
            query = "SELECT * FROM companies WHERE id = %s"
            self.cursor.execute(query, (company_id,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"✗ Error obteniendo compañía: {e}")
            return None
    
    def update_company(self, company_id: int, company_data: Dict[str, Any]):
        """Update company"""
        try:
            query = """
                UPDATE companies 
                SET name = %s, description = %s, contact_email = %s, 
                    contact_phone = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """
            self.cursor.execute(query, (
                company_data.get('name'),
                company_data.get('description', ''),
                company_data.get('contact_email', ''),
                company_data.get('contact_phone', ''),
                company_id
            ))
            self.conn.commit()
            print(f"✓ Compañía {company_id} actualizada")
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error actualizando compañía: {e}")
            raise
    
    def delete_company(self, company_id: int):
        """Delete company"""
        try:
            query = "DELETE FROM companies WHERE id = %s"
            self.cursor.execute(query, (company_id,))
            self.conn.commit()
            print(f"✓ Compañía {company_id} eliminada")
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error eliminando compañía: {e}")
            raise
    
    # ============================================================
    # CRUD Operations for Routes
    # ============================================================
    
    def create_route(self, route_data: Dict[str, Any]) -> int:
        """
        Create a new route
        
        Args:
            route_data: Dictionary with route fields
        
        Returns:
            ID of the created route
        """
        try:
            query = """
                INSERT INTO routes (
                    company_id, route_name, route_description,
                    origin_name, origin_latitude, origin_longitude, origin_departure_date,
                    destination_name, destination_latitude, destination_longitude, destination_arrival_date,
                    waypoints_json, segments_json, sensors_json,
                    log_interval_seconds, use_real_routes, transport_mode
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            self.cursor.execute(query, (
                route_data.get('company_id'),
                route_data.get('route_name'),
                route_data.get('route_description', ''),
                route_data.get('origin_name'),
                route_data.get('origin_latitude'),
                route_data.get('origin_longitude'),
                route_data.get('origin_departure_date'),
                route_data.get('destination_name'),
                route_data.get('destination_latitude'),
                route_data.get('destination_longitude'),
                route_data.get('destination_arrival_date'),
                route_data.get('waypoints_json'),
                route_data.get('segments_json'),
                route_data.get('sensors_json'),
                route_data.get('log_interval_seconds', 300),
                route_data.get('use_real_routes', False),
                route_data.get('transport_mode', 'driving-car')
            ))
            route_id = self.cursor.fetchone()['id']
            self.conn.commit()
            print(f"✓ Ruta creada con ID: {route_id}")
            return route_id
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error creando ruta: {e}")
            raise
    
    def get_routes_by_company(self, company_id: int) -> List[Dict[str, Any]]:
        """Get all routes for a company"""
        try:
            query = "SELECT * FROM routes WHERE company_id = %s ORDER BY route_name"
            self.cursor.execute(query, (company_id,))
            return self.cursor.fetchall()
        except Exception as e:
            print(f"✗ Error obteniendo rutas: {e}")
            return []
    
    def get_route_by_id(self, route_id: int) -> Optional[Dict[str, Any]]:
        """Get route by ID"""
        try:
            query = "SELECT * FROM routes WHERE id = %s"
            self.cursor.execute(query, (route_id,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"✗ Error obteniendo ruta: {e}")
            return None
    
    def update_route(self, route_id: int, route_data: Dict[str, Any]):
        """Update route"""
        try:
            query = """
                UPDATE routes 
                SET company_id = %s, route_name = %s, route_description = %s,
                    origin_name = %s, origin_latitude = %s, origin_longitude = %s, origin_departure_date = %s,
                    destination_name = %s, destination_latitude = %s, destination_longitude = %s, destination_arrival_date = %s,
                    waypoints_json = %s, segments_json = %s, sensors_json = %s,
                    log_interval_seconds = %s, use_real_routes = %s, transport_mode = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """
            self.cursor.execute(query, (
                route_data.get('company_id'),
                route_data.get('route_name'),
                route_data.get('route_description', ''),
                route_data.get('origin_name'),
                route_data.get('origin_latitude'),
                route_data.get('origin_longitude'),
                route_data.get('origin_departure_date'),
                route_data.get('destination_name'),
                route_data.get('destination_latitude'),
                route_data.get('destination_longitude'),
                route_data.get('destination_arrival_date'),
                route_data.get('waypoints_json'),
                route_data.get('segments_json'),
                route_data.get('sensors_json'),
                route_data.get('log_interval_seconds', 300),
                route_data.get('use_real_routes', False),
                route_data.get('transport_mode', 'driving-car'),
                route_id
            ))
            self.conn.commit()
            print(f"✓ Ruta {route_id} actualizada")
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error actualizando ruta: {e}")
            raise
    
    def delete_route(self, route_id: int):
        """Delete route"""
        try:
            query = "DELETE FROM routes WHERE id = %s"
            self.cursor.execute(query, (route_id,))
            self.conn.commit()
            print(f"✓ Ruta {route_id} eliminada")
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error eliminando ruta: {e}")
            raise
    
    def get_next_sensor_epc(self) -> str:
        """Get the next available sensor EPC number.
        
        Format: 5201F25030000001 (prefix 5201F2503 + 7 digit incremental number)
        
        Returns:
            Next available EPC string
        """
        try:
            # Get the maximum number from EPCs with format 5201F2503XXXXXXX
            query = """
                SELECT MAX(CAST(SUBSTRING(epc FROM 10) AS BIGINT)) as max_num 
                FROM simulations 
                WHERE epc LIKE '5201F2503%' AND LENGTH(epc) = 16
            """
            self.cursor.execute(query)
            result = self.cursor.fetchone()
            
            if result and result['max_num']:
                next_num = int(result['max_num']) + 1
            else:
                next_num = 1
            
            # Format: 5201F2503 + 7 digits
            return f"5201F2503{next_num:07d}"
        except Exception as e:
            print(f"✗ Error obteniendo siguiente EPC: {e}")
            return "5201F25030000001"
    
    def get_next_sensor_tid(self) -> str:
        """Get the next available sensor TID number.
        
        Format: E2C245002000056680000001 (prefix E2C24500200005668 + 7 digit incremental number)
        
        Returns:
            Next available TID string
        """
        try:
            # Get the maximum number from TIDs with format E2C24500200005668XXXXXXX
            query = """
                SELECT MAX(CAST(SUBSTRING(tid FROM 18) AS BIGINT)) as max_num 
                FROM simulations 
                WHERE tid LIKE 'E2C24500200005668%' AND LENGTH(tid) = 24
            """
            self.cursor.execute(query)
            result = self.cursor.fetchone()
            
            if result and result['max_num']:
                next_tid = int(result['max_num']) + 1
            else:
                next_tid = 1
            
            # Format: E2C24500200005668 + 7 digits
            return f"E2C24500200005668{next_tid:07d}"
        except Exception as e:
            print(f"✗ Error obteniendo siguiente TID: {e}")
            return "E2C245002000056680000001"


# Función helper para uso rápido
def save_simulation_to_neon(json_file: str = None, 
                           json_data: Dict[str, Any] = None,
                           segments_data: List[Dict[str, Any]] = None,
                           connection_string: str = None) -> int:
    """
    Función helper para guardar simulación en Neon
    
    Args:
        json_file: Ruta al archivo JSON de la simulación
        json_data: Datos de simulación como diccionario (alternativa a json_file)
        segments_data: Datos de segmentos
        connection_string: String de conexión (opcional)
    
    Returns:
        ID de la simulación guardada
    """
    if json_file:
        with open(json_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    
    if not json_data:
        raise ValueError("Debe proporcionar json_file o json_data")
    
    with DatabaseManager(connection_string) as db:
        return db.save_simulation_complete(json_data, segments_data)

def save_simulations_batch(json_files: List[str], 
                           connection_string: str = None,
                           show_progress: bool = True) -> List[int]:
    """
    Guarda múltiples simulaciones en una sola transacción (BATCH).
    Mucho más rápido que guardar una por una.
    
    Args:
        json_files: Lista de rutas a archivos JSON
        connection_string: String de conexión (opcional)
        show_progress: Mostrar progreso de guardado
    
    Returns:
        Lista de IDs de simulaciones guardadas
    """
    if not json_files:
        return []
    
    simulation_ids = []
    total = len(json_files)
    
    if show_progress:
        print(f"\n{'='*60}")
        print(f"💾 GUARDADO EN LOTE - {total} simulaciones")
        print(f"{'='*60}")
    
    with DatabaseManager(connection_string) as db:
        try:
            # Procesar todas las simulaciones en UNA SOLA transacción
            for idx, json_file in enumerate(json_files, 1):
                if show_progress and idx % 10 == 0:
                    progress = int((idx / total) * 100)
                    print(f"   📊 Progreso: {progress}% ({idx}/{total})")
                
                # Cargar JSON
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                # Guardar SIN commit individual (auto_commit=False)
                sim_id = db.save_simulation_complete(json_data, segments_data=None, auto_commit=False)
                simulation_ids.append(sim_id)
            
            # Commit una sola vez al final
            db.conn.commit()
            
            if show_progress:
                print(f"   ✅ {total} simulaciones guardadas exitosamente")
                print(f"   📋 IDs: {simulation_ids[0]} - {simulation_ids[-1]}")
                print(f"{'='*60}\n")
            
            return simulation_ids
            
        except Exception as e:
            db.conn.rollback()
            print(f"✗ Error en guardado batch: {e}")
            raise