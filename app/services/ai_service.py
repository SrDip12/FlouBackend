# app/services/ai_service.py

"""
Servicio de IA para Flou - Tutor Metamotivacional (Ported to Groq)
Basado en Miele & Scholer (2016) y el modelo de Task-Motivation Fit.
Restaura la lógica original determinística y heurística.
"""

import logging
import re
import json
import time
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
from pathlib import Path

from groq import Groq
from app.core.config import get_settings
from app.schemas.chat import (
    SessionStateSchema, Slots, QuickReply
)

# Configurar logging
logger = logging.getLogger(__name__)

# Configurar Cliente Groq
settings = get_settings()
try:
    client = Groq(api_key=settings.GROQ_API_KEY)
except Exception as e:
    logger.error(f"Error inicializando cliente Groq: {e}")
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
        tiempo_bloque=guess_tiempo_bloque(free_text) or current_slots.tiempo_bloque or 15
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

        completion = client.chat.completions.create(
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
    sentimiento: Optional[str] = None
) -> Dict:
    
    # 1. Seguridad: Ansiedad/Baja autoeficacia -> Prevención + Concreto
    if sentimiento in ["ansiedad_error", "baja_autoeficacia"]:
        enfoque = "prevencion_vigilant"
        nivel = "↓" # CONCRETO is ↓
    
    # Convertir nivel a símbolo para comparar con JSON
    nivel_sym = "↑" if nivel == "↑" or nivel == "ABSTRACTO" else "↓"
    
    candidates = []

    # Filtrar candidatos
    for strat in STRATEGIES:
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
        completion = client.chat.completions.create(
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
# SYSTEM PROMPT BUILDER
# ============================================================================

def get_system_prompt(enfoque: str, nivel: str) -> str:
    modo = "ENTUSIASTA (Velocidad, Cantidad, Logros)" if enfoque == "promocion_eager" else "VIGILANTE (Precisión, Calidad, Evitar Errores)"
    nivel_txt = "ABSTRACTO (El Por Qué, Propósito)" if nivel == "↑" else "CONCRETO (El Cómo, Pasos, Detalles)"
    
    return f"""Eres Flou, experta en Metamotivación.
    
TU MODO ACTUAL: {modo}
TU NIVEL DE DETALLE: {nivel_txt}

SI ES MODO ENTUSIASTA: Usa tono enérgico, enfócate en avanzar rápido, ignora errores.
SI ES MODO VIGILANTE: Usa tono calmado, enfócate en revisar y verificar.

REGLAS:
1. Valida la emoción del usuario en 1 frase empática.
2. Da UNA sola acción específica.
3. Sé natural, chilena, usa emojis.
4. Mantén respuesta bajo 90 palabras.
"""

# ============================================================================
# ORQUESTADOR PRINCIPAL
# ============================================================================

async def handle_user_turn(
    session: SessionStateSchema, 
    user_text: str, 
    context: str = "", 
    chat_history: Optional[List[Dict[str, str]]] = None
) -> Tuple[str, SessionStateSchema, Optional[List[Dict[str, Any]]], Dict[str, Any]]:
    
    # 1. Crisis Check
    crisis = await detect_crisis(user_text)
    if crisis.get("is_crisis") and crisis.get("confidence", 0) > 0.7:
        reply = "Escucho que estás en un momento muy difícil. Por favor, busca apoyo inmediato: **llama al 4141** (línea gratuita y confidencial del MINSAL). No estás sola/o."
        return reply, session, None, {}

    # 2. Greeting / Restart
    if "reiniciar" in user_text.lower():
         session = SessionStateSchema(user_id=session.user_id, session_id=session.session_id) # Reset
         return "¡Perfecto! Empecemos de nuevo. 🔄\n\n¿Cómo está tu motivación hoy?", session, [
             {"label": "😑 Aburrido/a", "value": "Estoy aburrido"},
             {"label": "😤 Frustrado/a", "value": "Estoy frustrado"},
             {"label": "😰 Ansioso/a", "value": "Estoy ansioso"},
             {"label": "🌀 Distraído/a", "value": "Estoy distraído"},
         ], {}
         
    if not chat_history and not session.metadata.get("greeted"):
        session.metadata["greeted"] = True
        return "Hola, soy Flou, tu asistente Task-Motivation. 😊 Para empezar, ¿por qué no me dices cómo está tu motivación hoy?", session, [
             {"label": "😑 Aburrido/a", "value": "Estoy aburrido"},
             {"label": "😤 Frustrado/a", "value": "Estoy frustrado"},
             {"label": "😰 Ansioso/a", "value": "Estoy ansioso"},
             {"label": "🌀 Distraído/a", "value": "Estoy distraído"},
        ], {}

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

    # Phase 5: Tiempo (Optional, default 15)
    if not session.slots.tiempo_bloque:
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
        tiempo_disponible=session.slots.tiempo_bloque,
        sentimiento=session.slots.sentimiento
    )
    
    # Check if strategy worked (if user is returning)
    if session.strategy_given:
         # Logic to detect success/failure from user_text would go here
         # For now, simplistic approach: generate next response assuming execution
         pass
    
    session.last_strategy = estrategia["nombre"]
    session.strategy_given = True
    
    # 6. Generate Response with Groq
    system_prompt = get_system_prompt(enfoque, Q3)
    system_prompt += f"\n\nESTRATEGIA A APLICAR: {estrategia['nombre']}\nDESCRIPCIÓN: {estrategia['descripcion']}\nTEMPLATE: {estrategia['template']}\n"
    system_prompt += f"\nVariables: tiempo={session.slots.tiempo_bloque}, tema={session.slots.tipo_tarea}\n"
    
    messages = [{"role": "system", "content": system_prompt}]
    if chat_history:
        for msg in chat_history[-6:]:
            role = "user" if msg.get("role") == "user" else "assistant"
            # Handle list of parts or string content
            content = msg.get("parts", [""])[0] if isinstance(msg.get("content"), list) else msg.get("content", "")
            if not content and "text" in msg: content = msg["text"]
            messages.append({"role": role, "content": str(content)})
    
    messages.append({"role": "user", "content": user_text})
    
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generation: {e}")
        reply = estrategia['template'].format(
            tiempo=session.slots.tiempo_bloque, 
            tema=session.slots.tipo_tarea,
            cantidad="varios",
            paso_1="Paso 1", paso_2="Paso 2", paso_3="Paso 3",
            item_1="Item 1", item_2="Item 2", item_3="Item 3", 
            paso_1_detallado="Paso 1", paso_2_detallado="Paso 2", paso_3_detallado="Paso 3",
            mitad_tiempo=int(session.slots.tiempo_bloque/2),
            accion_especifica="Comenzar"
        )

    return reply, session, [
        {"label": "✅ Me sirvió", "value": "helpful"},
        {"label": "❌ No me sirvió", "value": "not_helpful"}
    ], {"strategy": estrategia["nombre"]}
