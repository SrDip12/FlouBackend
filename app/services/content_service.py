from typing import List, Dict
from app.schemas.content import EducationalCard, ContentResponse

class ContentService:
    """Servicio para gestionar el contenido educativo e informativo"""
    
    def __init__(self):
        # Datos mock iniciales. En el futuro, esto vendría de una tabla 'educational_cards'
        self.cards_db = {
            "es": [
                {
                    "id": "self_knowledge_01",
                    "title": "Autoconocimiento",
                    "category": "Fundamentos",
                    "description": "Entender tus emociones es el primer paso para gestionarlas.",
                    "content": "El autoconocimiento implica mirar hacia adentro para comprender tus propios sentimientos, motivaciones y patrones de comportamiento. Al identificar qué desencadena ciertas emociones, puedes empezar a responder en lugar de reaccionar impulsivamente.",
                    "icon": "🧠",
                    "color": "#af95e6", # Lavanda
                    "order": 1
                },
                {
                    "id": "energy_01",
                    "title": "Energía Sostenible",
                    "category": "Bienestar",
                    "description": "Aprende a gestionar tu energía, no solo tu tiempo.",
                    "content": "A menudo nos enfocamos en gestionar nuestro tiempo, pero la energía es nuestro recurso más preciado. Presta atención a qué actividades te drenan (vampiros de energía) y cuáles te recargan. Intenta alternar periodos de alta concentración con descansos breves de recuperación.",
                    "icon": "⚡",
                    "color": "#98dfc9", # Menta
                    "order": 2
                },
                {
                    "id": "adaptability_01",
                    "title": "Adaptabilidad",
                    "category": "Resiliencia",
                    "description": "Fluir con los cambios en lugar de resistirse a ellos.",
                    "content": "La vida universitaria es impredecible. La adaptabilidad no significa no tener un plan, sino tener la flexibilidad mental para ajustar las velas cuando cambia el viento. Practica aceptar lo que no puedes controlar y enfócate en tu respuesta ante los desafíos.",
                    "icon": "🌊",
                    "color": "#85c4e9", # Cielo
                    "order": 3
                },
                {
                    "id": "purpose_01",
                    "title": "Propósito",
                    "category": "Motivación",
                    "description": "Encontrar el 'porqué' detrás de tus esfuerzos diarios.",
                    "content": "El propósito es el combustible que te mantiene en movimiento cuando la motivación inicial se desvanece. No tiene que ser una gran misión de vida; puede ser tan simple como querer aprender, ayudar a otros o construir un futuro mejor para ti y tu familia.",
                    "icon": "🎯",
                    "color": "#ffb7b2", # Salmón suave (complementario)
                    "order": 4
                }
            ],
            "en": [
                {
                    "id": "self_knowledge_01",
                    "title": "Self-Knowledge",
                    "category": "Foundations",
                    "description": "Understanding your emotions is the first step to managing them.",
                    "content": "Self-knowledge involves looking inward to understand your own feelings, motivations, and behavior patterns. By identifying what triggers certain emotions, you can start responding instead of reacting impulsively.",
                    "icon": "🧠",
                    "color": "#af95e6",
                    "order": 1
                },
                {
                    "id": "energy_01",
                    "title": "Sustainable Energy",
                    "category": "Wellness",
                    "description": "Learn to manage your energy, not just your time.",
                    "content": "We often focus on managing our time, but energy is our most precious resource. Pay attention to what activities drain you (energy vampires) and which ones recharge you. Try alternating periods of high concentration with short recovery breaks.",
                    "icon": "⚡",
                    "color": "#98dfc9",
                    "order": 2
                },
                {
                    "id": "adaptability_01",
                    "title": "Adaptability",
                    "category": "Resilience",
                    "description": "Flowing with changes rather than resisting them.",
                    "content": "University life is unpredictable. Adaptability doesn't mean not having a plan, but having the mental flexibility to adjust your sails when the wind changes. Practice accepting what you cannot control and focus on your response to challenges.",
                    "icon": "🌊",
                    "color": "#85c4e9",
                    "order": 3
                },
                {
                    "id": "purpose_01",
                    "title": "Purpose",
                    "category": "Motivation",
                    "description": "Finding the 'why' behind your daily efforts.",
                    "content": "Purpose is the fuel that keeps you moving when initial motivation fades. It doesn't have to be a grand life mission; it can be as simple as wanting to learn, help others, or build a better future for yourself and your family.",
                    "icon": "🎯",
                    "color": "#ffb7b2",
                    "order": 4
                }
            ]
        }

    async def get_educational_cards(self, lang: str = "es") -> ContentResponse:
        """
        Obtiene la lista de tarjetas educativas en el idioma solicitado.
        Si el idioma no existe, hace fallback a español.
        """
        # Normalizar idioma (tomar solo los dos primeros caracteres)
        lang_code = lang[:2].lower()
        if lang_code not in self.cards_db:
            lang_code = "es"
            
        cards_data = self.cards_db.get(lang_code, [])
        
        # Convertir diccionarios a objetos Pydantic
        cards = [EducationalCard(**card) for card in cards_data]
        
        return ContentResponse(
            cards=cards,
            language=lang_code,
            total=len(cards)
        )
