"""Orquestador Principal del Agente Inteligente de Triaje (Tooli / GLPI).

Implementa el ciclo completo del agente de Russell & Norvig:
1. PERCEPCIÓN:
   - Lectura de campos del ticket (asunto, descripción, formulario, apoyo).
   - Inferencia probabilística con modelos supervisados y Redes Neuronales (ML/DL).
   - Extracción de características latentes y evaluación de incertidumbre.
2. RAZONAMIENTO:
   - Ontología de dominio: mapeo a plataformas, grupos resolutores y competencias técnicas.
   - Motor de Lógica de Primer Orden (FOL): cláusulas de Horn y red de seguridad explicable.
   - Aprendizaje No Supervisado: clustering con DBSCAN para detectar duplicados o caídas masivas.
   - Modelo Estadístico de Regresión: pronóstico de tiempo de resolución y riesgo de SLA.
3. ACCIÓN:
   - Asignación oficial de urgencia y corrección de formulario si aplica.
   - Enrutamiento al técnico especialista en GLPI.
   - Redacción de respuesta preliminar para el estudiante.
   - Vinculación a incidente maestro si es evento masivo.
4. MEMORIA Y APRENDIZAJE:
   - Registro de decisiones y memoria de corto plazo.
   - Captura de retroalimentación del técnico humano para reentrenamiento continuo.
"""

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import joblib

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from triage.clustering import DetectorIncidentesNoSupervisado, ResultadoClustering
from triage.fol_rules import DeduccionFOL, MotorInferenciaFOL
from triage.ontology import AsignacionTecnica, OntologiaTI
from triage.response_generator import GeneradorRespuestaPreliminar
from triage.sla_regression import EstimadorSLA


@dataclass
class DecisionAgente:
    id_ticket: str
    urgencia_final: str
    formulario_final: str
    hubo_cambio_formulario: bool
    grupo_asignado: str
    tecnico_asignado: str
    tecnico_correo: str
    tiempo_sla_horas: float
    horas_estimadas_resolucion: float
    nivel_riesgo_sla: str
    es_duplicado: bool
    ticket_original_id: Optional[str]
    es_incidente_masivo: bool
    id_incidente_masivo: Optional[str]
    requiere_revision_humana: bool
    respuesta_preliminar: str
    justificacion_fol: List[str]
    explicacion_ontologica: str
    seguridad_ml_activada: bool
    confianza_ml_urgencia: float
    confianza_ml_formulario: float


class MemoriaAgente:
    """Gestiona la memoria episódica y el aprendizaje por retroalimentación."""

    def __init__(self, ruta_log: Optional[Path] = None):
        self.ruta_log = ruta_log or (RAIZ / "data" / "feedback_log.jsonl")
        self.ruta_log.parent.mkdir(parents=True, exist_ok=True)
        self.historial_decisiones: List[Dict[str, Any]] = []

    def guardar_decision(self, decision: DecisionAgente, ticket_original: Dict[str, Any]):
        registro = {
            "timestamp": datetime.now().isoformat(),
            "ticket": ticket_original,
            "decision": asdict(decision),
        }
        self.historial_decisiones.append(registro)

    def registrar_feedback_humano(
        self,
        id_ticket: str,
        urgencia_humana: str,
        formulario_humano: str,
        tecnico_humano: Optional[str] = None,
        comentarios: str = "",
    ):
        """Registra la corrección efectuada por un técnico humano."""
        registro = {
            "timestamp": datetime.now().isoformat(),
            "id_ticket": id_ticket,
            "urgencia_corregida": urgencia_humana,
            "formulario_corregido": formulario_humano,
            "tecnico_corregido": tecnico_humano,
            "comentarios": comentarios,
        }
        with self.ruta_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")


class AgenteTriaje:
    def __init__(self, usar_deep_learning: bool = False):
        self.usar_deep_learning = usar_deep_learning
        self.ontologia = OntologiaTI()
        self.motor_fol = MotorInferenciaFOL(umbral_confianza_minima=0.55)
        self.clustering = DetectorIncidentesNoSupervisado()
        self.generador_respuesta = GeneradorRespuestaPreliminar()
        self.memoria = MemoriaAgente()

        # Cargar regresor de SLA si existe
        ruta_sla = RAIZ / "models" / "sla_regression.joblib"
        if ruta_sla.exists():
            self.estimador_sla = EstimadorSLA.cargar(ruta_sla)
        else:
            self.estimador_sla = None

        # Cargar modelos de clasificación
        self._cargar_modelos()

    def _cargar_modelos(self):
        sufijo = "_deep" if self.usar_deep_learning else ""
        ruta_urg = RAIZ / "models" / f"urgencia{sufijo}.joblib"
        ruta_form = RAIZ / "models" / f"formulario{sufijo}.joblib"

        # Fallback a modelo clásico si el deep learning no está compilado
        if not ruta_urg.exists():
            ruta_urg = RAIZ / "models" / "urgencia.joblib"
        if not ruta_form.exists():
            ruta_form = RAIZ / "models" / "formulario.joblib"

        self.modelo_urgencia = joblib.load(ruta_urg) if ruta_urg.exists() else None
        self.modelo_formulario = joblib.load(ruta_form) if ruta_form.exists() else None

    # --- 1. PERCEPCIÓN ---
    def percibir(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        asunto = ticket.get("asunto", "")
        descripcion = ticket.get("descripcion", "")
        form_elegido = ticket.get("formulario_elegido", "Fallas Técnicas TIC")
        apoyo = ticket.get("apoyo", "Otra")

        texto_urg = f"{form_elegido} | {apoyo} | {asunto} | {descripcion}"
        texto_form = f"{asunto} . {descripcion}"

        # Predicción ML/DL de Urgencia
        pred_urg = "Media"
        conf_urg = 0.50
        if self.modelo_urgencia and hasattr(self.modelo_urgencia, "predict_proba"):
            probs_u = self.modelo_urgencia.predict_proba([texto_urg])[0]
            clases_u = self.modelo_urgencia.classes_
            pred_urg = str(clases_u[probs_u.argmax()])
            conf_urg = float(probs_u.max())

        # Predicción ML/DL de Formulario
        pred_form = form_elegido
        conf_form = 0.50
        if self.modelo_formulario and hasattr(self.modelo_formulario, "predict_proba"):
            probs_f = self.modelo_formulario.predict_proba([texto_form])[0]
            clases_f = self.modelo_formulario.classes_
            pred_form = str(clases_f[probs_f.argmax()])
            conf_form = float(probs_f.max())

        # Extracción heurística de factores latentes del texto
        texto_b = f"{asunto} {descripcion}".lower()
        tipo = "duda" if any(w in texto_b for w in ["como", "quisiera saber", "consulta", "pregunta", "donde"]) and not any(w in texto_b for w in ["error", "fallo", "no funciona", "caido", "bloqueado"]) else "falla"
        alcance = "institucional" if any(w in texto_b for w in ["toda la universidad", "todo el campus", "a todos"]) else ("grupo" if any(w in texto_b for w in ["todo el salon", "mi grupo", "varios companeros", "clase"]) else "individual")
        bloquea = not any(w in texto_b for w in ["puedo seguir trabajando", "no es grave", "solo quería reportarlo", "no me impide"])
        plazo = "inmediato" if any(w in texto_b for w in ["parcial", "examen", "en una hora", "15 minutos", "hoy vence", "ya"]) else ("cercano" if any(w in texto_b for w in ["manana", "viernes", "proxima semana", "pocos dias"]) else "ninguno")
        alternativa = any(w in texto_b for w in ["desde el celular", "otro computador", "otro dispositivo", "amigo"])

        return {
            "pred_urg": pred_urg,
            "conf_urg": conf_urg,
            "pred_form": pred_form,
            "conf_form": conf_form,
            "tipo": tipo,
            "alcance": alcance,
            "bloquea": bloquea,
            "plazo": plazo,
            "alternativa": alternativa,
        }

    # --- 2. RAZONAMIENTO ---
    def razonar(self, ticket: Dict[str, Any], percepciones: Dict[str, Any]) -> Dict[str, Any]:
        id_t = ticket.get("id", "sim_000000")
        form_elegido = ticket.get("formulario_elegido", "Fallas Técnicas TIC")
        apoyo = ticket.get("apoyo", "Otra")
        asunto = ticket.get("asunto", "")
        descripcion = ticket.get("descripcion", "")

        # A. Motor FOL: Deducción formal y red de seguridad
        deduccion_fol = self.motor_fol.razonar(
            id_ticket=id_t,
            tipo=percepciones["tipo"],
            alcance=percepciones["alcance"],
            bloquea=percepciones["bloquea"],
            plazo=percepciones["plazo"],
            alternativa=percepciones["alternativa"],
            urgencia_predicha_ml=percepciones["pred_urg"],
            confianza_ml=percepciones["conf_urg"],
        )

        urgencia_final = deduccion_fol.urgencia_deducida

        # B. Detección de formulario erróneo (umbral >= 0.60)
        cambio_formulario = False
        formulario_final = form_elegido
        if percepciones["pred_form"] != form_elegido and percepciones["conf_form"] >= 0.60:
            formulario_final = percepciones["pred_form"]
            cambio_formulario = True

        # C. Razonamiento Ontológico: Enrutamiento técnico y SLA
        asignacion_ont = self.ontologia.enrutar_ticket(
            formulario=formulario_final,
            apoyo=apoyo,
            urgencia=urgencia_final,
            asunto=asunto,
            descripcion=descripcion,
            tipo=percepciones["tipo"],
        )

        # D. Aprendizaje No Supervisado: Detección de Duplicados e Incidentes Masivos
        clustering_res = self.clustering.analizar_ticket(ticket)
        if clustering_res.es_incidente_masivo:
            # Los incidentes masivos se escalan a Crítica si aún no lo estaban
            urgencia_final = "Crítica"

        # E. Modelo Estadístico de Regresión: Tiempo y riesgo de SLA
        pred_sla = {"horas_estimadas": asignacion_ont.tiempo_max_resolucion_horas * 0.6, "nivel_riesgo_sla": "Bajo"}
        if self.estimador_sla:
            pred_sla = self.estimador_sla.predecir(
                urgencia=urgencia_final,
                es_falla=(percepciones["tipo"] == "falla"),
                plataforma_id=asignacion_ont.plataforma_id,
                carga_cola=12,
                limite_sla_horas=asignacion_ont.tiempo_max_resolucion_horas,
            )

        return {
            "urgencia_final": urgencia_final,
            "formulario_final": formulario_final,
            "cambio_formulario": cambio_formulario,
            "asignacion_ont": asignacion_ont,
            "deduccion_fol": deduccion_fol,
            "clustering_res": clustering_res,
            "pred_sla": pred_sla,
        }

    # --- 3. ACCIÓN ---
    def actuar(
        self,
        ticket: Dict[str, Any],
        percepciones: Dict[str, Any],
        razonamiento: Dict[str, Any],
    ) -> DecisionAgente:
        id_t = ticket.get("id", "sim_000000")
        asig: AsignacionTecnica = razonamiento["asignacion_ont"]
        fol: DeduccionFOL = razonamiento["deduccion_fol"]
        clust: ResultadoClustering = razonamiento["clustering_res"]
        sla = razonamiento["pred_sla"]

        # Generar Respuesta Preliminar al Estudiante (Acción 3)
        respuesta = self.generador_respuesta.generar(
            id_ticket=id_t,
            formulario_elegido=ticket.get("formulario_elegido", ""),
            formulario_correcto=razonamiento["formulario_final"],
            hubo_reenrutamiento=razonamiento["cambio_formulario"],
            urgencia=razonamiento["urgencia_final"],
            grupo_nombre=asig.grupo_nombre,
            tecnico_nombre=asig.tecnico_nombre,
            plataforma_id=asig.plataforma_id,
            horas_sla=asig.tiempo_max_resolucion_horas,
            horas_estimadas=sla["horas_estimadas"],
            es_duplicado=clust.es_duplicado,
            id_ticket_original=clust.ticket_original_id,
            es_incidente_masivo=clust.es_incidente_masivo,
        )

        decision = DecisionAgente(
            id_ticket=id_t,
            urgencia_final=razonamiento["urgencia_final"],
            formulario_final=razonamiento["formulario_final"],
            hubo_cambio_formulario=razonamiento["cambio_formulario"],
            grupo_asignado=asig.grupo_nombre,
            tecnico_asignado=asig.tecnico_nombre,
            tecnico_correo=asig.tecnico_correo,
            tiempo_sla_horas=asig.tiempo_max_resolucion_horas,
            horas_estimadas_resolucion=sla["horas_estimadas"],
            nivel_riesgo_sla=sla["nivel_riesgo_sla"],
            es_duplicado=clust.es_duplicado,
            ticket_original_id=clust.ticket_original_id,
            es_incidente_masivo=clust.es_incidente_masivo,
            id_incidente_masivo=clust.id_incidente_masivo,
            requiere_revision_humana=fol.requiere_revision_humana,
            respuesta_preliminar=respuesta,
            justificacion_fol=fol.trazabilidad_deductiva,
            explicacion_ontologica=asig.explicacion_ontologica,
            seguridad_ml_activada=fol.seguridad_ml_activada,
            confianza_ml_urgencia=percepciones["conf_urg"],
            confianza_ml_formulario=percepciones["conf_form"],
        )

        # 4. MEMORIA
        self.memoria.guardar_decision(decision, ticket)
        return decision

    def procesar_ticket(self, ticket: Dict[str, Any]) -> DecisionAgente:
        """Ciclo completo Percibir -> Razonar -> Actuar."""
        percepciones = self.percibir(ticket)
        razonamiento = self.razonar(ticket, percepciones)
        decision = self.actuar(ticket, percepciones, razonamiento)
        return decision
