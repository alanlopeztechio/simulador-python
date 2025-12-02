"""
Sensor configuration for multi-sensor support.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SensorConfig:
    """Configuration for a single RFID sensor/tag.
    
    Supports multiple sensors per route for comprehensive monitoring.
    """
    epc: str  # Electronic Product Code
    tid: str  # Tag Identifier
    
    # Sensor parameters
    name: Optional[str] = None
    logger_mode: str = "LOGGING"
    
    # Battery configuration
    battery_present: bool = True
    battery_voltage_min: float = 3.0
    battery_voltage_max: float = 3.2
    
    # LED settings
    led_enabled: bool = True
    led_mode: str = "ON_DEMAND"
    led_off_time_seconds: int = 2
    led_on_time_milliseconds: int = 50
    
    # Anti-tamper settings
    anti_tamper_enabled: bool = False
    anti_tamper_polarity: str = "DETECT_CONNECTION_OR_LIGHT"
    
    # Logger settings
    log_interval_seconds: int = 300
    log_delayed_start_samples: int = 1
    
    def get_display_name(self) -> str:
        """Get human-readable sensor name."""
        if self.name:
            return self.name
        # Use last 6 digits of EPC for brevity
        return f"Sensor {self.epc[-6:]}"
    
    @staticmethod
    def generate_default(index: int = 1) -> "SensorConfig":
        """Generate a default sensor configuration.
        
        Args:
            index: Sequential index for unique EPC/TID generation
            
        Returns:
            SensorConfig with generated EPC/TID
        """
        epc = f"5201F250300{index:05d}"
        tid = f"E2C24500200005668{index:07d}"
        
        return SensorConfig(
            epc=epc,
            tid=tid,
            name=f"Sensor {index}",
        )
