from typing import Dict, Optional
from fastapi import Request

# Diccionario de traducciones simple / Simple translation dictionary
# Estructura: { "KEY": { "es": "...", "en": "..." } }
TRANSLATIONS = {
    "generic_error": {
        "es": "Ha ocurrido un error inesperado.",
        "en": "An unexpected error occurred."
    },
    "not_found": {
        "es": "Recurso no encontrado.",
        "en": "Resource not found."
    },
    "unauthorized": {
        "es": "No autorizado. Por favor inicie sesión.",
        "en": "Unauthorized. Please log in."
    },
    "forbidden": {
        "es": "No tiene permisos para realizar esta acción.",
        "en": "You do not have permission to perform this action."
    },
    "profile_update_success": {
        "es": "Preferencias actualizadas correctamente.",
        "en": "Preferences updated successfully."
    },
    "validation_error": {
        "es": "Error de validación en los datos enviados.",
        "en": "Validation error in the submitted data."
    }
}

DEFAULT_LANGUAGE = "es"
SUPPORTED_LANGUAGES = ["es", "en"]

def get_translation(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """
    Obtiene el texto traducido para una clave dada.
    Si el idioma no existe, usa el default.
    Si la clave no existe, devuelve la clave misma.
    """
    if key not in TRANSLATIONS:
        return key
    
    return TRANSLATIONS[key].get(lang, TRANSLATIONS[key].get(DEFAULT_LANGUAGE, key))

def detect_user_language(request: Request, user_prefs: Optional[dict] = None) -> str:
    """
    Detecta el idioma preferido del usuario basado en la prioridad:
    1. Preferencia de usuario (si se proporciona desde la BD)
    2. Header Accept-Language
    3. Default (es)
    """
    # 1. Preferencia guardada (si existe)
    if user_prefs and user_prefs.get("language_preference"):
        lang = user_prefs.get("language_preference")
        if lang in SUPPORTED_LANGUAGES:
            return lang

    # 2. Header Accept-Language
    accept_language = request.headers.get("accept-language")
    if accept_language:
        # Simplificación: tomar los primeros 2 caracteres. 
        # Un parser más robusto podría ser necesario para casos complejos como 'en-US,en;q=0.9'.
        lang_code = accept_language.split(",")[0].strip()[:2].lower()
        if lang_code in SUPPORTED_LANGUAGES:
            return lang_code

    # 3. Default
    return DEFAULT_LANGUAGE
