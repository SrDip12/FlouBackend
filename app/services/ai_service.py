# app/services/ai_service.py

"""
Servicio de IA para Flou - Tutor Metamotivacional (Ported to Groq)
Basado en Miele & Scholer (2016) y el modelo de Task-Motivation Fit.

ARQUITECTURA REFACTORIZADA:
- Cliente AsyncGroq para operaciones no-bloqueantes.
- Streaming de tokens via generador asíncrono (SSE).
- Regex como Guardrail al inicio del pipeline (pre-procesamiento).
- Soporte i18n: el locale se inyecta en el System Prompt.
"""

import logging
import re
import json
import time
from typing import Optional, Dict, List, Tuple, Any, AsyncGenerator
from datetime import datetime
from pathlib import Path

from groq import AsyncGroq
from app.core.config import get_settings
from app.schemas.chat import (
    SessionStateSchema, Slots, QuickReply
)

# Configurar logging
logger = logging.getLogger(__name__)

# Configurar Cliente Groq ASÍNCRONO para streaming y operaciones no-bloqueantes
settings = get_settings()
try:
    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
except Exception as e:
    logger.error(f"Error inicializando cliente AsyncGroq: {e}")
    client = None

MODEL_NAME = 'llama-3.3-70b-versatile'
AI_NAME = 'Flou'

# Cargar estrategias desde JSON
STRATEGIES = []
try:
    strategies_path = Path("app/data/strategies.json")
    if strategies_path.exists():
        with open(strategies_path, "r", encoding="utf-8") as f:
            STRATEGIES = json.load(f)
        logger.info(f"Cargadas {len(STRATEGIES)} estrategias científicas.")
    else:
        logger.warning("No se encontró app/data/strategies.json")
except Exception as e:
    logger.error(f"Error cargando estrategias: {e}")

# ============================================================================
# LOGGING ESTRUCTURADO
# ============================================================================

def log_structured(level: str, event: str, **kwargs):
    """Helper para logging estructurado con contexto completo"""
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
        "service": "ai_service",
        **kwargs
    }
    getattr(logger, level)(json.dumps(log_data))

# ============================================================================
# HEURÍSTICAS DE EXTRACCIÓN (Portadas del original)
# ============================================================================

def guess_plazo(text: str) -> Optional[str]:
    text_lower = text.lower()
    if re.search(r'hoy|hoy día|ahora|en el día|para la noche', text_lower):
        return "hoy"
    if re.search(r'mañana|24\s*h|en un día', text_lower):
        return "<24h"
    if re.search(r'próxima semana|la otra semana|esta semana|en estos días|antes del finde', text_lower):
        return "esta_semana"
    if re.search(r'mes|semanas|>\s*1|próximo mes|largo plazo', text_lower):
        return ">1_semana"
    return None

def guess_tipo_tarea(text: str) -> Optional[str]:
    text_lower = text.lower()
    if re.search(r'ensayo|essay|informe|reporte|escrito', text_lower):
        return "ensayo"
    if re.search(r'esquema|outline|mapa conceptual|diagrama', text_lower):
        return "esquema"
    if re.search(r'borrador|draft|avance', text_lower):
        return "borrador"
    if re.search(r'presentaci(ón|on)|slides|powerpoint|discurso', text_lower):
        return "presentacion"
    if re.search(r'proof|corregir|correcci(ón|on)|edita(r|ción)|feedback', text_lower):
        return "proofreading"
    if re.search(r'mcq|alternativa(s)?|test|prueba|examen', text_lower):
        return "mcq"
    if re.search(r'protocolo|laboratorio|lab', text_lower):
        return "protocolo_lab"
    if re.search(r'problema(s)?|ejercicio(s)?|cálculo|guía', text_lower):
        return "resolver_problemas"
    if re.search(r'lectura|paper|art[ií]culo|leer|texto', text_lower):
        return "lectura_tecnica"
    if re.search(r'resumen|sintetizar|síntesis', text_lower):
        return "resumen"
    if re.search(r'c(ó|o)digo|programar', text_lower) and not re.search(r'bug|error', text_lower):
        return "coding"
    if re.search(r'bug|error|debug', text_lower):
        return "bugfix"
    return None

def guess_fase(text: str) -> Optional[str]:
    text_lower = text.lower()
    if re.search(r'ide(a|ación)|brainstorm|empezando|inicio', text_lower):
        return "ideacion"
    if re.search(r'plan|organizar|estructura', text_lower):
        return "planificacion"
    if re.search(r'escribir|redacci(ón|on)|hacer|resolver|desarrollar|avanzando', text_lower):
        return "ejecucion"
    if re.search(r'revis(ar|ión)|editar|proof|corregir|finalizando|últimos detalles', text_lower):
        return "revision"
    return None

def guess_sentimiento(text: str) -> Optional[str]:
    text_lower = text.lower()
    if re.search(r'frustra|enojado|molesto|rabia|irritado|impotencia|bloqueado|estancado', text_lower):
        return "frustracion"
    if re.search(r'ansiedad|miedo a equivocarme|nervios|preocupado|estresado|tenso|pánico|abrumado|agobiado', text_lower):
        return "ansiedad_error"
    if re.search(r'aburri|lata|paja|sin ganas|monótono|repetitivo|tedioso|desinterés', text_lower):
        return "aburrimiento"
    if re.search(r'dispers|distraído|rumi|dando vueltas|no me concentro|mente en blanco|divago|perdido', text_lower):
        return "dispersion_rumiacion"
    if re.search(r'autoeficacia baja|no puedo|no soy capaz|difícil|superado|inseguro|incapaz|no lo voy a lograr', text_lower):
        return "baja_autoeficacia"
    return None

def guess_tiempo_bloque(text: str) -> Optional[int]:
    text_lower = text.lower()
    if re.search(r'10|diez', text_lower):
        return 10
    if re.search(r'12|doce', text_lower):
        return 12
    if re.search(r'15|quince', text_lower):
        return 15
    if re.search(r'25|veinticinco', text_lower):
        return 25
    if re.search(r'45|cuarenta y cinco', text_lower):
        return 45
    return None

def extract_slots_heuristic(free_text: str, current_slots: Slots) -> Slots:
    """Extracción heurística de slots como fallback"""
    return Slots(
        sentimiento=guess_sentimiento(free_text) or current_slots.sentimiento,
        tipo_tarea=guess_tipo_tarea(free_text) or current_slots.tipo_tarea,
        plazo=guess_plazo(free_text) or current_slots.plazo,
        fase=guess_fase(free_text) or current_slots.fase,
        tiempo_bloque=guess_tiempo_bloque(free_text) or current_slots.tiempo_bloque
    )


# ============================================================================
# EXTRACCIÓN CON LLM (Groq)
# ============================================================================

async def extract_slots_with_llm(free_text: str, current_slots: Slots) -> Slots:
    """Extrae slots usando Groq JSON mode"""
    if not client:
        return extract_slots_heuristic(free_text, current_slots)

    try:
        sys_prompt = """Extrae como JSON los campos del texto del usuario:
- sentimiento: aburrimiento|frustracion|ansiedad_error|dispersion_rumiacion|baja_autoeficacia|otro
- sentimiento_otro: texto libre si es "otro"
- tipo_tarea: ensayo|esquema|borrador|lectura_tecnica|resumen|resolver_problemas|protocolo_lab|mcq|presentacion|coding|bugfix|proofreading
- plazo: hoy|<24h|esta_semana|>1_semana
- fase: ideacion|planificacion|ejecucion|revision
- tiempo_bloque: 10|12|15|20|25|30|45|60|90

Si un campo no aparece y no está en los slots actuales, usa null. Responde SOLO JSON."""

        user_prompt = f"""Texto: "{free_text}"
Slots actuales: {current_slots.model_dump_json()}"""

        completion = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=200
        )
        
        parsed = json.loads(completion.choices[0].message.content)
        
        return Slots(
            sentimiento=parsed.get('sentimiento') or current_slots.sentimiento,
            sentimiento_otro=parsed.get('sentimiento_otro') or current_slots.sentimiento_otro,
            tipo_tarea=parsed.get('tipo_tarea') or current_slots.tipo_tarea,
            ramo=parsed.get('ramo') or current_slots.ramo,
            plazo=parsed.get('plazo') or current_slots.plazo,
            fase=parsed.get('fase') or current_slots.fase,
            tiempo_bloque=parsed.get('tiempo_bloque') or current_slots.tiempo_bloque
        )
    except Exception as e:
        logger.warning(f"Error LLM extraction: {e}")
        return extract_slots_heuristic(free_text, current_slots)

# ============================================================================
# LOGICA DE ESTRATEGIAS (Determinística)
# ============================================================================

def infer_q2_q3(slots: Slots) -> Tuple[str, str, str]:
    """Infiere Q2 (A/B), Q3 (↑/↓) y enfoque"""
    A_tasks = ["ensayo", "esquema", "borrador", "presentacion", "coding"]
    B_tasks = ["proofreading", "mcq", "protocolo_lab", "resolver_problemas", 
               "bugfix", "lectura_tecnica", "resumen"]
    
    Q2 = "A"
    if slots.tipo_tarea in B_tasks:
        Q2 = "B"
    if slots.fase == "revision" or slots.plazo in ["hoy", "<24h"]:
        Q2 = "B"
    if slots.fase in ["ideacion", "planificacion"]:
        Q2 = "A"
    
    Q3 = "↓"
    if slots.fase in ["ideacion", "planificacion"]:
        Q3 = "↑"
    if slots.fase == "revision" or slots.plazo in ["hoy", "<24h"]:
        Q3 = "↓"
    
    # Mixto
    if slots.tipo_tarea == "ensayo" and slots.fase in ["planificacion", "ejecucion"]:
        Q3 = "mixto"
    
    enfoque = "promocion_eager" if Q2 == "A" else "prevencion_vigilant"
    return Q2, Q3, enfoque # enfoque is string to match JSON category prefixes

def seleccionar_estrategia(
    enfoque: str,
    nivel: str,
    tipo_tarea: str,
    fase: str,
    tiempo_disponible: int,
    sentimiento: Optional[str] = None,
    excluir: Optional[List[str]] = None
) -> Dict:
    
    # 1. Seguridad: Ansiedad/Baja autoeficacia -> Prevención + Concreto
    if sentimiento in ["ansiedad_error", "baja_autoeficacia"]:
        enfoque = "prevencion_vigilant"
        nivel = "↓" # CONCRETO is ↓
    
    # Convertir nivel a símbolo para comparar con JSON
    nivel_sym = "↑" if nivel == "↑" or nivel == "ABSTRACTO" else "↓"
    
    # Lista de estrategias excluidas (rechazadas previamente)
    excluidas = excluir or []
    
    candidates = []

    # Filtrar candidatos
    for strat in STRATEGIES:
        # Excluir estrategias rechazadas
        if strat.get("nombre") in excluidas:
            continue
        # Check tiempo
        if tiempo_disponible < strat.get("tiempo_minimo", 0):
            continue
            
        # Check tarea (si "cualquiera" o match directo)
        if "cualquiera" not in strat.get("tareas", []) and tipo_tarea not in strat.get("tareas", []):
            continue
            
        # Check fase
        if "cualquiera" not in strat.get("fases", []) and fase not in strat.get("fases", []):
            continue
            
        candidates.append(strat)
    
    # Prioridad: Coincidencia exacta de Enfoque y Nivel
    perfect_match = [s for s in candidates if 
                     s.get("category", "").lower() == enfoque.replace("promocion_eager", "promocion_eager").lower() 
                     or (s.get("enfoque") == enfoque and s.get("nivel") == nivel_sym)]
    
    # Refinar búsqueda
    # Buscar coincidencia de categoría principal (PROMOCION_EAGER / PREVENCION_VIGILANT)
    category_match = [s for s in candidates if s.get("category", "").lower() == enfoque.lower()]
    
    # De los de la misma categoría, buscar el nivel correcto
    level_match = [s for s in category_match if s.get("nivel_recomendado") == nivel_sym]
    
    if level_match:
        return level_match[0]
    
    if category_match:
        return category_match[0]
        
    # Si no hay match de categoría, buscar solo por nivel (ABSTRACTO/CONCRETO)
    cat_nivel = "ABSTRACTO" if nivel_sym == "↑" else "CONCRETO"
    nivel_only_match = [s for s in candidates if s.get("category") == cat_nivel]
    
    if nivel_only_match:
        return nivel_only_match[0]
        
    # Fallback si hay candidatos
    if candidates:
        return candidates[0]
        
    # Fallback absoluto
    return {
        "nombre": "Estrategia Genérica",
        "template": "Entiendo cómo te sientes. Vamos a trabajar en esto juntos/as.\n\n**En los próximos {tiempo} min:**\n{accion_especifica}\n\n¿Te parece bien empezar? 💪",
        "vibe": "NEUTRAL"
    }

# ============================================================================
# CRISIS DETECTION
# ============================================================================

async def detect_crisis(text: str) -> Dict[str, Any]:
    # Regex rápido
    crisis_regex = r'\b(suicid|quitarme la vida|no quiero vivir|hacerme daño|matarme|terminar con todo|autolesión|autolesion|cortarme|acabar con esto|quiero morir|sin salida)\b'
    if not re.search(crisis_regex, text, re.IGNORECASE):
        return {"is_crisis": False, "confidence": 1.0, "reason": "No keywords"}
        
    # Validation with LLM
    if not client:
        return {"is_crisis": True, "confidence": 0.5, "reason": "Regex match (no LLM)"}

    try:
        completion = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Analiza si el mensaje implica riesgo suicida REAL. Responde JSON: {\"is_crisis\": bool, \"confidence\": float}"},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(completion.choices[0].message.content)
    except:
        return {"is_crisis": True, "confidence": 0.5, "reason": "Regex match (LLM failed)"}

# ============================================================================
# SYSTEM PROMPT BUILDER — INFERENCIA ESPECULATIVA
# ============================================================================

def get_system_prompt(
    enfoque: str,
    nivel: str,
    user_locale: str = "es",
    user_name: str = "",
    current_time: str = "",
) -> str:
    """
    Construye el System Prompt con personalidad empática e inferencia especulativa.

    CAMBIO DE PARADIGMA (vs. versión anterior):
    - Antes: "Formulario policial" → 5 preguntas secuenciales obligatorias.
    - Ahora: Coach empático que INFIERE datos y propone de inmediato.
      Si le falta info, propone una estrategia razonable y pregunta
      "¿te sirve esto?" en lugar de interrogar.

    Args:
        enfoque: Resultado de Q2 (promocion_eager / prevencion_vigilant)
        nivel: Resultado de Q3 (↑ abstracto / ↓ concreto)
        user_locale: Idioma del usuario ('es' | 'en')
        user_name: Nombre del usuario (opcional, para personalizar el saludo)
        current_time: Hora actual en formato legible (ej: "14:30")
    """
    # --- Traducir la orientación motivacional a lenguaje natural ---
    # (Task-Motivation Fit camuflado: la IA actúa pero no verbaliza la teoría)
    if enfoque == "promocion_eager":
        orientacion_interna = (
            "El usuario está en MODO PROMOCIÓN-ENTUSIASTA. "
            "Priorizas velocidad, avanzar rápido, logros tangibles. "
            "Minimizas perfeccionismo. Tono enérgico, directo, motivador."
        )
    else:
        orientacion_interna = (
            "El usuario está en MODO PREVENCIÓN-VIGILANTE. "
            "Priorizas calidad, revisión cuidadosa, evitar errores. "
            "Tono calmado, estructurado, tranquilizador."
        )

    if nivel == "↑":
        nivel_interno = (
            "NIVEL ABSTRACTO: Conecta la tarea con su propósito, el 'por qué' importa. "
            "Motiva con visión y significado."
        )
    else:
        nivel_interno = (
            "NIVEL CONCRETO: El usuario necesita el 'cómo'. Pasos claros, "
            "detalles prácticos, micro-acciones inmediatas."
        )

    # --- Bloque de personalidad y tono según idioma ---
    if user_locale == "en":
        personalidad = f"""You are **Flou**, a warm and empathetic productivity coach.
You specialize in helping people start, focus, and follow through — especially when motivation is low.

YOUR VOICE:
- Professional yet warm. Think: supportive friend who happens to know psychology.
- Use emojis naturally (not excessively). Max 2-3 per message.
- Never sound robotic, scripted, or like a chatbot. Be human.
- Address the user{f' as {user_name}' if user_name else ''} with warmth.
{f'- Current time is {current_time}. Use this to contextualize your advice (morning energy, afternoon slump, late-night crunch).' if current_time else ''}

LANGUAGE: ALWAYS respond in English."""
    else:
        personalidad = f"""Eres **Flou**, una coach de productividad empática y cercana.
Te especializas en ayudar a las personas a comenzar, enfocarse y terminar — sobre todo cuando la motivación es baja.

TU VOZ:
- Habla de forma natural y cálida, como alguien que sabe de psicología y quiere ayudar. Nada de sonar como bot.
- Usa español neutro e internacional. Evita regionalismos, jerga o modismos locales.
- Usa emojis de forma orgánica (no abuses). Máximo 2-3 por mensaje.
- {f'Al usuario le dices {user_name}.' if user_name else 'Habla con calidez.'}
{f'- La hora actual es {current_time}. Úsala para contextualizar (energía matutina, bajón de tarde, sesión nocturna de estudio).' if current_time else ''}

IDIOMA: Responde SIEMPRE en Español neutro, comprensible en cualquier país hispanohablante."""

    # --- Bloque de inferencia especulativa ---
    if user_locale == "en":
        inferencia = """SPECULATIVE INFERENCE (CRITICAL):
- NEVER stop the conversation to ask for trivial data. If the user says "I have an exam", ASSUME it's soon and offer immediate help.
- If you're missing critical info, PROPOSE a reasonable strategy and ask "does this work for you?" instead of interrogating.
- You can infer: task type from context, urgency from language, emotional state from tone.
- Examples of WHAT NOT TO DO:
  ❌ "What type of task is this?"
  ❌ "When is your deadline?"
  ❌ "On a scale of 1-5, how stressed are you?"
- Examples of WHAT TO DO:
  ✅ "Sounds like you need to tackle some writing — here's a quick approach: [strategy]. Does this feel right?"
  ✅ "I can tell this is stressing you out. Let's start with just 10 minutes of focused work, then reassess."
  ✅ "Exam coming up? Here's a study sprint that works well under pressure..."
- Only ask ONE follow-up question at most, and only if genuinely ambiguous."""
    else:
        inferencia = """INFERENCIA ESPECULATIVA (CRÍTICO):
- NUNCA detengas la conversación para pedir datos triviales. Si el usuario dice "tengo examen", ASUME que es pronto y ofrece ayuda inmediata.
- Si te faltan datos críticos, PROPÓN una estrategia razonable y pregunta "¿te funciona esto?" en vez de interrogar.
- Puedes inferir: tipo de tarea por el contexto, urgencia por las palabras, estado emocional por el tono.
- Ejemplos de lo que NO debes hacer:
  ❌ "¿Qué tipo de tarea es?"
  ❌ "¿Para cuándo es tu plazo?"
  ❌ "Del 1 al 5, ¿qué tan estresado/a estás?"
- Ejemplos de lo que SÍ debes hacer:
  ✅ "Parece que necesitas ponerte a escribir — mira esta técnica: [estrategia]. ¿Te funciona?"
  ✅ "Noto que esto te está generando estrés. Empecemos con solo 10 minutos enfocados y vemos cómo va."
  ✅ "¿Examen pronto? Tengo un sprint de estudio que funciona muy bien bajo presión..."
- Si algo es genuinamente ambiguo, pregunta UNA sola cosa. Máximo una pregunta de seguimiento."""

    # --- Bloque de metodología (camuflada) ---
    if user_locale == "en":
        metodologia = f"""INTERNAL COMPASS (do NOT mention this to the user):
{orientacion_interna}
{nivel_interno}

Use this compass to calibrate your tone, your recommendations, and how much detail you give.
The user should never hear terms like "Promotion Focus" or "Prevention Focus". Just ACT accordingly."""
    else:
        metodologia = f"""BRÚJULA INTERNA (NO menciones esto al usuario):
{orientacion_interna}
{nivel_interno}

Usa esta brújula para calibrar tu tono, tus recomendaciones y cuánto detalle das.
El usuario NUNCA debe escuchar términos como "Enfoque de Promoción" o "Prevención". Simplemente ACTÚA acorde."""

    # --- Reglas de formato ---
    if user_locale == "en":
        formato = """RESPONSE RULES:
1. Validate the user's emotion in ONE empathetic phrase (never skip this).
2. Provide ONE specific, actionable recommendation — not a list of 5 options.
3. If the user is just chatting (no clear task), be conversational and empathetic. Don't force a strategy.
4. Keep responses under 100 words. Be concise. No walls of text.
5. Use **bold** for key actions or strategy names.
6. When you propose a strategy, frame it as an invitation: "Want to try...?" or "How about we...?"
7. NEVER output JSON, NEVER mention slots, NEVER say "I need more information"."""
    else:
        formato = """REGLAS DE RESPUESTA:
1. Valida la emoción del usuario en UNA frase empática (nunca te la saltes).
2. Da UNA sola recomendación específica y accionable — no una lista de 5 opciones.
3. Si el usuario solo conversa (sin tarea clara), sé conversacional y empática. No fuerces una estrategia.
4. Mantén respuestas bajo 100 palabras. Sé concisa. Nada de muros de texto.
5. Usa **negrita** para acciones clave o nombres de estrategias.
6. Cuando propones una estrategia, formúlala como invitación: "¿Te gustaría probar...?" o "¿Qué tal si...?"
7. NUNCA respondas JSON, NUNCA menciones slots, NUNCA digas "necesito más información"."""

    # --- Ensamblaje final del prompt ---
    return f"""{personalidad}

{inferencia}

{metodologia}

{formato}
"""

# ============================================================================
# ORQUESTADOR PRINCIPAL
# ============================================================================

async def handle_user_turn(
    session: SessionStateSchema, 
    user_text: str, 
    context: str = "", 
    chat_history: Optional[List[Dict[str, str]]] = None,
    user_locale: str = "es"
) -> Tuple[str, SessionStateSchema, Optional[List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Orquestador principal del turno de conversación.
    
    FLUJO REFACTORIZADO (Regex como Guardrail):
    1. PRE-PROCESAMIENTO: Regex detecta comandos (__greeting__, __accept__, __reject__)
       y crisis. Si hay match → respuesta inmediata, NO se llama al LLM.
    2. EXTRACCIÓN: Si no hay guardrail → extraer slots con LLM.
    3. ONBOARDING: Fases guiadas para recopilar datos.
    4. INFERENCIA: Q2/Q3 + selección de estrategia.
    5. GENERACIÓN LLM: Con i18n inyectado en el System Prompt.
    """
    
    # --- Respuestas rápidas de bienvenida (reutilizables) ---
    greeting_quick_replies = [
        {"label": "😑 Aburrido/a", "value": "Estoy aburrido"},
        {"label": "😤 Frustrado/a", "value": "Estoy frustrado"},
        {"label": "😰 Ansioso/a", "value": "Estoy ansioso"},
        {"label": "🌀 Distraído/a", "value": "Estoy distraído"},
    ]

    # 0. Comando especial: Auto-saludo desde el frontend
    if user_text.strip() == "__greeting__":
        session.metadata["greeted"] = True
        return (
            "Hola, soy Flou, tu asistente Task-Motivation. 😊 Para empezar, ¿por qué no me dices cómo está tu motivación hoy?",
            session,
            greeting_quick_replies,
            {}
        )

    # 0b. Comando especial: Validación de estrategia - ACEPTAR
    if user_text.strip() == "__accept_strategy__":
        strategy_name = session.last_strategy or "Estrategia"
        tiempo = session.slots.tiempo_bloque or 15
        return (
            f"¡Genial! 🎯 Vamos con **{strategy_name}**. Tu timer de {tiempo} minutos ya está corriendo. ¡Tú puedes! 💪",
            session,
            None,
            {
                "strategy": strategy_name,
                "timer_config": {"duration_minutes": tiempo, "label": strategy_name}
            }
        )

    # 0c. Comando especial: Validación de estrategia - RECHAZAR
    if user_text.strip() == "__reject_strategy__":
        # Incrementar contador de rechazos en metadata
        rejections = session.metadata.get("strategy_rejections", 0) + 1
        session.metadata["strategy_rejections"] = rejections
        # Registrar estrategia rechazada para no repetirla
        rejected_list = session.metadata.get("rejected_strategies", [])
        if session.last_strategy and session.last_strategy not in rejected_list:
            rejected_list.append(session.last_strategy)
            session.metadata["rejected_strategies"] = rejected_list
        
        # Si ya se rechazaron 2+ estrategias → redirigir a ejercicio de relajación
        if rejections >= 2:
            session.metadata["strategy_rejections"] = 0  # Reiniciar contador
            session.metadata["rejected_strategies"] = []  # Limpiar lista
            return (
                "Entiendo que no hemos encontrado la estrategia ideal todavía. 🧘 "
                "A veces lo mejor es tomarse un momento para relajarse antes de volver al trabajo. "
                "Te recomiendo probar un ejercicio de bienestar. ¡Después volvemos con todo! 💜",
                session,
                None,
                {"redirect": "wellness"}
            )
        
        # Si es el primer rechazo → reiniciar slots de estrategia y buscar otra
        session.strategy_given = False
        session.last_strategy = None
        return (
            "Sin problema, busquemos otra opción. 🔄 ¿Hay algo en particular que te gustaría probar diferente?",
            session,
            [
                {"label": "🔄 Sorpréndeme", "value": "Quiero otra estrategia diferente"},
                {"label": "⏱ Tengo poco tiempo", "value": "Dame algo rápido de hacer"},
                {"label": "🧘 Algo relajado", "value": "Quiero algo tranquilo"}
            ],
            {}
        )

    # 1. Crisis Check
    crisis = await detect_crisis(user_text)
    if crisis.get("is_crisis") and crisis.get("confidence", 0) > 0.7:
        reply = "Escucho que estás en un momento muy difícil. Por favor, busca apoyo inmediato: **llama al 4141** (línea gratuita y confidencial del MINSAL). No estás sola/o."
        return reply, session, None, {}

    # 2. Greeting / Restart
    if "reiniciar" in user_text.lower():
         session = SessionStateSchema(user_id=session.user_id, session_id=session.session_id)
         return "¡Perfecto! Empecemos de nuevo. 🔄\n\n¿Cómo está tu motivación hoy?", session, greeting_quick_replies, {}
         
    if not chat_history and not session.metadata.get("greeted"):
        session.metadata["greeted"] = True
        return "Hola, soy Flou, tu asistente Task-Motivation. 😊 Para empezar, ¿por qué no me dices cómo está tu motivación hoy?", session, greeting_quick_replies, {}

    # 3. Onboarding Flow (Phases 1-5)
    # Extract slots
    new_slots = await extract_slots_with_llm(user_text, session.slots)
    session.slots = new_slots
    session.iteration += 1

    # Phase 1: Sentimiento
    if not session.slots.sentimiento and session.iteration <= 3:
        return "Para poder ayudarte mejor, ¿cómo te sientes ahora mismo con tu trabajo?", session, [
             {"label": "😑 Aburrido/a", "value": "Me siento aburrido"},
             {"label": "😤 Frustrado/a", "value": "Me siento frustrado"},
             {"label": "😰 Ansioso/a", "value": "Tengo ansiedad"},
             {"label": "🌀 Distraído/a", "value": "Estoy distraído"}
        ], {}

    # Phase 2: Tarea
    if session.slots.sentimiento and not session.slots.tipo_tarea and session.iteration <= 4:
         return "Perfecto. Ahora cuéntame, ¿qué tipo de trabajo necesitas hacer?", session, [
            {"label": "📝 Escribir ensayo", "value": "Tengo que escribir un ensayo"},
            {"label": "📖 Leer/Estudiar", "value": "Tengo que leer"},
            {"label": "🧮 Resolver ejercicios", "value": "Tengo que resolver ejercicios"},
            {"label": "💻 Programar", "value": "Tengo que programar"}
         ], {}

    # Phase 3: Plazo
    if session.slots.sentimiento and session.slots.tipo_tarea and not session.slots.plazo and session.iteration <= 5:
        return "Entiendo. ¿Para cuándo necesitas tenerlo listo?", session, [
            {"label": "🔥 Hoy mismo", "value": "Es para hoy"},
            {"label": "⏰ Mañana", "value": "Es para mañana"},
            {"label": "📅 Esta semana", "value": "Es para esta semana"},
        ], {}

    # Phase 4: Fase
    if session.slots.sentimiento and session.slots.tipo_tarea and session.slots.plazo and not session.slots.fase and session.iteration <= 6:
        return "Muy bien. ¿En qué etapa del trabajo estás ahora?", session, [
            {"label": "💡 Empezando (Ideas)", "value": "Estoy en la fase de ideacion"},
            {"label": "📝 Ejecutando", "value": "Estoy ejecutando"},
            {"label": "🔍 Revisando", "value": "Estoy revisando"}
        ], {}

    # Phase 5: Tiempo disponible — preguntar cuánto tiempo tiene el usuario
    if not session.slots.tiempo_bloque and session.iteration <= 7:
        return "¡Ya casi! ⏱ ¿Cuánto tiempo tienes disponible ahora para trabajar con una estrategia?", session, [
            {"label": "⚡ 10 min", "value": "Tengo 10 minutos"},
            {"label": "⏰ 15 min", "value": "Tengo 15 minutos"},
            {"label": "🕐 25 min", "value": "Tengo 25 minutos"},
            {"label": "🕑 45 min", "value": "Tengo 45 minutos"},
        ], {}

    # Fallback: si no se extrajo tiempo después de varias iteraciones, usar 15 min
    # Solo si ya pasamos la fase de preguntas y estamos forzando una estrategia
    if not session.slots.tiempo_bloque and session.iteration > 8:
        session.slots.tiempo_bloque = 15

    # 4. Inferir Q2/Q3/Enfoque
    Q2, Q3, enfoque = infer_q2_q3(session.slots)
    session.metadata["Q2"] = Q2
    session.metadata["Q3"] = Q3
    session.metadata["enfoque"] = enfoque
    
    # 5. Seleccionar Estrategia
    estrategia = seleccionar_estrategia(
        enfoque=enfoque,
        nivel=Q3,
        tipo_tarea=session.slots.tipo_tarea,
        fase=session.slots.fase,
        tiempo_disponible=session.slots.tiempo_bloque or 15, # Fallback solo para selección
        sentimiento=session.slots.sentimiento
    )
    
    # Excluir estrategias previamente rechazadas para buscar alternativas
    rejected = session.metadata.get("rejected_strategies", [])
    if estrategia["nombre"] in rejected:
        # Buscar otra estrategia que no haya sido rechazada
        alt = seleccionar_estrategia(
            enfoque=enfoque, nivel=Q3,
            tipo_tarea=session.slots.tipo_tarea,
            fase=session.slots.fase,
            tiempo_disponible=session.slots.tiempo_bloque or 15,
            sentimiento=session.slots.sentimiento,
            excluir=rejected  # Pasar lista de excluidas
        )
        estrategia = alt
    
    session.last_strategy = estrategia["nombre"]
    session.strategy_given = True
    
    # 6. Generar respuesta con Groq (con i18n + hora actual en el prompt)
    hora_actual = datetime.now().strftime("%H:%M")
    system_prompt = get_system_prompt(
        enfoque, Q3,
        user_locale=user_locale,
        current_time=hora_actual,
    )
    system_prompt += f"\n\nESTRATEGIA A APLICAR: {estrategia['nombre']}\nDESCRIPCIÓN: {estrategia['descripcion']}\nTEMPLATE: {estrategia['template']}\n"
    system_prompt += f"\nVariables: tiempo={session.slots.tiempo_bloque or 15}, tema={session.slots.tipo_tarea}\n"
    
    messages = [{"role": "system", "content": system_prompt}]
    if chat_history:
        for msg in chat_history[-6:]:
            role = "user" if msg.get("role") == "user" else "assistant"
            content = msg.get("parts", [""])[0] if isinstance(msg.get("content"), list) else msg.get("content", "")
            if not content and "text" in msg: content = msg["text"]
            messages.append({"role": role, "content": str(content)})
    
    messages.append({"role": "user", "content": user_text})
    
    try:
        # Llamada ASÍNCRONA al LLM (sin streaming para el endpoint clásico)
        completion = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generation: {e}")
        reply = estrategia['template'].format(
            tiempo=session.slots.tiempo_bloque or 15, 
            tema=session.slots.tipo_tarea,
            cantidad="varios",
            paso_1="Paso 1", paso_2="Paso 2", paso_3="Paso 3",
            item_1="Item 1", item_2="Item 2", item_3="Item 3", 
            paso_1_detallado="Paso 1", paso_2_detallado="Paso 2", paso_3_detallado="Paso 3",
            mitad_tiempo=int((session.slots.tiempo_bloque or 15)/2),
            accion_especifica="Comenzar"
        )

    # Metadata response: SOLO enviamos la estrategia propuesta para validación.
    # NO enviamos timer_config aquí. El timer se envía solo al aceptar.
    response_metadata = {
        "strategy": estrategia["nombre"]
    }

    # Quick replies: ahora incluyen validación de estrategia
    quick_replies = [
        {"label": "✅ Empezar", "value": "__accept_strategy__", "icon": "✅", "color": "mint"},
        {"label": "🔄 Otra opción", "value": "__reject_strategy__", "icon": "🔄", "color": "sky"}
    ]

    return reply, session, quick_replies, response_metadata


# ============================================================================
# GENERADOR ASÍNCRONO DE STREAMING (SSE)
# ============================================================================

async def handle_user_turn_stream(
    session: SessionStateSchema,
    user_text: str,
    context: str = "",
    chat_history: Optional[List[Dict[str, str]]] = None,
    user_locale: str = "es"
) -> AsyncGenerator[str, None]:
    """
    Generador asíncrono que emite eventos SSE (Server Sent Events).
    Cada evento tiene el formato: "data: {json}\n\n"
    
    El frontend puede consumirlo con EventSource o fetch + ReadableStream.
    
    FLUJO:
    1. Emite 'start' → señal de inicio.
    2. GUARDRAIL REGEX: Si detecta comando o crisis → emite 'guardrail' + 'done' y SALE.
    3. Si no hay guardrail → pipeline normal de onboarding/slots.
    4. Si hay respuesta determinística (onboarding) → emite 'guardrail' + 'done'.
    5. Si se necesita LLM → stream de tokens uno a uno.
    6. Al finalizar tokens → emite 'quick_reply', 'metadata', 'session_state', 'done'.
    """
    import time as _time
    
    # --- Helper: formatear evento SSE ---
    def sse_event(event_type: str, data: Any) -> str:
        """Formatea un chunk como evento SSE estándar."""
        payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False)
        return f"data: {payload}\n\n"
    
    # --- 1. Emitir señal de inicio ---
    yield sse_event("start", {
        "session_id": str(session.session_id),
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # --- Respuestas rápidas de bienvenida (reutilizables) ---
    greeting_quick_replies = [
        {"label": "😑 Aburrido/a", "value": "Estoy aburrido"},
        {"label": "😤 Frustrado/a", "value": "Estoy frustrado"},
        {"label": "😰 Ansioso/a", "value": "Estoy ansioso"},
        {"label": "🌀 Distraído/a", "value": "Estoy distraído"},
    ]

    # =====================================================================
    # FASE 1: GUARDRAILS REGEX (Pre-procesamiento, NO llama al LLM)
    # =====================================================================
    
    # Guardrail: Comando __greeting__
    if user_text.strip() == "__greeting__":
        session.metadata["greeted"] = True
        yield sse_event("guardrail", {
            "text": "Hola, soy Flou, tu asistente Task-Motivation. 😊 Para empezar, ¿por qué no me dices cómo está tu motivación hoy?",
            "quick_replies": greeting_quick_replies
        })
        yield sse_event("session_state", session.model_dump(mode='json'))
        yield sse_event("done", {})
        return
    
    # Guardrail: Comando __accept_strategy__
    if user_text.strip() == "__accept_strategy__":
        strategy_name = session.last_strategy or "Estrategia"
        tiempo = session.slots.tiempo_bloque or 15
        yield sse_event("guardrail", {
            "text": f"¡Genial! 🎯 Vamos con **{strategy_name}**. Tu timer de {tiempo} minutos ya está corriendo. ¡Tú puedes! 💪",
            "quick_replies": None
        })
        yield sse_event("metadata", {
            "strategy": strategy_name,
            "timer_config": {"duration_minutes": tiempo, "label": strategy_name}
        })
        yield sse_event("session_state", session.model_dump(mode='json'))
        yield sse_event("done", {})
        return
    
    # Guardrail: Comando __reject_strategy__
    if user_text.strip() == "__reject_strategy__":
        rejections = session.metadata.get("strategy_rejections", 0) + 1
        session.metadata["strategy_rejections"] = rejections
        rejected_list = session.metadata.get("rejected_strategies", [])
        if session.last_strategy and session.last_strategy not in rejected_list:
            rejected_list.append(session.last_strategy)
            session.metadata["rejected_strategies"] = rejected_list
        
        if rejections >= 2:
            session.metadata["strategy_rejections"] = 0
            session.metadata["rejected_strategies"] = []
            yield sse_event("guardrail", {
                "text": "Entiendo que no hemos encontrado la estrategia ideal todavía. 🧘 A veces lo mejor es tomarse un momento para relajarse antes de volver al trabajo. Te recomiendo probar un ejercicio de bienestar. ¡Después volvemos con todo! 💜",
                "quick_replies": None
            })
            yield sse_event("metadata", {"redirect": "wellness"})
        else:
            session.strategy_given = False
            session.last_strategy = None
            yield sse_event("guardrail", {
                "text": "Sin problema, busquemos otra opción. 🔄 ¿Hay algo en particular que te gustaría probar diferente?",
                "quick_replies": [
                    {"label": "🔄 Sorpréndeme", "value": "Quiero otra estrategia diferente"},
                    {"label": "⏱ Tengo poco tiempo", "value": "Dame algo rápido de hacer"},
                    {"label": "🧘 Algo relajado", "value": "Quiero algo tranquilo"}
                ]
            })
        yield sse_event("session_state", session.model_dump(mode='json'))
        yield sse_event("done", {})
        return
    
    # Guardrail: Detección de CRISIS (regex rápido + validación LLM)
    crisis = await detect_crisis(user_text)
    if crisis.get("is_crisis") and crisis.get("confidence", 0) > 0.7:
        yield sse_event("guardrail", {
            "text": "Escucho que estás en un momento muy difícil. Por favor, busca apoyo inmediato: **llama al 4141** (línea gratuita y confidencial del MINSAL). No estás sola/o.",
            "quick_replies": None,
            "is_crisis": True
        })
        yield sse_event("session_state", session.model_dump(mode='json'))
        yield sse_event("done", {})
        return
    
    # Guardrail: Reiniciar sesión
    if "reiniciar" in user_text.lower():
        session = SessionStateSchema(user_id=session.user_id, session_id=session.session_id)
        yield sse_event("guardrail", {
            "text": "¡Perfecto! Empecemos de nuevo. 🔄\n\n¿Cómo está tu motivación hoy?",
            "quick_replies": greeting_quick_replies
        })
        yield sse_event("session_state", session.model_dump(mode='json'))
        yield sse_event("done", {})
        return
    
    # Guardrail: Saludo inicial automático
    if not chat_history and not session.metadata.get("greeted"):
        session.metadata["greeted"] = True
        yield sse_event("guardrail", {
            "text": "Hola, soy Flou, tu asistente Task-Motivation. 😊 Para empezar, ¿por qué no me dices cómo está tu motivación hoy?",
            "quick_replies": greeting_quick_replies
        })
        yield sse_event("session_state", session.model_dump(mode='json'))
        yield sse_event("done", {})
        return

    # =====================================================================
    # FASE 2: EXTRACCIÓN DE SLOTS + ONBOARDING (respuestas determinísticas)
    # =====================================================================
    new_slots = await extract_slots_with_llm(user_text, session.slots)
    session.slots = new_slots
    session.iteration += 1

    # Fases de onboarding: preguntas guiadas (sin LLM)
    onboarding_response = _check_onboarding_phase(session)
    if onboarding_response:
        text, qr = onboarding_response
        yield sse_event("guardrail", {"text": text, "quick_replies": qr})
        yield sse_event("session_state", session.model_dump(mode='json'))
        yield sse_event("done", {})
        return

    # Fallback: si no hay tiempo tras muchas iteraciones
    if not session.slots.tiempo_bloque and session.iteration > 8:
        session.slots.tiempo_bloque = 15

    # =====================================================================
    # FASE 3: INFERENCIA + SELECCIÓN DE ESTRATEGIA
    # =====================================================================
    Q2, Q3, enfoque = infer_q2_q3(session.slots)
    session.metadata["Q2"] = Q2
    session.metadata["Q3"] = Q3
    session.metadata["enfoque"] = enfoque

    estrategia = seleccionar_estrategia(
        enfoque=enfoque, nivel=Q3,
        tipo_tarea=session.slots.tipo_tarea,
        fase=session.slots.fase,
        tiempo_disponible=session.slots.tiempo_bloque or 15,
        sentimiento=session.slots.sentimiento
    )

    rejected = session.metadata.get("rejected_strategies", [])
    if estrategia["nombre"] in rejected:
        estrategia = seleccionar_estrategia(
            enfoque=enfoque, nivel=Q3,
            tipo_tarea=session.slots.tipo_tarea,
            fase=session.slots.fase,
            tiempo_disponible=session.slots.tiempo_bloque or 15,
            sentimiento=session.slots.sentimiento,
            excluir=rejected
        )

    session.last_strategy = estrategia["nombre"]
    session.strategy_given = True

    # =====================================================================
    # FASE 4: STREAMING DE TOKENS DEL LLM (Groq con stream=True)
    # =====================================================================
    hora_actual = datetime.now().strftime("%H:%M")
    system_prompt = get_system_prompt(
        enfoque, Q3,
        user_locale=user_locale,
        current_time=hora_actual,
    )
    system_prompt += f"\n\nESTRATEGIA A APLICAR: {estrategia['nombre']}\nDESCRIPCIÓN: {estrategia['descripcion']}\nTEMPLATE: {estrategia['template']}\n"
    system_prompt += f"\nVariables: tiempo={session.slots.tiempo_bloque or 15}, tema={session.slots.tipo_tarea}\n"

    messages = [{"role": "system", "content": system_prompt}]
    if chat_history:
        for msg in chat_history[-6:]:
            role = "user" if msg.get("role") == "user" else "assistant"
            content = msg.get("parts", [""])[0] if isinstance(msg.get("content"), list) else msg.get("content", "")
            if not content and "text" in msg:
                content = msg["text"]
            messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": user_text})

    full_reply = ""  # Acumulador para guardar el texto completo en BD
    try:
        # Invocación con stream=True: el LLM envía tokens incrementales
        stream = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=300,
            stream=True  # ← STREAMING ACTIVADO
        )
        
        # Iterar sobre cada chunk del stream asincrónicamente
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                token = delta.content
                full_reply += token
                # Emitir cada token individual al frontend
                yield sse_event("token", {"text": token})
                
    except Exception as e:
        logger.error(f"Error en streaming LLM: {e}")
        # Fallback: usar template de estrategia si el LLM falla
        fallback_reply = estrategia['template'].format(
            tiempo=session.slots.tiempo_bloque or 15,
            tema=session.slots.tipo_tarea,
            cantidad="varios",
            paso_1="Paso 1", paso_2="Paso 2", paso_3="Paso 3",
            item_1="Item 1", item_2="Item 2", item_3="Item 3",
            paso_1_detallado="Paso 1", paso_2_detallado="Paso 2", paso_3_detallado="Paso 3",
            mitad_tiempo=int((session.slots.tiempo_bloque or 15) / 2),
            accion_especifica="Comenzar"
        )
        full_reply = fallback_reply
        yield sse_event("token", {"text": fallback_reply})
        yield sse_event("error", {"message": str(e)})

    # =====================================================================
    # FASE 5: EMISIÓN DE METADATOS POST-STREAM
    # =====================================================================
    
    # Emitir quick replies de validación de estrategia
    yield sse_event("quick_reply", [
        {"label": "✅ Empezar", "value": "__accept_strategy__", "icon": "✅", "color": "mint"},
        {"label": "🔄 Otra opción", "value": "__reject_strategy__", "icon": "🔄", "color": "sky"}
    ])
    
    # Emitir metadata de la estrategia seleccionada
    yield sse_event("metadata", {
        "strategy": estrategia["nombre"],
        "full_reply": full_reply  # Texto completo para persistencia en BD
    })
    
    # Emitir el estado actualizado de la sesión
    yield sse_event("session_state", session.model_dump(mode='json'))
    
    # Señal de fin del stream
    yield sse_event("done", {})


# ============================================================================
# HELPER: VERIFICAR FASE DE ONBOARDING (Extraído para reutilización)
# ============================================================================

def _check_onboarding_phase(
    session: SessionStateSchema
) -> Optional[Tuple[str, List[Dict[str, str]]]]:
    """
    Verifica si la sesión está en una fase de onboarding (recopilación de datos).
    Retorna (texto, quick_replies) si hay pregunta pendiente, o None si ya se completó.
    Extraído como helper para reutilizar en handle_user_turn y handle_user_turn_stream.
    """
    # Fase 1: Sentimiento
    if not session.slots.sentimiento and session.iteration <= 3:
        return (
            "Para poder ayudarte mejor, ¿cómo te sientes ahora mismo con tu trabajo?",
            [
                {"label": "😑 Aburrido/a", "value": "Me siento aburrido"},
                {"label": "😤 Frustrado/a", "value": "Me siento frustrado"},
                {"label": "😰 Ansioso/a", "value": "Tengo ansiedad"},
                {"label": "🌀 Distraído/a", "value": "Estoy distraído"}
            ]
        )
    
    # Fase 2: Tarea
    if session.slots.sentimiento and not session.slots.tipo_tarea and session.iteration <= 4:
        return (
            "Perfecto. Ahora cuéntame, ¿qué tipo de trabajo necesitas hacer?",
            [
                {"label": "📝 Escribir ensayo", "value": "Tengo que escribir un ensayo"},
                {"label": "📖 Leer/Estudiar", "value": "Tengo que leer"},
                {"label": "🧮 Resolver ejercicios", "value": "Tengo que resolver ejercicios"},
                {"label": "💻 Programar", "value": "Tengo que programar"}
            ]
        )
    
    # Fase 3: Plazo
    if session.slots.sentimiento and session.slots.tipo_tarea and not session.slots.plazo and session.iteration <= 5:
        return (
            "Entiendo. ¿Para cuándo necesitas tenerlo listo?",
            [
                {"label": "🔥 Hoy mismo", "value": "Es para hoy"},
                {"label": "⏰ Mañana", "value": "Es para mañana"},
                {"label": "📅 Esta semana", "value": "Es para esta semana"},
            ]
        )
    
    # Fase 4: Fase de trabajo
    if (session.slots.sentimiento and session.slots.tipo_tarea and 
        session.slots.plazo and not session.slots.fase and session.iteration <= 6):
        return (
            "Muy bien. ¿En qué etapa del trabajo estás ahora?",
            [
                {"label": "💡 Empezando (Ideas)", "value": "Estoy en la fase de ideacion"},
                {"label": "📝 Ejecutando", "value": "Estoy ejecutando"},
                {"label": "🔍 Revisando", "value": "Estoy revisando"}
            ]
        )
    
    # Fase 5: Tiempo disponible
    if not session.slots.tiempo_bloque and session.iteration <= 7:
        return (
            "¡Ya casi! ⏱ ¿Cuánto tiempo tienes disponible ahora para trabajar con una estrategia?",
            [
                {"label": "⚡ 10 min", "value": "Tengo 10 minutos"},
                {"label": "⏰ 15 min", "value": "Tengo 15 minutos"},
                {"label": "🕐 25 min", "value": "Tengo 25 minutos"},
                {"label": "🕑 45 min", "value": "Tengo 45 minutos"},
            ]
        )
    
    # No hay fase de onboarding pendiente
    return None
