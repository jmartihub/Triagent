from http.server import HTTPServer
import json
import sys
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from triage.glpi_client import ClienteGLPI
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


if __name__ == "__main__":
    test_resumen_tickets_y_cumplimiento_sla()
    test_resumen_sin_tickets_o_datos_de_sla()
    test_endpoint_dashboard_usa_todos_los_tickets()
    print("dashboard ok")
