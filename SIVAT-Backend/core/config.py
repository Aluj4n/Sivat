from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "SIVAT Backend"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str
    
    # API Keys
    X_API_BEARER_TOKEN: str
    YOUTUBE_API_KEY: str

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
    # Módulo RAG: verificadores por RSS cada 30 min (publican pocas veces al día)
    INTERVAL_INGESTA_VERIFICADORES_SEGUNDOS: int = 1800
    VERIFICADORES_INGESTA_HABILITADA: bool = True
    # Módulo de Tendencias: agrupa el feed por tema cada 15 min (el primer
    # ciclo tarda ~1-2 min en CPU; los siguientes solo procesan lo nuevo)
    INTERVAL_TENDENCIAS_SEGUNDOS: int = 900
    TENDENCIAS_HABILITADAS: bool = True
    # Clave propia para Google Fact Check; si no se define se usa la de YouTube
    # (mismo proyecto de Google Cloud con ambas APIs habilitadas)
    GOOGLE_FACTCHECK_API_KEY: Optional[str] = None
    # Palabras mínimas para mostrar el resultado del modelo de texto. Medido
    # sobre el corpus: con menos de ~200 palabras casi todo le parece
    # desinformación (aprendió que las falsas eran más cortas).
    MIN_PALABRAS_MODELO: int = 200
    # Horas que una noticia no validada permanece en el feed (minimización, Ley 29733)
    RETENCION_FEED_HORAS: int = 24

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        # Un .env con variables que ya no se usan (p. ej. SECRET_KEY) sigue funcionando
        extra="ignore",
    )

settings = Settings()
