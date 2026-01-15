"""
Adapter module to bridge new RouteConfig models with existing LogSimulator.

This module converts the new data structures (RouteConfig, SegmentMetadata, Distribution)
into the format expected by the existing LogSimulator class.
"""

from math import ceil
from typing import List
from datetime import datetime, timedelta
import os
import json

from models.route import RouteConfig
from models.segment import SegmentMetadata
from models.distribution import Distribution
from models.sensor import SensorConfig
from simulator import LogSimulator, LogGeneratorInput, TempProfile, OpenStreetMapRouter


class SimulatorAdapter:
    """Adapts new RouteConfig to work with existing LogSimulator."""
    
    @staticmethod
    def generate_simulations(route_config: RouteConfig, 
                            num_samples: int = 1,
                            use_real_routes: bool = False,
                            use_secondary_routes: bool = False,
                            secondary_routes_count: int = 0,
                            output_dir: str = "simulation_outputs",
                            include_location_names: bool = False,
                            simulate_every_n_sensors: int = 1) -> List[str]:
        """Generate simulation JSONs from RouteConfig.
        
        Args:
            route_config: Complete route configuration
            num_samples: Number of JSON samples to generate
            use_real_routes: Whether to use OpenStreetMap routes
            use_secondary_routes: Whether to generate secondary/alternative routes
            secondary_routes_count: Number of secondary routes to generate (1-3)
            output_dir: Directory to save outputs
            include_location_names: Whether to include location names via reverse geocoding
            simulate_every_n_sensors: Number of sensors per simulation group (default: 1)
            
        Returns:
            List of generated file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        generated_files = []
        
        # Ensure segments are configured
        route_config.ensure_segments()
        
        # Get all coordinates
        coordinates = route_config.get_coordinates()
        if len(coordinates) < 2:
            raise ValueError("Route must have at least origin and destination")
        
        # Extract location names from RouteConfig if include_location_names is enabled
        location_names_map = {}
        if include_location_names:
            # Add origin name
            if route_config.origin:
                coord_key = f"{round(route_config.origin.latitude, 4)},{round(route_config.origin.longitude, 4)}"
                location_names_map[coord_key] = route_config.origin.name
            
            # Add destination name
            if route_config.destination:
                coord_key = f"{round(route_config.destination.latitude, 4)},{round(route_config.destination.longitude, 4)}"
                location_names_map[coord_key] = route_config.destination.name
            
            # Add waypoint names from segments
            for waypoint in route_config.waypoints:
                coord_key = f"{round(waypoint.latitude, 4)},{round(waypoint.longitude, 4)}"
                location_names_map[coord_key] = waypoint.name
            
            print(f"   📍 Preparando {len(location_names_map)} nombres de ubicaciones del UI")
        
        # Calculate time parameters
        if route_config.origin and route_config.origin.timestamp:
            start_time = route_config.origin.timestamp
        else:
            start_time = datetime.now()
        
        # Estimate total duration
        if route_config.destination and route_config.destination.timestamp and route_config.origin.timestamp:
            total_duration_hours = (route_config.destination.timestamp - route_config.origin.timestamp).total_seconds() / 3600
        else:
            # Fallback: use segment stop times + estimated travel
            total_duration_hours = route_config.calculate_total_duration_estimate()
        
        # Calculate number of temperature samples based on log interval and duration
        log_interval = route_config.log_interval_seconds
        num_temp_samples = max(2, int((total_duration_hours * 3600) / log_interval))
        
        # Advertir y limitar si son demasiadas muestras
        MAX_SAMPLES = 5000
        if num_temp_samples > MAX_SAMPLES:
            print(f"")
            print(f"   ⚠️  ADVERTENCIA: Demasiadas muestras calculadas ({num_temp_samples})")
            print(f"   🔧 Limitando a {MAX_SAMPLES} muestras para evitar bloqueo")
            print(f"   💡 Aumenta el log_interval a {int((total_duration_hours * 3600) / MAX_SAMPLES)} segundos")
            print(f"      para capturar toda la ruta sin límite.")
            print(f"")
            num_temp_samples = MAX_SAMPLES
        elif num_temp_samples > 2000:
            print(f"")
            print(f"   ℹ️  Ruta larga: generando {num_temp_samples} muestras")
            print(f"   ⏳ Esto puede tardar 30-60 segundos...")
            print(f"")
        
        # Convert segments to TempProfile objects for existing simulator
        segment_profiles = SimulatorAdapter._convert_segments_to_profiles(route_config.segments)
        
        # Generate for each sensor
        if not route_config.sensors:
            # No sensors defined, use default
            route_config.sensors = [SensorConfig.generate_default(1)]
        
        # ═══════════════════════════════════════════════════════════════════
        # OPTIMIZATION: Get routes ONCE before processing sensors
        # This prevents redundant API calls when multiple sensors share the same route
        # ═══════════════════════════════════════════════════════════════════
        print(f"\n🚀 OPTIMIZACIÓN: Obteniendo rutas UNA SOLA VEZ para {len(route_config.sensors)} sensores")
        
        routes_to_generate = []
        api_duration_hours = None  # Store real API duration
        
        if use_real_routes and use_secondary_routes and secondary_routes_count > 0:
            # Get alternative routes from OpenRouteService
            # El API retorna la ruta principal + las alternativas, por lo que solicitamos
            # secondary_routes_count rutas alternativas (el API agregará la principal automáticamente)
            print(f"\n🗺️  CALCULANDO RUTAS ALTERNATIVAS")
            print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"   📍 Origen: {coordinates[0]}")
            print(f"   📍 Destino: {coordinates[-1]}")
            print(f"   🚗 Modo: {route_config.transport_mode}")
            print(f"   🔢 Rutas solicitadas: 1 principal + {secondary_routes_count} secundarias")
            print(f"   ⚠️  Esto puede tardar 20-60 segundos...")
            print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            
            router = OpenStreetMapRouter()
            alternative_routes = router.get_alternative_routes(
                start=coordinates[0],
                end=coordinates[-1],
                mode=route_config.transport_mode,
                num_alternatives=secondary_routes_count
            )
            
            # Verificar que obtuvimos rutas
            if alternative_routes and len(alternative_routes) > 0:
                routes_to_generate = alternative_routes
                num_secondary = len(alternative_routes) - 1
                print(f"✓ Se obtuvieron {len(alternative_routes)} rutas (1 principal + {num_secondary} secundarias)")
                print(f"   💡 Estas rutas se reutilizarán para todos los sensores\n")
                
                # Get API duration from the main route
                if alternative_routes[0].get('duration_hours'):
                    api_duration_hours = alternative_routes[0]['duration_hours']
                
                # Si se solicitaron rutas secundarias pero solo se obtuvo la principal
                if len(alternative_routes) == 1 and secondary_routes_count > 0:
                    print(f"")
                    print(f"⚠️  ADVERTENCIA: Rutas alternativas no disponibles")
                    print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    print(f"   Se solicitaron {secondary_routes_count} ruta(s) secundaria(s)")
                    print(f"   pero OpenRouteService solo retornó la ruta principal.")
                    print(f"   ")
                    print(f"   Posibles razones:")
                    print(f"   • La región tiene pocas carreteras alternativas")
                    print(f"   • La distancia es muy corta (< 50 km)")
                    print(f"   • No existen rutas suficientemente diferentes")
                    print(f"   ")
                    print(f"   💡 Sugerencia: Prueba con una ruta más larga o")
                    print(f"      entre ciudades con más opciones de carreteras.")
                    print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    print(f"")
            else:
                # Fallback: usar solo ruta principal
                print("⚠️ No se pudieron obtener rutas alternativas, usando solo ruta principal")
                routes_to_generate = [{
                    'route_type': 'principal',
                    'coordinates': coordinates,
                    'distance_km': 0,
                    'duration_hours': total_duration_hours
                }]
        elif use_real_routes:
            # Get single route from API
            print(f"\n🗺️  CALCULANDO RUTA PRINCIPAL")
            print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"   📍 Puntos en la ruta: {len(coordinates)}")
            print(f"   🚗 Modo: {route_config.transport_mode}")
            print(f"   ⏳ Esperando respuesta del API...")
            print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            
            router = OpenStreetMapRouter()
            route_info = router.get_route_multi(coordinates, mode=route_config.transport_mode)
            
            if route_info and 'duration_hours' in route_info:
                api_duration_hours = route_info['duration_hours']
                routes_to_generate = [{
                    'route_type': 'principal',
                    'coordinates': route_info.get('coordinates', coordinates),
                    'distance_km': route_info.get('distance_km', 0),
                    'duration_hours': api_duration_hours
                }]
                print(f"   ✓ Ruta obtenida exitosamente")
                print(f"   💡 Esta ruta se reutilizará para todos los sensores\n")
            else:
                # Fallback if API fails
                routes_to_generate = [{
                    'route_type': 'principal',
                    'coordinates': coordinates,
                    'distance_km': 0,
                    'duration_hours': total_duration_hours
                }]
        else:
            # Only generate main route without real routes
            routes_to_generate = [{
                'route_type': 'principal',
                'coordinates': coordinates,
                'distance_km': 0,
                'duration_hours': total_duration_hours
            }]
        
        print(f"   📊 Rutas totales obtenidas: {len(routes_to_generate)}")
        print(f"   📦 Sensores a procesar: {len(route_config.sensors)}")
        print(f"   🎯 Archivos JSON a generar: {len(routes_to_generate) * len(route_config.sensors) * num_samples}")
        print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        # Update destination timestamp with real API duration if available
        if api_duration_hours is not None and route_config.origin and route_config.origin.timestamp:
            route_config.destination.timestamp = route_config.origin.timestamp + timedelta(hours=api_duration_hours)
            print(f"   ⏱️  Tiempo de tránsito actualizado: {api_duration_hours:.2f} hrs")
            # Recalculate total_duration_hours and num_temp_samples with real API data
            total_duration_hours = api_duration_hours
            num_temp_samples = max(2, int((total_duration_hours * 3600) / log_interval))
        
        # Build key_waypoints list with (lat, lng, name) tuples for inventories
        key_waypoints = []
        if include_location_names:
            if route_config.origin:
                key_waypoints.append((
                    route_config.origin.latitude,
                    route_config.origin.longitude,
                    route_config.origin.name
                ))
            for wp in route_config.waypoints:
                key_waypoints.append((wp.latitude, wp.longitude, wp.name))
            if route_config.destination:
                key_waypoints.append((
                    route_config.destination.latitude,
                    route_config.destination.longitude,
                    route_config.destination.name
                ))
            print(f"   📍 Creando {len(key_waypoints)} key_waypoints para inventories")
        
        # ═══════════════════════════════════════════════════════════════════
        # MAIN GENERATION LOOP: Iterate sensors → routes → samples
        # Routes are already pre-calculated, so we're just reusing them
        # Each sensor GROUP will use the SAME route coordinates AND SAME temperature distributions
        # Only EPC and TID will differ within the group
        # ═══════════════════════════════════════════════════════════════════
        # Validate and ensure simulate_every_n_sensors is at least 1
        simulate_every_n_sensors = max(1, simulate_every_n_sensors)

        total_sensors = len(route_config.sensors)
        group_size = simulate_every_n_sensors
        num_groups = ceil(total_sensors / group_size)

        print(f"   🔢 Sensores totales: {total_sensors}")
        print(f"   📦 Sensores por simulación: {group_size}")
        print(f"   🧪 Grupos de simulaciones: {num_groups}")
        print(f"   ✅ Sensores en cada grupo compartirán la misma loggedData")
        
        # Debug: Mostrar cálculo de grupos
        print(f"\n🔍 DEBUG:")
        print(f"   ceil({total_sensors} / {group_size}) = {num_groups}")
        for g in range(num_groups):
            start = g * group_size
            end = min(start + group_size, total_sensors)
            print(f"   Grupo {g+1}: sensores {start+1}-{end} ({end-start} sensores)")

        for group_idx in range(num_groups):
            start_idx = group_idx * group_size
            end_idx = min(start_idx + group_size, total_sensors)
            sensor_group = route_config.sensors[start_idx:end_idx]

            print(f"\n📦 Grupo {group_idx+1}/{num_groups}")
            print(f"   Sensores {start_idx+1} → {end_idx} (Total: {len(sensor_group)})")

            for route_idx, route_info in enumerate(routes_to_generate):
                route_type = route_info.get('route_type', 'principal')
                route_coords = route_info.get('coordinates', coordinates)

                for sample_idx in range(num_samples):
                    # ═══════════════════════════════════════════════════════════
                    # GENERAR UNA SOLA VEZ los datos de simulación por grupo
                    # Usamos el primer sensor del grupo solo como referencia
                    # ═══════════════════════════════════════════════════════════
                    reference_sensor = sensor_group[0]

                    config = LogGeneratorInput(
                        epc=reference_sensor.epc,
                        tid=reference_sensor.tid,
                        log_interval_in_seconds=log_interval,
                        number_of_samples=num_temp_samples,
                        start_timestamp=start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        lower_temp=segment_profiles[0].lower_temp if segment_profiles else 0.0,
                        upper_temp=segment_profiles[0].upper_temp if segment_profiles else 10.0,
                        start_lat=route_coords[0][0],
                        start_lng=route_coords[0][1],
                        end_lat=route_coords[-1][0],
                        end_lng=route_coords[-1][1],
                        number_of_stops=len(route_coords) - 2,
                        distribution_type=segment_profiles[0].distribution_type if segment_profiles else "normal",
                        waypoints=route_coords,
                        key_waypoints=key_waypoints if include_location_names else None,
                        transport_mode=route_config.transport_mode,
                        use_real_route=use_real_routes,
                        route_name=route_config.route_name,
                        route_id=route_config.id,
                        segment_profiles=segment_profiles,
                    )

                    simulator = LogSimulator(config)

                    # ✅ GENERAR UNA SOLA VEZ la simulación completa
                    print(f"   🎲 Generando loggedData para grupo {group_idx+1}, ruta {route_type}, muestra {sample_idx+1}...")
                    shared_data = simulator.generate(
                        include_location_names=include_location_names,
                        location_names=location_names_map if include_location_names else None
                    )

                    # ═══════════════════════════════════════════════════════════
                    # APLICAR LOS MISMOS DATOS (loggedData) a todos los sensores del grupo
                    # Solo cambiamos EPC y TID por sensor
                    # ═══════════════════════════════════════════════════════════
                    print(f"   📋 Aplicando la misma loggedData a {len(sensor_group)} sensores...")
                    for sensor_idx, sensor in enumerate(sensor_group):
                        # Hacer una copia profunda de los datos compartidos
                        import copy
                        data_copy = copy.deepcopy(shared_data)
                        
                        # Actualizar solo EPC y TID para este sensor
                        data_copy["EPC"] = sensor.epc
                        data_copy["TID"] = sensor.tid

                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                        filename = (
                            f"{route_config.route_name.replace(' ', '_')}"
                            f"_grp{group_idx+1}"
                            f"_{sensor.epc[-6:]}"
                            f"_{route_type}"
                            f"_{sample_idx+1}_{timestamp}.json"
                        )

                        filepath = os.path.join(output_dir, filename)

                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(data_copy, f, indent=2)

                        generated_files.append(filepath)
                        print(f"      ✓ Sensor {sensor_idx+1}/{len(sensor_group)}: {filename}")

        print(f"\n{'='*60}")
        print(f"✅ GENERACIÓN COMPLETADA")
        print(f"{'='*60}")
        print(f"   📊 Total de archivos generados: {len(generated_files)}")
        print(f"   📦 Grupos procesados: {num_groups}")
        print(f"   🎯 Sensores por grupo: {group_size}")
        print(f"{'='*60}\n")

        return generated_files
    
    @staticmethod
    def _convert_segments_to_profiles(segments: List[SegmentMetadata]) -> List[TempProfile]:
        """Convert SegmentMetadata with multiple distributions to TempProfile for existing simulator.
        
        For now, this uses the first distribution of each segment.
        TODO: Implement full multi-distribution blending in future phase.
        """
        profiles = []
        
        for segment in segments:
            if not segment.distributions:
                # No distributions defined, use defaults
                profile = TempProfile(
                    lower_temp=0.0,
                    upper_temp=10.0,
                    distribution_type="normal",
                    mean_temp=5.0,
                    std_dev=2.0,
                )
            else:
                # Use first distribution (multi-distribution blending will be implemented later)
                dist = segment.distributions[0]
                
                # Handle relative mode (simplified for now)
                if dist.mode == "relative":
                    # Convert relative to absolute using ambient
                    ambient = dist.ambient_temp if dist.ambient_temp else 20.0
                    offset = ambient * (dist.relative_offset_pct / 100.0)
                    lower_temp = (dist.lower_temp or 0.0) + offset
                    upper_temp = (dist.upper_temp or 10.0) + offset
                    mean_temp = (dist.mean_temp or 5.0) + offset if dist.mean_temp else None
                else:
                    # Absolute mode
                    lower_temp = dist.lower_temp or 0.0
                    upper_temp = dist.upper_temp or 10.0
                    mean_temp = dist.mean_temp
                
                profile = TempProfile(
                    lower_temp=lower_temp,
                    upper_temp=upper_temp,
                    distribution_type=dist.type,
                    mean_temp=mean_temp,
                    std_dev=dist.std_dev,
                    beta_alpha=dist.beta_alpha,
                    beta_beta=dist.beta_beta,
                    apply_ar1=segment.apply_smoothing,
                )
            
            profiles.append(profile)
        
        return profiles
    
    @staticmethod
    def generate_with_multi_distribution_blending(route_config: RouteConfig,
                                                   num_samples: int = 1,
                                                   use_real_routes: bool = False,
                                                   output_dir: str = "simulation_outputs") -> List[str]:
        """Advanced generation with full multi-distribution blending support.
        
        This method will be fully implemented when we refactor the temperature generation
        in LogSimulator to use DistributionBlender directly.
        
        For now, it falls back to the standard generation method.
        """
        # TODO: Implement full DistributionBlender integration
        # This will require modifying LogSimulator._generate_temperatures_segmented()
        # to use DistributionBlender.blend() for segments with multiple distributions
        
        print("⚠️  Multi-distribution blending not yet fully implemented.")
        print("   Using first distribution of each segment for now.")
        print("   Full blending support coming in next update.")
        
        return SimulatorAdapter.generate_simulations(
            route_config, num_samples, use_real_routes, output_dir
        )


if __name__ == "__main__":
    # Test the adapter
    from models.route import RouteConfig, RoutePoint
    from models.segment import SegmentMetadata
    from models.distribution import Distribution
    from models.sensor import SensorConfig
    from datetime import datetime
    
    # Create test configuration
    config = RouteConfig(
        route_name="Test Route",
        route_description="Test pharmaceutical transport",
    )
    
    config.origin = RoutePoint(
        name="CDMX",
        latitude=19.4326,
        longitude=-99.1332,
        point_type="origin",
        timestamp=datetime.now()
    )
    
    config.destination = RoutePoint(
        name="Guadalajara",
        latitude=20.6597,
        longitude=-103.3496,
        point_type="destination",
        timestamp=datetime.now() + timedelta(hours=6)
    )
    
    # Add segment with distribution
    segment = SegmentMetadata(
        description="Highway segment",
        segment_type="Highway",
        estimated_stop_time_minutes=30
    )
    
    dist = Distribution(
        type="normal",
        mode="absolute",
        lower_temp=0.0,
        upper_temp=10.0,
        mean_temp=5.0,
        std_dev=2.0,
    )
    segment.distributions.append(dist)
    config.segments.append(segment)
    
    # Add sensor
    config.sensors.append(SensorConfig.generate_default(1))
    
    # Generate
    files = SimulatorAdapter.generate_simulations(config, num_samples=1)
    print(f"\n✓ Generated {len(files)} file(s)")
    for f in files:
        print(f"  - {f}")
