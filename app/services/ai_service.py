import logging
import json
import uuid
import time
from typing import Optional, Dict, List, AsyncGenerator
from google import genai
from google.genai import types

from app.core.config import settings
from app.schemas.chat import SessionStateSchema, Slots
from app.services.rag_service import rag_engine

logger = logging.getLogger(__name__)

# Nuevo Cliente Unificado
client = genai.Client(api_key=settings.GEMINI_API_KEY)
MODEL_NAME = 'gemini-2.5-flash'  # Modelo actualizado

async def handle_user_turn(
    session: SessionStateSchema, 
    user_text: str, 
    context: str = "", 
    chat_history: Optional[List[Dict[str, str]]] = None
) -> tuple:
    """
    Orquestador v2 con RAG y Generación Dinámica
    """
    # 1. Recuperar Estrategia Inteligente (RAG)
    # Usamos lo que dijo el usuario para buscar en nuestra DB vectorial
    estrategia = rag_engine.retrieve(user_text, session.slots)
    
    # 2. Construir Prompt de Sistema Dinámico
    # Inyectamos la instrucción de actuación específica de la estrategia
    system_instruction = f"""
Eres Flou, un asistente para estudiantes de ingeniería informática.
Tu objetivo es desbloquear al estudiante usando la estrategia seleccionada.

[CONTEXTO DEL USUARIO]
- Sentimiento: {session.slots.sentimiento or 'Neutral'}
- Tarea: {session.slots.tipo_tarea or 'General'}
- Tiempo disponible: {session.slots.tiempo_bloque or 15} min
- Vibe actual: {estrategia.get('vibe', 'NEUTRAL')}

[ESTRATEGIA SELECCIONADA: "{estrategia['nombre']}"]
[TUS INSTRUCCIONES DE ACTUACIÓN]:
{estrategia['prompt_instruction']}

[REGLAS]
1. NO digas "He seleccionado esta estrategia". ¡ACTÚALA DIRECTAMENTE!
2. Sé breve y conciso (máximo 2 párrafos).
3. Termina con una pregunta o acción inmediata.
4. Si el vibe es HACKER, usa términos técnicos. Si es GAMER, usa metáforas de juego.
"""

    # 3. Preparar historial para la nueva API
    contents = []
    if chat_history:
        for msg in chat_history:
            # Adaptación simple de historial
            role = "user" if msg.get("role") == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg.get("parts", [""])[0])]
            ))
    
    # Agregar el mensaje actual
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_text)]
    ))

    try:
        # 4. Generación con Gemini 2.5
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                max_output_tokens=350
            )
        )
        
        reply = response.text
        
        # Actualizar sesión
        session.iteration += 1
        session.last_strategy = reply
        session.strategy_given = True
        
        # Quick replies estándar de feedback
        quick_replies = [
            {"label": "✅ Me sirve", "value": "me ayudó"},
            {"label": "❌ No me sirve", "value": "no funcionó"}
        ]
        
        return reply, session, quick_replies

    except Exception as e:
        logger.error(f"Error en generación Gemini: {e}")
        return "Tuve un error de conexión, pero intentemos esto: divide la tarea en dos y empieza por la mitad.", session, None

# (Nota: Mantén las funciones auxiliares de crisis o extracción de slots si las necesitas, 
# pero la lógica principal de 'handle_user_turn' es esta).
