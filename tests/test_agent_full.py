import sys
from pathlib import Path
from tempfile import TemporaryDirectory

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
    print("[OK] Ciclo completo del agente: Inferencia, enrutamiento y respuesta preliminar correctos")


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
    assert "Ajuste de Categoria" in decision.respuesta_preliminar
    print("[OK] Detección y corrección de formulario erróneo correcta")


def test_navegador_bloqueado_durante_examen_es_critico():
    ticket = {
        "id": "TEST_EXAMEN_NAVEGADOR",
        "formulario_elegido": "Fallas Técnicas TIC",
        "apoyo": "Otra",
        "asunto": "No puedo salir",
        "descripcion": (
            "Estoy en medio de un examen, abrí un sitio sospechoso y quedé atrapado en páginas "
            "que no solicité. No puedo cerrar el navegador ni volver al examen."
        ),
        "fecha_apertura": "2026-11-18 10:00",
    }

    with TemporaryDirectory() as temporal:
        for usar_deep_learning in (False, True):
            agente = AgenteTriaje(usar_deep_learning=usar_deep_learning)
            agente.memoria.ruta_log = Path(temporal) / f"feedback-{usar_deep_learning}.jsonl"
            decision = agente.procesar_ticket(ticket)
            assert decision.urgencia_final == "Crítica"
            assert decision.tiempo_sla_horas == 2.0
            assert decision.requiere_revision_humana is True
            assert "Soporte de Salas de Cómputo y Hardware" in decision.grupo_asignado
            assert any("[EVALUACIÓN EN CURSO]" in linea for linea in decision.justificacion_fol)
            assert "Avisa ahora al docente o supervisor" in decision.respuesta_preliminar
            assert "no esperes esa respuesta" in decision.respuesta_preliminar
            assert "Restablecimiento institucional" not in decision.respuesta_preliminar


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
    assert cliente.tickets_mock[101]["urgency"] == 5

    # Registrar respuesta preliminar
    ok_resp = cliente.registrar_respuesta_preliminar(101, "Hola, hemos recibido tu ticket.")
    assert ok_resp is True
    assert len(cliente.seguimientos_mock[101]) == 1
    print("[OK] Integración y actualización verificable en GLPI correcta")


if __name__ == "__main__":
    test_ciclo_completo_agente()
    test_deteccion_formulario_erroneo()
    test_navegador_bloqueado_durante_examen_es_critico()
    test_integracion_glpi_mock()
    print("\nTodos los tests del agente pasaron exitosamente.")
