#!/usr/bin/env python3
"""
Configuration loader for OLX Scraper
Loads settings from config.json with environment variable overrides
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import logging

# Load environment variables from .env file
def load_env_file():
    # Look for .env in project root
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.strip() and '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

# Load .env on import
load_env_file()

logger = logging.getLogger(__name__)

class Config:
    """Configuration manager for OLX scraper"""
    
    def __init__(self, config_file: str = "config.json"):
        """Initialize configuration from JSON file and environment variables"""
        # Look for config in project root or config folder
        if not Path(config_file).is_absolute():
            project_root = Path(__file__).parent.parent
            if (project_root / "config" / config_file).exists():
                self.config_file = project_root / "config" / config_file
            elif (project_root / config_file).exists():
                self.config_file = project_root / config_file
            else:
                self.config_file = Path(config_file)
        else:
            self.config_file = Path(config_file)
        self._config = {}
        self._load_config()
        self._apply_env_overrides()
    
    def _load_config(self):
        """Load configuration from JSON file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logger.info(f"✅ Configuration loaded from {self.config_file}")
            else:
                logger.warning(f"⚠️ Config file {self.config_file} not found, using defaults")
                self._config = self._get_default_config()
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in config file: {e}")
            logger.info("🔄 Using default configuration")
            self._config = self._get_default_config()
        
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")
            self._config = self._get_default_config()
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides"""
        env_mappings = {
            # Database
            'DATABASE_URL': 'database.url',
            'DB_POOL_MIN': 'database.pool_min_size',
            'DB_POOL_MAX': 'database.pool_max_size',
            
            # Railway Database (automatic)
            'POSTGRES_URL': 'database.url',
            'PGURL': 'database.url',
            
            # AWS S3
            'AWS_S3_BUCKET': 'aws_s3.bucket_name',
            'AWS_REGION': 'aws_s3.region',
            'S3_UPLOAD_ENABLED': 'workflow.enable_image_upload',
            
            # Scraper
            'COOKIES_FILE': 'scraper.cookies_file',
            'SCRAPER_HEADLESS': 'scraper.headless',
            'MAX_PAGES': 'scraper.default_max_pages',
            'MAX_CARS': 'scraper.default_max_cars',
            
            # Workflow
            'PHONE_EXTRACTION': 'workflow.enable_phone_extraction',
            'USER_MANAGEMENT': 'workflow.enable_user_management',
            
            # Logging
            'LOG_LEVEL': 'logging.level',
            'LOG_FILE': 'logging.file',
        }
        
        overrides_applied = 0
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                self._set_nested_value(config_path, self._parse_env_value(env_value))
                overrides_applied += 1
                logger.debug(f"🔧 Environment override: {env_var} -> {config_path}")
        
        if overrides_applied > 0:
            logger.info(f"🔧 Applied {overrides_applied} environment overrides")
    
    def _set_nested_value(self, path: str, value: Any):
        """Set nested configuration value using dot notation"""
        keys = path.split('.')
        current = self._config
        
        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the final value
        current[keys[-1]] = value
    
    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type"""
        # Boolean values
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Integer values
        try:
            return int(value)
        except ValueError:
            pass
        
        # Float values
        try:
            return float(value)
        except ValueError:
            pass
        
        # String value
        return value
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "database": {
                "url": "postgresql://car_user:dev_password@localhost:5432/car_marketplace_dev",
                "pool_min_size": 2,
                "pool_max_size": 10,
                "command_timeout": 60
            },
            "scraper": {
                "cookies_file": "cookies.txt",
                "headless": True,
                "default_max_pages": 2,
                "default_max_cars": 20,
                "random_delay_min": 2,
                "random_delay_max": 4,
                "phone_extraction_enabled": True,
                "user_agent_rotation": True
            },
            "aws_s3": {
                "bucket_name": "car-marketplace-images",
                "region": "eu-west-1",
                "upload_enabled": True,
                "max_images_per_car": 5,
                "image_quality": 85,
                "image_max_size": 1920
            },
            "workflow": {
                "enable_image_upload": True,
                "enable_user_management": True,
                "enable_phone_extraction": True,
                "batch_size": 10,
                "max_retries": 3,
                "retry_delay": 5
            },
            "logging": {
                "level": "INFO",
                "file": "olx_workflow.log",
                "max_file_size": "10MB",
                "backup_count": 5
            },
            "urls": {
                "base_url": "https://www.olx.pt",
                "cars_main": "https://www.olx.pt/carros-motos-e-barcos/carros/",
                "brand_template": "https://www.olx.pt/carros-motos-e-barcos/carros/{brand}/"
            }
        }
    
    def get(self, path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        try:
            keys = path.split('.')
            current = self._config
            
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            
            return current
            
        except Exception as e:
            logger.error(f"❌ Error getting config value '{path}': {e}")
            return default
    
    def get_database_url(self) -> str:
        """Get database URL"""
        return self.get('database.url', 'postgresql://car_user:dev_password@localhost:5432/car_marketplace_dev')
    
    def get_cookies_file(self) -> Optional[str]:
        """Get cookies file path if it exists"""
        cookies_file = self.get('scraper.cookies_file')
        if cookies_file and Path(cookies_file).exists():
            return cookies_file
        return None
    
    def get_brand_url(self, brand: str) -> str:
        """Get URL for specific brand"""
        template = self.get('urls.brand_template')
        return template.format(brand=brand.lower())
    
    def get_main_cars_url(self) -> str:
        """Get main cars page URL"""
        return self.get('urls.cars_main')
    
    def is_headless_enabled(self) -> bool:
        """Check if headless scraping is enabled"""
        return self.get('scraper.headless', True)
    
    def is_phone_extraction_enabled(self) -> bool:
        """Check if phone extraction is enabled"""
        return self.get('workflow.enable_phone_extraction', True)
    
    def is_image_upload_enabled(self) -> bool:
        """Check if image upload is enabled"""
        return self.get('workflow.enable_image_upload', True)
    
    def get_max_cars_default(self) -> int:
        """Get default maximum cars to scrape"""
        return self.get('scraper.default_max_cars', 20)
    
    def get_max_pages_default(self) -> int:
        """Get default maximum pages to scrape"""
        return self.get('scraper.default_max_pages', 2)
    
    def get_s3_config(self) -> Dict[str, Any]:
        """Get S3 configuration"""
        return self.get('aws_s3', {})
    
    def get_workflow_config(self) -> Dict[str, Any]:
        """Get workflow configuration"""
        return self.get('workflow', {})
    
    def to_dict(self) -> Dict[str, Any]:
        """Get full configuration as dictionary"""
        return self._config.copy()
    
    def save_config(self, config_file: Optional[str] = None):
        """Save current configuration to file"""
        target_file = Path(config_file) if config_file else self.config_file
        
        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Configuration saved to {target_file}")
            
        except Exception as e:
            logger.error(f"❌ Error saving config: {e}")

# Global config instance
config = Config()

# Convenience functions
def get_config() -> Config:
    """Get global config instance"""
    return config

def reload_config(config_file: str = "config.json"):
    """Reload configuration from file"""
    global config
    config = Config(config_file)
    return config

# Example usage and testing
def main():
    """Test configuration loading"""
    print("🔧 OLX Scraper Configuration Test")
    print("=" * 40)
    
    cfg = Config()
    
    print(f"Database URL: {cfg.get_database_url()}")
    print(f"Cookies file: {cfg.get_cookies_file()}")
    print(f"Headless mode: {cfg.is_headless_enabled()}")
    print(f"Phone extraction: {cfg.is_phone_extraction_enabled()}")
    print(f"Image upload: {cfg.is_image_upload_enabled()}")
    print(f"Max cars: {cfg.get_max_cars_default()}")
    print(f"Max pages: {cfg.get_max_pages_default()}")
    print(f"BMW URL: {cfg.get_brand_url('bmw')}")
    print(f"Main cars URL: {cfg.get_main_cars_url()}")
    
    print(f"\nS3 Config: {cfg.get_s3_config()}")
    print(f"Workflow Config: {cfg.get_workflow_config()}")

if __name__ == "__main__":
    main()