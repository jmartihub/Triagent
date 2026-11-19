"""Módulo de Aprendizaje No Supervisado: Clustering de Duplicados e Incidentes Masivos.

Implementa algoritmos no supervisados (DBSCAN y similitud coseno sobre vectores TF-IDF)
para analizar tickets en ventanas temporales:
1. Detección de Tickets Duplicados: reportes idénticos o paráfrasis directas del mismo problema.
2. Detección de Incidentes Masivos (Caídas Globales): brotes súbitos de tickets que comparten
   síntomas sin necesidad de etiquetas previas, agrupándolos bajo un "Incidente Padre".
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class ResultadoClustering:
    es_duplicado: bool
    ticket_original_id: Optional[str]
    similitud_duplicado: float
    es_incidente_masivo: bool
    id_incidente_masivo: Optional[str]
    tamano_cluster_masivo: int
    palabras_clave_cluster: List[str]
    alerta_emitida: Optional[str]


class DetectorIncidentesNoSupervisado:
    def __init__(
        self,
        umbral_duplicado: float = 0.75,
        eps_dbscan: float = 0.75,
        min_muestras_masivo: int = 3,
        ventana_horas: float = 3.0,
    ):
        self.umbral_duplicado = umbral_duplicado
        self.eps_dbscan = eps_dbscan
        self.min_muestras_masivo = min_muestras_masivo
        self.ventana_horas = ventana_horas

        self.vectorizador = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
            strip_accents="unicode",
        )
        self.buffer_tickets: List[Dict[str, Any]] = []

    def registrar_ticket(self, ticket: Dict[str, Any], tipo: str = "falla"):
        """Agrega un ticket a la memoria de trabajo temporal."""
        if "fecha_apertura" not in ticket or not ticket["fecha_apertura"]:
            fecha_dt = datetime.now()
        elif isinstance(ticket["fecha_apertura"], str):
            try:
                fecha_dt = datetime.strptime(ticket["fecha_apertura"], "%Y-%m-%d %H:%M")
            except ValueError:
                fecha_dt = datetime.now()
        else:
            fecha_dt = ticket["fecha_apertura"]

        copia = dict(ticket)
        copia["fecha_dt"] = fecha_dt
        copia["tipo"] = tipo
        form = ticket.get("formulario_elegido", "")
        apoyo = ticket.get("apoyo", "")
        asunto = ticket.get("asunto", "")
        desc = ticket.get("descripcion", "")
        copia["texto_completo"] = f"{form} | {apoyo} | {asunto} | {desc}".strip()
        self.buffer_tickets.append(copia)

    def analizar_ticket(self, nuevo_ticket: Dict[str, Any], tipo: str = "falla") -> ResultadoClustering:
        """Examina un ticket entrante contra la memoria de tickets recientes."""
        self.registrar_ticket(nuevo_ticket, tipo=tipo)
        t_actual = self.buffer_tickets[-1]
        fecha_corte = t_actual["fecha_dt"] - timedelta(hours=self.ventana_horas)

        # Filtrar tickets en la ventana temporal
        tickets_ventana = [
            t for t in self.buffer_tickets
            if t["fecha_dt"] >= fecha_corte
        ]

        if len(tickets_ventana) <= 1:
            return ResultadoClustering(
                es_duplicado=False,
                ticket_original_id=None,
                similitud_duplicado=0.0,
                es_incidente_masivo=False,
                id_incidente_masivo=None,
                tamano_cluster_masivo=1,
                palabras_clave_cluster=[],
                alerta_emitida=None,
            )

        textos = [t["texto_completo"] for t in tickets_ventana]
        matriz_tfidf = self.vectorizador.fit_transform(textos)
        vocab = np.array(self.vectorizador.get_feature_names_out())

        # Vector del ticket que acaba de ingresar (último en la ventana)
        idx_nuevo = len(tickets_ventana) - 1
        vec_nuevo = matriz_tfidf[idx_nuevo]

        # 1. Chequeo de duplicado directo con tickets previos
        similitudes = cosine_similarity(vec_nuevo, matriz_tfidf[:idx_nuevo])[0]
        max_sim_idx = int(np.argmax(similitudes)) if len(similitudes) > 0 else -1
        max_sim = float(similitudes[max_sim_idx]) if max_sim_idx >= 0 else 0.0

        es_duplicado = max_sim >= self.umbral_duplicado
        ticket_original_id = tickets_ventana[max_sim_idx]["id"] if es_duplicado else None

        # 2. Clustering no supervisado con DBSCAN (distancia coseno = 1 - similitud)
        # Convertir a matriz de distancias densa
        sim_matriz = cosine_similarity(matriz_tfidf)
        dist_matriz = np.clip(1.0 - sim_matriz, 0.0, 2.0)

        db = DBSCAN(eps=self.eps_dbscan, min_samples=self.min_muestras_masivo, metric="precomputed")
        etiquetas = db.fit_predict(dist_matriz)

        cluster_nuevo = etiquetas[idx_nuevo]
        es_incidente_masivo = False
        id_incidente_masivo = None
        tamano_cluster = 1
        top_palabras: List[str] = []
        alerta = None

        if cluster_nuevo != -1:  # -1 es ruido en DBSCAN
            miembros_idx = np.nonzero(etiquetas == cluster_nuevo)[0]
            tamano_cluster = len(miembros_idx)

            # Criterio ITIL e Ingeniería de Servicios:
            # 1. Debe alcanzar el umbral de muestras mínimas concurrentes (>= 3)
            # 2. Solo aplica a fallas de servicio (tipo == 'falla'). Las dudas/consultas/trámites
            #    son solicitudes de servicio informativas y NUNCA constituyen un incidente masivo.
            es_falla = (tipo == "falla")
            fallas_en_cluster = sum(1 for i in miembros_idx if tickets_ventana[i].get("tipo") == "falla")

            if tamano_cluster >= self.min_muestras_masivo and es_falla and fallas_en_cluster >= self.min_muestras_masivo:
                es_incidente_masivo = True
                id_incidente_masivo = f"INC_MASIVO_{tickets_ventana[miembros_idx[0]]['id']}"

                # Extraer palabras clave más salientes del cluster (centroide TF-IDF)
                centroide = np.asarray(matriz_tfidf[miembros_idx].mean(axis=0)).ravel()
                top_indices = centroide.argsort()[::-1][:5]
                top_palabras = [str(vocab[i]) for i in top_indices if centroide[i] > 0]

                alerta = (
                    f"ALERTA DE INCIDENTE MASIVO DETECTADO (DBSCAN): "
                    f"Se han agrupado {tamano_cluster} reportes concurrentes de falla en la última ventana temporal. "
                    f"Términos característicos del brote: {', '.join(top_palabras)}. "
                    f"Vinculados al incidente maestro {id_incidente_masivo}."
                )

        return ResultadoClustering(
            es_duplicado=es_duplicado,
            ticket_original_id=ticket_original_id,
            similitud_duplicado=round(max_sim, 4),
            es_incidente_masivo=es_incidente_masivo,
            id_incidente_masivo=id_incidente_masivo,
            tamano_cluster_masivo=tamano_cluster,
            palabras_clave_cluster=top_palabras,
            alerta_emitida=alerta,
        )
