from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from typing import List, Optional, AsyncGenerator
from uuid import UUID
import json
import logging
from datetime import datetime

from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatHistoryResponse,
    SessionStateSchema,
    Slots,
    QuickReply,
    MessageMetadata,
    FeedbackRequest,
    StreamChunk
)
from app.services.ai_service import handle_user_turn
from app.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================================
# ENDPOINTS DE SESIONES
# ============================================================================

@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(session_data: ChatSessionCreate):
    """
    Crea una nueva sesión de chat para el usuario.
    """
    supabase = get_supabase()
    
    try:
        # Crear sesión en Supabase
        result = supabase.table("chat_sessions").insert({
            "user_id": str(session_data.user_id),
            "title": session_data.title or "Nueva conversación",
            "is_active": True
        }).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo crear la sesión"
            )
        
        session = result.data[0]
        
        # Mensaje de bienvenida automático
        welcome_message = (
            "¡Hola! Soy Flou, tu asistente para desbloquear tu potencial académico. "
            "Cuéntame: ¿en qué estás trabajando ahora?"
        )
        
        supabase.table("chat_messages").insert({
            "session_id": session["id"],
            "sender": "ai",
            "content": welcome_message,
            "metadata": {
                "strategy_id": "welcome",
                "vibe": "NEUTRAL"
            }
        }).execute()
        
        return ChatSessionResponse(
            id=session["id"],
            user_id=session["user_id"],
            title=session["title"],
            is_active=session["is_active"],
            created_at=session["created_at"],
            message_count=1
        )
        
    except Exception as e:
        logger.error(f"Error creando sesión: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear sesión: {str(e)}"
        )


@router.get("/sessions/{user_id}", response_model=List[ChatSessionResponse])
async def get_user_sessions(user_id: UUID, active_only: bool = True):
    """
    Obtiene todas las sesiones de chat de un usuario.
    """
    supabase = get_supabase()
    
    try:
        query = supabase.table("chat_sessions").select("*").eq("user_id", str(user_id))
        
        if active_only:
            query = query.eq("is_active", True)
        
        result = query.order("created_at", desc=True).execute()
        
        sessions = []
        for session in result.data:
            # Contar mensajes de la sesión
            msg_count = supabase.table("chat_messages")\
                .select("id", count="exact")\
                .eq("session_id", session["id"])\
                .execute()
            
            sessions.append(ChatSessionResponse(
                id=session["id"],
                user_id=session["user_id"],
                title=session["title"],
                is_active=session["is_active"],
                created_at=session["created_at"],
                message_count=msg_count.count if msg_count else 0
            ))
        
        return sessions
        
    except Exception as e:
        logger.error(f"Error obteniendo sesiones: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener sesiones: {str(e)}"
        )


# ============================================================================
# ENDPOINTS DE MENSAJES
# ============================================================================

@router.post("/messages", response_model=ChatMessageResponse)
async def send_message(message_data: ChatMessageRequest):
    """
    Envía un mensaje al chatbot y obtiene una respuesta.
    Mantiene la lógica científica de metamotivación.
    """
    supabase = get_supabase()
    
    try:
        # 1. Obtener o crear sesión
        if message_data.session_id:
            session_result = supabase.table("chat_sessions")\
                .select("*")\
                .eq("id", str(message_data.session_id))\
                .single()\
                .execute()
            
            if not session_result.data:
                raise HTTPException(status_code=404, detail="Sesión no encontrada")
            
            session_id = message_data.session_id
        else:
            # Crear nueva sesión automáticamente
            new_session = supabase.table("chat_sessions").insert({
                "user_id": str(message_data.user_id),
                "title": "Nueva conversación",
                "is_active": True
            }).execute()
            
            session_id = new_session.data[0]["id"]
        
        # 2. Guardar mensaje del usuario
        user_msg = supabase.table("chat_messages").insert({
            "session_id": str(session_id),
            "sender": "user",
            "content": message_data.content
        }).execute()
        
        # 3. Obtener historial de la conversación (últimos 10 mensajes)
        history_result = supabase.table("chat_messages")\
            .select("sender, content")\
            .eq("session_id", str(session_id))\
            .order("created_at", desc=True)\
            .limit(10)\
            .execute()
        
        # Convertir a formato esperado por la IA
        chat_history = []
        for msg in reversed(history_result.data):  # Orden cronológico
            chat_history.append({
                "role": msg["sender"],
                "parts": [msg["content"]]
            })
        
        # 4. Preparar estado de sesión (Recuperar persistencia)
        current_state_json = session_result.data.get("current_state", {})
        if current_state_json and isinstance(current_state_json, dict) and "slots" in current_state_json:
            try:
                # Reconstuimos el estado desde el JSON guardado
                session_state = SessionStateSchema(**current_state_json)
                # Aseguramos que IDs sigan coincidiendo (por si acaso)
                session_state.session_id = session_id
                session_state.user_id = message_data.user_id
            except Exception as e:
                logger.warning(f"Error parseando estado de sesión: {e}, reiniciando estado.")
                session_state = SessionStateSchema(
                    session_id=session_id,
                    user_id=message_data.user_id,
                    slots=Slots()
                )
        else:
            session_state = SessionStateSchema(
                session_id=session_id,
                user_id=message_data.user_id,
                slots=Slots()
            )
        
        # 5. Pipeline de IA (Extracción + Estrategia + Generación)
        # NOTA: extract_slots ahora ocurre DENTRO de handle_user_turn
        ai_reply, updated_session, quick_replies, metadata = await handle_user_turn(
            session=session_state,
            user_text=message_data.content,
            context=message_data.context or "",
            chat_history=chat_history
        )
        
        # 6. Persistir el NUEVO estado de la sesión
        try:
             supabase.table("chat_sessions").update({
                 "current_state": updated_session.model_dump(mode='json')
             }).eq("id", str(session_id)).execute()
        except Exception as e:
             logger.error(f"Error guardando estado de sesión: {e}")

        # 7. Guardar respuesta de la IA
        ai_msg = supabase.table("chat_messages").insert({
            "session_id": str(session_id),
            "sender": "ai",
            "content": ai_reply,
            "metadata": metadata
        }).execute()
        
        # 8. Guardar log de decisión de IA para análisis científico
        if metadata:
            supabase.table("ai_decision_logs").insert({
                "user_id": str(message_data.user_id),
                "chat_message_id": ai_msg.data[0]["id"],
                "detected_parameters": metadata.get("detected_slots"),
                "applied_strategy_id": metadata.get("strategy_id"),
                "confidence_score": metadata.get("confidence_score")
            }).execute()
        
        # 9. Construir respuesta
        return ChatMessageResponse(
            message_id=ai_msg.data[0]["id"],
            session_id=session_id,
            sender="ai",
            content=ai_reply,
            quick_replies=[QuickReply(**qr) for qr in quick_replies] if quick_replies else None,
            metadata=MessageMetadata(**metadata) if metadata else None,
            created_at=ai_msg.data[0]["created_at"]
        )
        
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar mensaje: {str(e)}"
        )


@router.get("/messages/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: UUID, limit: int = 50):
    """
    Obtiene el historial completo de una sesión de chat.
    """
    supabase = get_supabase()
    
    try:
        # Obtener sesión
        session_result = supabase.table("chat_sessions")\
            .select("*")\
            .eq("id", str(session_id))\
            .single()\
            .execute()
        
        if not session_result.data:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        
        # Obtener mensajes
        messages_result = supabase.table("chat_messages")\
            .select("*")\
            .eq("session_id", str(session_id))\
            .order("created_at", desc=False)\
            .limit(limit)\
            .execute()
        
        messages = []
        for msg in messages_result.data:
            messages.append(ChatMessageResponse(
                message_id=msg["id"],
                session_id=session_id,
                sender=msg["sender"],
                content=msg["content"],
                metadata=MessageMetadata(**msg["metadata"]) if msg.get("metadata") else None,
                created_at=msg["created_at"]
            ))
        
        session_data = session_result.data
        return ChatHistoryResponse(
            session=ChatSessionResponse(
                id=session_data["id"],
                user_id=session_data["user_id"],
                title=session_data["title"],
                is_active=session_data["is_active"],
                created_at=session_data["created_at"],
                message_count=len(messages)
            ),
            messages=messages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener historial: {str(e)}"
        )


# ============================================================================
# ENDPOINT DE FEEDBACK
# ============================================================================

@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(feedback: FeedbackRequest):
    """
    Registra feedback del usuario sobre una respuesta de la IA.
    Crítico para mejorar las estrategias de metamotivación.
    """
    supabase = get_supabase()
    
    try:
        # Obtener el mensaje para extraer user_id
        msg_result = supabase.table("chat_messages")\
            .select("session_id")\
            .eq("id", feedback.message_id)\
            .single()\
            .execute()
        
        if not msg_result.data:
            raise HTTPException(status_code=404, detail="Mensaje no encontrado")
        
        session_result = supabase.table("chat_sessions")\
            .select("user_id")\
            .eq("id", msg_result.data["session_id"])\
            .single()\
            .execute()
        
        # Guardar feedback
        supabase.table("feedback").insert({
            "user_id": session_result.data["user_id"],
            "target_type": "chat_session",
            "target_id": str(feedback.message_id),
            "rating": 5 if feedback.rating == "helpful" else 1,
            "comment": feedback.comment
        }).execute()
        
        return {"status": "success", "message": "Feedback registrado"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error guardando feedback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar feedback: {str(e)}"
        )


# ============================================================================
# ENDPOINT DE LIMPIAR CHAT
# ============================================================================

@router.delete("/sessions/{session_id}/clear")
async def clear_chat_session(session_id: UUID):
    """
    Limpia todos los mensajes de una sesión y reinicia el estado de la IA.
    El usuario podrá empezar la conversación de cero sin crear una nueva sesión.
    """
    supabase = get_supabase()
    
    try:
        # Verificar que la sesión existe
        session_result = supabase.table("chat_sessions")\
            .select("id")\
            .eq("id", str(session_id))\
            .maybe_single()\
            .execute()
        
        if not session_result.data:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        
        # 1. Eliminar todos los mensajes de la sesión
        try:
            supabase.table("chat_messages")\
                .delete()\
                .eq("session_id", str(session_id))\
                .execute()
            logger.info(f"Mensajes de sesión {session_id} eliminados.")
        except Exception as del_err:
            logger.warning(f"No se pudieron eliminar mensajes (puede que no haya): {del_err}")
        
        # 2. Reiniciar el estado de la IA (current_state) a vacío
        #    Nota: requiere que la migración 20260211_add_session_state.sql se haya aplicado
        try:
            supabase.table("chat_sessions").update({
                "current_state": {}
            }).eq("id", str(session_id)).execute()
            logger.info(f"Estado de sesión {session_id} reiniciado.")
        except Exception as state_err:
            logger.warning(f"No se pudo reiniciar current_state (columna puede no existir): {state_err}")
        
        logger.info(f"Sesión {session_id} limpiada exitosamente.")
        return {"status": "ok", "message": "Chat limpiado exitosamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error limpiando sesión: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al limpiar sesión: {str(e)}"
        )
