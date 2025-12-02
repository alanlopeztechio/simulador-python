"""
Adapter module to bridge new RouteConfig models with existing LogSimulator.

This module converts the new data structures (RouteConfig, SegmentMetadata, Distribution)
into the format expected by the existing LogSimulator class.
"""

from typing import List, Optional
from datetime import datetime, timedelta
import os
import json

from models.route import RouteConfig
from models.segment import SegmentMetadata
from models.distribution import Distribution, DistributionBlender
from models.sensor import SensorConfig
from simulator import LogSimulator, LogGeneratorInput, TempProfile, OpenStreetMapRouter


class SimulatorAdapter:
    """Adapts new RouteConfig to work with existing LogSimulator."""
    
    @staticmethod
    def generate_simulations(route_config: RouteConfig, 
                            num_samples: int = 1,
                            use_real_routes: bool = False,
                            output_dir: str = "simulation_outputs") -> List[str]:
        """Generate simulation JSONs from RouteConfig.
        
        Args:
            route_config: Complete route configuration
            num_samples: Number of JSON samples to generate
            use_real_routes: Whether to use OpenStreetMap routes
            output_dir: Directory to save outputs
            
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
        
        # Convert segments to TempProfile objects for existing simulator
        segment_profiles = SimulatorAdapter._convert_segments_to_profiles(route_config.segments)
        
        # Generate for each sensor
        if not route_config.sensors:
            # No sensors defined, use default
            route_config.sensors = [SensorConfig.generate_default(1)]
        
        for sensor_idx, sensor in enumerate(route_config.sensors):
            for sample_idx in range(num_samples):
                # Create LogGeneratorInput
                config = LogGeneratorInput(
                    epc=sensor.epc,
                    tid=sensor.tid,
                    log_interval_in_seconds=log_interval,
                    number_of_samples=num_temp_samples,
                    start_timestamp=start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    lower_temp=segment_profiles[0].lower_temp if segment_profiles else 0.0,
                    upper_temp=segment_profiles[0].upper_temp if segment_profiles else 10.0,
                    start_lat=coordinates[0][0],
                    start_lng=coordinates[0][1],
                    end_lat=coordinates[-1][0],
                    end_lng=coordinates[-1][1],
                    number_of_stops=len(coordinates) - 2,
                    distribution_type=segment_profiles[0].distribution_type if segment_profiles else "normal",
                    waypoints=coordinates,
                    transport_mode=route_config.transport_mode,
                    use_real_route=use_real_routes,
                    route_name=route_config.route_name,
                    segment_profiles=segment_profiles,
                )
                
                # Create simulator
                simulator = LogSimulator(config)
                
                # Generate simulation data
                data = simulator.generate()
                
                # Save to file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{route_config.route_name.replace(' ', '_')}_{sensor.epc[-6:]}_{sample_idx+1}_{timestamp}.json"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                
                generated_files.append(filepath)
                print(f"✓ Generated: {filename}")
        
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
