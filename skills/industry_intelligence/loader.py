import os
import yaml
from typing import Dict, Optional
from hephae_common.models import IndustryConfig

class SkillLoader:
    """Loads industry-specific skill configurations from YAML files."""
    
    _cache: Dict[str, IndustryConfig] = {}
    
    @staticmethod
    def get_config(industry: str) -> Optional[IndustryConfig]:
        """Load and cache industry configuration."""
        industry_key = industry.lower()
        if industry_key in SkillLoader._cache:
            return SkillLoader._cache[industry_key]
        
        # Determine path to config
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "configs", f"{industry_key}.yaml")
        
        if not os.path.exists(config_path):
            return None
            
        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
                config = IndustryConfig(**data)
                SkillLoader._cache[industry_key] = config
                return config
        except Exception as e:
            # Fallback to a very basic config if loading fails
            return IndustryConfig(industry=industry)

def get_industry_config(industry: str) -> IndustryConfig:
    """Helper function to get config, defaults to a generic one if not found."""
    return SkillLoader.get_config(industry) or IndustryConfig(industry=industry)
