"""
Segment metadata and configuration.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from .distribution import Distribution


@dataclass
class SegmentMetadata:
    """Metadata and configuration for a route segment.
    
    A segment represents travel between two consecutive waypoints,
    with specific thermal profiles and characteristics.
    """
    description: str
    segment_type: str  # e.g., "highway", "urban", "rural", "fleet", "control"
    estimated_stop_time_minutes: int = 0
    
    # Multiple distributions per segment (KEY FEATURE)
    distributions: List[Distribution] = field(default_factory=list)
    
    # Blending strategy for multiple distributions
    blend_strategy: str = "weighted_average"  # "weighted_average", "alternating", "layered"
    
    # Temperature bounds for alarm checking (can differ from distribution bounds)
    alarm_lower_temp: Optional[float] = None
    alarm_upper_temp: Optional[float] = None
    
    # Smoothing/AR(1) parameters
    apply_smoothing: bool = False
    smoothing_phi: float = 0.8  # AR(1) coefficient
    
    def get_primary_bounds(self) -> tuple[float, float]:
        """Get primary temperature bounds from distributions or alarms.
        
        Returns:
            Tuple of (lower_temp, upper_temp)
        """
        if self.alarm_lower_temp is not None and self.alarm_upper_temp is not None:
            return (self.alarm_lower_temp, self.alarm_upper_temp)
        
        # Fallback: use first distribution's bounds
        if self.distributions:
            dist = self.distributions[0]
            if dist.lower_temp is not None and dist.upper_temp is not None:
                return (dist.lower_temp, dist.upper_temp)
        
        # Default fallback
        return (0.0, 10.0)
    
    def add_distribution(self, distribution: Distribution):
        """Add a distribution to this segment."""
        self.distributions.append(distribution)
    
    def remove_distribution(self, index: int):
        """Remove a distribution by index."""
        if 0 <= index < len(self.distributions):
            self.distributions.pop(index)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            'description': self.description,
            'segment_type': self.segment_type,
            'estimated_stop_time_minutes': self.estimated_stop_time_minutes,
            'distributions': [d.to_dict() for d in self.distributions],
            'blend_strategy': self.blend_strategy,
            'alarm_lower_temp': self.alarm_lower_temp,
            'alarm_upper_temp': self.alarm_upper_temp,
            'apply_smoothing': self.apply_smoothing,
            'smoothing_phi': self.smoothing_phi
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary."""
        distributions = []
        if data.get('distributions'):
            distributions = [Distribution.from_dict(d) for d in data['distributions']]
        
        return cls(
            description=data.get('description', ''),
            segment_type=data.get('segment_type', 'highway'),
            estimated_stop_time_minutes=data.get('estimated_stop_time_minutes', 0),
            distributions=distributions,
            blend_strategy=data.get('blend_strategy', 'weighted_average'),
            alarm_lower_temp=data.get('alarm_lower_temp'),
            alarm_upper_temp=data.get('alarm_upper_temp'),
            apply_smoothing=data.get('apply_smoothing', False),
            smoothing_phi=data.get('smoothing_phi', 0.8)
        )
