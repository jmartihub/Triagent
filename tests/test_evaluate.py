import sys
import tempfile
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from triage.agent import AgenteTriaje, MemoriaAgente
from triage.evaluate import ESTRATEGIAS, FACTORES, _a_bool, evaluar_conjunto
from triage.rubric import NIVELES, Factores, urgencia


def test_gold_holdout_es_consistente_con_la_rubrica():
    gold = pd.read_csv(RAIZ / "data" / "gold_holdout.csv")
    assert set(gold.urgencia) == set(NIVELES)
    for _, fila in gold.iterrows():
        esperado = urgencia(Factores(
            fila.tipo, fila.alcance, _a_bool(fila.bloquea), fila.plazo, _a_bool(fila.alternativa)
        ))
        assert fila.urgencia == esperado, (fila.asunto, fila.urgencia, esperado)
    print("[OK] gold_holdout: cada urgencia coincide con la rúbrica aplicada a sus factores")


def test_evaluar_conjunto_reporta_todas_las_estrategias_y_factores():
    gold = pd.read_csv(RAIZ / "data" / "gold_holdout.csv").fillna("").head(8)
    agente = AgenteTriaje(usar_deep_learning=True)
    with tempfile.TemporaryDirectory() as tmp:
        agente.memoria = MemoriaAgente(Path(tmp) / "feedback.jsonl")
        resultado = evaluar_conjunto(gold, agente, modelos={})

    assert set(resultado["urgencia"]) == {"reglas_solas", "modelo_factores", "agente"}
    for fuente in ("frases", "modelo", "agente"):
        assert set(resultado["factores_percepcion"][fuente]) == set(FACTORES)
    for estrategia in ("reglas_solas", "agente"):
        assert resultado["urgencia"][estrategia]["n"] == 8
        assert len(resultado["_predicciones"][estrategia]) == 8
    assert set(ESTRATEGIAS) >= set(resultado["urgencia"])
    print("[OK] evaluar_conjunto: métricas por estrategia y precisión por factor")


if __name__ == "__main__":
    test_gold_holdout_es_consistente_con_la_rubrica()
    test_evaluar_conjunto_reporta_todas_las_estrategias_y_factores()
    print("\nTodos los tests de evaluación pasaron exitosamente.")
