"""Orquestador Principal del Agente Inteligente de Triaje (Tooli / GLPI).

Implementa el ciclo completo del agente de Russell & Norvig:
1. PERCEPCIÓN:
   - Lectura de campos del ticket (asunto, descripción, formulario, apoyo).
   - Inferencia probabilística con modelos supervisados y Redes Neuronales (ML/DL).
   - Extracción refinada de factores latentes, exclusión de falsos positivos y detección de incidentes ya resueltos.
2. RAZONAMIENTO:
   - Aprendizaje Activo por Casos (CBR / Case-Based Reasoning): consulta previa de correcciones de técnicos humanos.
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
   - Memoria episódica activa: las correcciones humanas alimentan la base de conocimiento en tiempo real.
"""

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import unicodedata
import joblib
import yaml

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from triage.factor_model import RUTA_MODELOS as RUTA_MODELOS_FACTORES, PercepcionFactores
from triage.clustering import DetectorIncidentesNoSupervisado, ResultadoClustering
from triage.fol_rules import DeduccionFOL, MotorInferenciaFOL
from triage.ontology import AsignacionTecnica, OntologiaTI
from triage.response_generator import GeneradorRespuestaPreliminar
from triage.sla_regression import EstimadorSLA

NIVELES_URGENCIA = ("Baja", "Media", "Alta", "Crítica")
CARGA_COLA_POR_DEFECTO = 12


def limpiar_texto(texto: str) -> str:
    """Normaliza tildes y minúsculas para matching semántico robusto."""
    norm = unicodedata.normalize("NFD", texto)
    return "".join(c for c in norm if unicodedata.category(c) != "Mn").lower()


def cargar_senales(ruta: Optional[Path] = None) -> Dict[str, tuple]:
    """Carga las frases de config/senales.yaml normalizadas igual que el texto del ticket."""
    ruta = ruta or (RAIZ / "config" / "senales.yaml")
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return {
        clave: tuple(limpiar_texto(str(frase)) for frase in (frases or []))
        for clave, frases in datos.items()
    }


SENALES = cargar_senales()


FACTORES_RUBRICA = ("tipo", "alcance", "bloquea", "plazo", "alternativa")
ORDEN_ALCANCE = ("individual", "grupo", "institucional")
ORDEN_PLAZO = ("ninguno", "cercano", "inmediato")


def factores_por_frases(texto_b: str, tiene_pregunta: bool = False) -> Dict[str, Any]:
    """Factores según las frases explícitas de config/senales.yaml.

    Además de los factores devuelve "evidencia": qué grupos de frases aparecieron, para
    distinguir "la frase dice que no" de "no hay ninguna frase".
    """
    evidencia = {clave: any(frase in texto_b for frase in frases) for clave, frases in SENALES.items()}
    ya_resuelto = evidencia["incidente_resuelto"]

    if ya_resuelto or ((evidencia["consulta"] or tiene_pregunta) and not evidencia["falla"]):
        tipo = "duda"
    else:
        tipo = "falla"

    if evidencia["alcance_institucional"]:
        alcance = "institucional"
    elif evidencia["alcance_grupo"]:
        alcance = "grupo"
    else:
        alcance = "individual"

    # Las frases que niegan el bloqueo prevalecen sobre las que lo afirman.
    bloquea = not ya_resuelto and not evidencia["no_bloquea"] and evidencia["bloqueo"]

    if ya_resuelto:
        plazo = "ninguno"
    elif evidencia["plazo_inmediato"]:
        plazo = "inmediato"
    elif evidencia["plazo_cercano"]:
        plazo = "cercano"
    else:
        plazo = "ninguno"

    alternativa = evidencia["con_alternativa"] and not evidencia["sin_alternativa"]
    return {"tipo": tipo, "alcance": alcance, "bloquea": bloquea, "plazo": plazo,
            "alternativa": alternativa, "evidencia": evidencia}


def combinar_factores(frases: Dict[str, Any], modelo: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Combina frases explícitas y modelos por factor.

    Regla: si hay una frase explícita sobre un factor, esa evidencia manda (para alcance y
    plazo se toma el valor más grave entre frase y modelo); si no hay frase, decide el modelo.
    Sin modelos, el resultado es el de las frases.
    """
    base = {f: frases[f] for f in FACTORES_RUBRICA}
    if not modelo:
        return base
    ev = frases["evidencia"]
    if ev["incidente_resuelto"]:
        return base

    def mas_grave(orden, a, b):
        return orden[max(orden.index(a), orden.index(b))]

    return {
        "tipo": modelo["tipo"],
        "alcance": (
            mas_grave(ORDEN_ALCANCE, frases["alcance"], modelo["alcance"])
            if ev["alcance_institucional"] or ev["alcance_grupo"] else modelo["alcance"]
        ),
        "bloquea": (
            frases["bloquea"] if ev["no_bloquea"] or ev["bloqueo"] else modelo["bloquea"]
        ),
        "plazo": (
            mas_grave(ORDEN_PLAZO, frases["plazo"], modelo["plazo"])
            if ev["plazo_inmediato"] or ev["plazo_cercano"] else modelo["plazo"]
        ),
        "alternativa": (
            frases["alternativa"] if ev["con_alternativa"] or ev["sin_alternativa"] else modelo["alternativa"]
        ),
    }


def detectar_riesgo_seguridad_personal(texto: str) -> bool:
    """Detecta expresiones explícitas de peligro físico que requieren atención inmediata."""
    return any(senal in texto for senal in SENALES["riesgo_seguridad_personal"])


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
    aprendizaje_humano_aplicado: bool = False


class MemoriaAgente:
    """Gestiona la memoria episódica y el aprendizaje activo basado en casos (CBR)."""

    def __init__(self, ruta_log: Optional[Path] = None):
        self.ruta_log = ruta_log or (RAIZ / "data" / "feedback_log.jsonl")
        self.ruta_log.parent.mkdir(parents=True, exist_ok=True)
        self.historial_decisiones: Dict[str, Dict[str, Any]] = {}

    def guardar_decision(self, decision: DecisionAgente, ticket_original: Dict[str, Any]):
        registro = {
            "timestamp": datetime.now().isoformat(),
            "ticket": ticket_original,
            "decision": asdict(decision),
        }
        self.historial_decisiones[str(decision.id_ticket)] = registro

    def registrar_feedback_humano(
        self,
        id_ticket: str,
        urgencia_humana: str,
        formulario_humano: Optional[str],
        tecnico_humano: Optional[str] = None,
        comentarios: str = "",
        asunto: str = "",
        descripcion: str = "",
    ):
        """Registra la corrección efectuada por un técnico humano para aprendizaje en caliente."""
        if not asunto and str(id_ticket) in self.historial_decisiones:
            t = self.historial_decisiones[str(id_ticket)]["ticket"]
            asunto = t.get("asunto", "")
            descripcion = t.get("descripcion", "")

        registro = {
            "timestamp": datetime.now().isoformat(),
            "id_ticket": str(id_ticket),
            "asunto": asunto,
            "descripcion": descripcion,
            "texto_completo": f"{asunto} {descripcion}".strip(),
            "urgencia_corregida": urgencia_humana,
            "formulario_corregido": formulario_humano,
            "tecnico_corregido": tecnico_humano,
            "comentarios": comentarios,
        }
        with self.ruta_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    def buscar_caso_similar(self, texto_ticket: str, umbral: float = 0.55) -> Optional[Dict[str, Any]]:
        """Busca en la memoria si un técnico ya corrigió un caso semánticamente similar."""
        if not self.ruta_log.exists():
            return None

        correcciones = []
        try:
            for linea in self.ruta_log.read_text(encoding="utf-8").splitlines():
                if linea.strip():
                    correcciones.append(json.loads(linea))
        except Exception:
            return None

        # Un ticket puede corregirse varias veces: solo cuenta su corrección más reciente
        # (el log es append-only, así que la última línea por ticket es la vigente).
        vigentes: Dict[str, Dict[str, Any]] = {}
        for c in correcciones:
            if c.get("texto_completo"):
                vigentes.pop(str(c.get("id_ticket", "")), None)
                vigentes[str(c.get("id_ticket", ""))] = c
        casos_con_texto = list(vigentes.values())
        if not casos_con_texto:
            return None

        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        textos_historicos = [c["texto_completo"] for c in casos_con_texto]
        vec = TfidfVectorizer(strip_accents="unicode", ngram_range=(1, 2))
        try:
            mat = vec.fit_transform(textos_historicos + [texto_ticket])
            sims = cosine_similarity(mat[-1], mat[:-1])[0]
            # Ante empate de similitud, preferir la corrección más reciente.
            max_idx = len(sims) - 1 - int(np.argmax(sims[::-1]))
            if sims[max_idx] >= umbral:
                caso = dict(casos_con_texto[max_idx])
                caso["similitud"] = float(sims[max_idx])
                return caso
        except Exception:
            pass
        return None


class AgenteTriaje:
    def __init__(self, usar_deep_learning: bool = False):
        self.usar_deep_learning = usar_deep_learning
        self.ontologia = OntologiaTI()
        self.motor_fol = MotorInferenciaFOL(umbral_confianza_minima=0.55)
        self.clustering = DetectorIncidentesNoSupervisado()
        self.generador_respuesta = GeneradorRespuestaPreliminar()
        self.memoria = MemoriaAgente()
        # Tickets abiertos en la cola; alimenta la estimación de SLA. El dashboard la
        # actualiza con los datos de GLPI; sin esa información se usa un valor típico.
        self.carga_cola = CARGA_COLA_POR_DEFECTO

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

        if not ruta_urg.exists():
            ruta_urg = RAIZ / "models" / "urgencia.joblib"
        if not ruta_form.exists():
            ruta_form = RAIZ / "models" / "formulario.joblib"

        self.modelo_urgencia = joblib.load(ruta_urg) if ruta_urg.exists() else None
        self.modelo_formulario = joblib.load(ruta_form) if ruta_form.exists() else None
        # Sin models/factores.joblib la percepción usa solo las frases de config/senales.yaml.
        self.percepcion_factores = (
            PercepcionFactores.cargar(RUTA_MODELOS_FACTORES) if RUTA_MODELOS_FACTORES.exists() else None
        )

    # --- 1. PERCEPCIÓN REFINADA ---
    def percibir(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        asunto = ticket.get("asunto", "")
        descripcion = ticket.get("descripcion", "")
        form_elegido = ticket.get("formulario_elegido", "Fallas Técnicas TIC")
        apoyo = ticket.get("apoyo", "Otra")

        texto_urg = f"{form_elegido} | {apoyo} | {asunto} | {descripcion}"
        texto_form = f"{asunto} . {descripcion}"

        # Predicción probabilística inicial
        pred_urg = "Media"
        conf_urg = 0.50
        if self.modelo_urgencia and hasattr(self.modelo_urgencia, "predict_proba"):
            probs_u = self.modelo_urgencia.predict_proba([texto_urg])[0]
            clases_u = self.modelo_urgencia.classes_
            pred_urg = str(clases_u[probs_u.argmax()])
            conf_urg = float(probs_u.max())

        pred_form = form_elegido
        conf_form = 0.50
        if self.modelo_formulario and hasattr(self.modelo_formulario, "predict_proba"):
            probs_f = self.modelo_formulario.predict_proba([texto_form])[0]
            clases_f = self.modelo_formulario.classes_
            pred_form = str(clases_f[probs_f.argmax()])
            conf_form = float(probs_f.max())

        # Extracción de factores: frases explícitas (config/senales.yaml) + modelos por factor
        texto_b = limpiar_texto(f"{asunto} {descripcion}")
        riesgo_seguridad_personal = detectar_riesgo_seguridad_personal(texto_b)
        frases = factores_por_frases(texto_b, tiene_pregunta="?" in f"{asunto} {descripcion}")
        modelo = (
            {f: v for f, (v, _conf) in self.percepcion_factores.predecir(texto_urg).items()}
            if self.percepcion_factores else None
        )
        factores = combinar_factores(frases, modelo)

        incidente_navegador_en_evaluacion = (
            factores["bloquea"]
            and factores["plazo"] == "inmediato"
            and frases["evidencia"]["navegador"]
            and frases["evidencia"]["evaluacion"]
        )

        return {
            "pred_urg": pred_urg,
            "conf_urg": conf_urg,
            "pred_form": pred_form,
            "conf_form": conf_form,
            **factores,
            "factores_frases": {f: frases[f] for f in FACTORES_RUBRICA},
            "factores_modelo": modelo,
            "ya_resuelto": frases["evidencia"]["incidente_resuelto"],
            "riesgo_seguridad_personal": riesgo_seguridad_personal,
            "incidente_navegador_en_evaluacion": incidente_navegador_en_evaluacion,
        }

    # --- 2. RAZONAMIENTO Y APRENDIZAJE ACTIVO ---
    def razonar(self, ticket: Dict[str, Any], percepciones: Dict[str, Any]) -> Dict[str, Any]:
        id_t = ticket.get("id", "sim_000000")
        form_elegido = ticket.get("formulario_elegido", "Fallas Técnicas TIC")
        apoyo = ticket.get("apoyo", "Otra")
        asunto = ticket.get("asunto", "")
        descripcion = ticket.get("descripcion", "")
        texto_busqueda = f"{asunto} {descripcion}".strip()

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
            ya_resuelto=percepciones.get("ya_resuelto", False),
        )

        urgencia_final = deduccion_fol.urgencia_deducida
        aprendizaje_humano_aplicado = False

        # B. Aprendizaje Activo por Casos (CBR): ¿Un técnico humano corrigió un caso similar?
        caso_feedback = self.memoria.buscar_caso_similar(texto_busqueda, umbral=0.55)
        urg_corregida = caso_feedback.get("urgencia_corregida") if caso_feedback else None
        if urg_corregida in NIVELES_URGENCIA:
            ref = (
                f"Caso similar al ticket #{caso_feedback.get('id_ticket', '?')} corregido previamente "
                f"por el técnico a '{urg_corregida}' (Similitud: {caso_feedback.get('similitud', 0):.2f})."
            )
            if urgencia_final == "Crítica" and urg_corregida != "Crítica":
                # Un caso parecido no basta para rebajar automáticamente una urgencia Crítica
                # deducida por las reglas: se mantiene y se pide confirmación humana.
                deduccion_fol.requiere_revision_humana = True
                deduccion_fol.trazabilidad_deductiva.append(
                    f"[APRENDIZAJE HUMANO] {ref} No se rebaja una urgencia Crítica por similitud; "
                    "se mantiene y se solicita revisión humana."
                )
            else:
                urgencia_final = urg_corregida
                aprendizaje_humano_aplicado = True
                deduccion_fol.trazabilidad_deductiva.append(
                    f"[APRENDIZAJE HUMANO] {ref} El agente adopta el aprendizaje humano."
                )

        # La seguridad física prevalece sobre ML, aprendizaje humano y deduplicación.
        if percepciones.get("riesgo_seguridad_personal", False):
            urgencia_final = "Crítica"
            deduccion_fol.urgencia_deducida = "Crítica"
            deduccion_fol.escalamiento_inmediato = True
            deduccion_fol.requiere_revision_humana = True
            deduccion_fol.seguridad_ml_activada = True
            deduccion_fol.motivo_seguridad = (
                "Señales explícitas de posible peligro físico; requiere ayuda presencial inmediata."
            )
            deduccion_fol.trazabilidad_deductiva.append(
                f"[SEGURIDAD PERSONAL] Riesgo físico inmediato en el ticket {id_t}: "
                "se fuerza urgencia Crítica, escalamiento inmediato y revisión humana."
            )
        elif percepciones.get("incidente_navegador_en_evaluacion", False):
            urgencia_final = "Crítica"
            deduccion_fol.urgencia_deducida = "Crítica"
            deduccion_fol.escalamiento_inmediato = True
            deduccion_fol.requiere_revision_humana = True
            deduccion_fol.seguridad_ml_activada = True
            deduccion_fol.motivo_seguridad = (
                "El navegador impide continuar una evaluación en curso; requiere atención prioritaria."
            )
            deduccion_fol.trazabilidad_deductiva.append(
                f"[EVALUACIÓN EN CURSO] Bloqueo del navegador en el ticket {id_t}: "
                "se fuerza urgencia Crítica, escalamiento inmediato y revisión humana."
            )

        # C. Detección de formulario erróneo (umbral >= 0.60)
        cambio_formulario = False
        formulario_final = form_elegido
        if percepciones["pred_form"] != form_elegido and percepciones["conf_form"] >= 0.60:
            formulario_final = percepciones["pred_form"]
            cambio_formulario = True

        # D. Razonamiento Ontológico: Enrutamiento técnico y SLA
        urgencia_asignada = urgencia_final
        asignacion_ont = self.ontologia.enrutar_ticket(
            formulario=formulario_final,
            apoyo=apoyo,
            urgencia=urgencia_final,
            asunto=asunto,
            descripcion=descripcion,
            tipo=percepciones["tipo"],
        )

        # E. Aprendizaje No Supervisado: Detección de Duplicados e Incidentes Masivos
        clustering_res = self.clustering.analizar_ticket(ticket, tipo=percepciones["tipo"])
        if clustering_res.es_incidente_masivo and percepciones["tipo"] == "falla" and not clustering_res.es_duplicado:
            if percepciones["bloquea"]:
                urgencia_final = "Crítica"
                deduccion_fol.trazabilidad_deductiva.append(
                    f"[DBSCAN NO SUPERVISADO] Brote de falla masiva ({clustering_res.tamano_cluster_masivo} reportes concurrentes). "
                    f"Asociado al Incidente Maestro {clustering_res.id_incidente_masivo} y escalado a Crítica."
                )
            else:
                deduccion_fol.trazabilidad_deductiva.append(
                    f"[DBSCAN NO SUPERVISADO] Se detectó un brote de reportes ({clustering_res.tamano_cluster_masivo}), "
                    "pero el impacto fue clasificado como no bloqueante; se conserva la urgencia evaluada."
                )
        elif clustering_res.es_duplicado:
            deduccion_fol.trazabilidad_deductiva.append(
                f"[DUPLICADO DETECTADO] Solicitud recurrente (similitud: {clustering_res.similitud_duplicado:.2f}). "
                f"Asociado al ticket abierto previo #{clustering_res.ticket_original_id}. Se mantiene urgencia evaluada: {urgencia_final}."
            )

        if urgencia_final != urgencia_asignada:
            asignacion_ont = self.ontologia.enrutar_ticket(
                formulario=formulario_final,
                apoyo=apoyo,
                urgencia=urgencia_final,
                asunto=asunto,
                descripcion=descripcion,
                tipo=percepciones["tipo"],
            )

        # F. Modelo Estadístico de Regresión: Tiempo y riesgo de SLA
        pred_sla = {"horas_estimadas": asignacion_ont.tiempo_max_resolucion_horas * 0.6, "nivel_riesgo_sla": "Bajo"}
        if self.estimador_sla:
            pred_sla = self.estimador_sla.predecir(
                urgencia=urgencia_final,
                es_falla=(percepciones["tipo"] == "falla"),
                plataforma_id=asignacion_ont.plataforma_id,
                carga_cola=self.carga_cola,
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
            "aprendizaje_humano_aplicado": aprendizaje_humano_aplicado,
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

        # Generar Respuesta Preliminar al Estudiante
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
            riesgo_seguridad_personal=percepciones.get("riesgo_seguridad_personal", False),
            incidente_navegador_en_evaluacion=percepciones.get(
                "incidente_navegador_en_evaluacion", False
            ),
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
            aprendizaje_humano_aplicado=razonamiento["aprendizaje_humano_aplicado"],
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
