"""
Distribution models for temperature generation.
"""

from dataclasses import dataclass
from typing import Literal, Optional
import numpy as np
from scipy import stats


@dataclass
class Distribution:
    """Represents a temperature distribution configuration.
    
    Supports multiple distribution types with both absolute and relative modes.
    Relative mode applies percentage offset from ambient temperature.
    """
    type: Literal["normal", "beta", "truncnorm", "uniform"]
    mode: Literal["absolute", "relative"] = "absolute"
    
    # Parameters for normal/truncnorm
    mean_temp: Optional[float] = None
    std_dev: float = 5.0
    
    # Parameters for beta
    beta_alpha: float = 2.0
    beta_beta: float = 5.0
    
    # Temperature bounds (for absolute mode or relative baseline)
    lower_temp: Optional[float] = None
    upper_temp: Optional[float] = None
    
    # Weight for blending multiple distributions (0.0 to 1.0)
    weight: float = 1.0
    
    # Relative mode parameters
    ambient_temp: Optional[float] = None  # Base temperature for relative mode
    relative_offset_pct: float = 0.0  # Percentage offset from ambient
    
    def generate_samples(self, n: int, seed: Optional[int] = None) -> np.ndarray:
        """Generate n temperature samples from this distribution.
        
        Args:
            n: Number of samples to generate
            seed: Random seed for reproducibility
            
        Returns:
            Array of temperature values
        """
        if seed is not None:
            np.random.seed(seed)
        
        if self.mode == "relative":
            # Generate relative offsets and apply to ambient
            base_temp = self.ambient_temp if self.ambient_temp is not None else 20.0
            samples = self._generate_raw_samples(n)
            # Apply percentage offset
            offset = base_temp * (self.relative_offset_pct / 100.0)
            return samples + offset
        else:
            # Absolute mode - direct temperature values
            return self._generate_raw_samples(n)
    
    def _generate_raw_samples(self, n: int) -> np.ndarray:
        """Generate raw samples based on distribution type."""
        if self.type == "normal":
            mean = self.mean_temp if self.mean_temp is not None else 0.0
            samples = np.random.normal(mean, self.std_dev, size=n)
            # Apply soft bounds if provided
            if self.lower_temp is not None and self.upper_temp is not None:
                samples = np.clip(samples, self.lower_temp - 10, self.upper_temp + 10)
            return samples
        
        elif self.type == "beta":
            # Beta distribution generates values in [0, 1]
            beta_values = np.random.beta(self.beta_alpha, self.beta_beta, size=n)
            # Scale to temperature range
            if self.lower_temp is not None and self.upper_temp is not None:
                temp_range = self.upper_temp - self.lower_temp + 20
                return self.lower_temp - 10 + (beta_values * temp_range)
            else:
                # Default range if not specified
                return beta_values * 50 - 10
        
        elif self.type == "truncnorm":
            if self.lower_temp is None or self.upper_temp is None:
                raise ValueError("truncnorm requires lower_temp and upper_temp")
            mean = self.mean_temp if self.mean_temp is not None else (self.lower_temp + self.upper_temp) / 2
            std = max(1e-6, self.std_dev)
            a = (self.lower_temp - mean) / std
            b = (self.upper_temp - mean) / std
            return stats.truncnorm.rvs(a, b, loc=mean, scale=std, size=n)
        
        elif self.type == "uniform":
            if self.lower_temp is None or self.upper_temp is None:
                raise ValueError("uniform requires lower_temp and upper_temp")
            return np.random.uniform(self.lower_temp, self.upper_temp, size=n)
        
        else:
            raise ValueError(f"Unsupported distribution type: {self.type}")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            'type': self.type,
            'mode': self.mode,
            'mean_temp': self.mean_temp,
            'std_dev': self.std_dev,
            'beta_alpha': self.beta_alpha,
            'beta_beta': self.beta_beta,
            'lower_temp': self.lower_temp,
            'upper_temp': self.upper_temp,
            'weight': self.weight,
            'ambient_temp': self.ambient_temp,
            'relative_offset_pct': self.relative_offset_pct
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary."""
        return cls(
            type=data.get('type', 'normal'),
            mode=data.get('mode', 'absolute'),
            mean_temp=data.get('mean_temp'),
            std_dev=data.get('std_dev', 5.0),
            beta_alpha=data.get('beta_alpha', 2.0),
            beta_beta=data.get('beta_beta', 5.0),
            lower_temp=data.get('lower_temp'),
            upper_temp=data.get('upper_temp'),
            weight=data.get('weight', 1.0),
            ambient_temp=data.get('ambient_temp'),
            relative_offset_pct=data.get('relative_offset_pct', 0.0)
        )


class DistributionBlender:
    """Blends multiple distributions into a single temperature series.
    
    Supports different blending strategies for combining multiple distributions.
    """
    
    @staticmethod
    def blend(distributions: list[Distribution], n: int, 
              strategy: Literal["weighted_average", "alternating", "layered"] = "weighted_average",
              seed: Optional[int] = None) -> np.ndarray:
        """Blend multiple distributions into n samples.
        
        Args:
            distributions: List of Distribution objects to blend
            n: Number of samples to generate
            strategy: Blending strategy to use
            seed: Random seed for reproducibility
            
        Returns:
            Array of blended temperature values
        """
        if not distributions:
            raise ValueError("At least one distribution required")
        
        if len(distributions) == 1:
            return distributions[0].generate_samples(n, seed=seed)
        
        if strategy == "weighted_average":
            return DistributionBlender._weighted_average(distributions, n, seed)
        elif strategy == "alternating":
            return DistributionBlender._alternating(distributions, n, seed)
        elif strategy == "layered":
            return DistributionBlender._layered(distributions, n, seed)
        else:
            raise ValueError(f"Unsupported blending strategy: {strategy}")
    
    @staticmethod
    def _weighted_average(distributions: list[Distribution], n: int, seed: Optional[int]) -> np.ndarray:
        """Blend using weighted average of all distributions."""
        # Normalize weights
        total_weight = sum(d.weight for d in distributions)
        if total_weight == 0:
            total_weight = len(distributions)
            weights = [1.0 / len(distributions)] * len(distributions)
        else:
            weights = [d.weight / total_weight for d in distributions]
        
        # Generate samples from each distribution
        result = np.zeros(n)
        for dist, weight in zip(distributions, weights):
            samples = dist.generate_samples(n, seed=seed)
            result += samples * weight
        
        return np.round(result, 1)
    
    @staticmethod
    def _alternating(distributions: list[Distribution], n: int, seed: Optional[int]) -> np.ndarray:
        """Alternate between distributions in round-robin fashion."""
        result = np.zeros(n)
        for i in range(n):
            dist = distributions[i % len(distributions)]
            result[i] = dist.generate_samples(1, seed=seed if seed is None else seed + i)[0]
        return np.round(result, 1)
    
    @staticmethod
    def _layered(distributions: list[Distribution], n: int, seed: Optional[int]) -> np.ndarray:
        """Layer distributions: base + noise layers."""
        # First distribution is base
        result = distributions[0].generate_samples(n, seed=seed)
        
        # Add subsequent distributions as noise/variation
        for i, dist in enumerate(distributions[1:], start=1):
            noise = dist.generate_samples(n, seed=seed if seed is None else seed + i * 1000)
            # Add as small variation (scaled down)
            result += noise * 0.3 * dist.weight
        
        return np.round(result, 1)

