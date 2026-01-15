"""
Route configuration with rich metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import List, Optional, Tuple
import json
from .segment import SegmentMetadata
from .sensor import SensorConfig


@dataclass
class RoutePoint:
    """A point along the route (origin, waypoint, or destination)."""
    name: str
    latitude: float
    longitude: float
    point_type: str  # "origin", "waypoint", "destination"
    timestamp: Optional[datetime] = None  # Departure/arrival time
    
    def to_tuple(self) -> Tuple[float, float]:
        """Convert to (lat, lng) tuple."""
        return (self.latitude, self.longitude)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'point_type': self.point_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary."""
        timestamp = None
        if data.get('timestamp'):
            timestamp = datetime.fromisoformat(data['timestamp'])
        return cls(
            name=data['name'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            point_type=data['point_type'],
            timestamp=timestamp
        )


@dataclass
class RouteConfig:
    """Complete route configuration with metadata.
    
    This is the primary data structure for the new UI workflow,
    bundling route geometry, segment metadata, distributions, and sensors.
    """
    # Route metadata
    route_name: str
    route_description: str = ""
    company_id: Optional[int] = None  # Link to company
    id: Optional[int] = None  # Database ID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Route points (ordered)
    origin: RoutePoint = None
    destination: RoutePoint = None
    waypoints: List[RoutePoint] = field(default_factory=list)  # Intermediate stops
    
    # Segment configurations (one per leg between consecutive points)
    segments: List[SegmentMetadata] = field(default_factory=list)
    
    # Associated sensors
    sensors: List[SensorConfig] = field(default_factory=list)
    
    # Simulation parameters
    log_interval_seconds: int = 300  # 5 minutes
    use_real_routes: bool = False
    transport_mode: str = "driving-car"
    
    def get_all_points(self) -> List[RoutePoint]:
        """Get all route points in order: origin, waypoints, destination."""
        points = []
        if self.origin:
            points.append(self.origin)
        points.extend(self.waypoints)
        if self.destination:
            points.append(self.destination)
        return points
    
    def get_coordinates(self) -> List[Tuple[float, float]]:
        """Get coordinates as list of (lat, lng) tuples."""
        return [p.to_tuple() for p in self.get_all_points()]
    
    def get_num_segments(self) -> int:
        """Calculate number of segments (legs between consecutive points)."""
        num_points = len(self.get_all_points())
        return max(0, num_points - 1)
    
    def ensure_segments(self):
        """Ensure segment list matches route points.
        
        Creates default segments if missing or adjusts count to match points.
        """
        expected_segments = self.get_num_segments()
        current_segments = len(self.segments)
        
        if current_segments < expected_segments:
            # Add missing segments with defaults
            for i in range(current_segments, expected_segments):
                self.segments.append(SegmentMetadata(
                    description=f"Segment {i + 1}",
                    segment_type="highway",
                    estimated_stop_time_minutes=0,
                ))
        elif current_segments > expected_segments:
            # Remove excess segments
            self.segments = self.segments[:expected_segments]
    
    def calculate_total_duration_estimate(self) -> float:
        """Estimate total trip duration in hours.
        
        Based on segment stop times. If timestamps are provided on origin/destination,
        uses those instead.
        """
        if self.origin and self.origin.timestamp and self.destination and self.destination.timestamp:
            delta = self.destination.timestamp - self.origin.timestamp
            return delta.total_seconds() / 3600.0
        
        # Fallback: sum segment stop times + travel time estimate
        stop_time_hours = sum(s.estimated_stop_time_minutes for s in self.segments) / 60.0
        # Add estimated travel time (assume 1 hour per segment as rough estimate)
        travel_time_hours = len(self.segments) * 1.0
        return stop_time_hours + travel_time_hours
    
    def add_sensor(self, sensor: SensorConfig):
        """Add a sensor to this route."""
        self.sensors.append(sensor)
    
    def remove_sensor(self, index: int):
        """Remove a sensor from this route."""
        if 0 <= index < len(self.sensors):
            self.sensors.pop(index)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        from models.sensor import SensorConfig
        return {
            'id': self.id,
            'company_id': self.company_id,
            'route_name': self.route_name,
            'route_description': self.route_description,
            'origin_name': self.origin.name if self.origin else None,
            'origin_latitude': self.origin.latitude if self.origin else None,
            'origin_longitude': self.origin.longitude if self.origin else None,
            'origin_departure_date': self.origin.timestamp.date() if self.origin and self.origin.timestamp else None,
            'destination_name': self.destination.name if self.destination else None,
            'destination_latitude': self.destination.latitude if self.destination else None,
            'destination_longitude': self.destination.longitude if self.destination else None,
            'destination_arrival_date': self.destination.timestamp.date() if self.destination and self.destination.timestamp else None,
            'waypoints_json': json.dumps([wp.to_dict() for wp in self.waypoints]) if self.waypoints else None,
            'segments_json': json.dumps([s.to_dict() for s in self.segments]) if self.segments else None,
            'sensors_json': None,  # Sensors are now managed in simulation tab
            'log_interval_seconds': self.log_interval_seconds,
            'use_real_routes': self.use_real_routes,
            'transport_mode': self.transport_mode,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create RouteConfig from database dictionary."""
        # Parse origin
        origin = None
        if data.get('origin_name'):
            origin = RoutePoint(
                name=data['origin_name'],
                latitude=float(data['origin_latitude']),
                longitude=float(data['origin_longitude']),
                point_type='origin',
                timestamp=None  # Will set date separately
            )
            if data.get('origin_departure_date'):
                # Use the date from DB with default time (8:00 AM)
                origin.timestamp = datetime.combine(data['origin_departure_date'], datetime.min.time().replace(hour=8))
        
        # Parse destination
        destination = None
        if data.get('destination_name'):
            destination = RoutePoint(
                name=data['destination_name'],
                latitude=float(data['destination_latitude']),
                longitude=float(data['destination_longitude']),
                point_type='destination',
                timestamp=None
            )
            if data.get('destination_arrival_date'):
                # Use the date from DB with default time (18:00 / 6 PM)
                destination.timestamp = datetime.combine(data['destination_arrival_date'], datetime.min.time().replace(hour=18))
        
        # Parse waypoints
        waypoints = []
        if data.get('waypoints_json'):
            waypoints_data = json.loads(data['waypoints_json'])
            waypoints = [RoutePoint.from_dict(wp) for wp in waypoints_data]
        
        # Parse segments
        segments = []
        if data.get('segments_json'):
            segments_data = json.loads(data['segments_json'])
            segments = [SegmentMetadata.from_dict(seg) for seg in segments_data]
        
        return cls(
            id=data.get('id'),
            company_id=data.get('company_id'),
            route_name=data.get('route_name', ''),
            route_description=data.get('route_description', ''),
            origin=origin,
            destination=destination,
            waypoints=waypoints,
            segments=segments,
            sensors=[],  # Sensors are now managed in simulation tab
            log_interval_seconds=data.get('log_interval_seconds', 300),
            use_real_routes=data.get('use_real_routes', False),
            transport_mode=data.get('transport_mode', 'driving-car'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
        """Remove a sensor by index."""
        if 0 <= index < len(self.sensors):
            self.sensors.pop(index)
