from fastapi import APIRouter, Depends, Request
from app.schemas.content import ContentResponse
from app.services.content_service import ContentService
from app.core.i18n import detect_user_language
from app.routers.profiles import get_current_user_id

router = APIRouter()

@router.get("/content", response_model=ContentResponse)
async def get_info_content(
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    """
    Endpoint para obtener el contenido educativo.
    
    Devuelve la lista de 'Tarjetas Educativas' (Autoconocimiento, Energía, etc.)
    con los textos traducidos al idioma preferido del usuario.
    
    Args:
        user_id: ID del usuario autenticado (requerido para acceso)
        
    Returns:
        ContentResponse con la lista de tarjetas
    """
    lang = detect_user_language(request)
    service = ContentService()
    return await service.get_educational_cards(lang)
