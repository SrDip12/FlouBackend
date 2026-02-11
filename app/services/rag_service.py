import json
import logging
import os
import numpy as np
from typing import Dict, List, Optional
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings
from app.schemas.chat import Slots

logger = logging.getLogger(__name__)

class StrategyRAG:
    def __init__(self, strategies_file_path: str):
        settings = get_settings()
        self.strategies = []
        self.embeddings = []
        
        # Carga eficiente del modelo (Solo una vez en memoria)
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Modelo SentenceTransformer cargado exitosamente.")
        except Exception as e:
            logger.error(f"Error cargando SentenceTransformer: {e}")
            self.model = None
        
        # Cargar estrategias
        try:
            with open(strategies_file_path, 'r', encoding='utf-8') as f:
                self.strategies = json.load(f)
            logger.info(f"Cargadas {len(self.strategies)} estrategias de {strategies_file_path}")
            
            # Generar Embeddings (Cache en memoria)
            texts_to_embed = [
                f"{s['nombre']} {s['prompt_instruction']} {' '.join(s['tags'])}" 
                for s in self.strategies
            ]
            
            if texts_to_embed and self.model:
                try:
                    self.embeddings = self.model.encode(texts_to_embed)
                    logger.info(f"✅ Embeddings generados exitosamente.")
                
                except Exception as e:
                    logger.error(f"❌ Error generando embeddings: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error CRÍTICO inicializando RAG: {e}")

            # Estrategia fallback dummy si falla la carga
            self.strategies = [{
                "nombre": "Estrategia General",
                "prompt_instruction": "Sé empático y ayuda paso a paso.",
                "tiempo_min": 5,
                "vibe": "NEUTRAL"
            }]
            self.embeddings = []

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
            if self.model and len(self.embeddings) > 0:
                query_embedding = self.model.encode(user_query)
                
                # Calcular similitud coseno solo con los candidatos válidos
                best_score = -1.0
                best_strat_index = candidates_indices[0]
                
                for idx in candidates_indices:
                    # Producto punto (asumiendo vectores normalizados por la API, SentenceTransformer por defecto normaliza si se pide o es compatible con dot product si son normalizados)
                    # SentenceTransformer 'all-MiniLM-L6-v2' produce normalized vectors? Usually cosine similarity is preferred.
                    # User requested: "calcula la similitud usando numpy.dot (producto punto)."
                    # Note: all-MiniLM-L6-v2 produces normalized vectors if normalize_embeddings=True isn't specified but typically dot product on normalized vectors IS cosine similarity.
                    # We will trust the user's instruction to use np.dot.
                    
                    if idx < len(self.embeddings):
                        score = np.dot(query_embedding, self.embeddings[idx])
                        
                        if score > best_score:
                            best_score = score
                            best_strat_index = idx
                
                selected = self.strategies[best_strat_index]
                logger.info(f"Estrategia seleccionada: {selected['nombre']} (Score: {best_score:.4f})")
                return selected
            else:
                 logger.warning("Modelo de embeddings no disponible. Usando fallback por filtro.")
                 return self.strategies[candidates_indices[0]]

        except Exception as e:
            logger.error(f"Error en búsqueda vectorial: {e}")
            return self.strategies[0]

# Instancia Global
# Asegúrate de que la ruta sea relativa desde donde se ejecuta uvicorn
json_path = os.path.join(os.path.dirname(__file__), "../data/strategies.json")
rag_engine = StrategyRAG(json_path)
