from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class MoodLabel(str, Enum):
    """Etiquetas de estado emocional"""
    FELIZ = "feliz"
    TRANQUILO = "tranquilo"
    NEUTRAL = "neutral"
    ANSIOSO = "ansioso"
    TRISTE = "triste"
    ENOJADO = "enojado"
    ESTRESADO = "estresado"

class EnergyLevel(str, Enum):
    """Niveles de energía basados en el semáforo"""
    ROJO = "rojo"      # Energía nula
    AMBAR = "ambar"    # Energía media
    VERDE = "verde"    # Energía adecuada

class CheckInRequest(BaseModel):
    """Modelo para recibir un check-in diario"""
    mood_label: MoodLabel = Field(..., description="Etiqueta del estado emocional")
    mood_score: int = Field(..., ge=1, le=5, description="Nivel del estado de ánimo (1-5)")
    feelings: Optional[List[str]] = Field(default=None, description="Lista de sentimientos adicionales")
    note: Optional[str] = Field(default=None, max_length=500, description="Nota opcional del usuario")

class CheckInResponse(BaseModel):
    """Respuesta después de guardar un check-in"""
    id: int
    user_id: str
    mood_label: str
    mood_score: int
    feelings: Optional[List[str]]
    note: Optional[str]
    created_at: datetime
    message: str

class EnergyRequest(BaseModel):
    """Modelo para recibir el nivel de energía"""
    energy_level: EnergyLevel = Field(..., description="Nivel de energía (Rojo/Ámbar/Verde)")

class ExerciseResponse(BaseModel):
    """Respuesta con ejercicio de relajación"""
    exercise_type: str = Field(..., description="Tipo de ejercicio")
    title: str = Field(..., description="Título del ejercicio")
    description: str = Field(..., description="Descripción del ejercicio")
    duration_seconds: int = Field(..., description="Duración en segundos")
    instructions: List[str] = Field(..., description="Instrucciones paso a paso")
    energy_level: str = Field(..., description="Nivel de energía para el que está diseñado")

class MotivationResponse(BaseModel):
    """Respuesta con mensaje motivacional"""
    message: str = Field(..., description="Mensaje motivacional de Flou")
    author: str = Field(default="Flou", description="Autor del mensaje")
    category: Optional[str] = Field(default=None, description="Categoría del mensaje")
