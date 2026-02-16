from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID

# ============================================================================
# SCHEMAS DE SLOTS Y ESTADO DE SESIÓN (Mantiene lógica científica original)
# ============================================================================

class Slots(BaseModel):
    """
    Slots de estado emocional y contextual del usuario.
    Estos parámetros son fundamentales para la selección de estrategias de metamotivación.
    """
    sentimiento: Optional[str] = None  # "frustrado", "ansioso", "bloqueado", etc.
    sentimiento_otro: Optional[str] = None
    tipo_tarea: Optional[str] = None   # "coding", "ensayo", "debugging", etc.
    ramo: Optional[str] = None
    plazo: Optional[str] = None        # "hoy", "<24h", "esta_semana", ">1_semana"
    fase: Optional[str] = None         # "ideacion", "planificacion", "ejecucion", "revision"
    tiempo_bloque: Optional[int] = None  # Minutos disponibles — DEBE ser None para forzar pregunta
    nivel_urgencia: Optional[str] = None  # "alta", "media", "baja"
    autoeficacia: Optional[str] = None  # "alta", "media", "baja"
    
    class Config:
        json_schema_extra = {
            "example": {
                "sentimiento": "frustrado",
                "tipo_tarea": "debugging",
                "tiempo_bloque": 10,
                "nivel_urgencia": "alta",
                "autoeficacia": "baja"
            }
        }


class SessionStateSchema(BaseModel):
    """
    Estado completo de una sesión de chat.
    Mantiene el contexto conversacional y las decisiones de la IA.
    """
    session_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    iteration: int = 0
    slots: Slots = Field(default_factory=Slots)
    last_strategy: Optional[str] = None
    strategy_given: bool = False
    
    # Nuevos campos para modernización
    current_vibe: Optional[str] = "NEUTRAL"  # HACKER, GAMER, ZEN, PROFESIONAL, SUPPORT
    conversation_phase: str = "initial"  # initial, exploration, intervention, closure
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# SCHEMAS DE MENSAJES (Modernizados)
# ============================================================================

class QuickReply(BaseModel):
    """Respuesta rápida sugerida al usuario"""
    label: str = Field(..., description="Texto visible del botón")
    value: str = Field(..., description="Valor a enviar cuando se presiona")
    icon: Optional[str] = None  # Emoji o nombre de ícono
    color: Optional[str] = None  # Color del botón (lavender, mint, sky)


class MessageMetadata(BaseModel):
    """Metadata enriquecida de cada mensaje"""
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    strategy: Optional[str] = None  # Nombre de la estrategia seleccionada
    confidence_score: Optional[float] = None
    detected_slots: Optional[Dict[str, Any]] = None
    vibe: Optional[str] = None
    processing_time_ms: Optional[int] = None
    # Configuración del timer visual (Pomodoro)
    timer_config: Optional[Dict[str, Any]] = None  # {"duration_minutes": int, "label": str}
    # Redirección a otra pantalla (ej: "wellness" tras 2 rechazos)
    redirect: Optional[str] = None


class ChatMessageRequest(BaseModel):
    """Request para enviar un mensaje al chatbot"""
    session_id: Optional[UUID] = None
    user_id: UUID
    content: str = Field(..., min_length=1, max_length=2000)
    context: Optional[str] = None  # Contexto adicional (ej: código que está debuggeando)
    user_locale: str = Field(default="es", description="Idioma del usuario: 'es' o 'en'")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "content": "Estoy atascado con un bug y no sé por dónde empezar",
                "context": "Debugging en Python",
                "user_locale": "es"
            }
        }


class ChatMessageResponse(BaseModel):
    """Response de un mensaje del chatbot"""
    message_id: int
    session_id: UUID
    sender: Literal["user", "ai", "system"]
    content: str
    quick_replies: Optional[List[QuickReply]] = None
    metadata: Optional[MessageMetadata] = None
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": 42,
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "sender": "ai",
                "content": "Perfecto, vamos a hacer Rubber Duck Debugging...",
                "quick_replies": [
                    {"label": "✅ Me sirve", "value": "me ayudó"},
                    {"label": "❌ No me sirve", "value": "no funcionó"}
                ],
                "metadata": {
                    "strategy_id": "debug_rubber_duck",
                    "strategy_name": "Rubber Duck Debugging",
                    "vibe": "HACKER",
                    "confidence_score": 0.87
                },
                "created_at": "2026-02-08T18:00:00Z"
            }
        }


class ChatSessionCreate(BaseModel):
    """Request para crear una nueva sesión de chat"""
    user_id: UUID
    title: Optional[str] = None


class ChatSessionResponse(BaseModel):
    """Response con información de sesión"""
    id: UUID
    user_id: UUID
    title: Optional[str]
    is_active: bool
    created_at: datetime
    message_count: Optional[int] = 0


class ChatHistoryResponse(BaseModel):
    """Response con historial completo de una sesión"""
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]
    current_state: Optional[SessionStateSchema] = None


# ============================================================================
# SCHEMAS PARA STREAMING (SSE - Server Sent Events)
# ============================================================================

class StreamChunk(BaseModel):
    """
    Chunk individual enviado al frontend via SSE (Server Sent Events).
    Tipos:
      - 'start': Señal de inicio del stream, data contiene session_id.
      - 'token': Token de texto individual del LLM.
      - 'quick_reply': Lista de quick replies al finalizar generación.
      - 'metadata': Metadatos de la estrategia y decisión de la IA.
      - 'guardrail': Respuesta inmediata desde regex/crisis (sin LLM).
      - 'session_state': Estado actualizado de la sesión (para persistencia).
      - 'done': Señal de fin del stream.
      - 'error': Error durante el procesamiento.
    """
    event: Literal[
        "start", "token", "quick_reply", "metadata",
        "guardrail", "session_state", "done", "error"
    ]
    data: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FeedbackRequest(BaseModel):
    """Feedback sobre una respuesta de la IA"""
    message_id: int
    rating: Literal["helpful", "not_helpful", "neutral"]
    comment: Optional[str] = None
