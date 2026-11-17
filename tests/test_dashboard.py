from http.server import HTTPServer
import json
import sys
from pathlib import Path
from threading import Thread
import urllib.error
import urllib.request
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from triage.glpi_client import ClienteGLPI, GLPIError
from triage.web_dashboard import DashboardHandler, resumir_tickets


def test_resumen_tickets_y_cumplimiento_sla():
    tickets = [
        {"id": 1, "status": 1, "urgency": 5},
        {"id": 2, "status": 2, "urgency": 4},
        {"id": 3, "status": 4, "urgency": 3},
        {
            "id": 4,
            "status": 5,
            "urgency": 2,
            "time_to_resolve": "2026-11-15 12:00:00",
            "solvedate": "2026-11-15 11:00:00",
        },
        {
            "id": 5,
            "status": 6,
            "urgency": 1,
            "time_to_resolve": "2026-11-15T12:00:00Z",
            "solvedate": "2026-11-15T12:01:00+00:00",
        },
        {"id": 6, "status": 5, "urgency": 3},
    ]

    resumen = resumir_tickets(tickets)

    assert resumen == {
        "total": 6,
        "activos": 3,
        "resueltos": 3,
        "urgencias": {"Crítica": 1, "Alta": 1, "Media": 2, "Baja": 2},
        "sin_urgencia": 0,
        "sla": {"cumplimiento_pct": 50.0, "evaluados": 2},
    }


def test_resumen_sin_tickets_o_datos_de_sla():
    assert resumir_tickets([]) == {
        "total": 0,
        "activos": 0,
        "resueltos": 0,
        "urgencias": {"Crítica": 0, "Alta": 0, "Media": 0, "Baja": 0},
        "sin_urgencia": 0,
        "sla": {"cumplimiento_pct": None, "evaluados": 0},
    }
    resumen = resumir_tickets([{"status": 5, "urgency": 0}])
    assert resumen["sla"] == {"cumplimiento_pct": None, "evaluados": 0}
    assert resumen["sin_urgencia"] == 1


def test_endpoint_dashboard_usa_todos_los_tickets():
    cliente = ClienteGLPI(modo_mock=True)
    cliente.conectar()
    cliente.crear_ticket("Nuevo", "Descripción")
    cliente.crear_ticket("En curso", "Descripción")
    cliente.tickets_mock[2]["status"] = 2
    DashboardHandler.cliente_glpi = cliente

    servidor = HTTPServer(("127.0.0.1", 0), DashboardHandler)
    hilo = Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        with urlopen(f"http://127.0.0.1:{servidor.server_port}/api/dashboard") as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        assert datos["metricas"]["total"] == 2
        assert datos["metricas"]["activos"] == 2
        assert len(datos["tickets"]) == 2
        assert datos["glpi_mock"] is True
    finally:
        servidor.shutdown()
        hilo.join()
        servidor.server_close()


def test_fallo_al_crear_ticket_devuelve_error_sin_identificador_simulado():
    class ClienteFallido:
        modo_mock = False

        def crear_ticket(self, _asunto, _descripcion):
            raise GLPIError("ERROR_NOT_ALLOWED_IP")

    cliente_anterior = DashboardHandler.cliente_glpi
    agente_anterior = DashboardHandler.agente
    DashboardHandler.cliente_glpi = ClienteFallido()
    DashboardHandler.agente = None
    servidor = HTTPServer(("127.0.0.1", 0), DashboardHandler)
    hilo = Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        solicitud = urllib.request.Request(
            f"http://127.0.0.1:{servidor.server_port}/api/triajar",
            data=json.dumps({"asunto": "Prueba", "descripcion": "Falla"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(solicitud)
        except urllib.error.HTTPError as error:
            datos = json.loads(error.read().decode())
            assert error.code == 502
            assert datos["mensaje"] == "ERROR_NOT_ALLOWED_IP"
            assert "id_ticket" not in datos
        else:
            raise AssertionError("Expected the GLPI failure to be returned")
    finally:
        servidor.shutdown()
        hilo.join()
        servidor.server_close()
        DashboardHandler.cliente_glpi = cliente_anterior
        DashboardHandler.agente = agente_anterior


def test_endpoint_feedback_guarda_urgencia_seleccionada():
    class MemoriaFalsa:
        historial_decisiones = {
            "45": {"ticket": {"asunto": "Acceso al portal", "descripcion": "No puedo ingresar"}}
        }

        def __init__(self):
            self.registro = None
            self.fallar_al_guardar = False

        def registrar_feedback_humano(self, **datos):
            if self.fallar_al_guardar:
                raise OSError("archivo de memoria no disponible")
            self.registro = datos

    class AgenteFalso:
        def __init__(self):
            self.memoria = MemoriaFalsa()

    class ClienteGLPIFalso:
        def __init__(self):
            self.urgencias = []
            self.fallar_al_actualizar = False

        def actualizar_urgencia(self, id_ticket, urgencia):
            if self.fallar_al_actualizar:
                raise GLPIError("Permiso de actualización denegado")
            self.urgencias.append((id_ticket, urgencia))
            return True

    agente_anterior = DashboardHandler.agente
    cliente_anterior = DashboardHandler.cliente_glpi
    agente = AgenteFalso()
    cliente = ClienteGLPIFalso()
    DashboardHandler.agente = agente
    DashboardHandler.cliente_glpi = cliente
    servidor = HTTPServer(("127.0.0.1", 0), DashboardHandler)
    hilo = Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        solicitud = urllib.request.Request(
            f"http://127.0.0.1:{servidor.server_port}/api/feedback",
            data=json.dumps({"id_ticket": 45, "urgencia_corregida": "Alta"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(solicitud) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        assert datos["ok"] is True
        assert datos["glpi_actualizado"] is True
        assert agente.memoria.registro["urgencia_humana"] == "Alta"
        assert agente.memoria.registro["asunto"] == "Acceso al portal"
        assert cliente.urgencias == [(45, "Alta")]

        cliente.fallar_al_actualizar = True
        solicitud = urllib.request.Request(
            f"http://127.0.0.1:{servidor.server_port}/api/feedback",
            data=json.dumps({"id_ticket": 45, "urgencia_corregida": "Baja"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(solicitud)
        except urllib.error.HTTPError as error:
            datos = json.loads(error.read().decode("utf-8"))
            assert error.code == 502
            assert "Permiso de actualización denegado" in datos["mensaje"]
            assert agente.memoria.registro["urgencia_humana"] == "Alta"
        else:
            raise AssertionError("Expected the GLPI update error to be reported")

        cliente.fallar_al_actualizar = False
        agente.memoria.fallar_al_guardar = True
        solicitud = urllib.request.Request(
            f"http://127.0.0.1:{servidor.server_port}/api/feedback",
            data=json.dumps({"id_ticket": 45, "urgencia_corregida": "Baja"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(solicitud)
        except urllib.error.HTTPError as error:
            datos = json.loads(error.read().decode("utf-8"))
            assert error.code == 500
            assert datos["glpi_actualizado"] is True
            assert "archivo de memoria no disponible" in datos["mensaje"]
        else:
            raise AssertionError("Expected the feedback persistence error to be reported")
    finally:
        servidor.shutdown()
        hilo.join()
        servidor.server_close()
        DashboardHandler.agente = agente_anterior
        DashboardHandler.cliente_glpi = cliente_anterior


if __name__ == "__main__":
    test_resumen_tickets_y_cumplimiento_sla()
    test_resumen_sin_tickets_o_datos_de_sla()
    test_endpoint_dashboard_usa_todos_los_tickets()
    test_fallo_al_crear_ticket_devuelve_error_sin_identificador_simulado()
    test_endpoint_feedback_guarda_urgencia_seleccionada()
    print("dashboard ok")
