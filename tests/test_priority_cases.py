import csv
from datetime import datetime, timedelta
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from triage.agent import AgenteTriaje


def test_prioridades_gold_manual():
    with (RAIZ / "data" / "gold_manual.csv").open(encoding="utf-8", newline="") as archivo:
        tickets_gold = list(csv.DictReader(archivo))

    agente = AgenteTriaje(usar_deep_learning=True)
    with TemporaryDirectory() as temporal:
        agente.memoria.ruta_log = Path(temporal) / "feedback.jsonl"
        correctos = 0
        fecha_inicial = datetime(2026, 11, 1)

        for indice, ticket in enumerate(tickets_gold):
            decision = agente.procesar_ticket({
                "id": f"GOLD_{indice + 1:03d}",
                "formulario_elegido": ticket["formulario_elegido"],
                "apoyo": ticket["apoyo"],
                "asunto": ticket["asunto"],
                "descripcion": ticket["descripcion"],
                "fecha_apertura": (fecha_inicial + timedelta(hours=4 * indice)).strftime("%Y-%m-%d %H:%M"),
            })
            correctos += decision.urgencia_final == ticket["urgencia"]

    assert correctos >= 20, f"El agente acertó {correctos}/{len(tickets_gold)} prioridades"


if __name__ == "__main__":
    test_prioridades_gold_manual()
    print("prioridades gold manual ok")
