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

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from triage.clustering import DetectorIncidentesNoSupervisado, ResultadoClustering
from triage.fol_rules import DeduccionFOL, MotorInferenciaFOL
from triage.ontology import AsignacionTecnica, OntologiaTI
from triage.response_generator import GeneradorRespuestaPreliminar
from triage.sla_regression import EstimadorSLA


def limpiar_texto(texto: str) -> str:
    """Normaliza tildes y minúsculas para matching semántico robusto."""
    norm = unicodedata.normalize("NFD", texto)
    return "".join(c for c in norm if unicodedata.category(c) != "Mn").lower()


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
        formulario_humano: str,
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

        casos_con_texto = [c for c in correcciones if c.get("texto_completo")]
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
            max_idx = int(np.argmax(sims))
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

        # Extracción semántica refinada de factores
        texto_b = limpiar_texto(f"{asunto} {descripcion}")

        # Detección de incidente resuelto o aviso sin impacto activo
        frases_resueltas = [
            "ya todo esta bien", "ya esta bien", "ya funciona", "ya se arreglo",
            "ya se soluciono", "solo duro", "duro 5 minutos", "era solo una actualizacion",
            "ya pude entrar", "ya tengo acceso", "falsa alarma", "no era nada",
            "se arreglo solo", "se soluciono solo"
        ]
        ya_resuelto = any(f in texto_b for f in frases_resueltas)

        # Tipo
        terminos_duda = [
            "como", "quisiera saber", "consulta", "pregunta", "donde", "orientacion",
            "procedimiento", "proceso", "requisitos", "informacion sobre", "solicito saber",
            "como puedo", "donde puedo", "que debo hacer", "solicitud de", "inquietud",
            "como descargar", "como instalar", "como pagar", "como ingresar por primera vez",
            "instrucciones", "tutorial", "guia", "se puede", "no se si",
            "solo quiero confirmar", "quiero confirmar", "me gustaria saber",
            "es posible", "cuantos", "cuantas", "hasta que hora"
        ]
        terminos_falla = [
            "error", "fallo", "falla", "no funciona", "caido", "bloqueado", "denegado",
            "no tengo acceso", "no abre", "se congela", "pantalla negra", "pantallazo",
            "se cierra", "no me deja", "no puedo ingresar", "no conecta", "sin internet",
            "sin conexion", "dañado", "interrupcion", "lentitud extrema", "no se puede",
            "no puedo pagar", "no puedo enviar", "no puedo usar",
            "no puedo hacer", "no enciende", "no encienden", "no hay wifi",
            "sin wifi", "no hay internet", "restablecimiento no me llega",
            "nadie de mi programa puede entrar", "nadie puede entrar",
            "nadie puede conectarse"
        ]
        hay_senal_de_consulta = any(w in texto_b for w in terminos_duda) or "?" in f"{asunto} {descripcion}"
        hay_senal_de_falla = any(w in texto_b for w in terminos_falla)
        if ya_resuelto:
            tipo = "duda"
        elif hay_senal_de_consulta and not hay_senal_de_falla:
            tipo = "duda"
        else:
            tipo = "falla"

        # Alcance
        if any(w in texto_b for w in [
            "toda la universidad", "todo el campus", "a todos los estudiantes",
            "nadie en la universidad", "todo el edificio", "en toda la sede",
            "caida masiva", "caida general", "a nivel general", "servidor caido",
            "a nadie le funciona", "nadie de mi programa", "nadie del programa",
            "a todo mi programa", "todos los estudiantes de mi programa",
            "nadie puede entrar", "nadie puede conectarse"
        ]):
            alcance = "institucional"
        elif any(w in texto_b for w in [
            "todo el salon", "mi grupo", "varios companeros", "a todos nos sale",
            "en mi clase", "en la sala", "en el laboratorio", "a varios",
            "a todo el curso", "en el bloque", "todo el piso", "varios estamos afectados"
        ]):
            alcance = "grupo"
        else:
            alcance = "individual"

        # Bloqueo
        no_bloquea_frases = [
            "puedo seguir trabajando", "no es grave", "solo queria reportarlo",
            "no me impide", "ya todo esta bien", "ya esta bien", "ya funciona",
            "ya pude", "duro 5 minutos", "era solo una actualizacion", "solo es una duda",
            "solo quiero saber", "es informativo", "funciona pero", "solo queria preguntar",
            "puedo seguir conectado", "puedo trabajar", "igual puedo trabajar",
            "igual puedo", "a veces", "por momentos", "solo lo reporto",
            "no tengo afan", "cruce de horarios"
        ]
        terminos_bloqueo = [
            "no tengo acceso", "bloqueado", "acceso denegado", "no me deja entrar",
            "no puedo ingresar", "completamente bloqueado", "no puedo continuar",
            "no deja hacer nada", "imposible acceder", "no puedo presentar",
            "no me deja pagar", "no puedo enviar", "no puedo matricular", "cuenta suspendida",
            "no carga el examen", "no abre el examen", "se queda en blanco", "clave incorrecta",
            "no me deja", "no abre", "no carga", "no inicia", "no funciona", "no responde",
            "no conecta", "no me deja usar", "no puedo usar", "no puedo conectarme",
            "no me deja conectarme", "no hay wifi", "sin wifi",
            "no hay internet", "nadie puede conectarse", "se cerro el programa",
            "nadie de mi programa puede entrar",
            "no me aparece abierta la inscripcion", "error al pagar", "no puedo pagar",
            "no se puede ingresar", "no se puede conectar", "error al unir",
            "restablecimiento no me llega", "no puedo hacer mis actividades",
            "no encienden", "no enciende"
        ]
        if ya_resuelto or any(w in texto_b for w in no_bloquea_frases):
            bloquea = False
        else:
            if any(w in texto_b for w in terminos_bloqueo):
                bloquea = True
            else:
                bloquea = False

        # Plazo: evitar falsos positivos con adverbios "ya" en frases como "ya está bien"
        if ya_resuelto:
            plazo = "ninguno"
        elif any(w in texto_b for w in [
            "en una hora", "en 15 minutos", "hoy vence", "vence hoy",
            "empieza ya", "es ya", "entrega hoy", "en media hora",
            "en 30 minutos", "en 10 minutos", "en 20 minutos", "tengo clase ya",
            "clase en una hora", "en este momento", "plazo maximo hoy", "cierra en minutos",
            "cierra hoy", "ultimo dia", "ahora mismo", "presento ahora",
            "vence en una hora", "vence en 30 minutos", "vence en 15 minutos",
            "vence en 10 minutos",
            "en medio de un parcial", "en medio de un examen", "examen en curso",
            "parcial en curso", "evaluacion en curso", "sustentacion en curso",
            "parcial ahora", "examen ahora", "empieza en este momento"
        ]):
            plazo = "inmediato"
        elif any(w in texto_b for w in [
            "manana", "viernes", "proxima semana", "pocos dias", "este fin de semana",
            "fecha limite", "esta noche", "en 24 horas", "en 48 horas", "en dos dias",
            "limite de entrega", "en tres dias", "en 3 dias", "en cuatro dias",
            "en 4 dias", "en cinco dias", "en 5 dias", "en 72 horas",
            "mas adelante", "proximo semestre"
        ]):
            plazo = "cercano"
        else:
            plazo = "ninguno"

        # Alternativa
        tiene_alt = any(w in texto_b for w in [
            "desde el celular", "otro computador", "otro dispositivo", "amigo",
            "otra sala", "en la app movil", "usando datos", "en otro navegador",
            "en modo incognito", "desde mi casa", "otro correo", "ir a tesoreria",
            "puedo ir a tesoreria", "desde tesoreria", "otra sede", "otro laboratorio"
        ])
        sin_alt = any(w in texto_b for w in [
            "no tengo otra forma", "no tengo otra manera", "sin alternativa",
            "es la unica forma", "unica manera", "no encuentro otra manera",
            "no tengo otro equipo", "no tengo celular", "unico computador",
            "no tengo como", "no tengo mas opciones"
        ])
        alternativa = tiene_alt and not sin_alt

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
            "ya_resuelto": ya_resuelto,
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
        if caso_feedback:
            urg_previa = urgencia_final
            urgencia_final = caso_feedback["urgencia_corregida"]
            aprendizaje_humano_aplicado = True
            deduccion_fol.trazabilidad_deductiva.append(
                f"[APRENDIZAJE HUMANO] Caso similar al ticket #{caso_feedback.get('id_ticket', '?')} "
                f"corregido previamente por el técnico a '{urgencia_final}' (Similitud: {caso_feedback.get('similitud', 0):.2f}). "
                f"El agente adopta el aprendizaje humano."
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
