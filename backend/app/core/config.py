#app/core/config.py
""" 
Configuration general et transversale de l'application.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str 
    APP_NETWORK: str 
    APP_DOMAIN: str 
    APP_PORT: int 
    ENCRYPTION_KEY: str 
    POSTGRES_DB: str 
    POSTGRES_HOST: str 
    POSTGRES_PORT: int 
    POSTGRES_USER: str 
    POSTGRES_PASSWORD: str 
    ENVIRONMENT: str 
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int

    # fonction considerée comme une propriété de la classe,
    @property 
    def url(self) -> str: 
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # attribut par convention, pour définir le fichier .env à utiliser
    model_config = SettingsConfigDict(env_file = ".env", extra = "ignore")

settings = Settings() # type: ignore[call-arg]

