"""Motor de Inferencia en Lógica de Primer Orden (FOL - First-Order Logic).

Formaliza el razonamiento deductivo del agente:
- Predicados de primer orden sobre tickets, estados y urgencias.
- Reglas expresadas como Cláusulas de Horn / Implicaciones lógicas.
- Inferencia hacia adelante (Forward Chaining) con traza de prueba formal (justificación explicable).
- Red de seguridad (Safety Net): corrige o audita las predicciones probabilísticas de ML.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class Predicado:
    nombre: str
    argumentos: Tuple[Any, ...]

    def __str__(self) -> str:
        args_str = ", ".join(repr(a) for a in self.argumentos)
        return f"{self.nombre}({args_str})"


@dataclass
class ReglaFOL:
    id_regla: str
    nombre: str
    premisas: List[Predicado]
    conclusion: Predicado
    explicacion_formal: str

    def evaluar(self, base_hechos: Set[Predicado]) -> bool:
        """Verifica si todas las premisas se satisfacen en la base de hechos."""
        return all(p in base_hechos for p in self.premisas)


@dataclass
class DeduccionFOL:
    urgencia_deducida: str
    escalamiento_inmediato: bool
    requiere_revision_humana: bool
    reglas_disparadas: List[str]
    trazabilidad_deductiva: List[str]
    seguridad_ml_activada: bool
    urgencia_ml_original: Optional[str] = None
    motivo_seguridad: Optional[str] = None


class MotorInferenciaFOL:
    """Motor de deducción en Lógica de Primer Orden para el Agente de Triaje."""

    def __init__(self, umbral_confianza_minima: float = 0.55):
        self.umbral_confianza = umbral_confianza_minima
        self.reglas = self._construir_reglas()

    def _construir_reglas(self) -> List[ReglaFOL]:
        t = "?t"
        return [
            # R0: Incidente ya resuelto o aviso informativo -> Baja
            ReglaFOL(
                id_regla="FOL-R00",
                nombre="Incidente Resuelto o Informativo",
                premisas=[
                    Predicado("YaResuelto", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Baja")),
                explicacion_formal="∀t (YaResuelto(t) → Urgencia(t, Baja))",
            ),
            # R1: Impacto Masivo/Grupo con Bloqueo -> Crítica + Escalamiento
            ReglaFOL(
                id_regla="FOL-R01",
                nombre="Falla Masiva Bloqueante",
                premisas=[
                    Predicado("AfectaGrupoOInstitucional", (t,)),
                    Predicado("Bloquea", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Crítica")),
                explicacion_formal="∀t (AfectaGrupoOInstitucional(t) ∧ Bloquea(t) → Urgencia(t, Crítica))",
            ),
            # R2: Falla Masiva No Bloqueante -> Alta
            ReglaFOL(
                id_regla="FOL-R02",
                nombre="Falla Masiva Parcial",
                premisas=[
                    Predicado("AfectaGrupoOInstitucional", (t,)),
                    Predicado("NoBloquea", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Alta")),
                explicacion_formal="∀t (AfectaGrupoOInstitucional(t) ∧ ¬Bloquea(t) → Urgencia(t, Alta))",
            ),
            # R3: Duda sin plazo -> Baja
            ReglaFOL(
                id_regla="FOL-R03",
                nombre="Consulta Informativa Sin Plazo",
                premisas=[
                    Predicado("EsDuda", (t,)),
                    Predicado("SinPlazo", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Baja")),
                explicacion_formal="∀t (EsDuda(t) ∧ SinPlazo(t) → Urgencia(t, Baja))",
            ),
            # R4: Duda con plazo (inmediato o cercano) -> Media
            ReglaFOL(
                id_regla="FOL-R04",
                nombre="Consulta Con Plazo Temporal",
                premisas=[
                    Predicado("EsDuda", (t,)),
                    Predicado("TienePlazo", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Media")),
                explicacion_formal="∀t (EsDuda(t) ∧ TienePlazo(t) → Urgencia(t, Media))",
            ),
            # R5: Falla individual bloqueante con plazo inmediato y sin alternativa -> Crítica
            ReglaFOL(
                id_regla="FOL-R05",
                nombre="Falla Crítica Individual Inmediata",
                premisas=[
                    Predicado("EsFalla", (t,)),
                    Predicado("AlcanceIndividual", (t,)),
                    Predicado("Bloquea", (t,)),
                    Predicado("PlazoInmediato", (t,)),
                    Predicado("SinAlternativa", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Crítica")),
                explicacion_formal=(
                    "∀t (EsFalla(t) ∧ AlcanceIndividual(t) ∧ Bloquea(t) ∧ "
                    "PlazoInmediato(t) ∧ ¬Alternativa(t) → Urgencia(t, Crítica))"
                ),
            ),
            # R6: Falla individual bloqueante con plazo inmediato pero con alternativa -> Alta
            ReglaFOL(
                id_regla="FOL-R06",
                nombre="Falla Alta Individual con Alternativa Mitigante",
                premisas=[
                    Predicado("EsFalla", (t,)),
                    Predicado("AlcanceIndividual", (t,)),
                    Predicado("Bloquea", (t,)),
                    Predicado("PlazoInmediato", (t,)),
                    Predicado("TieneAlternativa", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Alta")),
                explicacion_formal=(
                    "∀t (EsFalla(t) ∧ AlcanceIndividual(t) ∧ Bloquea(t) ∧ "
                    "PlazoInmediato(t) ∧ Alternativa(t) → Urgencia(t, Alta))"
                ),
            ),
            # R7: Falla individual bloqueante con plazo cercano y sin alternativa -> Alta
            ReglaFOL(
                id_regla="FOL-R07",
                nombre="Falla Alta Individual Plazo Cercano",
                premisas=[
                    Predicado("EsFalla", (t,)),
                    Predicado("AlcanceIndividual", (t,)),
                    Predicado("Bloquea", (t,)),
                    Predicado("PlazoCercano", (t,)),
                    Predicado("SinAlternativa", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Alta")),
                explicacion_formal=(
                    "∀t (EsFalla(t) ∧ AlcanceIndividual(t) ∧ Bloquea(t) ∧ "
                    "PlazoCercano(t) ∧ ¬Alternativa(t) → Urgencia(t, Alta))"
                ),
            ),
            # R8: Falla individual bloqueante con plazo cercano con alternativa -> Media
            ReglaFOL(
                id_regla="FOL-R08",
                nombre="Falla Media Individual Mitigada",
                premisas=[
                    Predicado("EsFalla", (t,)),
                    Predicado("AlcanceIndividual", (t,)),
                    Predicado("Bloquea", (t,)),
                    Predicado("PlazoCercano", (t,)),
                    Predicado("TieneAlternativa", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Media")),
                explicacion_formal=(
                    "∀t (EsFalla(t) ∧ AlcanceIndividual(t) ∧ Bloquea(t) ∧ "
                    "PlazoCercano(t) ∧ Alternativa(t) → Urgencia(t, Media))"
                ),
            ),
            # R8B: Falla individual bloqueante sin plazo explícito pero sin alternativa -> Alta
            ReglaFOL(
                id_regla="FOL-R08B",
                nombre="Bloqueo Individual Total Sin Alternativa",
                premisas=[
                    Predicado("EsFalla", (t,)),
                    Predicado("AlcanceIndividual", (t,)),
                    Predicado("Bloquea", (t,)),
                    Predicado("SinAlternativa", (t,)),
                    Predicado("SinPlazo", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Alta")),
                explicacion_formal=(
                    "∀t (EsFalla(t) ∧ AlcanceIndividual(t) ∧ Bloquea(t) ∧ "
                    "¬Alternativa(t) ∧ SinPlazo(t) → Urgencia(t, Alta))"
                ),
            ),
            # R8C: Falla individual bloqueante sin plazo explícito con alternativa mitigante -> Media
            ReglaFOL(
                id_regla="FOL-R08C",
                nombre="Bloqueo Individual Mitigado Sin Plazo",
                premisas=[
                    Predicado("EsFalla", (t,)),
                    Predicado("AlcanceIndividual", (t,)),
                    Predicado("Bloquea", (t,)),
                    Predicado("TieneAlternativa", (t,)),
                    Predicado("SinPlazo", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Media")),
                explicacion_formal=(
                    "∀t (EsFalla(t) ∧ AlcanceIndividual(t) ∧ Bloquea(t) ∧ "
                    "Alternativa(t) ∧ SinPlazo(t) → Urgencia(t, Media))"
                ),
            ),
            # R9: Falla individual no bloqueante con plazo -> Media
            ReglaFOL(
                id_regla="FOL-R09",
                nombre="Falla No Bloqueante con Plazo",
                premisas=[
                    Predicado("EsFalla", (t,)),
                    Predicado("NoBloquea", (t,)),
                    Predicado("TienePlazo", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Media")),
                explicacion_formal="∀t (EsFalla(t) ∧ ¬Bloquea(t) ∧ TienePlazo(t) → Urgencia(t, Media))",
            ),
            # R10: Falla individual no bloqueante sin plazo -> Baja
            ReglaFOL(
                id_regla="FOL-R10",
                nombre="Falla Leve Sin Plazo",
                premisas=[
                    Predicado("EsFalla", (t,)),
                    Predicado("NoBloquea", (t,)),
                    Predicado("SinPlazo", (t,)),
                ],
                conclusion=Predicado("Urgencia", (t, "Baja")),
                explicacion_formal="∀t (EsFalla(t) ∧ ¬Bloquea(t) ∧ SinPlazo(t) → Urgencia(t, Baja))",
            ),
            # R11: Regla de Escalamiento Inmediato
            ReglaFOL(
                id_regla="FOL-ESC01",
                nombre="Escalamiento por Urgencia Crítica",
                premisas=[
                    Predicado("Urgencia", (t, "Crítica")),
                ],
                conclusion=Predicado("EscalamientoInmediato", (t,)),
                explicacion_formal="∀t (Urgencia(t, Crítica) → EscalamientoInmediato(t))",
            ),
        ]

    def instanciar_hechos(
        self,
        id_ticket: str,
        tipo: str,
        alcance: str,
        bloquea: bool,
        plazo: str,
        alternativa: bool,
        confianza_ml: float = 1.0,
        ya_resuelto: bool = False,
    ) -> Set[Predicado]:
        """Convierte los atributos percibidos en proposiciones de primer orden instanciadas."""
        t = id_ticket
        hechos: Set[Predicado] = set()

        # Resuelto o informativo
        if ya_resuelto:
            hechos.add(Predicado("YaResuelto", (t,)))

        # Tipo
        if tipo == "duda":
            hechos.add(Predicado("EsDuda", (t,)))
        else:
            hechos.add(Predicado("EsFalla", (t,)))

        # Alcance
        if alcance in ("grupo", "institucional"):
            hechos.add(Predicado("AfectaGrupoOInstitucional", (t,)))
        else:
            hechos.add(Predicado("AlcanceIndividual", (t,)))

        # Bloqueo
        if bloquea and not ya_resuelto:
            hechos.add(Predicado("Bloquea", (t,)))
        else:
            hechos.add(Predicado("NoBloquea", (t,)))

        # Plazo
        if plazo == "inmediato" and not ya_resuelto:
            hechos.add(Predicado("PlazoInmediato", (t,)))
            hechos.add(Predicado("TienePlazo", (t,)))
        elif plazo == "cercano" and not ya_resuelto:
            hechos.add(Predicado("PlazoCercano", (t,)))
            hechos.add(Predicado("TienePlazo", (t,)))
        else:
            hechos.add(Predicado("SinPlazo", (t,)))

        # Alternativa
        if alternativa:
            hechos.add(Predicado("TieneAlternativa", (t,)))
        else:
            hechos.add(Predicado("SinAlternativa", (t,)))

        # Incertidumbre
        if confianza_ml < self.umbral_confianza:
            hechos.add(Predicado("ConfianzaBaja", (t,)))

        return hechos

    def razonar(
        self,
        id_ticket: str,
        tipo: str,
        alcance: str,
        bloquea: bool,
        plazo: str,
        alternativa: bool,
        urgencia_predicha_ml: Optional[str] = None,
        confianza_ml: float = 1.0,
        ya_resuelto: bool = False,
    ) -> DeduccionFOL:
        """Aplica encadenamiento hacia adelante sobre los hechos del ticket."""
        t = id_ticket
        base_hechos = self.instanciar_hechos(
            t, tipo, alcance, bloquea, plazo, alternativa, confianza_ml, ya_resuelto
        )

        reglas_disparadas: List[str] = []
        trazabilidad: List[str] = []
        urgencia_deducida = "Media"  # Valor conservador por defecto
        escalamiento = False
        revision_humana = False
        seguridad_activada = False
        motivo_seguridad = None

        # Red de seguridad 1: Confianza baja del modelo de ML
        if Predicado("ConfianzaBaja", (t,)) in base_hechos:
            revision_humana = True
            seguridad_activada = True
            motivo_seguridad = (
                f"Confianza probabilística ({confianza_ml:.2f}) inferior al umbral de seguridad "
                f"({self.umbral_confianza:.2f}). Se retiene en urgencia conservadora 'Media' "
                f"y se solicita confirmación al técnico humano."
            )
            trazabilidad.append(
                f"[SEGURIDAD] ConfianzaBaja({t}) → RevisionHumana({t}) ∧ UrgenciaDefecto({t}, Media)"
            )

        # Proceso de inferencia hacia adelante (Forward Chaining)
        cambio = True
        while cambio:
            cambio = False
            for regla in self.reglas:
                # Reemplazar la variable ?t por el ID concreto del ticket
                premisas_instanciadas = [
                    Predicado(p.nombre, tuple(t if a == "?t" else a for a in p.argumentos))
                    for p in regla.premisas
                ]
                conclusion_instanciada = Predicado(
                    regla.conclusion.nombre,
                    tuple(t if a == "?t" else a for a in regla.conclusion.argumentos),
                )

                if conclusion_instanciada not in base_hechos:
                    if all(p in base_hechos for p in premisas_instanciadas):
                        base_hechos.add(conclusion_instanciada)
                        reglas_disparadas.append(regla.id_regla)
                        trazabilidad.append(
                            f"[{regla.id_regla}] {regla.nombre}: "
                            f"{', '.join(str(p) for p in premisas_instanciadas)} "
                            f"⊢ {conclusion_instanciada} | Justificación: {regla.explicacion_formal}"
                        )
                        cambio = True

                        if conclusion_instanciada.nombre == "Urgencia":
                            urgencia_deducida = conclusion_instanciada.argumentos[1]
                        if conclusion_instanciada.nombre == "EscalamientoInmediato":
                            escalamiento = True

        # Red de seguridad 2: Auditoría contra predicción de ML
        # Si ML subestima una situación que en lógica es de mayor urgencia (riesgo para SLA)
        if urgencia_predicha_ml:
            niveles = ["Baja", "Media", "Alta", "Crítica"]
            idx_ml = niveles.index(urgencia_predicha_ml) if urgencia_predicha_ml in niveles else 1
            idx_fol = niveles.index(urgencia_deducida) if urgencia_deducida in niveles else 1

            if idx_fol > idx_ml:
                seguridad_activada = True
                motivo_seguridad = (
                    f"Conflicto de seguridad detectado: El modelo ML estimó '{urgencia_predicha_ml}', "
                    f"pero las reglas deterministas de primer orden demuestran gravedad '{urgencia_deducida}'. "
                    f"El árbitro FOL prevalece por política de protección de SLA."
                )
                trazabilidad.append(f"[ÁRBITRO FOL] Corrección: {urgencia_predicha_ml} → {urgencia_deducida}")

        return DeduccionFOL(
            urgencia_deducida=urgencia_deducida,
            escalamiento_inmediato=escalamiento,
            requiere_revision_humana=revision_humana,
            reglas_disparadas=reglas_disparadas,
            trazabilidad_deductiva=trazabilidad,
            seguridad_ml_activada=seguridad_activada,
            urgencia_ml_original=urgencia_predicha_ml,
            motivo_seguridad=motivo_seguridad,
        )
