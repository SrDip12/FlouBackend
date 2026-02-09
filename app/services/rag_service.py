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
        self.embedding_model = 'models/text-embedding-004' # Default optimista
        
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
                try:
                    # INTENTO 1: Nombre limpio (text-embedding-004)
                    try:
                        chosen_model = 'text-embedding-004'
                        response = self.client.models.embed_content(
                            model=chosen_model,
                            contents=texts_to_embed
                        )
                        self.embedding_model = chosen_model
                        logger.info(f"✅ Éxito con {chosen_model}")
                    except Exception as e1:
                        logger.warning(f"Fallo text-embedding-004 ({e1}), probando con prefijo...")
                        
                        # INTENTO 2: Con prefijo (models/text-embedding-004)
                        chosen_model = 'models/text-embedding-004'
                        response = self.client.models.embed_content(
                            model=chosen_model,
                            contents=texts_to_embed
                        )
                        self.embedding_model = chosen_model
                        logger.info(f"✅ Éxito con {chosen_model}")
                
                except Exception as e2:
                    logger.warning(f"Fallo models/text-embedding-004 ({e2}), usando fallback LEGACY...")
                    
                    # INTENTO 3: Fallback (models/embedding-001)
                    self.embedding_model = 'models/embedding-001'
                    response = self.client.models.embed_content(
                        model=self.embedding_model,
                        contents=texts_to_embed
                    )
                    logger.info(f"⚠️ Usando fallback {self.embedding_model}")

                # Extraer vectores
                self.embeddings = [e.values for e in response.embeddings]
                
        except Exception as e:
            logger.error(f"❌ Error CRÍTICO inicializando RAG: {e}")
            
            # DIAGNÓSTICO PROFUNDO
            try:
                logger.info("--- DIAGNÓSTICO DE MODELOS REALES ---")
                for m in self.client.models.list():
                    methods = getattr(m, 'supported_generation_methods', [])
                    if 'embedContent' in methods:
                        # Loguear nombre REAL y versión
                        version = getattr(m, 'version', 'unknown')
                        logger.info(f"📍 MODELO: {m.name} | VERSIÓN: {version}")
                logger.info("---------------------------------------")
            except Exception as debug_e:
                logger.error(f"Error listando modelos: {debug_e}")

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
            # Vectorizar la query usando el modelo que sabemos que funciona
            try:
                query_resp = self.client.models.embed_content(
                    model=self.embedding_model,
                    contents=user_query
                )
            except Exception as e:
                logger.warning(f"Error vectorizando query con {self.embedding_model} ({e}), reintentando...")
                # Intento desesperado con fallback legacy si el modelo guardado falla de repente
                fallback = 'models/embedding-001'
                query_resp = self.client.models.embed_content(
                    model=fallback,
                    contents=user_query
                )
                self.embedding_model = fallback # Actualizamos para siguiente vez
            
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
