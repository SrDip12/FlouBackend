import logging
import json
import time
from typing import Optional, Dict, List
from groq import Groq

from app.core.config import get_settings
from app.schemas.chat import SessionStateSchema, Slots
from app.services.rag_service import rag_engine

logger = logging.getLogger(__name__)

# Obtener configuración
settings = get_settings()

# Nuevo Cliente Groq
# Inicializamos cliente solo si hay API Key, si no, fallará en tiempo de ejecución de manera controlada o aquí mismo.
try:
    client = Groq(api_key=settings.GROQ_API_KEY)
except Exception as e:
    logger.error(f"Error inicializando cliente Groq: {e}")
    client = None

MODEL_NAME = 'llama-3.3-70b-versatile'

async def handle_user_turn(
    session: SessionStateSchema, 
    user_text: str, 
    context: str = "", 
    chat_history: Optional[List[Dict[str, str]]] = None
) -> tuple:
    """
    Orquestador v3 con RAG, Generación Dinámica y Logging Científico.
    
    Retorna: (reply_text, updated_session, quick_replies, metadata)
    """
    start_time = time.time()
    
    # 1. Recuperar Estrategia Inteligente (RAG)
    # Usamos lo que dijo el usuario para buscar en nuestra DB vectorial
    estrategia = rag_engine.retrieve(user_text, session.slots)
    
    # 2. Actualizar el vibe de la sesión basado en la estrategia
    session.current_vibe = estrategia.get('vibe', 'NEUTRAL')
    
    # 3. Construir Prompt de Sistema Dinámico
    # Inyectamos la instrucción de actuación específica de la estrategia
    system_instruction = f"""
Eres Flou, un asistente para estudiantes de ingeniería informática.
Tu objetivo es desbloquear al estudiante usando la estrategia seleccionada.

[CONTEXTO DEL USUARIO]
- Sentimiento: {session.slots.sentimiento or 'Neutral'}
- Tarea: {session.slots.tipo_tarea or 'General'}
- Tiempo disponible: {session.slots.tiempo_bloque or 15} min
- Vibe actual: {estrategia.get('vibe', 'NEUTRAL')}
- Iteración: {session.iteration + 1}

[ESTRATEGIA SELECCIONADA: "{estrategia['nombre']}"]
[TUS INSTRUCCIONES DE ACTUACIÓN]:
{estrategia['prompt_instruction']}

[REGLAS ESTRICTAS]
1. NO digas "He seleccionado esta estrategia". ¡ACTÚALA DIRECTAMENTE!
2. Sé breve y conciso (máximo 2 párrafos).
3. Termina con una pregunta o acción inmediata.
4. Si el vibe es HACKER, usa términos técnicos. Si es GAMER, usa metáforas de juego.
5. Adapta tu tono al vibe: ZEN (calmado), SUPPORT (validador), PROFESIONAL (directo).
"""
    
    # 4. Preparar historial para la nueva API (OpenAI compatible)
    messages = [{"role": "system", "content": system_instruction}]
    
    if chat_history:
        for msg in chat_history[-6:]:  # Solo últimos 6 mensajes para mantener contexto relevante
            # Mapear roles: 'model' -> 'assistant', 'user' -> 'user'
            role = "user" if msg.get("role") == "user" else "assistant"
            content = msg.get("parts", [""])[0] 
            messages.append({"role": role, "content": str(content)})
    
    # Agregar contexto adicional si existe
    final_user_text = user_text
    if context:
        final_user_text = f"{user_text}\n\n[Contexto adicional: {context}]"
    
    # Agregar el mensaje actual
    messages.append({"role": "user", "content": final_user_text})

    try:
        # 5. Generación con Groq
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=350
        )
        
        reply = completion.choices[0].message.content
        
        # 6. Actualizar sesión
        session.iteration += 1
        session.last_strategy = estrategia['nombre']
        session.strategy_given = True
        
        # 7. Generar Quick Replies Dinámicos basados en el vibe
        quick_replies = _generate_quick_replies(estrategia['vibe'], session.iteration)
        
        # 8. Metadata para logging científico
        processing_time = int((time.time() - start_time) * 1000)
        metadata = {
            "strategy_id": estrategia.get('id'),
            "strategy_name": estrategia['nombre'],
            "vibe": estrategia['vibe'],
            "confidence_score": 0.85,  # Placeholder
            "detected_slots": session.slots.model_dump(),
            "processing_time_ms": processing_time,
            "iteration": session.iteration
        }
        
        logger.info(
            f"Estrategia aplicada: {estrategia['nombre']} | "
            f"Vibe: {estrategia['vibe']} | "
            f"Tiempo: {processing_time}ms"
        )
        
        return reply, session, quick_replies, metadata

    except Exception as e:
        logger.error(f"Error en generación Groq: {e}", exc_info=True)
        
        # Fallback con estrategia de emergencia
        fallback_reply = _get_fallback_response(session.slots.sentimiento)
        fallback_quick_replies = [
            {"label": "🔄 Reintentar", "value": "retry", "icon": "🔄"},
            {"label": "💬 Hablar con humano", "value": "human_support", "icon": "💬"}
        ]
        
        metadata = {
            "strategy_id": "fallback",
            "strategy_name": "Emergency Fallback",
            "vibe": "SUPPORT",
            "error": str(e)
        }
        
        return fallback_reply, session, fallback_quick_replies, metadata


def _generate_quick_replies(vibe: str, iteration: int) -> List[Dict[str, str]]:
    """
    Genera quick replies contextuales basados en el vibe y la iteración.
    """
    base_replies = [
        {"label": "✅ Me sirve", "value": "helpful", "icon": "✅", "color": "mint"},
        {"label": "❌ No me sirve", "value": "not_helpful", "icon": "❌", "color": "lavender"}
    ]
    
    # Quick replies específicos por vibe
    vibe_specific = {
        "HACKER": [
            {"label": "🐛 Explicar bug", "value": "explain_bug", "icon": "🐛"},
            {"label": "📝 Ver código", "value": "show_code", "icon": "📝"}
        ],
        "GAMER": [
            {"label": "🎮 Siguiente nivel", "value": "next_level", "icon": "🎮"},
            {"label": "💾 Guardar progreso", "value": "save_progress", "icon": "💾"}
        ],
        "ZEN": [
            {"label": "🧘 Respirar", "value": "breathing_exercise", "icon": "🧘"},
            {"label": "📍 Enfocar", "value": "focus_mode", "icon": "📍"}
        ],
        "SUPPORT": [
            {"label": "💪 Continuar", "value": "continue", "icon": "💪"},
            {"label": "🔄 Cambiar enfoque", "value": "change_approach", "icon": "🔄"}
        ]
    }
    
    # Combinar base + específicos del vibe
    if vibe in vibe_specific:
        return base_replies + vibe_specific[vibe][:1]  # Solo agregar 1 para no saturar
    
    return base_replies


def _get_fallback_response(sentimiento: Optional[str]) -> str:
    """
    Respuestas de emergencia cuando falla la IA principal.
    """
    fallbacks = {
        "frustrado": "Entiendo que estás frustrado. Vamos paso a paso: ¿qué es lo primero que necesitas resolver ahora mismo?",
        "ansioso": "Respira. Vamos a simplificar esto. Cierra todo excepto lo esencial y enfócate en UNA cosa.",
        "bloqueado": "Cuando estamos bloqueados, ayuda cambiar de perspectiva. ¿Qué pasaría si empiezas por la parte más fácil?",
        None: "Tuve un problema técnico, pero estoy aquí. Cuéntame: ¿en qué estás trabajando ahora?"
    }
    
    return fallbacks.get(sentimiento, fallbacks[None])


# ============================================================================
# FUNCIÓN AUXILIAR: Extracción de Slots (Groq JSON Mode)
# ============================================================================

async def extract_slots_from_text(user_text: str, current_slots: Slots) -> Slots:
    """
    Extrae slots emocionales y contextuales del texto del usuario.
    Usa Groq Llama 3 en modo JSON.
    """
    try:
        extraction_prompt = f"""
Analiza el siguiente mensaje de un estudiante y extrae parámetros emocionales y contextuales.

Mensaje: "{user_text}"

Extrae:
1. sentimiento: frustrado, ansioso, bloqueado, motivado, neutral
2. tipo_tarea: coding, debugging, ensayo, planificacion, revision, general
3. nivel_urgencia: alta, media, baja
4. autoeficacia: alta (confiado), media, baja (síndrome del impostor)

Responde SOLO un objeto JSON válido con estas claves:
{{"sentimiento": "...", "tipo_tarea": "...", "nivel_urgencia": "...", "autoeficacia": "..."}}
"""
        
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Eres un extractor de datos. Responde JSON válido."},
                {"role": "user", "content": extraction_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=100
        )
        
        # Parsear JSON de la respuesta
        extracted = json.loads(completion.choices[0].message.content)
        
        # Actualizar solo los campos que se detectaron
        for key, value in extracted.items():
            if value and hasattr(current_slots, key):
                setattr(current_slots, key, value)
        
        return current_slots
        
    except Exception as e:
        logger.warning(f"No se pudieron extraer slots: {e}")
        return current_slots
