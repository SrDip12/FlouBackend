from uuid import UUID
from fastapi import HTTPException
from datetime import datetime, timedelta
from typing import List, Dict
from collections import Counter
from app.core.supabase_client import get_supabase
from app.schemas.profile import ProfileSettings, ProfileResponse
from app.schemas.profile_stats import ProfileStatsResponse, ProfileUpdateRequest, ProfileUpdateResponse
from app.core.i18n import get_translation

class ProfileService:
    def __init__(self):
        self.supabase = get_supabase()

    async def get_profile(self, user_id: str) -> dict:
        """
        Obtiene el perfil de un usuario por su ID.
        """
        try:
            response = self.supabase.table("profiles").select("*").eq("id", user_id).single().execute()
            if not response.data:
                # Esto usualmente no debería pasar si el usuario existe en Auth,
                # pero manejamos el caso.
                raise HTTPException(status_code=404, detail="Profile not found")
            return response.data
        except Exception as e:
            # En una app real, distinguiríamos entre error de red y "no encontrado"
            print(f"Error fetching profile: {e}")
            raise HTTPException(status_code=400, detail=str(e))

    async def update_settings(self, user_id: str, settings: ProfileSettings, lang: str = "es") -> dict:
        """
        Actualiza las preferencias del usuario.
        """
        updates = settings.model_dump(exclude_unset=True)
        
        if not updates:
            return {"message": "No changes provided"}

        try:
            # Actualizamos también updated_at
            # Nota: Supabase suele manejar updated_at con triggers, pero si no, es bueno enviarlo.
            # Asumiremos que mandamos los datos a actualizar.
            response = self.supabase.table("profiles").update(updates).eq("id", user_id).execute()
            
            if not response.data:
                 raise HTTPException(status_code=404, detail=get_translation("not_found", lang))
            
            return {
                "message": get_translation("profile_update_success", lang),
                "data": response.data[0]
            }
        except Exception as e:
            print(f"Error updating settings: {e}")
            raise HTTPException(status_code=500, detail=get_translation("generic_error", lang))

    async def get_profile_stats(self, user_id: str, lang: str = "es") -> ProfileStatsResponse:
        """
        Calcula y devuelve estadísticas del perfil:
        - Racha de días consecutivos con check-in
        - Resumen de los últimos 5 estados de ánimo
        - Promedio de mood_score
        - Estado de ánimo más común
        """
        try:
            # Obtener todos los check-ins del usuario ordenados por fecha
            response = self.supabase.table("daily_checkins")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .execute()
            
            checkins = response.data if response.data else []
            
            # Calcular racha de días consecutivos
            streak_days = self._calculate_streak(checkins)
            
            # Obtener últimos 5 estados de ánimo
            recent_moods = []
            for checkin in checkins[:5]:
                recent_moods.append({
                    "mood_label": checkin.get("mood_label"),
                    "mood_score": checkin.get("mood_score"),
                    "date": checkin.get("created_at"),
                    "note": checkin.get("note")
                })
            
            # Calcular promedio de mood_score
            if checkins:
                total_score = sum(c.get("mood_score", 0) for c in checkins)
                average_mood_score = round(total_score / len(checkins), 2)
                
                # Encontrar el mood más común
                mood_labels = [c.get("mood_label") for c in checkins if c.get("mood_label")]
                if mood_labels:
                    most_common_mood = Counter(mood_labels).most_common(1)[0][0]
                else:
                    most_common_mood = None
            else:
                average_mood_score = 0.0
                most_common_mood = None
            
            return ProfileStatsResponse(
                streak_days=streak_days,
                total_checkins=len(checkins),
                recent_moods=recent_moods,
                average_mood_score=average_mood_score,
                most_common_mood=most_common_mood
            )
            
        except Exception as e:
            print(f"Error obteniendo estadísticas: {e}")
            raise HTTPException(
                status_code=500,
                detail=get_translation("generic_error", lang)
            )

    def _calculate_streak(self, checkins: List[Dict]) -> int:
        """
        Calcula la racha de días consecutivos con check-in.
        
        Args:
            checkins: Lista de check-ins ordenados por fecha descendente
            
        Returns:
            Número de días consecutivos con check-in
        """
        if not checkins:
            return 0
        
        streak = 0
        today = datetime.now().date()
        
        # Convertir las fechas de check-in a objetos date
        checkin_dates = []
        for checkin in checkins:
            created_at_str = checkin.get("created_at")
            if created_at_str:
                # Parsear la fecha (formato ISO)
                checkin_date = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')).date()
                checkin_dates.append(checkin_date)
        
        # Eliminar duplicados y ordenar
        unique_dates = sorted(set(checkin_dates), reverse=True)
        
        if not unique_dates:
            return 0
        
        # Verificar si hay check-in hoy o ayer (para mantener la racha)
        if unique_dates[0] not in [today, today - timedelta(days=1)]:
            return 0
        
        # Contar días consecutivos
        expected_date = unique_dates[0]
        for date in unique_dates:
            if date == expected_date:
                streak += 1
                expected_date = date - timedelta(days=1)
            else:
                break
        
        return streak

    async def update_profile_info(self, user_id: str, profile_update: ProfileUpdateRequest, lang: str = "es") -> ProfileUpdateResponse:
        """
        Actualiza la información del perfil del usuario.
        Permite editar carrera, edad, y condiciones de salud/neurodivergencia.
        """
        updates = profile_update.model_dump(exclude_unset=True)
        
        if not updates:
            return ProfileUpdateResponse(
                message=get_translation("no_changes", lang) if lang == "es" else "No changes provided",
                updated_fields=[],
                profile={}
            )

        try:
            # Actualizar el perfil
            response = self.supabase.table("profiles").update(updates).eq("id", user_id).execute()
            
            if not response.data:
                raise HTTPException(status_code=404, detail=get_translation("not_found", lang))
            
            updated_profile = response.data[0]
            
            return ProfileUpdateResponse(
                message=get_translation("profile_update_success", lang) if lang == "es" 
                        else "Profile updated successfully",
                updated_fields=list(updates.keys()),
                profile=updated_profile
            )
            
        except Exception as e:
            print(f"Error actualizando perfil: {e}")
            raise HTTPException(
                status_code=500,
                detail=get_translation("generic_error", lang)
            )
