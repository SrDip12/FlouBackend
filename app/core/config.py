import os
from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Flou Backend"
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    # Gemini AI
    GEMINI_API_KEY: str
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()
