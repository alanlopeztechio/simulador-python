from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import random
from typing import List, Dict, Any, Literal, Optional, Tuple
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats
import requests
import folium
from geopy.distance import geodesic
import os


@dataclass
class LogGeneratorInput:
    epc: str
    tid: str
    log_interval_in_seconds: int
    number_of_samples: int
    start_timestamp: str  # formato ISO, e.g. "2025-10-24T18:05:00Z"
    lower_temp: float
    upper_temp: float
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    number_of_stops: int
    distribution_type: Literal["normal", "beta", "truncnorm", "uniform"] = "normal"
    # Lista opcional de puntos de ruta (lat, lng) incluyendo origen y último destino.
    # Si se proporciona, tiene prioridad sobre start/end.
    waypoints: Optional[List[Tuple[float, float]]] = None
    # Modo de transporte para la ruta real
    transport_mode: Literal["driving-car", "foot-walking", "cycling-regular"] = "driving-car"
    # Parámetros para distribución normal
    mean_temp: float = None  # Si es None, se usa el promedio de lower y upper
    std_dev: float = 5.0
    # Parámetros para distribución beta
    beta_alpha: float = 2.0
    beta_beta: float = 5.0
    # Ruta real usando OpenStreetMap
    use_real_route: bool = False
    route_name: str = "Custom Route"
    # Per-segment temperature/distribution profiles. One entry per leg between waypoints.
    # If provided, overrides global lower/upper/distribution for the corresponding samples.
    segment_profiles: Optional[List["TempProfile"]] = None


@dataclass
class TempProfile:
    """Per-segment temperature profile configuration."""
    lower_temp: float
    upper_temp: float
    distribution_type: Literal["normal", "beta", "truncnorm", "uniform"] = "normal"
    mean_temp: Optional[float] = None
    std_dev: float = 5.0
    beta_alpha: float = 2.0
    beta_beta: float = 5.0
    # Smoothing (exponential/AR(1)-like) toggle per segment (simple, no extra params)
    apply_ar1: bool = False


@dataclass
class UseCaseConfig:
    """Configuration for a specific use case"""
    name: str
    description: str
    start_location: Tuple[float, float]  # (lat, lng)
    end_location: Tuple[float, float]  # (lat, lng)
    start_location_name: str
    end_location_name: str
    expected_duration_hours: float  # Duración esperada del viaje
    lower_temp: float
    upper_temp: float
    distribution_type: Literal["normal", "beta", "truncnorm", "uniform"]
    transport_mode: Literal["driving-car", "foot-walking", "cycling-regular"] = "driving-car"
    # Parámetros específicos del caso
    temperature_profile: str = "stable"  # stable, increasing, decreasing, fluctuating
    number_of_stops: int = 3
    mean_temp: float = None
    std_dev: float = 5.0
    beta_alpha: float = 2.0
    beta_beta: float = 5.0


class OpenStreetMapRouter:
    """Cliente para obtener rutas reales usando OpenStreetMap / OpenRouteService"""
    
    def __init__(self):
        # Public OpenRouteService API (limit: 40 requests/min, 2000 requests/day)
        # Para producción, registrarse en https://openrouteservice.org/ para obtener una API key
        self.base_url = "https://api.openrouteservice.org/v2/directions"
        # Nota: Usar API key personal para mejor rate limit
        self.api_key = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjMwYWY3NzRhN2U1YjRkMWRhMDdhNDRmYzM4ZDBkMmYwIiwiaCI6Im11cm11cjY0In0="  # Usuario debe configurar su propia key
        
    def get_route(self, start: Tuple[float, float], end: Tuple[float, float], 
                  mode: str = "driving-car") -> Optional[Dict[str, Any]]:
        """
        Obtiene una ruta real entre dos puntos usando OpenRouteService
        
        Args:
            start: (lat, lng) punto de inicio
            end: (lat, lng) punto de destino
            mode: driving-car, foot-walking, cycling-regular
            
        Returns:
            Dict con información de la ruta o None si falla
        """
        # Si no hay API key, usar ruta lineal simple
        if not self.api_key:
            print("⚠️  No se configuró API key de OpenRouteService. Usando ruta lineal simple.")
            return self._get_simple_route(start, end)
        
        try:
            url = f"{self.base_url}/{mode}?api_key={self.api_key}&start={start[1]},{start[0]}&end={end[1]},{end[0]}"
            print(f"🌐 Obteniendo ruta: {url}")
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=100)
            
            if response.status_code == 200:
                data = response.json()
                if 'features' in data and len(data['features']) > 0:
                    feature = data['features'][0]
                    return {
                        'coordinates': [(coord[1], coord[0]) for coord in feature['geometry']['coordinates']],
                        'distance_km': feature['properties']['summary']['distance'] / 1000,
                        'duration_hours': feature['properties']['summary']['duration'] / 3600
                    }
            else:
                print(f"⚠️  Error en API OpenRouteService: {response.status_code}")
                return self._get_simple_route(start, end)
                
        except Exception as e:
            print(f"⚠️  Error obteniendo ruta: {e}")
            return self._get_simple_route(start, end)

    def get_route_multi(self, points: List[Tuple[float, float]], mode: str = "driving-car") -> Optional[Dict[str, Any]]:
        """Obtiene una ruta real pasando múltiples puntos usando POST API.
        
        Para múltiples waypoints, OpenRouteService requiere usar la API POST con JSON body.
        El formato GET solo soporta origen y destino (2 puntos).
        
        Fallback: genera una ruta simple segmentando entre puntos consecutivos.
        """
        if not points or len(points) < 2:
            return None

        if not self.api_key:
            return self._get_simple_route_multi(points)

        try:
            # Para múltiples waypoints, usar POST API
            url = f"{self.base_url}/{mode}/geojson"
            headers = {
                'Authorization': self.api_key,
                'Content-Type': 'application/json; charset=utf-8',
                'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8'
            }
            
            # Body con todas las coordenadas en formato [lng, lat]
            # Límite de OpenRouteService: 70 waypoints máximo
            if len(points) > 70:
                print(f"   ⚠️ Demasiados waypoints ({len(points)}), reduciendo a 70...")
                # Tomar muestras equidistantes
                indices = np.linspace(0, len(points) - 1, 70, dtype=int)
                sampled_points = [points[i] for i in indices]
                body = {
                    "coordinates": [[lng, lat] for (lat, lng) in sampled_points]
                }
            else:
                body = {
                    "coordinates": [[lng, lat] for (lat, lng) in points]
                }
            
            print(f"🌐 Obteniendo ruta multi-punto (POST): {url}")
            print(f"   Puntos: {len(points)}")
            
            response = requests.post(url, json=body, headers=headers, timeout=100)
            
            if response.status_code == 200:
                data = response.json()
                if 'features' in data and len(data['features']) > 0:
                    feature = data['features'][0]
                    coords = [(c[1], c[0]) for c in feature['geometry']['coordinates']]
                    distance_km = feature['properties']['summary']['distance'] / 1000
                    duration_hours = feature['properties']['summary']['duration'] / 3600
                    
                    print(f"   ✓ Ruta obtenida: {distance_km:.2f} km, {duration_hours:.2f} hrs")
                    
                    return {
                        'coordinates': coords,
                        'distance_km': distance_km,
                        'duration_hours': duration_hours
                    }
            else:
                print(f"⚠️  Error en API OpenRouteService (multi-POST): {response.status_code}")
                # Mostrar parte del cuerpo para diagnóstico
                try:
                    print(f"     Respuesta: {response.text[:300]}")
                except Exception:
                    pass

                # Fallback alternativo: intentar endpoint sin '/geojson'
                if response.status_code in (404, 405):
                    alt_url = f"{self.base_url}/{mode}"
                    print(f"   ↪️ Reintentando en endpoint alternativo: {alt_url}")
                    alt_headers = headers.copy()
                    alt_headers['Accept'] = 'application/json'
                    alt_resp = requests.post(alt_url, json=body, headers=alt_headers, timeout=100)
                    if alt_resp.status_code == 200:
                        data = alt_resp.json()
                        # Formato alternativo: routes[0].geometry.coordinates (lng, lat)
                        # Cubrimos ambos posibles formatos
                        coords = None
                        distance_km = None
                        duration_hours = None
                        if isinstance(data, dict):
                            if 'routes' in data and data['routes']:
                                r0 = data['routes'][0]
                                if 'geometry' in r0 and 'coordinates' in r0['geometry']:
                                    coords = [(c[1], c[0]) for c in r0['geometry']['coordinates']]
                                if 'summary' in r0:
                                    if 'distance' in r0['summary']:
                                        distance_km = r0['summary']['distance'] / 1000
                                    if 'duration' in r0['summary']:
                                        duration_hours = r0['summary']['duration'] / 3600
                            elif 'features' in data and data['features']:
                                feature = data['features'][0]
                                if 'geometry' in feature:
                                    coords = [(c[1], c[0]) for c in feature['geometry']['coordinates']]
                                if 'properties' in feature and 'summary' in feature['properties']:
                                    distance_km = feature['properties']['summary'].get('distance', 0) / 1000
                                    duration_hours = feature['properties']['summary'].get('duration', 0) / 3600
                        if coords:
                            distance_km = distance_km if distance_km is not None else 0.0
                            duration_hours = duration_hours if duration_hours is not None else 0.0
                            print(f"   ✓ Ruta obtenida (ALT): {distance_km:.2f} km, {duration_hours:.2f} hrs")
                            return {
                                'coordinates': coords,
                                'distance_km': distance_km,
                                'duration_hours': duration_hours
                            }
                        else:
                            print("   ⚠️ Formato de respuesta alternativo no reconocido")
                    else:
                        print(f"   ⚠️ Endpoint alternativo también falló: {alt_resp.status_code}")
                        try:
                            print(f"     Respuesta: {alt_resp.text[:300]}")
                        except Exception:
                            pass

                return self._get_simple_route_multi(points)
        except Exception as e:
            print(f"⚠️  Error obteniendo ruta (multi): {e}")
            return self._get_simple_route_multi(points)
    
    def _get_simple_route(self, start: Tuple[float, float], end: Tuple[float, float]) -> Dict[str, Any]:
        """Genera una ruta lineal simple entre dos puntos"""
        # Generar puntos intermedios
        num_points = 20
        coordinates = []
        for i in range(num_points):
            t = i / (num_points - 1)
            lat = start[0] + (end[0] - start[0]) * t
            lng = start[1] + (end[1] - start[1]) * t
            coordinates.append((lat, lng))
        
        # Calcular distancia aproximada
        distance_km = geodesic(start, end).kilometers
        # Asumir velocidad promedio de 60 km/h para driving
        duration_hours = distance_km / 60.0
        
        return {
            'coordinates': coordinates,
            'distance_km': distance_km,
            'duration_hours': duration_hours
        }

    def _get_simple_route_multi(self, points: List[Tuple[float, float]]) -> Dict[str, Any]:
        """Genera una ruta simple uniéndo líneas rectas entre puntos consecutivos"""
        all_coords: List[Tuple[float, float]] = []
        total_distance_km = 0.0
        for i in range(len(points) - 1):
            seg = self._get_simple_route(points[i], points[i + 1])
            if i > 0 and seg['coordinates']:
                # evitar duplicar el nodo de unión
                all_coords.extend(seg['coordinates'][1:])
            else:
                all_coords.extend(seg['coordinates'])
            total_distance_km += geodesic(points[i], points[i + 1]).kilometers
        # Asumir 60 km/h
        duration_hours = total_distance_km / 60.0 if total_distance_km > 0 else 0
        return {
            'coordinates': all_coords,
            'distance_km': total_distance_km,
            'duration_hours': duration_hours
        }
    
    def _decode_polyline(self, encoded: str, precision: int = 5) -> List[Tuple[float, float]]:
        """Decodifica una polyline codificada en formato Google/OpenRouteService.
        
        Args:
            encoded: String de polyline codificada
            precision: Precisión (5 para ORS, 6 para Google)
            
        Returns:
            Lista de tuplas (lat, lng)
        """
        coordinates = []
        index = 0
        lat = 0
        lng = 0
        
        while index < len(encoded):
            # Decodificar latitud
            result = 0
            shift = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlat = ~(result >> 1) if result & 1 else result >> 1
            lat += dlat
            
            # Decodificar longitud
            result = 0
            shift = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlng = ~(result >> 1) if result & 1 else result >> 1
            lng += dlng
            
            # Convertir a coordenadas
            coordinates.append((lat / 10**precision, lng / 10**precision))
        
        return coordinates
    
    def set_api_key(self, api_key: str):
        """Configura la API key de OpenRouteService"""
        self.api_key = api_key
    
    def get_alternative_routes(self, start: Tuple[float, float], end: Tuple[float, float], 
                              mode: str = "driving-car", num_alternatives: int = 3) -> List[Dict[str, Any]]:
        """
        Obtiene rutas alternativas usando el parámetro alternative_routes de OpenRouteService
        
        Args:
            start: (lat, lng) punto de inicio
            end: (lat, lng) punto de destino
            mode: driving-car, foot-walking, cycling-regular
            num_alternatives: número de rutas alternativas ADICIONALES a solicitar (1-3 recomendado)
                             El API siempre retorna la ruta principal como la primera ruta,
                             más las alternativas solicitadas. Total = 1 + num_alternatives
            
        Returns:
            Lista de diccionarios con información de rutas alternativas
            La primera ruta es la principal, las siguientes son alternativas
            Ejemplo: Si num_alternatives=2, retorna [principal, secondary-1, secondary-2]
        """
        if not self.api_key:
            print("⚠️  No se configuró API key de OpenRouteService. Retornando solo ruta principal.")
            main_route = self._get_simple_route(start, end)
            return [main_route] if main_route else []
        
        try:
            url = f"{self.base_url}/{mode}/json"
            headers = {
                'Authorization': self.api_key,
                'Content-Type': 'application/json'
            }
            
            # Body con coordenadas y parámetro alternative_routes
            # Nota: OpenRouteService requiere mínimo 2 rutas alternativas, sino da error 2018
            actual_alternatives = max(2, num_alternatives)
            body = {
                "coordinates": [[start[1], start[0]], [end[1], end[0]]],  # lng, lat
                "alternative_routes": {
                    "target_count": actual_alternatives,
                    "share_factor": 0.5,  # Rutas deben diferir al menos 50% (más flexible)
                    "weight_factor": 1.8   # Rutas pueden ser hasta 80% más largas (más flexible)
                },
                "geometry_simplify": False,  # No simplificar geometría
                "continue_straight": False
            }
            
            print(f"🌐 Solicitando ruta principal + {num_alternatives} rutas alternativas: {url}")
            
            response = requests.post(url, json=body, headers=headers, timeout=100)
            
            if response.status_code == 200:
                data = response.json()
                routes = []
                
                if 'routes' in data and len(data['routes']) > 0:
                    print(f"   ✓ API retornó {len(data['routes'])} ruta(s)")
                    
                    for idx, route in enumerate(data['routes']):
                        route_type = "principal" if idx == 0 else f"secondary-{idx}"
                        
                        # Extraer coordenadas (pueden venir codificadas)
                        coords = []
                        if 'geometry' in route:
                            # La geometría puede estar codificada en polyline
                            if isinstance(route['geometry'], str):
                                # Geometría codificada - decodificar polyline
                                print(f"   ⚠️ Geometría codificada para ruta {route_type}, decodificando...")
                                try:
                                    coords = self._decode_polyline(route['geometry'])
                                    print(f"   ✓ Decodificados {len(coords)} puntos")
                                except Exception as e:
                                    print(f"   ❌ Error decodificando: {e}")
                                    coords = []
                            elif isinstance(route['geometry'], dict) and 'coordinates' in route['geometry']:
                                coords = [(c[1], c[0]) for c in route['geometry']['coordinates']]
                            else:
                                coords = []
                        
                        # Si no hay coordenadas, usar coordenadas simples
                        if not coords:
                            coords = [start, end]
                        
                        route_info = {
                            'route_type': route_type,
                            'coordinates': coords,
                            'distance_km': route.get('summary', {}).get('distance', 0) / 1000,
                            'duration_hours': route.get('summary', {}).get('duration', 0) / 3600
                        }
                        
                        routes.append(route_info)
                        print(f"   ✓ Ruta {route_type}: {route_info['distance_km']:.2f} km, {route_info['duration_hours']:.2f} hrs")
                    
                    print(f"   📊 Total de rutas procesadas: {len(routes)}")
                
                if routes:
                    return routes
                else:
                    print("   ⚠️ No se encontraron rutas en la respuesta")
                    
            else:
                print(f"⚠️  Error en API OpenRouteService: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Response: {response.text[:300]}")
                    
        except Exception as e:
            print(f"⚠️  Error obteniendo rutas alternativas: {e}")
        
        # Fallback: retornar solo la ruta principal
        main_route = self.get_route(start, end, mode)
        if main_route:
            main_route['route_type'] = 'principal'
            return [main_route]
        return []


class PredefinedUseCases:
    """Casos de uso predefinidos con rutas y escenarios dramatizados"""
    
    @staticmethod
    def get_case_1_pharmaceutical_cold_chain() -> UseCaseConfig:
        """
        CASO 1: Cadena de Frío Farmacéutica - Transporte de Vacunas
        Ruta: Ciudad de México → Guadalajara (aprox. 6 horas)
        Dramatización: Monitoreo crítico de vacunas COVID-19 que requieren -20°C
        """
        return UseCaseConfig(
            name="Cadena Frío Farmacéutica",
            description="Transporte crítico de vacunas que requieren temperatura ultra-baja (-25°C a -15°C)",
            start_location=(19.4326, -99.1332),  # Ciudad de México
            end_location=(20.6597, -103.3496),  # Guadalajara
            start_location_name="CDMX - Almacén Farmacéutico",
            end_location_name="Guadalajara - Hospital Central",
            expected_duration_hours=6.5,
            lower_temp=-25.0,
            upper_temp=-15.0,
            distribution_type="normal",
            transport_mode="driving-car",
            temperature_profile="stable",  # Debe mantenerse estable
            number_of_stops=2,  # Paradas en casetas
            mean_temp=-20.0,
            std_dev=2.5  # Poca variación
        )
    
    @staticmethod
    def get_case_2_perishable_food() -> UseCaseConfig:
        """
        CASO 2: Alimentos Perecederos - Transporte de Mariscos Frescos
        Ruta: Puerto de Veracruz → Ciudad de México (aprox. 5 horas)
        Dramatización: Mariscos frescos que deben mantenerse entre 0°C y 4°C
        """
        return UseCaseConfig(
            name="Alimentos Perecederos",
            description="Transporte de mariscos frescos desde puerto con monitoreo estricto (0°C a 4°C)",
            start_location=(19.1738, -96.1342),  # Veracruz (Puerto)
            end_location=(19.4326, -99.1332),  # Ciudad de México
            start_location_name="Veracruz - Puerto Pesquero",
            end_location_name="CDMX - Mercado Central",
            expected_duration_hours=5.0,
            lower_temp=0.0,
            upper_temp=4.0,
            distribution_type="beta",
            transport_mode="driving-car",
            temperature_profile="increasing",  # Tiende a aumentar durante el viaje
            number_of_stops=3,
            beta_alpha=2.0,
            beta_beta=8.0  # Sesgo hacia temperaturas bajas
        )
    
    @staticmethod
    def get_case_3_industrial_chemicals() -> UseCaseConfig:
        """
        CASO 3: Químicos Industriales - Transporte de Sustancias Termosensibles
        Ruta: Monterrey → Querétaro (aprox. 7 horas)
        Dramatización: Químicos que NO deben exceder 30°C ni bajar de 10°C
        """
        return UseCaseConfig(
            name="Químicos Industriales",
            description="Transporte de reactivos químicos termosensibles (10°C a 30°C)",
            start_location=(25.6866, -100.3161),  # Monterrey
            end_location=(20.5888, -100.3899),  # Querétaro
            start_location_name="Monterrey - Planta Química",
            end_location_name="Querétaro - Laboratorio Industrial",
            expected_duration_hours=7.0,
            lower_temp=10.0,
            upper_temp=30.0,
            distribution_type="normal",
            transport_mode="driving-car",
            temperature_profile="fluctuating",  # Fluctúa por condiciones ambientales
            number_of_stops=4,
            mean_temp=20.0,
            std_dev=6.0  # Mayor variación
        )
    
    @staticmethod
    def get_all_cases() -> List[UseCaseConfig]:
        """Retorna todos los casos de uso predefinidos"""
        return [
            PredefinedUseCases.get_case_1_pharmaceutical_cold_chain(),
            PredefinedUseCases.get_case_2_perishable_food(),
            PredefinedUseCases.get_case_3_industrial_chemicals()
        ]


class LogSimulator:
    def __init__(self, config: LogGeneratorInput):
        self.config = config
        self.temperatures = []
        self.timestamps = []
        self.coordinates = []
        self.route_info = None
        self.osm_router = OpenStreetMapRouter()
        
    @classmethod
    def from_use_case(cls, use_case: UseCaseConfig, epc: str, tid: str, 
                     start_timestamp: str = None, use_real_route: bool = False):
        """Crea un LogSimulator a partir de un caso de uso predefinido"""
        
        if start_timestamp is None:
            start_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Calcular número de muestras basado en duración esperada
        # Usar intervalos de 5 minutos (300 segundos) para viajes largos
        log_interval = 300  # 5 minutos
        number_of_samples = int((use_case.expected_duration_hours * 3600) / log_interval)
        
        config = LogGeneratorInput(
            epc=epc,
            tid=tid,
            log_interval_in_seconds=log_interval,
            number_of_samples=number_of_samples,
            start_timestamp=start_timestamp,
            lower_temp=use_case.lower_temp,
            upper_temp=use_case.upper_temp,
            start_lat=use_case.start_location[0],
            start_lng=use_case.start_location[1],
            end_lat=use_case.end_location[0],
            end_lng=use_case.end_location[1],
            number_of_stops=use_case.number_of_stops,
            distribution_type=use_case.distribution_type,
            mean_temp=use_case.mean_temp,
            std_dev=use_case.std_dev,
            beta_alpha=use_case.beta_alpha,
            beta_beta=use_case.beta_beta,
            use_real_route=use_real_route,
            route_name=use_case.name
        )
        
        return cls(config)

    @classmethod
    def from_waypoints(
        cls,
        epc: str,
        tid: str,
        waypoints: List[Tuple[float, float]],
        *,
        start_timestamp: Optional[str] = None,
        lower_temp: float = 0.0,
        upper_temp: float = 10.0,
    distribution_type: Literal["normal", "beta", "truncnorm", "uniform"] = "normal",
        mean_temp: Optional[float] = None,
        std_dev: float = 5.0,
        beta_alpha: float = 2.0,
        beta_beta: float = 5.0,
        log_interval_in_seconds: int = 300,
        number_of_samples: Optional[int] = None,
        use_real_route: bool = False,
        transport_mode: Literal["driving-car", "foot-walking", "cycling-regular"] = "driving-car",
        route_name: str = "Ruta Personalizada",
        segment_profiles: Optional[List["TempProfile"]] = None,
    ):
        """Crea un LogSimulator a partir de una lista de puntos (origen + paradas + destino final).

        Si number_of_samples no se proporciona, se estima con base en la duración de la ruta
        (real si use_real_route=True, o asumida a 60 km/h) y el log_interval_in_seconds.
        """
        if not waypoints or len(waypoints) < 2:
            raise ValueError("Se requieren al menos 2 puntos: origen y un destino/parada")

        if start_timestamp is None:
            start_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

        # Estimar duración para definir muestras si no fue especificado
        est_number_of_samples = number_of_samples
        if number_of_samples is None:
            router = OpenStreetMapRouter()
            if use_real_route:
                info = router.get_route_multi(waypoints, mode=transport_mode)
            else:
                info = router._get_simple_route_multi(waypoints)
            duration_hours = (info['duration_hours'] if info else 0) or 1.0
            duration_seconds = max(1, int(duration_hours * 3600))
            # Asegurar al menos 2 muestras (inicio y fin)
            est_number_of_samples = max(2, int(duration_seconds / log_interval_in_seconds) + 1)

        config = LogGeneratorInput(
            epc=epc,
            tid=tid,
            log_interval_in_seconds=log_interval_in_seconds,
            number_of_samples=est_number_of_samples,
            start_timestamp=start_timestamp,
            lower_temp=lower_temp,
            upper_temp=upper_temp,
            start_lat=waypoints[0][0],
            start_lng=waypoints[0][1],
            end_lat=waypoints[-1][0],
            end_lng=waypoints[-1][1],
            number_of_stops=max(0, len(waypoints) - 2),
            distribution_type=distribution_type,
            waypoints=waypoints,
            transport_mode=transport_mode,
            mean_temp=mean_temp,
            std_dev=std_dev,
            beta_alpha=beta_alpha,
            beta_beta=beta_beta,
            use_real_route=use_real_route,
            route_name=route_name,
            segment_profiles=segment_profiles,
        )

        return cls(config)
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parsea timestamp ISO a datetime"""
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    
    
    def _generate_temperatures_normal(self) -> List[float]:
        """Genera temperaturas usando distribución normal"""
        mean = self.config.mean_temp if self.config.mean_temp is not None else (
            self.config.lower_temp + self.config.upper_temp) / 2
        
        temps = []
        for _ in range(self.config.number_of_samples):
            temp = np.random.normal(mean, self.config.std_dev)
            # Aplicar límites suaves
            temp = np.clip(temp, self.config.lower_temp - 10, self.config.upper_temp + 10)
            temps.append(round(float(temp), 1))
        
        return temps
    
    def _generate_temperatures_beta(self) -> List[float]:
        """Genera temperaturas usando distribución beta"""
        temps = []
        temp_range = self.config.upper_temp - self.config.lower_temp + 20  # +20 para permitir exceder límites
        
        for _ in range(self.config.number_of_samples):
            # Beta distribution genera valores entre 0 y 1
            beta_value = np.random.beta(self.config.beta_alpha, self.config.beta_beta)
            # Escalar al rango de temperaturas
            temp = self.config.lower_temp - 10 + (beta_value * temp_range)
            temps.append(round(float(temp), 1))
        
        return temps

    def _generate_temperatures_truncnorm(self) -> List[float]:
        """Genera temperaturas con Normal truncada en [lower, upper]."""
        lower = self.config.lower_temp
        upper = self.config.upper_temp
        mean = self.config.mean_temp if self.config.mean_temp is not None else (lower + upper) / 2
        std = max(1e-6, self.config.std_dev)
        a = (lower - mean) / std
        b = (upper - mean) / std
        vals = stats.truncnorm.rvs(a, b, loc=mean, scale=std, size=self.config.number_of_samples)
        return [round(float(v), 1) for v in vals]

    def _generate_temperatures_uniform(self) -> List[float]:
        """Genera temperaturas uniformes en [lower, upper]."""
        lower = self.config.lower_temp
        upper = self.config.upper_temp
        vals = np.random.uniform(lower, upper, size=self.config.number_of_samples)
        return [round(float(v), 1) for v in vals]
    
    def _generate_temperatures(self) -> List[float]:
        """Genera temperaturas según configuración global o por segmentos si está disponible."""
        # Si hay perfiles por segmento y hay waypoints, usar generación segmentada
        if (
            self.config.segment_profiles
            and self.config.waypoints
            and len(self.config.waypoints) >= 2
            and self.coordinates
            and len(self.coordinates) == self.config.number_of_samples
        ):
            return self._generate_temperatures_segmented()

        if self.config.distribution_type == "normal":
            return self._generate_temperatures_normal()
        elif self.config.distribution_type == "beta":
            return self._generate_temperatures_beta()
        elif self.config.distribution_type == "truncnorm":
            return self._generate_temperatures_truncnorm()
        elif self.config.distribution_type == "uniform":
            return self._generate_temperatures_uniform()
        else:
            raise ValueError(f"Tipo de distribución no soportado: {self.config.distribution_type}")

    def _generate_temperatures_segmented(self) -> List[float]:
        """Genera temperaturas por tramos (entre waypoints) usando perfiles específicos por segmento.

        Mapea los índices de muestras a segmentos encontrando, sobre las coordenadas interpoladas,
        los índices más cercanos a cada waypoint y asignando los rangos consecutivos.
        """
        num_samples = self.config.number_of_samples
        coords = self.coordinates
        waypoints = self.config.waypoints or []
        num_segments = max(0, len(waypoints) - 1)

        # Normalizar perfiles: si faltan, completar con configuración global
        profiles: List[TempProfile] = []
        for i in range(num_segments):
            if self.config.segment_profiles and i < len(self.config.segment_profiles) and self.config.segment_profiles[i]:
                profiles.append(self.config.segment_profiles[i])
            else:
                profiles.append(TempProfile(
                    lower_temp=self.config.lower_temp,
                    upper_temp=self.config.upper_temp,
                    distribution_type=self.config.distribution_type,
                    mean_temp=self.config.mean_temp,
                    std_dev=self.config.std_dev,
                    beta_alpha=self.config.beta_alpha,
                    beta_beta=self.config.beta_beta,
                ))

        # Obtener mapeo muestras->segmento
        mapping = self._compute_sample_segment_mapping()
        sample_to_seg = mapping["sample_to_segment"] if mapping else None

        temps: List[float] = [0.0] * num_samples

        # Generador auxiliar por perfil
        def _smooth(vals: List[float], phi: float = 0.8) -> List[float]:
            if not vals:
                return vals
            out = [vals[0]]
            alpha = 1.0 - phi
            for v in vals[1:]:
                out.append(phi * out[-1] + alpha * v)
            return [round(float(x), 1) for x in out]

        def gen_for_profile(n: int, prof: TempProfile) -> List[float]:
            if n <= 0:
                return []
            if prof.distribution_type == "normal":
                mean = prof.mean_temp if prof.mean_temp is not None else (prof.lower_temp + prof.upper_temp) / 2
                vals = np.random.normal(mean, prof.std_dev, size=n)
                vals = np.clip(vals, prof.lower_temp - 10, prof.upper_temp + 10)
                out = [round(float(v), 1) for v in vals]
                return _smooth(out) if prof.apply_ar1 else out
            elif prof.distribution_type == "beta":
                temp_range = prof.upper_temp - prof.lower_temp + 20
                beta_vals = np.random.beta(prof.beta_alpha, prof.beta_beta, size=n)
                vals = prof.lower_temp - 10 + (beta_vals * temp_range)
                out = [round(float(v), 1) for v in vals]
                return _smooth(out) if prof.apply_ar1 else out
            elif prof.distribution_type == "truncnorm":
                mean = prof.mean_temp if prof.mean_temp is not None else (prof.lower_temp + prof.upper_temp) / 2
                std = max(1e-6, prof.std_dev)
                a = (prof.lower_temp - mean) / std
                b = (prof.upper_temp - mean) / std
                vals = stats.truncnorm.rvs(a, b, loc=mean, scale=std, size=n)
                out = [round(float(v), 1) for v in vals]
                return _smooth(out) if prof.apply_ar1 else out
            elif prof.distribution_type == "uniform":
                vals = np.random.uniform(prof.lower_temp, prof.upper_temp, size=n)
                out = [round(float(v), 1) for v in vals]
                return _smooth(out) if prof.apply_ar1 else out
            else:
                raise ValueError(f"Tipo de distribución no soportado en segmento: {prof.distribution_type}")

        # Asignar por segmentos usando el mapeo de muestras
        if sample_to_seg is not None:
            # Construir índices por segmento
            seg_indices: List[List[int]] = [[] for _ in range(num_segments)]
            for i, seg in enumerate(sample_to_seg):
                if seg is not None and 0 <= seg < num_segments:
                    seg_indices[seg].append(i)
            # Generar y asignar
            for seg in range(num_segments):
                idxs = seg_indices[seg]
                if not idxs:
                    continue
                seg_temps = gen_for_profile(len(idxs), profiles[seg])
                for k, idx in enumerate(idxs):
                    temps[idx] = seg_temps[k]
        else:
            # Fallback al corte por distancia si no hay mapeo
            # Encontrar índices aproximados de cada waypoint dentro de las coordenadas interpoladas
            def nearest_index(target: Tuple[float, float]) -> int:
                min_d = float('inf')
                min_i = 0
                for i, c in enumerate(coords):
                    d = geodesic((c[0], c[1]), (target[0], target[1])).meters
                    if d < min_d:
                        min_d = d
                        min_i = i
                return min_i

            wp_indices = [nearest_index(wp) for wp in waypoints]
            # Asegurar orden no decreciente y cubrir extremos
            wp_indices[0] = 0
            wp_indices[-1] = num_samples - 1
            for i in range(1, len(wp_indices)):
                if wp_indices[i] <= wp_indices[i-1]:
                    wp_indices[i] = min(num_samples - 1, wp_indices[i-1] + 1)

            for seg in range(num_segments):
                start_i = wp_indices[seg]
                end_i = wp_indices[seg + 1]
                length = max(1, end_i - start_i + (1 if seg == num_segments - 1 else 0))
                seg_temps = gen_for_profile(length, profiles[seg])
                for k, val in enumerate(seg_temps):
                    idx = start_i + k
                    if idx >= num_samples:
                        break
                    temps[idx] = val

        # Rellenar posibles huecos por redondeos
        for i in range(num_samples):
            if temps[i] == 0.0:
                # Usar valor vecino más cercano si existe, o global normal
                if i > 0 and temps[i-1] != 0.0:
                    temps[i] = temps[i-1]
                else:
                    mean = self.config.mean_temp if self.config.mean_temp is not None else (
                        self.config.lower_temp + self.config.upper_temp) / 2
                    temps[i] = round(float(np.random.normal(mean, self.config.std_dev)), 1)

        return temps

    def _compute_sample_segment_mapping(self) -> Optional[Dict[str, Any]]:
        """Calcula indices de waypoints y mapeo de cada muestra a su segmento.

        Devuelve dict con:
        - 'wp_indices': lista de índices de muestra más cercanos a cada waypoint
        - 'sample_to_segment': lista de tamaño num_samples con índice de segmento por muestra
        """
        if not (self.config.waypoints and len(self.config.waypoints) >= 2 and self.coordinates):
            return None
        num_samples = self.config.number_of_samples
        waypoints = self.config.waypoints
        coords = self.coordinates
        num_segments = len(waypoints) - 1

        # Encontrar índices aproximados de cada waypoint 
        def nearest_index(target: Tuple[float, float]) -> int:
            min_d = float('inf')
            min_i = 0
            for i, c in enumerate(coords):
                d = geodesic((c[0], c[1]), (target[0], target[1])).meters
                if d < min_d:
                    min_d = d
                    min_i = i
            return min_i

        wp_indices = [nearest_index(wp) for wp in waypoints]
        wp_indices[0] = 0
        wp_indices[-1] = num_samples - 1
        for i in range(1, len(wp_indices)):
            if wp_indices[i] <= wp_indices[i-1]:
                wp_indices[i] = min(num_samples - 1, wp_indices[i-1] + 1)

        # Construir mapeo muestras->segmento
        sample_to_seg: List[Optional[int]] = [None] * num_samples
        for seg in range(num_segments):
            start_i = wp_indices[seg]
            end_i = wp_indices[seg + 1]
            last_inclusive = end_i if seg == num_segments - 1 else end_i - 1
            for idx in range(start_i, last_inclusive + 1):
                if 0 <= idx < num_samples:
                    sample_to_seg[idx] = seg

        # Guardar en instancia para reutilizar
        self._wp_indices = wp_indices
        self._sample_segment_idx = sample_to_seg
        return {"wp_indices": wp_indices, "sample_to_segment": sample_to_seg}
    
    def _interpolate_coordinates(self) -> List[tuple]:
        # Interpola coordenadas para N muestras usando ruta real o simple
        # Si hay waypoints definidos, se priorizan
        if self.config.waypoints and len(self.config.waypoints) >= 2:
            if self.config.use_real_route:
                route = self.osm_router.get_route_multi(self.config.waypoints, mode=self.config.transport_mode)
            else:
                route = self.osm_router._get_simple_route_multi(self.config.waypoints)

            if route:
                self.route_info = route
                route_coords = route['coordinates']
                return self._interpolate_route_points(route_coords, self.config.number_of_samples)

        # Sin waypoints explícitos, usar start/end
        if self.config.use_real_route:
            route = self.osm_router.get_route(
                (self.config.start_lat, self.config.start_lng),
                (self.config.end_lat, self.config.end_lng),
                mode=self.config.transport_mode,
            )
            if route:
                self.route_info = route
                route_coords = route['coordinates']
                return self._interpolate_route_points(route_coords, self.config.number_of_samples)
        
        # Ruta lineal simple (fallback) entre start/end
        coordinates = []
        total_points = self.config.number_of_samples
        
        # Generar puntos de parada aleatorios
        stop_indices = sorted(random.sample(range(1, total_points - 1), 
                                           min(self.config.number_of_stops, max(0, total_points - 2))))
        
        lat_diff = self.config.end_lat - self.config.start_lat
        lng_diff = self.config.end_lng - self.config.start_lng
        
        for i in range(total_points):
            # Si está en una parada, usar las coordenadas anteriores
            if i > 0 and i in stop_indices:
                coordinates.append(coordinates[-1])
            else:
                progress = i / (total_points - 1) if total_points > 1 else 0
                lat = self.config.start_lat + (lat_diff * progress)
                lng = self.config.start_lng + (lng_diff * progress)
                coordinates.append((round(lat, 6), round(lng, 6)))
        
        return coordinates
    
    def _interpolate_route_points(self, route_points: List[Tuple[float, float]], 
                                 num_samples: int) -> List[Tuple[float, float]]:
        # Interpola puntos de una ruta para obtener el número deseado de muestras
        if len(route_points) == num_samples:
            return route_points
        
        # Calcular distancias acumuladas
        distances = [0]
        for i in range(1, len(route_points)):
            dist = geodesic(route_points[i-1], route_points[i]).meters
            distances.append(distances[-1] + dist)
        
        total_distance = distances[-1]
        
        # Generar muestras equidistantes
        interpolated = []
        for i in range(num_samples):
            target_dist = (i / (num_samples - 1)) * total_distance if num_samples > 1 else 0
            
            # Encontrar segmento correspondiente
            for j in range(len(distances) - 1):
                if distances[j] <= target_dist <= distances[j + 1]:
                    # Interpolación lineal en el segmento
                    segment_progress = (target_dist - distances[j]) / (distances[j + 1] - distances[j]) if distances[j + 1] != distances[j] else 0
                    lat = route_points[j][0] + (route_points[j + 1][0] - route_points[j][0]) * segment_progress
                    lng = route_points[j][1] + (route_points[j + 1][1] - route_points[j][1]) * segment_progress
                    interpolated.append((round(lat, 6), round(lng, 6)))
                    break
        
        return interpolated if interpolated else route_points
    
    def _generate_inventories(self, num_inventories: int = 2) -> List[Dict[str, Any]]:
        # Genera lecturas de inventario RFID
        inventories = []
        start_dt = self._parse_timestamp(self.config.start_timestamp)
        
        for i in range(num_inventories):
            timestamp = start_dt + timedelta(seconds=i * 5)
            inventory = {
                "readerTimestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "readerHost": f"FX9600{random.randint(100000, 999999):X}",
                "readerMAC": ":".join([f"{random.randint(0, 255):02X}" for _ in range(6)]),
                "readerLatitude": round(self.config.start_lat, 2),
                "readerLongitude": round(self.config.start_lng, 2),
                "readerAccuracyInMeters": round(random.uniform(10.0, 20.0), 1),
                "readerChannel": random.choice([905250, 912250, 915250]),
                "readerRSSI": round(random.uniform(-60.0, -50.0), 1),
                "tagPacketPC": "3F00",
                "tagXPC_W1": "0424",
                "tagTemperatureInC": round(random.uniform(self.config.lower_temp, self.config.upper_temp), 1),
                "tagBatteryPresent": True,
                "tagBatteryVoltage": round(random.uniform(3.0, 3.2), 2),
                "tagSensorCode": random.randint(100, 130),
                "tagOnChipRSSI": random.randint(10, 20),
                "loggerState": "LOGGING",
                "loggerRtc": (start_dt - timedelta(seconds=random.randint(10, 20))).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "loggerNextSample": random.randint(10, 20)
            }
            inventories.append(inventory)
        
        return inventories
    
    def _check_alarms(self, temperatures: List[float]) -> Dict[str, Any]:
        # Determina si hay alarmas basadas en temperaturas
        # Si hay perfiles por segmento, evaluar cada muestra con su perfil
        sample_to_seg = getattr(self, "_sample_segment_idx", None)
        profiles = self.config.segment_profiles if self.config.segment_profiles else None

        def bounds_for_sample(i: int) -> Tuple[float, float]:
            if profiles and sample_to_seg is not None and i < len(sample_to_seg):
                seg = sample_to_seg[i]
                if seg is not None and 0 <= seg < len(profiles) and profiles[seg]:
                    return profiles[seg].lower_temp, profiles[seg].upper_temp
            return self.config.lower_temp, self.config.upper_temp

        has_low = False
        has_high = False
        for i, t in enumerate(temperatures):
            low_b, high_b = bounds_for_sample(i)
            if t < low_b:
                has_low = True
            if t > high_b:
                has_high = True
        has_temp_alarm = has_low or has_high
        
        alarm_temp_value = None
        alarm_timestamp = None
        
        if has_temp_alarm:
            # Encontrar primera temperatura fuera de rango con límites por segmento
            for i, temp in enumerate(temperatures):
                low_b, high_b = bounds_for_sample(i)
                if temp < low_b or temp > high_b:
                    alarm_temp_value = temp
                    start_dt = self._parse_timestamp(self.config.start_timestamp)
                    alarm_timestamp = (start_dt + timedelta(seconds=i * self.config.log_interval_in_seconds)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                    break
        
        return {
            "alarmAny": has_temp_alarm,
            "alarmTemperature": has_temp_alarm,
            "alarmLowTemperature": has_low,
            "alarmHighTemperature": has_high,
            "alarmTamper": False,
            "alarmLowBattery": False,
            "alarmInitialBattery": False,
            "alarmTemperatureTimestamp": alarm_timestamp,
            "alarmTemperatureValue": alarm_temp_value,
            "alarmTamperTimestamp": None,
            "alarmBatteryTimestamp": None
        }
    
    def generate(self) -> Dict[str, Any]:
        # Genera el JSON completo de simulación
        start_dt = self._parse_timestamp(self.config.start_timestamp)
        # Primero calcular coordenadas, luego temperaturas (algunas configuraciones dependen de segmentos)
        self.coordinates = self._interpolate_coordinates()
        self.temperatures = self._generate_temperatures()
        
        # Generar timestamps y loggedData
        logged_data = []
        self.timestamps = []
        
        for i in range(self.config.number_of_samples):
            timestamp = start_dt + timedelta(seconds=i * self.config.log_interval_in_seconds)
            self.timestamps.append(timestamp)
            temp_val = self.temperatures[i]
            # Tamper por muestra: True si excede límites (por tramo si aplica), False en caso contrario
            low_b, high_b = self._bounds_for_sample(i)
            tamper_flag = True if (temp_val < low_b or temp_val > high_b) else False
            logged_data.append({
                "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tempInC": temp_val,
                "tamper": tamper_flag
            })
        
        # Generar estructura completa
        result = {
            "version": "1.1.0",
            "EPC": self.config.epc,
            "TID": self.config.tid,
            "inventories": self._generate_inventories(),
            "configuration": {
                "logIntervalInSeconds": self.config.log_interval_in_seconds,
                "logDelayedStartInSamples": 1,
                "logNumberOfSamples": self.config.number_of_samples,
                "temperatureLowerLimit": self.config.lower_temp,
                "temperatureLowerLimitAlarmDelay": 1,
                "temperatureUpperLimit": self.config.upper_temp,
                "temperatureUpperLimitAlarmDelay": 1,
                "ledEnabled": True,
                "ledMode": "ON_DEMAND",
                "ledOffTimeInSeconds": 2,
                "ledOnTimeInMilliseconds": 50,
                "fingerSpotEnabled": True,
                "fingerSpotForLoggerArming": False,
                "antiTamperEnabled": False,
                "antiTamperpolarity": "DETECT_CONNECTION_OR_LIGHT"
            },
            "arming": {
                "armStatus": "SUCCESSFUL",
                "armErrorNumber": 0,
                "armErrorMessage": None,
                "armTimestamp": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "armFingerSpotTimestamp": None
            },
            "alarms": self._check_alarms(self.temperatures),
            "loggedData": logged_data
        }
        
        return result
    
    def generate_json_string(self, indent: int = 2) -> str:
        # Genera el JSON como string formateado
        return json.dumps(self.generate(), indent=indent)
    
    def save_to_file(self, filename: str, indent: int = 2):
        # Guarda el JSON en un archivo
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.generate(), f, indent=indent)

    def compute_segment_stats(self) -> List[Dict[str, Any]]:
        """Calcula estadísticas observadas por tramo (entre waypoints) sobre las temperaturas generadas.

        Retorna una lista de dicts con:
        - segment (int): índice del tramo
        - from_waypoint / to_waypoint: coordenadas (lat, lng)
        - sample_start / sample_end: rango de índices de muestra asignados al tramo
        - sample_count (int)
        - observed_min / observed_max / observed_mean / observed_std (float)
        - configured: límites y distribución configurados para el tramo
        """
        stats_list: List[Dict[str, Any]] = []
        # Asegurar que existan datos
        if not self.temperatures:
            return stats_list
        # Asegurar mapeo de muestras a segmento
        mapping = getattr(self, "_sample_segment_idx", None)
        if mapping is None:
            m = self._compute_sample_segment_mapping()
            mapping = m["sample_to_segment"] if m else None
        sample_to_seg = mapping
        waypoints = self.config.waypoints or [(self.config.start_lat, self.config.start_lng), (self.config.end_lat, self.config.end_lng)]
        num_segments = max(0, len(waypoints) - 1)

        # Normalizar perfiles: si no hay, usar global
        profiles: List[TempProfile] = []
        for i in range(num_segments):
            if self.config.segment_profiles and i < len(self.config.segment_profiles) and self.config.segment_profiles[i]:
                profiles.append(self.config.segment_profiles[i])
            else:
                profiles.append(TempProfile(
                    lower_temp=self.config.lower_temp,
                    upper_temp=self.config.upper_temp,
                    distribution_type=self.config.distribution_type,
                    mean_temp=self.config.mean_temp,
                    std_dev=self.config.std_dev,
                    beta_alpha=self.config.beta_alpha,
                    beta_beta=self.config.beta_beta,
                ))

        # Construir índices por segmento
        seg_indices: List[List[int]] = [[] for _ in range(num_segments)]
        if sample_to_seg is not None:
            for i, seg in enumerate(sample_to_seg):
                if seg is not None and 0 <= seg < num_segments:
                    seg_indices[seg].append(i)
        else:
            # si no hay mapeo, asignar todo al único tramo (si existe)
            if num_segments == 1:
                seg_indices[0] = list(range(len(self.temperatures)))

        # Calcular estadísticas
        for seg in range(num_segments):
            idxs = seg_indices[seg]
            temps = [self.temperatures[i] for i in idxs] if idxs else []
            observed_min = float(min(temps)) if temps else None
            observed_max = float(max(temps)) if temps else None
            observed_mean = float(np.mean(temps)) if temps else None
            observed_std = float(np.std(temps)) if temps else None
            sample_start = int(min(idxs)) if idxs else None
            sample_end = int(max(idxs)) if idxs else None
            from_wp = waypoints[seg]
            to_wp = waypoints[seg + 1]
            prof = profiles[seg]
            stats_list.append({
                "segment": seg,
                "from_waypoint": {"lat": from_wp[0], "lng": from_wp[1]},
                "to_waypoint": {"lat": to_wp[0], "lng": to_wp[1]},
                "sample_start": sample_start,
                "sample_end": sample_end,
                "sample_count": len(idxs),
                "observed_min": observed_min,
                "observed_max": observed_max,
                "observed_mean": observed_mean,
                "observed_std": observed_std,
                "configured": {
                    "lower_temp": prof.lower_temp,
                    "upper_temp": prof.upper_temp,
                    "distribution_type": prof.distribution_type,
                    "mean_temp": prof.mean_temp,
                    "std_dev": prof.std_dev,
                    "beta_alpha": prof.beta_alpha,
                    "beta_beta": prof.beta_beta,
                }
            })

        return stats_list
    
    def _bounds_for_sample(self, i: int) -> Tuple[float, float]:
        """Obtiene límites inferior/superior aplicables a la muestra i, usando perfiles por tramo si existen."""
        sample_to_seg = getattr(self, "_sample_segment_idx", None)
        profiles = self.config.segment_profiles if self.config.segment_profiles else None
        if profiles and sample_to_seg is not None and i < len(sample_to_seg):
            seg = sample_to_seg[i]
            if seg is not None and 0 <= seg < len(profiles) and profiles[seg]:
                return profiles[seg].lower_temp, profiles[seg].upper_temp
        return self.config.lower_temp, self.config.upper_temp

    def generate_map(self, output_file: str = "route_map.html"):
        # Genera un mapa interactivo de la ruta con OpenStreetMap
        if not self.coordinates or not self.temperatures:
            raise ValueError("Primero debe generar los datos usando generate()")
        
        # Crear mapa centrado en el punto medio
        center_lat = (self.config.start_lat + self.config.end_lat) / 2
        center_lng = (self.config.start_lng + self.config.end_lng) / 2
        
        m = folium.Map(location=[center_lat, center_lng], zoom_start=7)
        
        # Intelligent markers based on waypoints
        if self.config.waypoints and len(self.config.waypoints) >= 2:
            # ORIGIN marker (first waypoint) - Green
            folium.Marker(
                [self.config.waypoints[0][0], self.config.waypoints[0][1]],
                popup=f"<b>🟢 Origin</b><br>{self.config.route_name}",
                icon=folium.Icon(color='green', icon='play')
            ).add_to(m)
            
            # INTERMEDIATE STOPS markers (middle waypoints) - Blue
            if len(self.config.waypoints) > 2:
                for idx, (lat, lng) in enumerate(self.config.waypoints[1:-1], start=1):
                    folium.Marker(
                        [lat, lng],
                        popup=f"<b>🔵 Stop {idx}</b>",
                        icon=folium.Icon(color='blue', icon='flag')
                    ).add_to(m)
            
            # DESTINATION marker (last waypoint) - Red
            folium.Marker(
                [self.config.waypoints[-1][0], self.config.waypoints[-1][1]],
                popup=f"<b>🔴 Final Destination</b><br>{self.config.route_name}",
                icon=folium.Icon(color='red', icon='stop')
            ).add_to(m)
        else:
            # Fallback if no waypoints defined (use start/end)
            folium.Marker(
                [self.config.start_lat, self.config.start_lng],
                popup=f"<b>Start</b><br>{self.config.route_name}",
                icon=folium.Icon(color='green', icon='play')
            ).add_to(m)
            
            folium.Marker(
                [self.config.end_lat, self.config.end_lng],
                popup=f"<b>End</b><br>{self.config.route_name}",
                icon=folium.Icon(color='red', icon='stop')
            ).add_to(m)

        
        # Asegurar mapeo de segmentos para coloreo por tramo si aplica
        if not hasattr(self, "_sample_segment_idx"):
            self._compute_sample_segment_mapping()

        # Agregar línea de ruta con colores según temperatura y límites por tramo
        for i in range(len(self.coordinates) - 1):
            temp = self.temperatures[i]
            low_b, high_b = self._bounds_for_sample(i)
            # Determinar color según temperatura vs límites del tramo
            color = 'green'
            if temp < low_b:
                color = 'blue'
            elif temp > high_b:
                color = 'red'
            
            folium.PolyLine(
                [self.coordinates[i], self.coordinates[i + 1]],
                color=color,
                weight=4,
                opacity=0.7,
                popup=f"Temp: {temp}°C<br>Time: {self.timestamps[i].strftime('%H:%M')}"
            ).add_to(m)
        
        # Agregar marcadores de temperatura cada N puntos
        sample_interval = max(1, len(self.coordinates) // 10)
        for i in range(0, len(self.coordinates), sample_interval):
            if i > 0 and i < len(self.coordinates) - 1:
                temp = self.temperatures[i]
                low_b, high_b = self._bounds_for_sample(i)
                color = 'green'
                if temp < low_b:
                    color = 'blue'
                elif temp > high_b:
                    color = 'red'
                
                folium.CircleMarker(
                    location=self.coordinates[i],
                    radius=5,
                    popup=f"<b>Sample {i}</b><br>Temp: {temp}°C<br>Time: {self.timestamps[i].strftime('%H:%M:%S')}",
                    color=color,
                    fill=True,
                    fillColor=color
                ).add_to(m)
        
        # Guardar mapa
        m.save(output_file)
        print(f"✓ Mapa interactivo guardado: {output_file}")
        
        return m
    
    def plot_results(self, save_path: str = None):
        # Genera gráficas completas de los resultados
        if not self.temperatures or not self.timestamps:
            raise ValueError("Primero debe generar los datos usando generate()")
        
        fig = plt.figure(figsize=(18, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # 1. Temperatura vs Tiempo
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(self.timestamps, self.temperatures, marker='o', linestyle='-', linewidth=2, markersize=4, color='#2E86AB')
        ax1.axhline(y=self.config.lower_temp, color='blue', linestyle='--', linewidth=2, label=f'Lower limit ({self.config.lower_temp}°C)', alpha=0.7)
        ax1.axhline(y=self.config.upper_temp, color='red', linestyle='--', linewidth=2, label=f'Upper limit ({self.config.upper_temp}°C)', alpha=0.7)
        ax1.fill_between(self.timestamps, self.config.lower_temp, self.config.upper_temp, alpha=0.2, color='green', label='Safe range')
        
        # Marcar violaciones
        violations_low = [(self.timestamps[i], self.temperatures[i]) for i in range(len(self.temperatures)) if self.temperatures[i] < self.config.lower_temp]
        violations_high = [(self.timestamps[i], self.temperatures[i]) for i in range(len(self.temperatures)) if self.temperatures[i] > self.config.upper_temp]
        
        if violations_low:
            ax1.scatter([v[0] for v in violations_low], [v[1] for v in violations_low], 
                       color='blue', s=100, marker='v', zorder=5, label='Low violation')
        if violations_high:
            ax1.scatter([v[0] for v in violations_high], [v[1] for v in violations_high], 
                       color='red', s=100, marker='^', zorder=5, label='High violation')
        
        ax1.set_xlabel('Time', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Temperature (°C)', fontsize=12, fontweight='bold')
        ax1.set_title(f'Temperature Monitoring - {self.config.route_name}\nEPC: {self.config.epc}', 
                     fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.legend(loc='best')
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # 2. Histograma y Distribución
        ax2 = fig.add_subplot(gs[1, 0])
        counts, bins, patches = ax2.hist(self.temperatures, bins=25, density=True, alpha=0.7, 
                                        color='skyblue', edgecolor='black', linewidth=1.2)
        
        # Colorear barras según rango
        for i, patch in enumerate(patches):
            temp = (bins[i] + bins[i+1]) / 2
            if temp < self.config.lower_temp:
                patch.set_facecolor('lightblue')
            elif temp > self.config.upper_temp:
                patch.set_facecolor('lightcoral')
            else:
                patch.set_facecolor('lightgreen')
        
        # Overlay de la distribución teórica
        x_range = np.linspace(min(self.temperatures), max(self.temperatures), 100)
        if self.config.distribution_type == "normal":
            mean = np.mean(self.temperatures)
            std = np.std(self.temperatures)
            pdf = stats.norm.pdf(x_range, mean, std)
            ax2.plot(x_range, pdf, 'r-', linewidth=3, label=f'Normal(μ={mean:.1f}, σ={std:.1f})')
        elif self.config.distribution_type == "beta":
            temp_min = min(self.temperatures)
            temp_max = max(self.temperatures)
            if temp_max != temp_min:
                x_normalized = (x_range - temp_min) / (temp_max - temp_min)
                pdf_normalized = stats.beta.pdf(x_normalized, self.config.beta_alpha, self.config.beta_beta)
                pdf = pdf_normalized / (temp_max - temp_min)
                ax2.plot(x_range, pdf, 'r-', linewidth=3, label=f'Beta(α={self.config.beta_alpha}, β={self.config.beta_beta})')
        
        ax2.axvline(x=self.config.lower_temp, color='blue', linestyle='--', linewidth=2, alpha=0.7)
        ax2.axvline(x=self.config.upper_temp, color='red', linestyle='--', linewidth=2, alpha=0.7)
        ax2.set_xlabel('Temperature (°C)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Density', fontsize=11, fontweight='bold')
        ax2.set_title('Temperature Distribution', fontsize=12, fontweight='bold')
        ax2.legend()
        ax2.grid(True, alpha=0.3, linestyle='--')
        
        # 3. Box Plot
        ax3 = fig.add_subplot(gs[1, 1])
        box = ax3.boxplot(self.temperatures, vert=True, patch_artist=True, 
                         boxprops=dict(facecolor='lightblue', linewidth=2),
                         whiskerprops=dict(linewidth=2),
                         capprops=dict(linewidth=2),
                         medianprops=dict(color='darkblue', linewidth=2))
        ax3.axhline(y=self.config.lower_temp, color='blue', linestyle='--', linewidth=2, label='Lower limit', alpha=0.7)
        ax3.axhline(y=self.config.upper_temp, color='red', linestyle='--', linewidth=2, label='Upper limit', alpha=0.7)
        ax3.set_ylabel('Temperature (°C)', fontsize=11, fontweight='bold')
        ax3.set_title('Temperature Box Plot', fontsize=12, fontweight='bold')
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 4. Q-Q Plot (para validar distribución)
        ax4 = fig.add_subplot(gs[1, 2])
        if self.config.distribution_type == "normal":
            stats.probplot(self.temperatures, dist="norm", plot=ax4)
            ax4.set_title('Q-Q Plot (Normal)', fontsize=12, fontweight='bold')
        else:
            # Para beta, normalizar primero
            temp_normalized = [(t - min(self.temperatures)) / (max(self.temperatures) - min(self.temperatures)) 
                              for t in self.temperatures]
            stats.probplot(temp_normalized, dist="beta", sparams=(self.config.beta_alpha, self.config.beta_beta), plot=ax4)
            ax4.set_title('Q-Q Plot (Beta)', fontsize=12, fontweight='bold')
        ax4.grid(True, alpha=0.3, linestyle='--')
        
        # 5. Mapa de Ruta
        ax5 = fig.add_subplot(gs[2, 0])
        lats = [coord[0] for coord in self.coordinates]
        lngs = [coord[1] for coord in self.coordinates]
        
        # Normalizar temperaturas para mapa de color
        norm = plt.Normalize(vmin=min(self.temperatures), vmax=max(self.temperatures))
        scatter = ax5.scatter(lngs, lats, c=self.temperatures, cmap='RdYlBu_r', s=80, 
                            edgecolors='black', linewidth=0.5, norm=norm, zorder=3)
        ax5.plot(lngs, lats, 'k--', alpha=0.3, linewidth=1.5, zorder=1)
        ax5.plot(lngs[0], lats[0], 'go', markersize=18, label='Start', 
                markeredgecolor='black', markeredgewidth=2, zorder=4)
        ax5.plot(lngs[-1], lats[-1], 'rs', markersize=18, label='End', 
                markeredgecolor='black', markeredgewidth=2, zorder=4)
        ax5.set_xlabel('Longitude', fontsize=11, fontweight='bold')
        ax5.set_ylabel('Latitude', fontsize=11, fontweight='bold')
        ax5.set_title('Route and Temperatures', fontsize=12, fontweight='bold')
        ax5.legend()
        ax5.grid(True, alpha=0.3, linestyle='--')
        cbar = plt.colorbar(scatter, ax=ax5)
        cbar.set_label('Temperatura (°C)', fontsize=10, fontweight='bold')
        
        # 6. Estadísticas
        ax6 = fig.add_subplot(gs[2, 1:])
        ax6.axis('off')
        
        # Calcular duración total
        duration_hours = (self.timestamps[-1] - self.timestamps[0]).total_seconds() / 3600
        
        # Calcular distancia aproximada
        total_distance = sum(geodesic(self.coordinates[i], self.coordinates[i+1]).kilometers 
                           for i in range(len(self.coordinates)-1))
        
        violations_count = len(violations_low) + len(violations_high)
        compliance_rate = ((len(self.temperatures) - violations_count) / len(self.temperatures)) * 100

        # Formatted text (avoid triple-quoted f-strings for better compatibility)
        interval_line = f"Sampling interval: {self.config.log_interval_in_seconds}s ({self.config.log_interval_in_seconds/60:.1f} min)"
        sep = "=" * 70
        line_sep = "─" * 70
        lines = [
            sep,
            f"SIMULATION REPORT - {self.config.route_name}",
            sep,
            "",
            "CONFIGURATION",
            line_sep,
            f"Distribution: {self.config.distribution_type.upper()}",
            f"Total samples: {self.config.number_of_samples}",
            interval_line,
            f"Total duration: {duration_hours:.2f} hours",
            f"Approximate distance: {total_distance:.2f} km",
            "",
            "TEMPERATURES",
            line_sep,
            f"Mean: {np.mean(self.temperatures):.2f}°C",
            f"Median: {np.median(self.temperatures):.2f}°C",
            f"Standard Deviation: {np.std(self.temperatures):.2f}°C",
            f"Minimum: {min(self.temperatures):.2f}°C",
            f"Maximum: {max(self.temperatures):.2f}°C",
            f"Allowed range: [{self.config.lower_temp}°C, {self.config.upper_temp}°C]",
            "",
            "ALARMS AND COMPLIANCE",
            line_sep,
            f"⚠️  Total violations: {violations_count} ({(violations_count/len(self.temperatures)*100):.1f}%)",
            f"❄️  Temperatures below limit: {len(violations_low)}",
            f"🔥 Temperatures above limit: {len(violations_high)}",
            f"✓  Compliance rate: {compliance_rate:.1f}%",
            "",
            "ROUTE",
            line_sep,
            f"Origin: ({self.config.start_lat:.4f}, {self.config.start_lng:.4f})",
            f"Destination: ({self.config.end_lat:.4f}, {self.config.end_lng:.4f})",
            f"Scheduled stops: {self.config.number_of_stops}",
            "",
            f"EPC: {self.config.epc}",
            f"TID: {self.config.tid}",
            sep,
        ]
        stats_text = "\n".join(lines)
        
        ax6.text(0.05, 0.95, stats_text, transform=ax6.transAxes, 
                fontsize=9, verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.6, pad=1))
        
        plt.suptitle(f'COMPLETE ANALYSIS - {self.config.route_name.upper()}', 
                    fontsize=16, fontweight='bold', y=0.995)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✓ Gráfica guardada: {save_path}")
        
        plt.show()


class BatchSimulator:
    # Clase para generar múltiples JSONs en lote
    
    @staticmethod
    def generate_all_use_cases(output_dir: str = "use_cases_output", 
                              use_real_routes: bool = False,
                              plot_individual: bool = True) -> List[Dict[str, Any]]:
        # Genera simulaciones para todos los casos de uso predefinidos
        
        os.makedirs(output_dir, exist_ok=True)
        
        use_cases = PredefinedUseCases.get_all_cases()
        results = []
        simulators = []
        
        print("\n" + "="*80)
        print("GENERACIÓN DE CASOS DE USO - SIMULADOR DE CADENA DE FRÍO")
        print("="*80)
        
        for i, use_case in enumerate(use_cases, 1):
            print(f"\n{'─'*80}")
            print(f"CASO {i}: {use_case.name}")
            print(f"{'─'*80}")
            print(f"Descripción: {use_case.description}")
            print(f"Ruta: {use_case.start_location_name} → {use_case.end_location_name}")
            print(f"Duración estimada: {use_case.expected_duration_hours:.1f} horas")
            print(f"Rango de temperatura: [{use_case.lower_temp}°C, {use_case.upper_temp}°C]")
            print(f"Distribución: {use_case.distribution_type}")
            
            # Generar EPC y TID únicos
            epc = f"5201F250300{i:05d}"
            tid = f"E2C24500200005668{i:07d}"
            
            # Crear simulador
            simulator = LogSimulator.from_use_case(
                use_case=use_case,
                epc=epc,
                tid=tid,
                use_real_route=use_real_routes
            )
            
            # Generar datos
            data = simulator.generate()
            results.append(data)
            simulators.append(simulator)
            
            # Guardar JSON
            json_filename = f"{output_dir}/case_{i}_{use_case.name.replace(' ', '_').lower()}.json"
            simulator.save_to_file(json_filename)
            print(f"✓ JSON guardado: {json_filename}")
            
            # Generar mapa interactivo
            map_filename = f"{output_dir}/map_case_{i}_{use_case.name.replace(' ', '_').lower()}.html"
            simulator.generate_map(map_filename)
            
            # Generar gráficas individuales
            if plot_individual:
                plot_filename = f"{output_dir}/plot_case_{i}_{use_case.name.replace(' ', '_').lower()}.png"
                simulator.plot_results(save_path=plot_filename)
        
        print(f"\n{'='*80}")
        print(f"✓ COMPLETADO: {len(results)} casos de uso generados en '{output_dir}'")
        print(f"{'='*80}\n")
        
        return results, simulators


# Ejemplo de uso principal
if __name__ == "__main__":
    print("\n" + "🚚 " * 30)
    print("SIMULADOR DE MONITOREO DE CADENA DE FRÍO CON RFID")
    print("Sistema de generación de datos parametrizados con OpenStreetMap")
    print("🚚 " * 30 + "\n")
    
    # Opción 1: Generar todos los casos de uso predefinidos
    results, simulators = BatchSimulator.generate_all_use_cases(
        output_dir="use_cases_output",
        use_real_routes=False,  # Cambiar a True si tienes API key de OpenRouteService
        plot_individual=True
    )
    
    print("\n✅ Simulación completada exitosamente!")
    print(f"📊 Revisa los resultados en la carpeta 'use_cases_output'")
    print(f"📁 Se generaron {len(results)} archivos JSON")
    print(f"🗺️  Se generaron {len(results)} mapas interactivos HTML")
    print(f"📈 Se generaron {len(results)} gráficas de análisis PNG")