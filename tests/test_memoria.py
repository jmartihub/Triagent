import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from triage.agent import AgenteTriaje, MemoriaAgente


def test_usa_la_correccion_mas_reciente_por_ticket():
    with tempfile.TemporaryDirectory() as tmp:
        memoria = MemoriaAgente(Path(tmp) / "feedback.jsonl")
        for urgencia in ("Alta", "Media", "Baja"):
            memoria.registrar_feedback_humano(
                "4", urgencia, "Procesos de Pago",
                asunto="Pago erroneo", descripcion="Realicé un pago equivocado",
            )
        caso = memoria.buscar_caso_similar("Pago erroneo Realicé un pago equivocado")
        assert caso is not None
        assert caso["urgencia_corregida"] == "Baja", caso
    print("[OK] Memoria: se usa la corrección más reciente de cada ticket")


def test_caso_similar_no_rebaja_una_urgencia_critica():
    with tempfile.TemporaryDirectory() as tmp:
        agente = AgenteTriaje(usar_deep_learning=True)
        agente.memoria = MemoriaAgente(Path(tmp) / "feedback.jsonl")
        ticket = {
            "id": "900",
            "formulario_elegido": "Fallas Técnicas TIC",
            "apoyo": "Teams",
            "asunto": "Teams caído en mi clase",
            "descripcion": (
                "Estamos en medio de un parcial por Teams y a todo el salón nos sale error "
                "al unirnos, no tenemos otra forma de entrar."
            ),
        }
        antes = agente.procesar_ticket(dict(ticket))
        assert antes.urgencia_final == "Crítica", antes.urgencia_final

        agente.memoria.registrar_feedback_humano(
            "1", "Baja", "Fallas Técnicas TIC",
            asunto=ticket["asunto"], descripcion=ticket["descripcion"],
        )
        agente.clustering.buffer_tickets.clear()
        despues = agente.procesar_ticket(dict(ticket, id="901"))
        assert despues.urgencia_final == "Crítica", despues.urgencia_final
        assert despues.requiere_revision_humana
        assert not despues.aprendizaje_humano_aplicado
    print("[OK] Memoria: un caso similar no rebaja automáticamente una urgencia Crítica")


if __name__ == "__main__":
    test_usa_la_correccion_mas_reciente_por_ticket()
    test_caso_similar_no_rebaja_una_urgencia_critica()
    print("\nTodos los tests de memoria pasaron exitosamente.")
