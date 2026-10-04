import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, validator
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "SIVAT Backend"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str
    
    # API Keys
    X_API_BEARER_TOKEN: str
    YOUTUBE_API_KEY: str
    
    # Security
    SECRET_KEY: str

    # Ingesta automática en segundo plano (panel Internacionales en tiempo real)
    INTERVAL_INGESTA_INTERNACIONAL_SEGUNDOS: int = 60
    # GDELT es gratuito y sin API key: limita a 1 consulta/5s y puede bloquear la IP
    # por tiempo prolongado si se insiste. Se sondea por separado y con menor frecuencia.
    INTERVAL_INGESTA_GDELT_SEGUNDOS: int = 600
    GDELT_INGESTA_HABILITADA: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()
