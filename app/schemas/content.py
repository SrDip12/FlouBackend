from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class ContentLanguage(str, Enum):
    """Idiomas disponibles para el contenido"""
    ES = "es"
    EN = "en"

class EducationalCard(BaseModel):
    """Modelo para una tarjeta educativa"""
    id: str = Field(..., description="Identificador único de la tarjeta")
    title: str = Field(..., description="Título de la tarjeta")
    category: str = Field(..., description="Categoría (Autoconocimiento, Energía, etc.)")
    description: str = Field(..., description="Descripción breve")
    content: str = Field(..., description="Contenido completo de la tarjeta")
    icon: Optional[str] = Field(default=None, description="Icono o emoji representativo")
    color: Optional[str] = Field(default=None, description="Color asociado (hex)")
    order: int = Field(default=0, description="Orden de visualización")

class ContentResponse(BaseModel):
    """Respuesta con lista de tarjetas educativas"""
    cards: List[EducationalCard] = Field(..., description="Lista de tarjetas educativas")
    language: str = Field(..., description="Idioma del contenido")
    total: int = Field(..., description="Total de tarjetas")
