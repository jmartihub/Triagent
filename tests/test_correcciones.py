from contextlib import contextmanager
from http.server import HTTPServer
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
import urllib.error
import urllib.request

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from triage.agent import AgenteTriaje, MemoriaAgente
from triage.glpi_client import ClienteGLPI
from triage.web_dashboard import DashboardHandler


@contextmanager
def servidor_con(agente, cliente):
    anteriores = DashboardHandler.agente, DashboardHandler.cliente_glpi
    DashboardHandler.agente, DashboardHandler.cliente_glpi = agente, cliente
    servidor = HTTPServer(("127.0.0.1", 0), DashboardHandler)
    hilo = Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_port}"
    finally:
        servidor.shutdown()
        hilo.join()
        servidor.server_close()
        DashboardHandler.agente, DashboardHandler.cliente_glpi = anteriores


def pedir(url, datos=None):
    solicitud = urllib.request.Request(
        url,
        data=json.dumps(datos).encode() if datos is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if datos is not None else "GET",
    )
    try:
        with urllib.request.urlopen(solicitud) as respuesta:
            return respuesta.status, json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8") or "{}")


def test_memoria_anula_la_correccion_vigente():
    with tempfile.TemporaryDirectory() as tmp:
        memoria = MemoriaAgente(Path(tmp) / "feedback.jsonl")
        memoria.registrar_feedback_humano("7", "Alta", None, asunto="Wifi", descripcion="no conecta",
                                          urgencia_anterior="Media")
        assert "7" in memoria.correcciones_vigentes()
        anulada = memoria.anular_correccion("7")
        assert anulada["urgencia_anterior"] == "Media"
        assert memoria.correcciones_vigentes() == {}
        assert memoria.buscar_caso_similar("Wifi no conecta") is None
        assert memoria.anular_correccion("7") is None
    print("[OK] Memoria: una corrección anulada deja de usarse para aprender")


def test_decisiones_persisten_entre_reinicios():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "decisiones.jsonl"
        agente = AgenteTriaje(usar_deep_learning=True)
        agente.memoria = MemoriaAgente(Path(tmp) / "feedback.jsonl", ruta_decisiones=ruta)
        agente.procesar_ticket({"id": "12", "asunto": "Banner", "descripcion": "no abre", "apoyo": "Banner"})
        recargada = MemoriaAgente(Path(tmp) / "feedback.jsonl", ruta_decisiones=ruta)
        decision = recargada.historial_decisiones["12"]["decision"]
        assert set(decision["factores"]) == {"tipo", "alcance", "bloquea", "plazo", "alternativa"}
    print("[OK] Memoria: las decisiones del agente sobreviven a un reinicio del panel")


def test_corregir_listar_y_deshacer_desde_el_panel():
    with tempfile.TemporaryDirectory() as tmp:
        agente = AgenteTriaje(usar_deep_learning=True)
        agente.memoria = MemoriaAgente(Path(tmp) / "feedback.jsonl")
        cliente = ClienteGLPI(modo_mock=True)
        cliente.conectar()
        id_glpi = cliente.crear_ticket("Teams no abre", "No puedo entrar a la clase")
        cliente.actualizar_urgencia(id_glpi, "Media")
        agente.procesar_ticket({"id": str(id_glpi), "asunto": "Teams no abre",
                                "descripcion": "No puedo entrar a la clase", "apoyo": "Teams"})

        with servidor_con(agente, cliente) as base:
            estado, datos = pedir(f"{base}/api/dashboard")
            assert estado == 200 and str(id_glpi) in datos["decisiones"]
            assert "justificacion_fol" in datos["decisiones"][str(id_glpi)]

            estado, datos = pedir(f"{base}/api/feedback", {"id_ticket": id_glpi, "urgencia_corregida": "Crítica"})
            assert estado == 200 and datos["ok"], datos
            assert cliente.obtener_ticket(id_glpi)["urgency"] == 5

            estado, datos = pedir(f"{base}/api/correcciones")
            ultima = datos["correcciones"][0]
            assert ultima["urgencia_anterior"] == "Media" and ultima["vigente"] and not ultima["anulada"]

            estado, datos = pedir(f"{base}/api/feedback/deshacer", {"id_ticket": id_glpi})
            assert estado == 200 and datos["urgencia_restaurada"] == "Media", datos
            assert cliente.obtener_ticket(id_glpi)["urgency"] == 3

            estado, datos = pedir(f"{base}/api/correcciones")
            assert datos["correcciones"][0]["anulada"] and not datos["correcciones"][0]["vigente"]

            estado, datos = pedir(f"{base}/api/feedback/deshacer", {"id_ticket": id_glpi})
            assert estado == 404 and not datos["ok"]
    print("[OK] Panel: corregir, ver el historial y deshacer restaura la urgencia en GLPI")


if __name__ == "__main__":
    test_memoria_anula_la_correccion_vigente()
    test_decisiones_persisten_entre_reinicios()
    test_corregir_listar_y_deshacer_desde_el_panel()
    print("\nTodos los tests de correcciones pasaron exitosamente.")
