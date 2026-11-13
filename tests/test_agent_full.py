import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from triage.agent import AgenteTriaje
from triage.glpi_client import ClienteGLPI


def test_ciclo_completo_agente():
    agente = AgenteTriaje(usar_deep_learning=True)

    # 1. Caso de examen en una hora
    ticket = {
        "id": "TEST_001",
        "formulario_elegido": "Fallas Técnicas TIC",
        "apoyo": "Banner",
        "asunto": "No puedo entrar a Banner",
        "descripcion": "No me deja entrar a la plataforma y tengo examen en una hora. No tengo otra forma de presentarlo.",
        "tiene_adjunto": 0,
        "fecha_apertura": "2026-11-13 14:00",
    }
    decision = agente.procesar_ticket(ticket)

    assert decision.urgencia_final == "Crítica"
    assert "Sistemas Académicos" in decision.grupo_asignado
    assert "Carolina Gómez" in decision.tecnico_asignado
    assert decision.tiempo_sla_horas == 2.0
    assert len(decision.respuesta_preliminar) > 50
    assert decision.seguridad_ml_activada is True  # Rescatado por la red de seguridad FOL
    print("✓ Ciclo completo del agente: Inferencia, enrutamiento y respuesta preliminar correctos")


def test_deteccion_formulario_erroneo():
    agente = AgenteTriaje(usar_deep_learning=True)

    ticket = {
        "id": "TEST_002",
        "formulario_elegido": "Fallas Técnicas TIC",
        "apoyo": "Pagos en línea",
        "asunto": "Error en mi liquidación",
        "descripcion": "Mi liquidación no incluye el descuento que me corresponde para pagar el semestre en el banco.",
        "tiene_adjunto": 0,
        "fecha_apertura": "2026-11-13 14:05",
    }
    decision = agente.procesar_ticket(ticket)
    assert decision.hubo_cambio_formulario is True
    assert decision.formulario_final == "Procesos de Pago"
    assert "Gestión Financiera" in decision.grupo_asignado
    assert "Ajuste de Categoría" in decision.respuesta_preliminar
    print("✓ Detección y corrección de formulario erróneo correcta")


def test_integracion_glpi_mock():
    cliente = ClienteGLPI(modo_mock=True)
    assert cliente.conectar() is True

    # Actualizar ticket
    ok_upd = cliente.actualizar_ticket(
        id_ticket=101,
        urgencia_nombre="Crítica",
        tecnico_nombre="Carolina Gómez",
        formulario_nombre="Fallas Técnicas TIC",
    )
    assert ok_upd is True
    assert cliente.tickets_mock[101]["urgencia"] == 5

    # Registrar respuesta preliminar
    ok_resp = cliente.registrar_respuesta_preliminar(101, "Hola, hemos recibido tu ticket.")
    assert ok_resp is True
    assert len(cliente.seguimientos_mock[101]) == 1
    print("✓ Integración y actualización verificable en GLPI correcta")


if __name__ == "__main__":
    test_ciclo_completo_agente()
    test_deteccion_formulario_erroneo()
    test_integracion_glpi_mock()
    print("\nTodos los tests del agente pasaron exitosamente.")
