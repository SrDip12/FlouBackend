from fastapi import APIRouter, Depends, HTTPException, Header, Request
from app.schemas.wellness import (
    CheckInRequest,
    CheckInResponse,
    EnergyRequest,
    ExerciseResponse,
    MotivationResponse,
    ExerciseCompletionRequest,
    ExerciseCompletionResponse
)
from app.services.wellness_service import WellnessService
from app.core.i18n import detect_user_language
from app.routers.profiles import get_current_user_id

router = APIRouter()

@router.post("/check-in", response_model=CheckInResponse)
async def create_checkin(
    request: Request,
    checkin: CheckInRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Endpoint para guardar un check-in diario.
    
    Recibe el estado emocional (mood_label) y nivel (mood_score).
    Guarda el registro en la tabla daily_checkins.
    
    Args:
        checkin: Datos del check-in (mood_label, mood_score, feelings, note)
        user_id: ID del usuario autenticado
        
    Returns:
        CheckInResponse con los datos guardados y mensaje de confirmación
    """
    lang = detect_user_language(request)
    service = WellnessService()
    return await service.save_checkin(user_id, checkin, lang)


@router.post("/energy", response_model=ExerciseResponse)
async def get_energy_exercise(
    request: Request,
    energy_request: EnergyRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Endpoint para obtener un ejercicio basado en el nivel de energía.
    
    Recibe el nivel de energía (Rojo/Ámbar/Verde) y devuelve un ejercicio
    'mock' (estático) de la tabla relaxation_exercises según el color.
    
    Args:
        energy_request: Nivel de energía del usuario
        user_id: ID del usuario autenticado
        
    Returns:
        ExerciseResponse con el ejercicio recomendado
    """
    lang = detect_user_language(request)
    service = WellnessService()
    return await service.get_exercise_by_energy(energy_request, lang)


@router.get("/motivation", response_model=MotivationResponse)
async def get_motivation(
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    """
    Endpoint para obtener un mensaje motivacional aleatorio de Flou.
    
    Devuelve un mensaje inspirador y de apoyo para el usuario.
    
    Args:
        user_id: ID del usuario autenticado
        
    Returns:
        MotivationResponse con el mensaje motivacional
    """
    lang = detect_user_language(request)
    service = WellnessService()
    return await service.get_motivation_message(lang)


@router.post("/exercises/complete", response_model=ExerciseCompletionResponse)
async def complete_exercise(
    request: Request,
    completion: ExerciseCompletionRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Endpoint para registrar que un ejercicio ha sido completado.
    
    Args:
        completion: Datos del ejercicio completado
        user_id: ID del usuario autenticado
        
    Returns:
        ExerciseCompletionResponse con confirmación
    """
    lang = detect_user_language(request)
    service = WellnessService()
    return await service.save_exercise_completion(user_id, completion, lang)
