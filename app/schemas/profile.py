from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID

class ThemePreference(str, Enum):
    LIGHT = 'light'
    DARK = 'dark'
    SYSTEM = 'system'

class LanguagePreference(str, Enum):
    ES = 'es'
    EN = 'en'

class ProfileSettings(BaseModel):
    """Modelo para actualizar preferencias de usuario"""
    theme_preference: Optional[ThemePreference] = Field(None, description="Preferencia de tema de UI")
    language_preference: Optional[LanguagePreference] = Field(None, description="Preferencia de idioma")
    research_consent: Optional[bool] = Field(None, description="Consentimiento para uso de datos en investigación")

class ProfileBase(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    institution_id: Optional[int] = None
    career_program: Optional[str] = None
    semester: Optional[int] = None
    avatar_url: Optional[str] = None
    theme_preference: Optional[ThemePreference] = ThemePreference.SYSTEM
    language_preference: Optional[LanguagePreference] = LanguagePreference.ES
    research_consent: Optional[bool] = False

class ProfileResponse(ProfileBase):
    """Modelo completo de respuesta de perfil"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
