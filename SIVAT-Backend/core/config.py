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

    # Ingesta automática del panel Internacionales (feed temporal, ver NoticiaFeed)
    # GDELT: se revisa cada 3 min si salió el archivo GKG de 15 min (estático, sin 429).
    INTERVAL_INGESTA_GDELT_SEGUNDOS: int = 180
    GDELT_INGESTA_HABILITADA: bool = True
    # YouTube: cada búsqueda cuesta 100 de 10,000 unidades diarias -> 96 búsquedas/día
    # caben en la cuota con 15 min. Bajar el intervalo exige pedir más cuota a Google.
    INTERVAL_INGESTA_YOUTUBE_SEGUNDOS: int = 900
    YOUTUBE_INGESTA_HABILITADA: bool = True
    # Bluesky (búsqueda pública) y medios (RSS): sin clave ni cuota estricta;
    # 5 min basta para noticias y no castiga a servicios gratuitos.
    INTERVAL_INGESTA_BLUESKY_SEGUNDOS: int = 300
    BLUESKY_INGESTA_HABILITADA: bool = True
    # Reddit sin OAuth solo tolera pedidos muy espaciados (responde 429 incluso
    # con 20 s de separación); 10 min y un único pedido por ciclo.
    INTERVAL_INGESTA_REDDIT_SEGUNDOS: int = 600
    REDDIT_INGESTA_HABILITADA: bool = True
    INTERVAL_INGESTA_RSS_SEGUNDOS: int = 300
    RSS_INGESTA_HABILITADA: bool = True
    # Horas que una noticia no validada permanece en el feed (minimización, Ley 29733)
    RETENCION_FEED_HORAS: int = 24

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()
