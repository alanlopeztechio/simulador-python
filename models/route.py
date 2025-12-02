"""
Route configuration with rich metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple
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


@dataclass
class RouteConfig:
    """Complete route configuration with metadata.
    
    This is the primary data structure for the new UI workflow,
    bundling route geometry, segment metadata, distributions, and sensors.
    """
    # Route metadata
    route_name: str
    route_description: str = ""
    
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
        """Remove a sensor by index."""
        if 0 <= index < len(self.sensors):
            self.sensors.pop(index)
