"""Generador de tickets sintéticos en español, con la forma de los formularios de Tooli.

Cada ticket tiene los campos que ve el agente (formulario elegido, apoyo elegido,
asunto, descripción, adjunto) y las etiquetas (urgencia por rúbrica, formulario
correcto). Se añade ruido para que no sea trivial: pistas omitidas, errores de
tipeo, registro informal, formulario equivocado y ruido de etiqueta.

Aun así es texto fabricado por plantillas: las métricas sobre estos datos son
optimistas. Úsense junto con el conjunto escrito a mano (data/gold_manual.csv).
"""

import csv
import random
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from .banks import (ALCANCE, ALTERNATIVA, BLOQUEO, CIERRES, DIAS, EVENTOS, FT, HORAS,
                    INTROS_DUDA, INTROS_FALLA, P_URGENTE, PLAZO, PP, SC, SINTOMAS, SM,
                    TRAMITES)
from .rubric import Factores, desplazar, urgencia

RAIZ = Path(__file__).resolve().parents[2]

# Con qué formularios se suelen confundir los estudiantes (formulario correcto -> elegido).
CONFUSIONES = {
    FT: [SC, SM, PP],
    SC: [FT],
    PP: [FT, SM],
    SM: [FT, PP],
}
PESO_FORMULARIO = {FT: 0.50, SC: 0.20, PP: 0.15, SM: 0.15}
P_MAL_FORMULARIO = 0.12
P_APOYO_OTRA = 0.15
P_RUIDO_ETIQUETA = 0.05

COLUMNAS = [
    "id", "fecha_apertura", "formulario_elegido", "apoyo", "asunto", "descripcion",
    "tiene_adjunto", "formulario_correcto", "mal_categorizado", "urgencia",
    # Variables latentes: transparencia/análisis, NO son entrada del modelo.
    "apoyo_real", "tipo", "alcance", "bloquea", "plazo", "alternativa",
]


def cargar_apoyos():
    cfg = yaml.safe_load((RAIZ / "config" / "taxonomy.yaml").read_text(encoding="utf-8"))
    return {f["nombre"]: f.get("apoyos", []) for f in cfg["formularios"] if f.get("nucleo")}


def sortear_factores(rng):
    tipo = "duda" if rng.random() < 0.25 else "falla"
    alcance = "individual" if tipo == "duda" else rng.choices(
        ["individual", "grupo", "institucional"], [0.82, 0.10, 0.08])[0]
    bloquea = tipo == "falla" and rng.random() < 0.55
    plazo = rng.choices(["inmediato", "cercano", "ninguno"], [0.12, 0.25, 0.63])[0]
    alternativa = rng.random() < 0.35
    return Factores(tipo, alcance, bloquea, plazo, alternativa)


def rellenar(frase, rng):
    """Sustituye los marcadores de las pistas ({n}, {h}, {evento}...) por valores al azar."""
    evento, tramite = rng.choice(EVENTOS), rng.choice(TRAMITES)
    valores = {
        "n": str(rng.choice([5, 10, 15, 20, 25, 30, 40, 45])),
        "h": rng.choice(HORAS),
        "d": str(rng.randint(2, 5)),
        "dia": rng.choice(DIAS),
        "evento": evento, "Evento": mayuscula(evento),
        "tramite": tramite, "Tramite": mayuscula(tramite),
    }
    return frase.format(**valores) if "{" in frase else frase


def frases_de_factores(f, rng):
    """Frases que revelan los factores; cada pista se omite a veces (ambigüedad real)."""
    frases = []
    if f.alcance != "individual" and rng.random() < 0.85:
        frases.append(rng.choice(ALCANCE[f.alcance]))
    if f.tipo == "falla":
        if f.bloquea and rng.random() < 0.85:
            frases.append(rng.choice(BLOQUEO[True]))
        elif not f.bloquea and rng.random() < 0.25:
            frases.append(rng.choice(BLOQUEO[False]))
        if f.alternativa and rng.random() < 0.70:
            frases.append(rng.choice(ALTERNATIVA[True]))
        elif not f.alternativa and f.bloquea and rng.random() < 0.35:
            frases.append(rng.choice(ALTERNATIVA[False]))
    if f.plazo != "ninguno" and rng.random() < 0.85:
        frases.append(rng.choice(PLAZO[f.plazo]))
    elif f.plazo == "ninguno" and rng.random() < 0.15:
        frases.append(rng.choice(PLAZO["ninguno"]))
    rng.shuffle(frases)
    return [rellenar(frase, rng) for frase in frases]


def mayuscula(texto):
    return texto[:1].upper() + texto[1:]


def construir_descripcion(sintoma, f, rng):
    intros = INTROS_FALLA if f.tipo == "falla" else INTROS_DUDA
    primera = mayuscula(rng.choice(intros) + sintoma)
    if not primera.endswith((".", "?")):
        primera += "?" if f.tipo == "duda" and rng.random() < 0.5 else "."
    partes = [primera] + frases_de_factores(f, rng)
    cierre = rng.choice(CIERRES)
    if cierre:
        partes.append(cierre)
    return " ".join(partes)


def construir_asunto(apoyo_real, sintoma, f, nivel, rng):
    # Asuntos cortos, como el real ("Portal Banner"): casi no informan; la descripción sí.
    opciones = [apoyo_real, apoyo_real, f"Problema con {apoyo_real}",
                "Solicitud de apoyo", "Ayuda por favor"]
    if f.tipo == "falla":
        opciones += [f"Error en {apoyo_real}", "Problema técnico"]
    else:
        opciones += [f"Consulta {apoyo_real}", "Consulta", "Pregunta"]
    asunto = mayuscula(rng.choice(opciones))
    if rng.random() < P_URGENTE[nivel]:
        asunto = rng.choice(["URGENTE: ", "Urgente - ", "Urgente "]) + asunto
    return asunto


def quitar_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def degradar(texto, rng):
    """Ruido de escritura: sin tildes, minúsculas, typos, sin puntuación."""
    if rng.random() < 0.30:
        texto = quitar_tildes(texto)
    if rng.random() < 0.25:
        texto = texto.lower()
    if rng.random() < 0.20:
        letras = list(texto)
        for _ in range(rng.choice([1, 2])):
            i = rng.randrange(1, max(2, len(letras) - 1))
            if letras[i].isalpha() and letras[i + 1].isalpha():
                if rng.random() < 0.5:
                    letras[i], letras[i + 1] = letras[i + 1], letras[i]
                else:
                    letras[i] = ""
        texto = "".join(letras)
    if rng.random() < 0.15:
        texto = texto.replace(",", "").replace(".", "")
    return texto


def generar(n=6000, semilla=42):
    rng = random.Random(semilla)
    apoyos_por_form = cargar_apoyos()
    claves_por_form = {
        form: [a for (fm, a) in SINTOMAS if fm == form] for form in apoyos_por_form
    }
    inicio = datetime(2026, 2, 2, 7, 0)
    filas = []
    for i in range(1, n + 1):
        form_correcto = rng.choices(list(PESO_FORMULARIO), list(PESO_FORMULARIO.values()))[0]
        apoyo_real = rng.choice(claves_por_form[form_correcto])
        f = sortear_factores(rng)
        nivel = urgencia(f)
        sintoma = rng.choice(SINTOMAS[(form_correcto, apoyo_real)][f.tipo])

        # Formulario y apoyo que el estudiante terminó eligiendo.
        if rng.random() < P_MAL_FORMULARIO:
            form_elegido = rng.choice(CONFUSIONES[form_correcto])
            apoyo = rng.choice(apoyos_por_form[form_elegido])
        else:
            form_elegido = form_correcto
            apoyo = apoyo_real
            if "Otra" in apoyos_por_form[form_elegido] and rng.random() < P_APOYO_OTRA:
                apoyo = "Otra"

        descripcion = degradar(construir_descripcion(sintoma, f, rng), rng)
        asunto = degradar(construir_asunto(apoyo_real, sintoma, f, nivel, rng), rng)
        if rng.random() < P_RUIDO_ETIQUETA:
            nivel = desplazar(nivel, rng.choice([-1, 1]))

        fecha = inicio + timedelta(days=rng.randrange(0, 270), minutes=rng.randrange(0, 12 * 60))
        filas.append({
            "id": f"sim_{i:06d}",
            "fecha_apertura": fecha.strftime("%Y-%m-%d %H:%M"),
            "formulario_elegido": form_elegido,
            "apoyo": apoyo,
            "asunto": asunto,
            "descripcion": descripcion,
            "tiene_adjunto": int(rng.random() < 0.18),
            "formulario_correcto": form_correcto,
            "mal_categorizado": int(form_elegido != form_correcto),
            "urgencia": nivel,
            "apoyo_real": apoyo_real,
            "tipo": f.tipo,
            "alcance": f.alcance,
            "bloquea": int(f.bloquea),
            "plazo": f.plazo,
            "alternativa": int(f.alternativa),
        })
    return filas


def guardar(filas, ruta):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS, lineterminator="\n")
        w.writeheader()
        w.writerows(filas)


def main(n=6000, semilla=42):
    filas = generar(n, semilla)
    ruta = RAIZ / "data" / "tickets_sinteticos.csv"
    guardar(filas, ruta)
    from collections import Counter
    print(f"{len(filas)} tickets -> {ruta}")
    print("urgencia:", dict(Counter(r["urgencia"] for r in filas)))
    print("formulario correcto:", dict(Counter(r["formulario_correcto"] for r in filas)))
    print("mal categorizados:", sum(r["mal_categorizado"] for r in filas))


if __name__ == "__main__":
    main()
