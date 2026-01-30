from typing import Dict, List
import random
from datetime import datetime
from fastapi import HTTPException
from app.core.supabase_client import get_supabase
from app.schemas.wellness import (
    CheckInRequest, 
    CheckInResponse, 
    EnergyRequest, 
    ExerciseResponse,
    MotivationResponse,
    EnergyLevel
)
from app.core.i18n import get_translation

class WellnessService:
    """Servicio para gestionar check-ins, energía y motivación"""
    
    def __init__(self):
        self.supabase = get_supabase()
        
        # Ejercicios mock organizados por nivel de energía
        self.mock_exercises = {
            EnergyLevel.ROJO: {
                "exercise_type": "respiracion_profunda",
                "title": "Respiración Profunda Restaurativa",
                "description": "Ejercicio de respiración para recuperar energía cuando te sientes agotado",
                "duration_seconds": 300,  # 5 minutos
                "instructions": [
                    "Encuentra un lugar cómodo donde puedas sentarte o recostarte",
                    "Cierra los ojos suavemente",
                    "Inhala profundamente por la nariz contando hasta 4",
                    "Mantén el aire contando hasta 4",
                    "Exhala lentamente por la boca contando hasta 6",
                    "Repite este ciclo durante 5 minutos",
                    "Observa cómo tu cuerpo se relaja con cada respiración"
                ]
            },
            EnergyLevel.AMBAR: {
                "exercise_type": "estiramiento_consciente",
                "title": "Estiramiento Consciente",
                "description": "Serie de estiramientos suaves para reactivar tu energía",
                "duration_seconds": 420,  # 7 minutos
                "instructions": [
                    "Ponte de pie en un espacio cómodo",
                    "Estira los brazos hacia arriba, alcanzando el techo",
                    "Inclínate suavemente hacia los lados, manteniendo 10 segundos cada lado",
                    "Gira el cuello lentamente en círculos, 5 veces en cada dirección",
                    "Estira los hombros llevándolos hacia atrás en círculos",
                    "Toca tus dedos de los pies manteniendo las piernas rectas",
                    "Respira profundamente en cada estiramiento"
                ]
            },
            EnergyLevel.VERDE: {
                "exercise_type": "meditacion_gratitud",
                "title": "Meditación de Gratitud",
                "description": "Práctica de mindfulness para mantener tu energía positiva",
                "duration_seconds": 600,  # 10 minutos
                "instructions": [
                    "Siéntate en una posición cómoda con la espalda recta",
                    "Cierra los ojos y respira naturalmente",
                    "Piensa en 3 cosas por las que estás agradecido hoy",
                    "Visualiza cada una con detalle, sintiendo la gratitud",
                    "Sonríe suavemente mientras mantienes estos pensamientos",
                    "Respira profundamente y siente la energía positiva",
                    "Cuando estés listo, abre los ojos lentamente"
                ]
            }
        }
        
        # Mensajes motivacionales de Flou
        self.motivational_messages = [
            {
                "message": "Recuerda: cada pequeño paso cuenta. Estás haciendo un gran trabajo cuidando de ti mismo. 💜",
                "category": "autocuidado"
            },
            {
                "message": "Tu bienestar mental es tan importante como tu éxito académico. Tómate el tiempo que necesites. 🌟",
                "category": "balance"
            },
            {
                "message": "Está bien no estar bien todo el tiempo. Lo importante es que estás aquí, trabajando en ti. 🌱",
                "category": "aceptacion"
            },
            {
                "message": "Eres más fuerte de lo que crees. Cada día que te levantas es una victoria. 💪",
                "category": "fortaleza"
            },
            {
                "message": "No estás solo en esto. Estoy aquí para acompañarte en cada paso del camino. 🤝",
                "category": "apoyo"
            },
            {
                "message": "Tus emociones son válidas. Permítete sentirlas sin juzgarte. 💙",
                "category": "validacion"
            },
            {
                "message": "El progreso no siempre es lineal, y eso está bien. Celebra cada pequeño logro. 🎉",
                "category": "progreso"
            },
            {
                "message": "Respira. Este momento pasará. Tienes las herramientas para superarlo. 🌊",
                "category": "calma"
            },
            {
                "message": "Tu salud mental importa. Priorízala sin culpa. 💚",
                "category": "prioridad"
            },
            {
                "message": "Cada día es una nueva oportunidad para cuidarte mejor. Empieza ahora. ✨",
                "category": "renovacion"
            }
        ]

    async def save_checkin(self, user_id: str, checkin: CheckInRequest, lang: str = "es") -> CheckInResponse:
        """
        Guarda un check-in diario en la base de datos.
        
        Args:
            user_id: ID del usuario
            checkin: Datos del check-in
            lang: Idioma para mensajes
            
        Returns:
            CheckInResponse con los datos guardados
        """
        try:
            # Preparar datos para insertar
            checkin_data = {
                "user_id": user_id,
                "mood_label": checkin.mood_label.value,
                "mood_score": checkin.mood_score,
                "feelings": checkin.feelings or [],
                "note": checkin.note
            }
            
            # Insertar en la base de datos
            response = self.supabase.table("daily_checkins").insert(checkin_data).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=500, 
                    detail=get_translation("generic_error", lang)
                )
            
            # Obtener el registro insertado
            saved_data = response.data[0]
            
            return CheckInResponse(
                id=saved_data["id"],
                user_id=saved_data["user_id"],
                mood_label=saved_data["mood_label"],
                mood_score=saved_data["mood_score"],
                feelings=saved_data.get("feelings"),
                note=saved_data.get("note"),
                created_at=datetime.fromisoformat(saved_data["created_at"].replace('Z', '+00:00')),
                message=get_translation("checkin_success", lang) if lang == "es" 
                        else "Check-in saved successfully! Keep taking care of yourself. 💜"
            )
            
        except Exception as e:
            print(f"Error guardando check-in: {e}")
            raise HTTPException(
                status_code=500,
                detail=get_translation("generic_error", lang)
            )

    async def get_exercise_by_energy(self, energy_request: EnergyRequest, lang: str = "es") -> ExerciseResponse:
        """
        Devuelve un ejercicio mock basado en el nivel de energía.
        
        Args:
            energy_request: Nivel de energía del usuario
            lang: Idioma para el ejercicio
            
        Returns:
            ExerciseResponse con el ejercicio recomendado
        """
        try:
            # Obtener el ejercicio correspondiente al nivel de energía
            exercise_data = self.mock_exercises.get(energy_request.energy_level)
            
            if not exercise_data:
                raise HTTPException(
                    status_code=400,
                    detail="Nivel de energía no válido"
                )
            
            # TODO: En el futuro, estos ejercicios vendrán de la tabla relaxation_exercises
            # y se podrán filtrar por idioma
            
            return ExerciseResponse(
                exercise_type=exercise_data["exercise_type"],
                title=exercise_data["title"],
                description=exercise_data["description"],
                duration_seconds=exercise_data["duration_seconds"],
                instructions=exercise_data["instructions"],
                energy_level=energy_request.energy_level.value
            )
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error obteniendo ejercicio: {e}")
            raise HTTPException(
                status_code=500,
                detail=get_translation("generic_error", lang)
            )

    async def get_motivation_message(self, lang: str = "es") -> MotivationResponse:
        """
        Devuelve un mensaje motivacional aleatorio de Flou.
        
        Args:
            lang: Idioma para el mensaje
            
        Returns:
            MotivationResponse con el mensaje motivacional
        """
        try:
            # Seleccionar un mensaje aleatorio
            selected_message = random.choice(self.motivational_messages)
            
            # TODO: En el futuro, estos mensajes vendrán de una tabla en la BD
            # y se podrán filtrar por idioma y categoría
            
            return MotivationResponse(
                message=selected_message["message"],
                author="Flou",
                category=selected_message.get("category")
            )
            
        except Exception as e:
            print(f"Error obteniendo mensaje motivacional: {e}")
            raise HTTPException(
                status_code=500,
                detail=get_translation("generic_error", lang)
            )
