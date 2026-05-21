# backend/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = ""
    neon_connection_string: str = ""
    elevenlabs_api_key: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    review_supabase_url: str = ""
    review_supabase_key: str = ""
    voice_texts_dir: str = "voice_texts"
    audios_root: str = "audios"
    input_dir: str = "input"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def db_url(self) -> str:
        return self.database_url or self.neon_connection_string

settings = Settings()
