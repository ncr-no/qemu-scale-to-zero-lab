from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field
from typing import Optional

class Config(BaseSettings):
    model_config = ConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        env_prefix=""
    )
    
    # Redis configuration
    REDIS_URL: str = Field(default="redis://redis:6379/0", description="Redis connection URL")
    
    # Lock configuration
    LOCK_TTL: int = Field(default=300, description="Lock TTL in seconds (5 minutes)")
    GROUP_LABEL: str = Field(default="qemu-lab", description="Docker container group label")
    
    # Docker configuration
    DOCKER_HOST: Optional[str] = Field(default=None, description="Docker daemon host URL")
    DOCKER_TLS_VERIFY: Optional[str] = Field(default="0", description="Docker TLS verification")
    DOCKER_CERT_PATH: Optional[str] = Field(default=None, description="Path to Docker TLS certificates")
    
    # Logging configuration
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

config = Config()