from fastapi import APIRouter, Depends, HTTPException, Header, Request
from app.schemas.profile import ProfileSettings, ProfileResponse
from app.schemas.profile_stats import ProfileStatsResponse, ProfileUpdateRequest, ProfileUpdateResponse
from app.services.profile_service import ProfileService
from app.core.i18n import detect_user_language, get_translation

router = APIRouter()

# Dependency overrideable for testing
def get_current_user_id(authorization: str = Header(...)):
    """
    Extracts user_id from Authorization header.
    In a real production app, this should verify the JWT signature 
    using Supabase Auth secrets.
    """
    try:
        token = authorization.split(" ")[1]
        user = ProfileService().supabase.auth.get_user(token)
        if not user or not user.user:
             raise HTTPException(status_code=401, detail="Invalid token")
        return user.user.id
    except Exception as e:
        # Fallback for development/testing if auth not fully set up or valid
        # REMOVE IN PRODUCTION
        # return "test-user-id" 
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    service = ProfileService()
    profile = await service.get_profile(user_id)
    return profile

@router.patch("/settings")
async def update_profile_settings(
    request: Request,
    settings: ProfileSettings,
    user_id: str = Depends(get_current_user_id)
):
    service = ProfileService()
    
    # 1. Get current profile to check current language preference for response
    # Or rely on Request header detection first, then updated value.
    # Let's use the helper to detect intent.
    # We pass None for user_prefs initially because we are in the request context, 
    # but strictly speaking, we could fetch DB prefs first. 
    # For efficiency, we just use header or default for the response message language,
    # or the NEW value they are setting!
    
    target_lang = "es"
    if settings.language_preference:
        target_lang = settings.language_preference.value
    else:
        target_lang = detect_user_language(request)

    result = await service.update_settings(user_id, settings, lang=target_lang)
    return result

@router.get("/stats", response_model=ProfileStatsResponse)
async def get_profile_statistics(
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    """
    Endpoint para obtener estadísticas del perfil.
    
    Calcula y devuelve:
    - Racha de días consecutivos con check-in
    - Resumen de los últimos 5 estados de ánimo
    - Promedio de mood_score
    - Estado de ánimo más común
    
    Returns:
        ProfileStatsResponse con todas las estadísticas
    """
    lang = detect_user_language(request)
    service = ProfileService()
    return await service.get_profile_stats(user_id, lang)

@router.put("/update", response_model=ProfileUpdateResponse)
async def update_profile_information(
    request: Request,
    profile_update: ProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Endpoint para actualizar información del perfil.
    
    Permite editar:
    - Carrera o programa de estudios
    - Semestre actual
    - Edad
    - Condiciones de salud
    - Condiciones de neurodivergencia
    - Nombre completo
    
    Returns:
        ProfileUpdateResponse con los campos actualizados
    """
    lang = detect_user_language(request)
    service = ProfileService()
    return await service.update_profile_info(user_id, profile_update, lang)

