"""Rúbrica de urgencia del agente de triaje.

La urgencia se decide a partir de cuatro factores que el texto del ticket
puede revelar. Esta misma función etiqueta los datos sintéticos y servirá de
base para las reglas lógicas (predicados) del agente: el modelo de ML estima
los factores/urgencia desde el texto y las reglas actúan como red de seguridad.

Importante: la rúbrica es una DEFINICIÓN nuestra de urgencia, no una verdad
externa. Los umbrales deben ajustarse con criterio de TI.
"""

from dataclasses import dataclass

NIVELES = ["Baja", "Media", "Alta", "Crítica"]


@dataclass(frozen=True)
class Factores:
    tipo: str          # "falla" (algo no funciona) | "duda" (consulta)
    alcance: str       # "individual" | "grupo" | "institucional"
    bloquea: bool      # impide continuar con lo que la persona hacía
    plazo: str         # "inmediato" | "cercano" | "ninguno"
    alternativa: bool  # existe otra forma razonable de lograrlo mientras tanto


def urgencia(f: Factores) -> str:
    # R1. Afecta a muchas personas o a un servicio institucional.
    if f.alcance in ("grupo", "institucional"):
        return "Crítica" if f.bloquea else "Alta"

    # R2. Dudas y consultas: solo suben a Media si hay plazo.
    if f.tipo == "duda":
        return "Media" if f.plazo != "ninguno" else "Baja"

    # R3. Fallas individuales.
    if f.bloquea:
        if f.plazo == "inmediato":
            return "Alta" if f.alternativa else "Crítica"
        if f.plazo == "cercano":
            return "Media" if f.alternativa else "Alta"
        # Sin plazo explícito: si no tiene alternativa, es Alta; si tiene alternativa mitigante, es Media.
        return "Alta" if not f.alternativa else "Media"
    return "Media" if f.plazo != "ninguno" else "Baja"


def desplazar(nivel: str, paso: int) -> str:
    """Mueve un nivel hacia arriba/abajo (se usa para ruido de etiqueta)."""
    i = max(0, min(len(NIVELES) - 1, NIVELES.index(nivel) + paso))
    return NIVELES[i]
