import json
import logging
import os
import numpy as np
from typing import Dict, List, Optional
from google import genai
from google.genai import types

from app.core.config import get_settings
from app.schemas.chat import Slots

logger = logging.getLogger(__name__)

class StrategyRAG:
    def __init__(self, strategies_file_path: str):
        settings = get_settings()
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.strategies = []
        self.embeddings = []
        
        # Cargar estrategias
        try:
            with open(strategies_file_path, 'r', encoding='utf-8') as f:
                self.strategies = json.load(f)
            logger.info(f"Cargadas {len(self.strategies)} estrategias de {strategies_file_path}")
            
            # Generar Embeddings (Cache en memoria)
            # Concatenamos contenido + tags para enriquecer la búsqueda semántica
            texts_to_embed = [
                f"{s['nombre']} {s['prompt_instruction']} {' '.join(s['tags'])}" 
                for s in self.strategies
            ]
            
            if texts_to_embed:
                # Llamada a la API v2 (text-embedding-004)
                response = self.client.models.embed_content(
                    model='text-embedding-004',
                    contents=texts_to_embed
                )
                # Extraer vectores
                self.embeddings = [e.values for e in response.embeddings]
                
        except Exception as e:
            logger.error(f"Error inicializando RAG: {e}")
            # Estrategia fallback dummy si falla la carga
            self.strategies = [{
                "nombre": "Estrategia General",
                "prompt_instruction": "Sé empático y ayuda paso a paso.",
                "tiempo_min": 5,
                "vibe": "NEUTRAL"
            }]

    def retrieve(self, user_query: str, current_slots: Slots) -> Dict:
        """
        Recupera la mejor estrategia combinando filtros lógicos y búsqueda semántica.
        """
        user_time = current_slots.tiempo_bloque or 15
        
        # 1. FILTRO DURO (Lógica)
        candidates_indices = []
        for i, strat in enumerate(self.strategies):
            # Si requiere más tiempo del que tengo, descartar
            if strat.get('tiempo_min', 0) > user_time:
                continue
            candidates_indices.append(i)
            
        if not candidates_indices:
            logger.warning("Ninguna estrategia cumple el filtro de tiempo. Usando fallback.")
            return self.strategies[0]

        try:
            # 2. BÚSQUEDA SEMÁNTICA (Vectorial)
            # Vectorizar la query del usuario
            query_resp = self.client.models.embed_content(
                model='text-embedding-004',
                contents=user_query
            )
            query_embedding = query_resp.embeddings[0].values
            
            # Calcular similitud coseno solo con los candidatos válidos
            best_score = -1.0
            best_strat_index = candidates_indices[0]
            
            for idx in candidates_indices:
                if not self.embeddings: break
                
                # Producto punto (asumiendo vectores normalizados por la API)
                score = np.dot(query_embedding, self.embeddings[idx])
                
                if score > best_score:
                    best_score = score
                    best_strat_index = idx
            
            selected = self.strategies[best_strat_index]
            logger.info(f"Estrategia seleccionada: {selected['nombre']} (Score: {best_score:.4f})")
            return selected

        except Exception as e:
            logger.error(f"Error en búsqueda vectorial: {e}")
            return self.strategies[0]

# Instancia Global
# Asegúrate de que la ruta sea relativa desde donde se ejecuta uvicorn
json_path = os.path.join(os.path.dirname(__file__), "../data/strategies.json")
rag_engine = StrategyRAG(json_path)
