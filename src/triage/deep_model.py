"""Variante de Deep Learning: Red Neuronal Multicapa (MLP - Multi-Layer Perceptron).

Implementa la arquitectura de Deep Learning con capas densas ocultas:
- Entrada con representaciones vectoriales densificadas (n-gramas de palabras y caracteres).
- Capas ocultas con activaciones ReLU y optimizador Adam con regularización L2 y parada temprana.
- Salida Softmax para clasificación multiclase de Urgencia y Formulario.

Permite comparar experimentalmente el modelo clásico (Regresión Logística) contra Deep Learning,
tal como lo exige la propuesta y la rúbrica del curso.
"""

from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import FeatureUnion, Pipeline

import sys
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from triage.rubric import NIVELES
from triage.train import subestima_critica, texto_formulario, texto_urgencia
SEMILLA = 42


def construir_red_neuronal(capas: tuple = (128, 64), max_iter: int = 400) -> Pipeline:
    """Construye un pipeline con extracción de características y Red Neuronal Profunda (MLP)."""
    vec = FeatureUnion([
        ("palabras", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, strip_accents="unicode")),
        ("caracteres", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True, strip_accents="unicode")),
    ])

    mlp = MLPClassifier(
        hidden_layer_sizes=capas,
        activation="relu",
        solver="adam",
        alpha=0.001,          # Regularización L2
        batch_size=64,
        learning_rate="adaptive",
        learning_rate_init=0.001,
        max_iter=max_iter,
        early_stopping=True,  # Prevenir sobreajuste
        n_iter_no_change=15,
        random_state=SEMILLA,
    )
    return Pipeline([("vec", vec), ("mlp", mlp)])


def evaluar_modelo(y_true, y_pred, etiquetas):
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


def main():
    print("=== Entrenando variante Deep Learning (Red Neuronal MLP) ===")
    df = pd.read_csv(RAIZ / "data" / "tickets_sinteticos.csv").fillna("")
    df = df.drop_duplicates(subset=["asunto", "descripcion"]).reset_index(drop=True)

    train, test = train_test_split(df, test_size=0.2, stratify=df.urgencia, random_state=SEMILLA)

    # Entrenar Redes Neuronales
    print("Entrenando Red Neuronal de Urgencia (Capas: 128 -> 64)...")
    m_urg_deep = construir_red_neuronal((128, 64)).fit(texto_urgencia(train), train.urgencia)

    print("Entrenando Red Neuronal de Formulario (Capas: 128 -> 64)...")
    m_form_deep = construir_red_neuronal((128, 64)).fit(texto_formulario(train), train.formulario_correcto)

    resultados = {}

    # Evaluación en test sintético
    pred_u_test = m_urg_deep.predict(texto_urgencia(test))
    pred_f_test = m_form_deep.predict(texto_formulario(test))

    resultados["sintetico_prueba"] = {
        "urgencia": evaluar_modelo(test.urgencia, pred_u_test, NIVELES)
        | {"subestima_critica": subestima_critica(test.urgencia, pred_u_test)},
        "formulario_correcto": evaluar_modelo(test.formulario_correcto, pred_f_test, sorted(df.formulario_correcto.unique())),
    }

    # Evaluación en Gold Manual
    gold_ruta = RAIZ / "data" / "gold_manual.csv"
    if gold_ruta.exists():
        gold = pd.read_csv(gold_ruta).fillna("")
        pred_u_gold = m_urg_deep.predict(texto_urgencia(gold))
        pred_f_gold = m_form_deep.predict(texto_formulario(gold))

        resultados["gold_manual"] = {
            "urgencia": evaluar_modelo(gold.urgencia, pred_u_gold, NIVELES)
            | {"subestima_critica": subestima_critica(gold.urgencia, pred_u_gold)},
            "formulario_correcto": evaluar_modelo(gold.formulario_correcto, pred_f_gold, sorted(df.formulario_correcto.unique())),
        }

    print("\n--- Resultados Deep Learning en Test Sintético ---")
    r_s = resultados["sintetico_prueba"]["urgencia"]
    print(f"Urgencia: Accuracy={r_s['accuracy']} | Macro-F1={r_s['macro_f1']} | Críticos subestimados={r_s['subestima_critica']}")

    if "gold_manual" in resultados:
        print("\n--- Resultados Deep Learning en Gold Manual (Generalización) ---")
        r_g = resultados["gold_manual"]["urgencia"]
        print(f"Urgencia: Accuracy={r_g['accuracy']} | Macro-F1={r_g['macro_f1']} | Críticos subestimados={r_g['subestima_critica']}")

    # Guardar modelos y reporte
    joblib.dump(m_urg_deep, RAIZ / "models" / "urgencia_deep.joblib")
    joblib.dump(m_form_deep, RAIZ / "models" / "formulario_deep.joblib")

    ruta_reporte = RAIZ / "reports" / "metrics_deep.json"
    ruta_reporte.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nModelos guardados en models/ y métricas en {ruta_reporte}")


if __name__ == "__main__":
    main()
