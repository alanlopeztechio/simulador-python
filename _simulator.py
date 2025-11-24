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
    # start_lat: float
    # start_lng: float
    # end_lat: float
    # end_lng: float
    # number_of_stops: int
    rutas: List[Tuple[float, float]]
    distribution_type: Literal["normal", "beta"] = "normal"
    # Parámetros para distribución normal
    mean_temp: float = None  # Si es None, se usa el promedio de lower y upper
    std_dev: float = 5.0
    # Parámetros para distribución beta
    beta_alpha: float = 2.0
    beta_beta: float = 5.0
    # Ruta real usando OpenStreetMap
    use_real_route: bool = False
    route_name: str = "Custom Route"


@dataclass
class UseCaseConfig:
    """Configuración para un caso de uso específico"""
    name: str
    description: str
    # Campos obligatorios principales (sin valores por defecto)
    lower_temp: float
    upper_temp: float
    distribution_type: Literal["normal", "beta"]

    # Campos opcionales con valores por defecto
    transport_mode: Literal["driving-car", "foot-walking", "cycling-regular"] = "driving-car"
    # Parámetros específicos del caso
    temperature_profile: str = "stable"  # stable, increasing, decreasing, fluctuating
    number_of_stops: int = 3
    mean_temp: float = None
    std_dev: float = 5.0
    beta_alpha: float = 2.0
    beta_beta: float = 5.0

    # Campos opcionales (compatibilidad con versiones previas)
    start_location: Optional[Tuple[float, float]] = None  # (lat, lng)
    end_location: Optional[Tuple[float, float]] = None  # (lat, lng)
    start_location_name: str = ""
    end_location_name: str = ""
    expected_duration_hours: float = 0.0  # Duración esperada del viaje
    rutas: List[Tuple[float, float]] = field(default_factory=list)

class OpenStreetMapRouter:
    """Cliente para obtener rutas reales usando OpenStreetMap / OpenRouteService"""
   
    def __init__(self):
        # API pública de OpenRouteService (límite: 40 requests/min, 2000 requests/day)
        # Para producción, registrarse en https://openrouteservice.org/ para obtener una API key
        self.base_url = "https://api.openrouteservice.org/v2/directions"
        # Nota: Usar API key personal para mejor rate limit
        self.api_key = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjU4ZDhkZGI0MGY3ZDQ4Mzc4MTI2M2Y0MWY2YzRhMGMxIiwiaCI6Im11cm11cjY0In0="  # Usuario debe configurar su propia key
       
    def get_route(self, start: Tuple[float, float], end: Tuple[float, float],
                  mode: str = "driving-car") -> Optional[Dict[str, Any]]:
        """
        Obtiene una ruta real entre dos puntos usando D
       
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
            print(url)
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
   
    def set_api_key(self, api_key: str):
        """Configura la API key de OpenRouteService"""
        self.api_key = api_key

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
            # start_location=(19.4326, -99.1332),  # Ciudad de México
            # end_location=(20.6597, -103.3496),  # Guadalajara
            # start_location_name="CDMX - Almacén Farmacéutico",
            # end_location_name="Guadalajara - Hospital Central",
            # expected_duration_hours=6.5,
            lower_temp=-25.0,
            upper_temp=-15.0,
            distribution_type="normal",
            transport_mode="driving-car",
            temperature_profile="stable",  # Debe mantenerse estable
            number_of_stops=2,  # Paradas en casetas
            mean_temp=-20.0,
            std_dev=2.5,  # Poca variación
            rutas=[(19.4326, -99.1332), (19.7045, -100.5230), (20.6597, -103.3496)]
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
            # start_location_name="Veracruz - Puerto Pesquero",
            # end_location_name="CDMX - Mercado Central",
            # expected_duration_hours=5.0,
            lower_temp=0.0,
            upper_temp=4.0,
            distribution_type="beta",
            transport_mode="driving-car",
            temperature_profile="increasing",  # Tiende a aumentar durante el viaje
            number_of_stops=3,
            beta_alpha=2.0,
            beta_beta=8.0,  # Sesgo hacia temperaturas bajas
            rutas=[(19.1738, -96.1342), (19.4326, -99.1332), (19.7045, -100.5230)]
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
            std_dev=6.0, # Mayor variación
            rutas=[(19.1738, -96.1342), (19.4326, -99.1332), (19.7045, -100.5230)]
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
        # Asegurar al menos 1 muestra si expected_duration_hours no está definido o es 0
        number_of_samples = max(1, int((use_case.expected_duration_hours * 3600) / log_interval))
        
        # Construir la lista de vértices (rutas) a partir del caso de uso.
        # Preferir `use_case.rutas` si está definido, si no, caer a start/end si existen.
        if getattr(use_case, "rutas", None):
            rutas_list = use_case.rutas
        else:
            # Compatibilidad: si el caso de uso todavía tuviera start/end (no usual), convertir a rutas
            try:
                rutas_list = [use_case.start_location, use_case.end_location]
            except Exception:
                rutas_list = []

        config = LogGeneratorInput(
            epc=epc,
            tid=tid,
            log_interval_in_seconds=log_interval,
            number_of_samples=number_of_samples,
            start_timestamp=start_timestamp,
            lower_temp=use_case.lower_temp,
            upper_temp=use_case.upper_temp,
            distribution_type=use_case.distribution_type,
            mean_temp=use_case.mean_temp,
            std_dev=use_case.std_dev,
            beta_alpha=use_case.beta_alpha,
            beta_beta=use_case.beta_beta,
            use_real_route=use_real_route,
            route_name=use_case.name,
            rutas=rutas_list
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
    
    def _generate_temperatures(self) -> List[float]:
        """Genera temperaturas según el tipo de distribución seleccionado"""
        if self.config.distribution_type == "normal":
            return self._generate_temperatures_normal()
        elif self.config.distribution_type == "beta":
            return self._generate_temperatures_beta()
        else:
            raise ValueError(f"Tipo de distribución no soportado: {self.config.distribution_type}")
    
    def _interpolate_coordinates(self) -> List[tuple]:
        """Interpola coordenadas siguiendo la secuencia de puntos en self.config.rutas.
        Si use_real_route = True intenta obtener cada segmento A->B, B->C, ... desde OSM.
        Une los segmentos (evitando duplicar vértices) y finalmente interpola para
        devolver exactamente number_of_samples coordenadas.
        Si falla la obtención de ruta real, cae a una ruta lineal que une los puntos dados.
        """
        rutas = getattr(self.config, "rutas", None) or []
        num_samples = max(1, self.config.number_of_samples)

        # Si se pidió ruta real y hay al menos dos puntos, solicitar cada segmento
        if self.config.use_real_route and len(rutas) >= 2:
            full_coords: List[Tuple[float, float]] = []
            segments_info = []

            for i in range(len(rutas) - 1):
                start_pt = rutas[i]
                end_pt = rutas[i + 1]
                try:
                    route = self.osm_router.get_route(start_pt, end_pt, mode=getattr(self.config, "transport_mode", "driving-car"))
                except Exception:
                    route = None

                if route and "coordinates" in route and route["coordinates"]:
                    seg_coords = route["coordinates"]
                    segments_info.append(route)
                else:
                    # Fallback simple straight segment (get_route ya hace fallback, pero por seguridad)
                    seg_coords = self.osm_router._get_simple_route(start_pt, end_pt)["coordinates"]
                    segments_info.append({"coordinates": seg_coords, "distance_km": geodesic(start_pt, end_pt).kilometers})

                # Evitar duplicar el punto de unión entre segmentos
                if full_coords and seg_coords and full_coords[-1] == seg_coords[0]:
                    full_coords.extend(seg_coords[1:])
                else:
                    full_coords.extend(seg_coords)

            # Guardar info de ruta compuesta
            self.route_info = {
                "segments": segments_info,
                "coordinates": full_coords
            }

            # Si ya tenemos suficientes puntos, tomar índices equidistantes
            if len(full_coords) >= num_samples:
                indices = np.linspace(0, len(full_coords) - 1, num_samples, dtype=int)
                return [full_coords[i] for i in indices]
            # Si no, interpolar sobre la ruta completa para obtener exactamente num_samples
            return self._interpolate_route_points(full_coords, num_samples)

        # Fallback (no use_real_route): construir ruta poligonal que une todos los puntos de rutas
        if len(rutas) >= 2:
            # Usar las rutas como vértices de una polyline y luego interpolar a num_samples
            poly_coords: List[Tuple[float, float]] = []
            for pt in rutas:
                poly_coords.append((round(pt[0], 6), round(pt[1], 6)))
            return self._interpolate_route_points(poly_coords, num_samples)

        # Si sólo hay un punto (parada única), repetir ese punto num_samples veces
        if len(rutas) == 1:
            pt = rutas[0]
            return [(round(pt[0], 6), round(pt[1], 6)) for _ in range(num_samples)]

        # Si no hay forma de construir ruta, retornar lista vacía
        return []
    
    def _interpolate_route_points(self, route_points: List[Tuple[float, float]], 
                                 num_samples: int) -> List[Tuple[float, float]]:
        """Interpola puntos de una ruta para obtener el número deseado de muestras"""
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
        """Genera lecturas de inventario RFID"""
        inventories = []
        start_dt = self._parse_timestamp(self.config.start_timestamp)
        
        for i in range(num_inventories):
            timestamp = start_dt + timedelta(seconds=i * 5)
            inventory = {
                "readerTimestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "readerHost": f"FX9600{random.randint(100000, 999999):X}",
                "readerMAC": ":".join([f"{random.randint(0, 255):02X}" for _ in range(6)]),
                "readerLatitude": round(self.config.rutas[0][0], 2) if getattr(self.config, 'rutas', None) else 0.0,
                "readerLongitude": round(self.config.rutas[0][1], 2) if getattr(self.config, 'rutas', None) else 0.0,
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
        """Determina si hay alarmas basadas en temperaturas"""
        has_low = any(t < self.config.lower_temp for t in temperatures)
        has_high = any(t > self.config.upper_temp for t in temperatures)
        has_temp_alarm = has_low or has_high
        
        alarm_temp_value = None
        alarm_timestamp = None
        
        if has_temp_alarm:
            # Encontrar primera temperatura fuera de rango
            for i, temp in enumerate(temperatures):
                if temp < self.config.lower_temp or temp > self.config.upper_temp:
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
        """Genera el JSON completo de simulación"""
        start_dt = self._parse_timestamp(self.config.start_timestamp)
        self.temperatures = self._generate_temperatures()
        self.coordinates = self._interpolate_coordinates()
        
        # Generar timestamps y loggedData
        logged_data = []
        self.timestamps = []
        
        for i in range(self.config.number_of_samples):
            timestamp = start_dt + timedelta(seconds=i * self.config.log_interval_in_seconds)
            self.timestamps.append(timestamp)
            logged_data.append({
                "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tempInC": self.temperatures[i],
                "tamper": False
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
        """Genera el JSON como string formateado"""
        return json.dumps(self.generate(), indent=indent)
    
    def save_to_file(self, filename: str, indent: int = 2):
        """Guarda el JSON en un archivo"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.generate(), f, indent=indent)
    
    def generate_map(self, output_file: str = "route_map.html"):
        """Genera un mapa interactivo de la ruta con OpenStreetMap"""
        if not self.coordinates or not self.temperatures:
            raise ValueError("Primero debe generar los datos usando generate()")
        
        # Crear mapa centrado en el punto medio de las paradas si están disponibles
        if getattr(self.config, 'rutas', None) and len(self.config.rutas) > 0:
            lats = [p[0] for p in self.config.rutas]
            lngs = [p[1] for p in self.config.rutas]
            center_lat = sum(lats) / len(lats)
            center_lng = sum(lngs) / len(lngs)
        else:
            # Fallback: centrar en la media de coordenadas ya generadas
            center_lat = sum([c[0] for c in self.coordinates]) / len(self.coordinates)
            center_lng = sum([c[1] for c in self.coordinates]) / len(self.coordinates)

        m = folium.Map(location=[center_lat, center_lng], zoom_start=7)

        # Agregar marcadores de inicio y fin basados en `rutas` si existen
        if getattr(self.config, 'rutas', None) and len(self.config.rutas) > 0:
            start_pt = self.config.rutas[0]
            end_pt = self.config.rutas[-1]
            folium.Marker(
                [start_pt[0], start_pt[1]],
                popup=f"<b>Inicio</b><br>{self.config.route_name}",
                icon=folium.Icon(color='green', icon='play')
            ).add_to(m)

            folium.Marker(
                [end_pt[0], end_pt[1]],
                popup=f"<b>Fin</b><br>{self.config.route_name}",
                icon=folium.Icon(color='red', icon='stop')
            ).add_to(m)
        
        # Agregar línea de ruta con colores según temperatura
        for i in range(len(self.coordinates) - 1):
            temp = self.temperatures[i]
            
            # Determinar color según temperatura
            if temp < self.config.lower_temp:
                color = 'blue'
            elif temp > self.config.upper_temp:
                color = 'red'
            else:
                color = 'green'
            
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
                color = 'blue' if temp < self.config.lower_temp else ('red' if temp > self.config.upper_temp else 'green')
                
                folium.CircleMarker(
                    location=self.coordinates[i],
                    radius=5,
                    popup=f"<b>Muestra {i}</b><br>Temp: {temp}°C<br>Hora: {self.timestamps[i].strftime('%H:%M:%S')}",
                    color=color,
                    fill=True,
                    fillColor=color
                ).add_to(m)
        
        # Guardar mapa
        m.save(output_file)
        print(f"✓ Mapa interactivo guardado: {output_file}")
        
        return m
    
    def plot_results(self, save_path: str = None):
        """Genera gráficas completas de los resultados"""
        if not self.temperatures or not self.timestamps:
            raise ValueError("Primero debe generar los datos usando generate()")
        
        fig = plt.figure(figsize=(18, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # 1. Temperatura vs Tiempo
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(self.timestamps, self.temperatures, marker='o', linestyle='-', linewidth=2, markersize=4, color='#2E86AB')
        ax1.axhline(y=self.config.lower_temp, color='blue', linestyle='--', linewidth=2, label=f'Límite inferior ({self.config.lower_temp}°C)', alpha=0.7)
        ax1.axhline(y=self.config.upper_temp, color='red', linestyle='--', linewidth=2, label=f'Límite superior ({self.config.upper_temp}°C)', alpha=0.7)
        ax1.fill_between(self.timestamps, self.config.lower_temp, self.config.upper_temp, alpha=0.2, color='green', label='Rango seguro')
        
        # Marcar violaciones
        violations_low = [(self.timestamps[i], self.temperatures[i]) for i in range(len(self.temperatures)) if self.temperatures[i] < self.config.lower_temp]
        violations_high = [(self.timestamps[i], self.temperatures[i]) for i in range(len(self.temperatures)) if self.temperatures[i] > self.config.upper_temp]
        
        if violations_low:
            ax1.scatter([v[0] for v in violations_low], [v[1] for v in violations_low], 
                       color='blue', s=100, marker='v', zorder=5, label='Violación baja')
        if violations_high:
            ax1.scatter([v[0] for v in violations_high], [v[1] for v in violations_high], 
                       color='red', s=100, marker='^', zorder=5, label='Violación alta')
        
        ax1.set_xlabel('Tiempo', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Temperatura (°C)', fontsize=12, fontweight='bold')
        ax1.set_title(f'Monitoreo de Temperatura - {self.config.route_name}\nEPC: {self.config.epc}', 
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
        ax2.set_xlabel('Temperatura (°C)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Densidad', fontsize=11, fontweight='bold')
        ax2.set_title('Distribución de Temperaturas', fontsize=12, fontweight='bold')
        ax2.legend()
        ax2.grid(True, alpha=0.3, linestyle='--')
        
        # 3. Box Plot
        ax3 = fig.add_subplot(gs[1, 1])
        ax3.boxplot(self.temperatures, vert=True, patch_artist=True,
                    boxprops=dict(facecolor='lightblue', linewidth=2),
                    whiskerprops=dict(linewidth=2),
                    capprops=dict(linewidth=2),
                    medianprops=dict(color='darkblue', linewidth=2))
        ax3.axhline(y=self.config.lower_temp, color='blue', linestyle='--', linewidth=2, label='Límite inferior', alpha=0.7)
        ax3.axhline(y=self.config.upper_temp, color='red', linestyle='--', linewidth=2, label='Límite superior', alpha=0.7)
        ax3.set_ylabel('Temperatura (°C)', fontsize=11, fontweight='bold')
        ax3.set_title('Box Plot de Temperaturas', fontsize=12, fontweight='bold')
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis='y', linestyle='--')

        # 4. Q-Q Plot (para validar distribución)
        ax4 = fig.add_subplot(gs[1, 2])
        if self.config.distribution_type == "normal":
            stats.probplot(self.temperatures, dist="norm", plot=ax4)
            ax4.set_title('Q-Q Plot (Normal)', fontsize=12, fontweight='bold')
        else:
            # Para beta, normalizar primero evitando división por cero
            temp_min = min(self.temperatures)
            temp_max = max(self.temperatures)
            if temp_max != temp_min:
                temp_normalized = [(t - temp_min) / (temp_max - temp_min) for t in self.temperatures]
            else:
                # Si todas las temperaturas son iguales, usar 0.5 para todos los valores normalizados
                temp_normalized = [0.5 for _ in self.temperatures]
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
        ax5.plot(lngs[0], lats[0], 'go', markersize=18, label='Inicio', 
                markeredgecolor='black', markeredgewidth=2, zorder=4)
        ax5.plot(lngs[-1], lats[-1], 'rs', markersize=18, label='Fin', 
                markeredgecolor='black', markeredgewidth=2, zorder=4)
        ax5.set_xlabel('Longitud', fontsize=11, fontweight='bold')
        ax5.set_ylabel('Latitud', fontsize=11, fontweight='bold')
        ax5.set_title('Ruta y Temperaturas', fontsize=12, fontweight='bold')
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

        # Preparar información de origen/destino a partir de rutas
        if getattr(self.config, 'rutas', None) and len(self.config.rutas) > 0:
            origin_lat, origin_lng = self.config.rutas[0]
            dest_lat, dest_lng = self.config.rutas[-1]
            num_paradas = len(self.config.rutas)
        else:
            origin_lat = origin_lng = dest_lat = dest_lng = float('nan')
            num_paradas = 0

        stats_text = f"""
        {'='*70}
        REPORTE DE SIMULACIÓN - {self.config.route_name}
        {'='*70}
        
        CONFIGURACIÓN
        {'─'*70}
        Distribución: {self.config.distribution_type.upper()}
        Muestras totales: {self.config.number_of_samples}
        Intervalo de muestreo: {self.config.log_interval_in_seconds}s ({self.config.log_interval_in_seconds/60:.1f} min)
        Duración total: {duration_hours:.2f} horas
        Distancia aproximada: {total_distance:.2f} km
        
        TEMPERATURAS
        {'─'*70}
        Media: {np.mean(self.temperatures):.2f}°C
        Mediana: {np.median(self.temperatures):.2f}°C
        Desviación Estándar: {np.std(self.temperatures):.2f}°C
        Mínima: {min(self.temperatures):.2f}°C
        Máxima: {max(self.temperatures):.2f}°C
        Rango permitido: [{self.config.lower_temp}°C, {self.config.upper_temp}°C]
        
        ALARMAS Y CUMPLIMIENTO
        {'─'*70}
        ⚠️  Violaciones totales: {violations_count} ({(violations_count/len(self.temperatures)*100):.1f}%)
        ❄️  Temperaturas bajo límite: {len(violations_low)}
        🔥 Temperaturas sobre límite: {len(violations_high)}
        ✓  Tasa de cumplimiento: {compliance_rate:.1f}%
        
    RUTA
        {'─'*70}
    Origen: ({origin_lat:.4f}, {origin_lng:.4f})
    Destino: ({dest_lat:.4f}, {dest_lng:.4f})
    Paradas programadas: {num_paradas}
        
        EPC: {self.config.epc}
        TID: {self.config.tid}
        {'='*70}
        """
        
        ax6.text(0.05, 0.95, stats_text, transform=ax6.transAxes, 
                fontsize=9, verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.6, pad=1))
        
        plt.suptitle(f'ANÁLISIS COMPLETO - {self.config.route_name.upper()}', 
                    fontsize=16, fontweight='bold', y=0.995)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✓ Gráfica guardada: {save_path}")
        
        plt.show()


class BatchSimulator:
    """Clase para generar múltiples JSONs en lote"""
    
    @staticmethod
    def generate_all_use_cases(output_dir: str = "use_cases_output", 
                              use_real_routes: bool = False,
                              plot_individual: bool = True) -> List[Dict[str, Any]]:
        """Genera simulaciones para todos los casos de uso predefinidos"""
        
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
    print("📊 Revisa los resultados en la carpeta 'use_cases_output'")
    print(f"📁 Se generaron {len(results)} archivos JSON")
    print(f"🗺️  Se generaron {len(results)} mapas interactivos HTML")
    print(f"📈 Se generaron {len(results)} gráficas de análisis PNG")