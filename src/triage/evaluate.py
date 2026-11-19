"""Evaluación comparativa del agente de triaje.

Compara, sobre los mismos tickets, cuatro formas de decidir la urgencia:
- modelo_clasico: TF-IDF + Regresión Logística (models/urgencia.joblib).
- modelo_mlp: red neuronal MLP (models/urgencia_deep.joblib).
- reglas_solas: rúbrica aplicada a los factores según las frases de config/senales.yaml.
- modelo_factores: rúbrica aplicada a los factores que predicen los modelos por factor.
- agente: ciclo completo percibir -> razonar -> actuar (lo que usa el dashboard), con
  frases y modelos de factores combinados.

Conjuntos:
- sintetico_prueba: el mismo 20 % de prueba que usan train.py y deep_model.py.
- gold_manual: 24 tickets escritos a mano. Las reglas se ajustaron mirando estos tickets,
  así que sirven como conjunto de desarrollo, no como medida independiente.
- gold_holdout: tickets escritos a mano que no deben usarse para ajustar reglas ni modelos.

Cuando el conjunto trae los factores etiquetados (tipo, alcance, bloquea, plazo, alternativa),
también se mide qué tan bien los detecta la percepción.

Uso: python main.py evaluar
"""

import json
from pathlib import Path
import sys
import tempfile
from typing import Dict, List

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from triage.agent import AgenteTriaje, MemoriaAgente  # noqa: E402
from triage.rubric import NIVELES, Factores, urgencia  # noqa: E402
from triage.train import SEMILLA, subestima_critica, texto_urgencia  # noqa: E402

FACTORES = ("tipo", "alcance", "bloquea", "plazo", "alternativa")
ESTRATEGIAS = ("modelo_clasico", "modelo_mlp", "reglas_solas", "modelo_factores", "agente")
FUENTES = ("frases", "modelo", "agente")


def _a_bool(valor) -> bool:
    return str(valor).strip().lower() in ("1", "true", "si", "sí")


def cargar_conjuntos() -> Dict[str, pd.DataFrame]:
    conjuntos = {}
    df = pd.read_csv(RAIZ / "data" / "tickets_sinteticos.csv").fillna("")
    df = df.drop_duplicates(subset=["asunto", "descripcion"]).reset_index(drop=True)
    _, test = train_test_split(df, test_size=0.2, stratify=df.urgencia, random_state=SEMILLA)
    conjuntos["sintetico_prueba"] = test.reset_index(drop=True)
    for nombre in ("gold_manual", "gold_holdout"):
        ruta = RAIZ / "data" / f"{nombre}.csv"
        if ruta.exists():
            conjuntos[nombre] = pd.read_csv(ruta).fillna("")
    return conjuntos


def metricas(y_true, y_pred) -> Dict[str, float]:
    return {
        "n": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=NIVELES, average="macro", zero_division=0)), 4),
        "criticos_subestimados": round(float(subestima_critica(y_true, y_pred)), 4),
    }


def evaluar_conjunto(df: pd.DataFrame, agente: AgenteTriaje, modelos: Dict[str, object]) -> Dict:
    """Evalúa todas las estrategias sobre un conjunto; devuelve métricas y predicciones."""
    preds: Dict[str, List[str]] = {e: [] for e in ESTRATEGIAS}
    factores_pred: Dict[str, Dict[str, List]] = {fuente: {f: [] for f in FACTORES} for fuente in FUENTES}
    formulario_pred: List[str] = []

    for nombre, modelo in modelos.items():
        preds[nombre] = [str(p) for p in modelo.predict(texto_urgencia(df))]

    for i, fila in df.iterrows():
        ticket = {
            "id": f"EVAL_{i}",
            "formulario_elegido": fila["formulario_elegido"],
            "apoyo": fila["apoyo"],
            "asunto": fila["asunto"],
            "descripcion": fila["descripcion"],
        }
        # Cada ticket se evalúa por separado: sin duplicados ni brotes de tickets anteriores.
        agente.clustering.buffer_tickets.clear()
        percepcion = agente.percibir(ticket)
        decision = agente.actuar(ticket, percepcion, agente.razonar(ticket, percepcion))

        preds["agente"].append(decision.urgencia_final)
        formulario_pred.append(decision.formulario_final)
        fuentes = {
            "frases": percepcion["factores_frases"],
            "modelo": percepcion["factores_modelo"],
            "agente": {f: percepcion[f] for f in FACTORES},
        }
        preds["reglas_solas"].append(urgencia(Factores(*(fuentes["frases"][f] for f in FACTORES))))
        if fuentes["modelo"]:
            preds["modelo_factores"].append(urgencia(Factores(*(fuentes["modelo"][f] for f in FACTORES))))
        for fuente, valores in fuentes.items():
            if valores:
                for f in FACTORES:
                    factores_pred[fuente][f].append(valores[f])

    y = df["urgencia"].tolist()
    resultado = {
        "urgencia": {e: metricas(y, preds[e]) for e in ESTRATEGIAS if preds[e]},
        "formulario_agente": round(float(accuracy_score(df["formulario_correcto"], formulario_pred)), 4),
    }
    if all(f in df.columns for f in FACTORES):
        resultado["factores_percepcion"] = {}
        for fuente in FUENTES:
            if not factores_pred[fuente]["tipo"]:
                continue
            resultado["factores_percepcion"][fuente] = {}
            for f in FACTORES:
                real = [_a_bool(v) for v in df[f]] if f in ("bloquea", "alternativa") else df[f].tolist()
                acc = accuracy_score(real, factores_pred[fuente][f])
                resultado["factores_percepcion"][fuente][f] = round(float(acc), 4)
    resultado["_predicciones"] = preds
    return resultado


def imprimir(resultados: Dict) -> None:
    for conjunto, r in resultados.items():
        n = next(iter(r["urgencia"].values()))["n"]
        print(f"\n=== {conjunto} (n={n}) ===")
        print(f"{'estrategia':16s} {'exactitud':>9s} {'macro-F1':>9s} {'críticos subest.':>17s}")
        for estrategia, m in r["urgencia"].items():
            print(f"{estrategia:16s} {m['accuracy']:9.3f} {m['macro_f1']:9.3f} {m['criticos_subestimados']:17.1%}")
        print(f"Formulario correcto (agente): {r['formulario_agente']:.3f}")
        if "factores_percepcion" in r:
            print("Exactitud por factor:")
            for fuente, valores in r["factores_percepcion"].items():
                texto = "  ".join(f"{f}={v:.2f}" for f, v in valores.items())
                print(f"  {fuente:8s} {texto}")


def main():
    modelos = {}
    for nombre, archivo in (("modelo_clasico", "urgencia.joblib"), ("modelo_mlp", "urgencia_deep.joblib")):
        ruta = RAIZ / "models" / archivo
        if ruta.exists():
            modelos[nombre] = joblib.load(ruta)

    agente = AgenteTriaje(usar_deep_learning=True)
    resultados = {}
    with tempfile.TemporaryDirectory() as temporal:
        # La memoria de correcciones locales no debe influir en la evaluación.
        agente.memoria = MemoriaAgente(Path(temporal) / "feedback.jsonl")
        for nombre, df in cargar_conjuntos().items():
            print(f"Evaluando {nombre} ({len(df)} tickets)...")
            resultados[nombre] = evaluar_conjunto(df, agente, modelos)

    for r in resultados.values():
        r.pop("_predicciones")
    imprimir(resultados)
    (RAIZ / "reports").mkdir(exist_ok=True)
    salida = RAIZ / "reports" / "evaluacion.json"
    salida.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultados guardados en {salida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
