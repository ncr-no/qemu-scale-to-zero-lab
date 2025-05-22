from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Config(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")
    REDIS_URL: str = "redis://redis:6379/0"
    LOCK_TTL: int = 300  # 5 minutes in seconds
    GROUP_LABEL: str = "qemu-lab"

config = Config()