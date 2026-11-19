"""Percepción neuronal de factores: un clasificador por factor de la rúbrica.

En vez de predecir la urgencia directamente, se predicen los cinco factores que la
definen (tipo, alcance, bloquea, plazo, alternativa) y la rúbrica / el motor FOL deciden
la urgencia a partir de ellos. Así la parte estadística generaliza el lenguaje libre y la
parte simbólica conserva una decisión explicable.

Se entrena con las etiquetas de factores de data/tickets_sinteticos.csv, usando la misma
partición de entrenamiento que train.py y deep_model.py.

Uso: python main.py factores
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from triage.train import SEMILLA, nuevo_modelo, texto_urgencia  # noqa: E402

FACTORES = ("tipo", "alcance", "bloquea", "plazo", "alternativa")
BOOLEANOS = ("bloquea", "alternativa")
RUTA_MODELOS = RAIZ / "models" / "factores.joblib"


def etiquetas_factor(serie: pd.Series, factor: str) -> pd.Series:
    """Normaliza las etiquetas: los factores booleanos se entrenan como 'si' / 'no'."""
    if factor in BOOLEANOS:
        return serie.map(lambda v: "si" if str(v).strip().lower() in ("1", "true", "si", "sí") else "no")
    return serie.astype(str)


class PercepcionFactores:
    """Conjunto de clasificadores, uno por factor."""

    def __init__(self, modelos: Dict[str, Any]):
        self.modelos = modelos

    @classmethod
    def entrenar(cls, df: pd.DataFrame) -> "PercepcionFactores":
        textos = texto_urgencia(df)
        return cls({f: nuevo_modelo().fit(textos, etiquetas_factor(df[f], f)) for f in FACTORES})

    def predecir(self, texto: str) -> Dict[str, Any]:
        """Devuelve cada factor con su confianza: {'bloquea': (True, 0.91), ...}."""
        resultado = {}
        for factor, modelo in self.modelos.items():
            probs = modelo.predict_proba([texto])[0]
            clase = str(modelo.classes_[probs.argmax()])
            valor = (clase == "si") if factor in BOOLEANOS else clase
            resultado[factor] = (valor, float(probs.max()))
        return resultado

    def guardar(self, ruta: Path = RUTA_MODELOS):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.modelos, ruta)

    @classmethod
    def cargar(cls, ruta: Path = RUTA_MODELOS) -> "PercepcionFactores":
        return cls(joblib.load(ruta))


def main():
    df = pd.read_csv(RAIZ / "data" / "tickets_sinteticos.csv").fillna("")
    df = df.drop_duplicates(subset=["asunto", "descripcion"]).reset_index(drop=True)
    train, test = train_test_split(df, test_size=0.2, stratify=df.urgencia, random_state=SEMILLA)

    print("Entrenando un clasificador por factor (TF-IDF + Regresión Logística)...")
    percepcion = PercepcionFactores.entrenar(train)

    textos_test = texto_urgencia(test)
    resultados = {}
    for factor, modelo in percepcion.modelos.items():
        acc = accuracy_score(etiquetas_factor(test[factor], factor), modelo.predict(textos_test))
        resultados[factor] = round(float(acc), 4)
        print(f"  {factor:12s} exactitud en prueba sintética = {acc:.3f}")

    percepcion.guardar()
    (RAIZ / "reports").mkdir(exist_ok=True)
    (RAIZ / "reports" / "metrics_factores.json").write_text(
        json.dumps({"sintetico_prueba": resultados}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Modelos guardados en {RUTA_MODELOS.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
