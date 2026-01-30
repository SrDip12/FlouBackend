from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ProfileStatsResponse(BaseModel):
    """Respuesta con estadísticas del perfil"""
    streak_days: int = Field(..., description="Días consecutivos con check-in")
    total_checkins: int = Field(..., description="Total de check-ins realizados")
    recent_moods: List[dict] = Field(..., description="Últimos 5 estados de ánimo")
    average_mood_score: float = Field(..., description="Promedio de mood_score")
    most_common_mood: Optional[str] = Field(default=None, description="Estado de ánimo más frecuente")

class ProfileUpdateRequest(BaseModel):
    """Modelo para actualizar información del perfil"""
    career_program: Optional[str] = Field(default=None, max_length=200, description="Carrera o programa de estudios")
    semester: Optional[int] = Field(default=None, ge=1, le=12, description="Semestre actual")
    age: Optional[int] = Field(default=None, ge=16, le=100, description="Edad del usuario")
    health_conditions: Optional[List[str]] = Field(default=None, description="Condiciones de salud")
    neurodivergence: Optional[List[str]] = Field(default=None, description="Condiciones de neurodivergencia")
    full_name: Optional[str] = Field(default=None, max_length=100, description="Nombre completo")

class ProfileUpdateResponse(BaseModel):
    """Respuesta después de actualizar el perfil"""
    message: str
    updated_fields: List[str]
    profile: dict
