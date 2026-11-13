"""Modelo base: TF-IDF + regresión logística.

Dos modelos:
  1. Urgencia (Baja/Media/Alta/Crítica) a partir de formulario + apoyo + asunto + descripción.
  2. Formulario correcto a partir SOLO del texto (asunto + descripción). Si el formulario
     predicho difiere del elegido y la confianza supera un umbral, el agente marca el
     ticket como posible "mal categorizado".

Se evalúa en (a) un 20% de los datos sintéticos y (b) un conjunto escrito a mano
(data/gold_manual.csv), que no sale de las plantillas y mide mejor la generalización.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

from .rubric import NIVELES

RAIZ = Path(__file__).resolve().parents[2]
UMBRAL_MAL_FORMULARIO = 0.60
SEMILLA = 42


def texto_urgencia(df):
    return df.formulario_elegido + " | " + df.apoyo + " | " + df.asunto + " | " + df.descripcion


def texto_formulario(df):
    return df.asunto + " . " + df.descripcion


def nuevo_modelo():
    vec = FeatureUnion([
        ("palabras", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True,
                                     strip_accents="unicode")),
        ("letras", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3,
                                   sublinear_tf=True, strip_accents="unicode")),
    ])
    clf = LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced")
    return Pipeline([("vec", vec), ("clf", clf)])


def evaluar(y_true, y_pred, etiquetas):
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    rep = classification_report(y_true, y_pred, labels=etiquetas, output_dict=True, zero_division=0)
    return {
        "n": int(len(y_true)),
        "accuracy": round(float(rep["accuracy"]), 4),
        "macro_f1": round(float(rep["macro avg"]["f1-score"]), 4),
        "por_clase": {e: {k: round(float(rep[e][k]), 4) for k in ("precision", "recall", "f1-score")}
                      | {"support": int(rep[e]["support"])} for e in etiquetas},
        "matriz": confusion_matrix(y_true, y_pred, labels=etiquetas).tolist(),
        "etiquetas": etiquetas,
    }


def subestima_critica(y_true, y_pred):
    """Fracción de tickets Críticos que el modelo manda a Baja o Media (el error más caro)."""
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    crit = y_true == "Crítica"
    if crit.sum() == 0:
        return None
    return round(float(np.isin(y_pred[crit], ["Baja", "Media"]).mean()), 4)


def detectar_mal_formulario(modelo_form, df):
    proba = modelo_form.predict_proba(texto_formulario(df))
    clases = modelo_form.classes_
    pred = clases[proba.argmax(axis=1)]
    confianza = proba.max(axis=1)
    marca = (pred != df.formulario_elegido.values) & (confianza >= UMBRAL_MAL_FORMULARIO)
    return pred, marca


def metricas_deteccion(real, marca):
    real, marca = np.asarray(real).astype(bool), np.asarray(marca).astype(bool)
    tp = int((real & marca).sum())
    precision = tp / marca.sum() if marca.sum() else 0.0
    recall = tp / real.sum() if real.sum() else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "marcados": int(marca.sum()), "reales": int(real.sum())}


def evaluar_conjunto(nombre, df, m_urg, m_form, resultados, mostrar_errores=False):
    pred_u = m_urg.predict(texto_urgencia(df))
    pred_f, marca = detectar_mal_formulario(m_form, df)
    mal_real = (df.formulario_elegido != df.formulario_correcto).values
    resultados[nombre] = {
        "urgencia": evaluar(df.urgencia, pred_u, NIVELES)
        | {"subestima_critica": subestima_critica(df.urgencia, pred_u)},
        "formulario_correcto": evaluar(df.formulario_correcto, pred_f, sorted(df.formulario_correcto.unique())),
        "deteccion_mal_formulario": metricas_deteccion(mal_real, marca),
    }
    r = resultados[nombre]
    print(f"\n=== {nombre} (n={len(df)}) ===")
    print(f"Urgencia:   accuracy={r['urgencia']['accuracy']}  macro-F1={r['urgencia']['macro_f1']}  "
          f"Críticos subestimados={r['urgencia']['subestima_critica']}")
    print(f"Formulario: accuracy={r['formulario_correcto']['accuracy']}  "
          f"macro-F1={r['formulario_correcto']['macro_f1']}")
    d = r["deteccion_mal_formulario"]
    print(f"Detección de formulario equivocado: precisión={d['precision']}  recall={d['recall']}  "
          f"({d['marcados']} marcados / {d['reales']} reales)")
    if mostrar_errores:
        print("\nErrores de urgencia:")
        for i in np.where(pred_u != df.urgencia.values)[0]:
            fila = df.iloc[i]
            print(f"  real={fila.urgencia:8s} pred={pred_u[i]:8s} | {fila.asunto} | {fila.descripcion[:110]}")
        print("\nErrores de formulario correcto:")
        for i in np.where(pred_f != df.formulario_correcto.values)[0]:
            fila = df.iloc[i]
            print(f"  real={fila.formulario_correcto} pred={pred_f[i]} | {fila.descripcion[:90]}")


def main():
    df = pd.read_csv(RAIZ / "data" / "tickets_sinteticos.csv").fillna("")
    antes = len(df)
    df = df.drop_duplicates(subset=["asunto", "descripcion"]).reset_index(drop=True)
    print(f"Tickets: {antes} -> {len(df)} tras quitar duplicados exactos de texto")

    train, test = train_test_split(df, test_size=0.2, stratify=df.urgencia, random_state=SEMILLA)

    m_urg = nuevo_modelo().fit(texto_urgencia(train), train.urgencia)
    m_form = nuevo_modelo().fit(texto_formulario(train), train.formulario_correcto)

    resultados = {}

    # Baselines de urgencia sobre el conjunto de prueba.
    todo_media = np.array(["Media"] * len(test))
    mayoria = DummyClassifier(strategy="most_frequent").fit(texto_urgencia(train), train.urgencia)
    resultados["baselines_urgencia"] = {
        "todo_Media (supuesto de GLPI por defecto)": evaluar(test.urgencia, todo_media, NIVELES)["macro_f1"],
        "clase_mayoritaria": evaluar(test.urgencia, mayoria.predict(texto_urgencia(test)), NIVELES)["macro_f1"],
    }
    print("\nBaselines (macro-F1 de urgencia):", resultados["baselines_urgencia"])

    evaluar_conjunto("sintetico_prueba", test, m_urg, m_form, resultados)

    gold_ruta = RAIZ / "data" / "gold_manual.csv"
    if gold_ruta.exists():
        gold = pd.read_csv(gold_ruta).fillna("")
        evaluar_conjunto("gold_manual", gold, m_urg, m_form, resultados, mostrar_errores=True)
        todo_media_g = np.array(["Media"] * len(gold))
        resultados["baselines_urgencia"]["todo_Media en gold"] = evaluar(gold.urgencia, todo_media_g, NIVELES)["macro_f1"]

    (RAIZ / "models").mkdir(exist_ok=True)
    (RAIZ / "reports").mkdir(exist_ok=True)
    joblib.dump(m_urg, RAIZ / "models" / "urgencia.joblib")
    joblib.dump(m_form, RAIZ / "models" / "formulario.joblib")
    (RAIZ / "reports" / "metrics.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nModelos guardados en models/ y métricas en reports/metrics.json")


if __name__ == "__main__":
    main()
