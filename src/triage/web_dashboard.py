"""Panel Web del Agente de Triaje y Priorizacion (Tooli / GLPI).

Servidor HTTP en Python para la interfaz institucional de gestion y control:
- Simulador de Solicitud de Tooli (estudiante envia ticket).
- Visualizacion en tiempo real del ciclo del Agente:
  * Percepcion probabilistica ML/DL
  * Deduccion formal FOL y red de seguridad
  * Asignacion Ontologica de tecnicos y calculo de SLA por regresion
  * Deteccion no supervisada de brotes/duplicados por DBSCAN
  * Aprendizaje activo por casos (CBR) desde correcciones humanas
- Monitor de la cola de GLPI con sincronizacion bidireccional.
- Panel de Retroalimentacion Humana (Human-in-the-loop).
"""

from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sys
from typing import Optional
import urllib.parse

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from triage.agent import AgenteTriaje, MemoriaAgente
from triage.glpi_client import ClienteGLPI, GLPIError


SIN_CLIENTE_GLPI = "No hay un cliente de GLPI configurado."

URGENCIAS_GLPI = {
    1: "Baja",
    2: "Baja",
    3: "Media",
    4: "Alta",
    5: "Crítica",
}
ESTADOS_GLPI = {
    1: "Nuevo",
    2: "En curso / Asignado",
    3: "Planificado",
    4: "En espera",
    5: "Resuelto",
    6: "Cerrado",
}


def _urgencia_ticket(ticket):
    urgencia = ticket.get("urgency")
    try:
        return URGENCIAS_GLPI.get(int(urgencia))
    except (TypeError, ValueError):
        if isinstance(urgencia, str):
            urgencia_normalizada = urgencia.strip().casefold()
            return next(
                (nombre for nombre in URGENCIAS_GLPI.values() if nombre.casefold() == urgencia_normalizada),
                None,
            )
        return None


def _estado_ticket(ticket):
    estado = ticket.get("status")
    try:
        return int(estado)
    except (TypeError, ValueError):
        if isinstance(estado, str):
            estado_normalizado = estado.strip().casefold()
            return next(
                (codigo for codigo, nombre in ESTADOS_GLPI.items() if nombre.casefold() == estado_normalizado),
                None,
            )
        return None


def _fecha_glpi(valor):
    if not isinstance(valor, str) or not valor.strip():
        return None
    try:
        fecha = datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
        if fecha.tzinfo:
            fecha = fecha.astimezone(timezone.utc).replace(tzinfo=None)
        return fecha
    except ValueError:
        return None


def resumir_tickets(tickets):
    """Calcula métricas únicamente con los datos que GLPI devuelve."""
    urgencias = {"Crítica": 0, "Alta": 0, "Media": 0, "Baja": 0}
    activos = 0
    resueltos = 0
    sla_evaluados = 0
    sla_cumplidos = 0

    for ticket in tickets:
        estado = _estado_ticket(ticket)
        if estado in (5, 6):
            resueltos += 1
            fecha_limite = _fecha_glpi(ticket.get("time_to_resolve"))
            fecha_resolucion = _fecha_glpi(ticket.get("solvedate"))
            if fecha_limite and fecha_resolucion:
                sla_evaluados += 1
                sla_cumplidos += fecha_resolucion <= fecha_limite
        else:
            activos += 1

        urgencia = _urgencia_ticket(ticket)
        if urgencia:
            urgencias[urgencia] += 1

    return {
        "total": len(tickets),
        "activos": activos,
        "resueltos": resueltos,
        "urgencias": urgencias,
        "sin_urgencia": len(tickets) - sum(urgencias.values()),
        "sla": {
            "cumplimiento_pct": round(sla_cumplidos * 100 / sla_evaluados, 1) if sla_evaluados else None,
            "evaluados": sla_evaluados,
        },
    }


# Interfaz del dashboard (HTML, CSS y JS en un solo archivo, sin dependencias externas).
HTML_INDEX = (Path(__file__).resolve().parent / "static" / "index.html").read_text(encoding="utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
    agente: AgenteTriaje = None
    cliente_glpi: ClienteGLPI = None

    def log_message(self, format, *args):
        pass

    def obtener_tickets_dashboard(self):
        if not self.cliente_glpi:
            return []
        tickets = self.cliente_glpi.obtener_todos_los_tickets(limite=1000)
        if self.agente:
            # La carga real de la cola (tickets no resueltos ni cerrados) alimenta el estimador de SLA.
            self.agente.carga_cola = sum(1 for t in tickets if _estado_ticket(t) not in (5, 6))
        return tickets

    def resumen_decisiones(self, tickets):
        """Lo que decidió el agente para los tickets de la cola que pasaron por él."""
        historial = self.agente.memoria.historial_decisiones if self.agente else {}
        resumen = {}
        for ticket in tickets:
            registro = historial.get(str(ticket.get("id")))
            if not registro:
                continue
            d = registro.get("decision", {})
            resumen[str(ticket.get("id"))] = {
                campo: d.get(campo) for campo in (
                    "urgencia_final", "formulario_final", "hubo_cambio_formulario", "tecnico_asignado",
                    "requiere_revision_humana", "confianza_ml_urgencia", "seguridad_ml_activada",
                    "aprendizaje_humano_aplicado", "es_duplicado", "es_incidente_masivo",
                    "justificacion_fol", "factores",
                )
            }
        return resumen

    def listar_correcciones(self):
        """Historial de correcciones (más recientes primero), marcando vigentes y anuladas."""
        correcciones = self.agente.memoria.leer_correcciones() if self.agente else []
        vigentes = self.agente.memoria.correcciones_vigentes() if self.agente else {}
        anuladas = {c.get("corrección_anulada") for c in correcciones if c.get("anulada")}
        historial = [
            {
                "timestamp": c.get("timestamp"),
                "id_ticket": c.get("id_ticket"),
                "asunto": c.get("asunto", ""),
                "urgencia_anterior": c.get("urgencia_anterior"),
                "urgencia_corregida": c.get("urgencia_corregida"),
                "anulada": c.get("timestamp") in anuladas,
                "vigente": vigentes.get(str(c.get("id_ticket")), {}).get("timestamp") == c.get("timestamp"),
            }
            for c in correcciones if not c.get("anulada")
        ]
        self.enviar_json({"correcciones": list(reversed(historial))[:100]})

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)

        if url.path == "/" or url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_INDEX.encode("utf-8"))
            return

        if url.path == "/api/dashboard":
            try:
                tickets = self.obtener_tickets_dashboard()
            except GLPIError as error:
                self.enviar_json({"error": str(error), "glpi_mock": False}, status=502)
                return
            self.enviar_json({
                "tickets": tickets,
                "metricas": resumir_tickets(tickets),
                "decisiones": self.resumen_decisiones(tickets),
                "glpi_mock": not self.cliente_glpi or self.cliente_glpi.modo_mock,
            })
            return

        if url.path == "/api/correcciones":
            self.listar_correcciones()
            return

        if url.path == "/api/tickets":
            try:
                self.enviar_json(self.obtener_tickets_dashboard())
            except GLPIError as error:
                self.enviar_json({"error": str(error)}, status=502)
            return

        if url.path == "/api/ontologia":
            datos = {
                "tecnicos": self.agente.ontologia.tecnicos if self.agente else [],
                "sla": self.agente.ontologia.sla if self.agente else {},
            }
            self.enviar_json(datos)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            datos = json.loads(post_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error(400, "Invalid JSON")
            return
        if not isinstance(datos, dict):
            self.send_error(400, "JSON object required")
            return

        if url.path == "/api/triajar":
            asunto = datos.get("asunto", "")
            descripcion = datos.get("descripcion", "")
            if not isinstance(asunto, str) or not asunto.strip() or not isinstance(descripcion, str) or not descripcion.strip():
                self.send_error(400, "Asunto y descripción son obligatorios")
                return
            form = datos.get("formulario_elegido", "Fallas Técnicas TIC")
            apoyo = datos.get("apoyo", "Otra")
            if not isinstance(form, str) or not isinstance(apoyo, str):
                self.send_error(400, "Formulario y apoyo deben ser texto")
                return

            if not self.cliente_glpi:
                self.enviar_json(
                    {"ok": False, "mensaje": SIN_CLIENTE_GLPI},
                    status=503,
                )
                return
            try:
                id_glpi = self.cliente_glpi.crear_ticket(asunto, descripcion)
            except GLPIError as error:
                self.enviar_json({"ok": False, "mensaje": str(error)}, status=502)
                return

            ticket_sim = {
                "id": str(id_glpi),
                "formulario_elegido": form,
                "apoyo": apoyo,
                "asunto": asunto,
                "descripcion": descripcion,
                "fecha_apertura": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

            decision = self.agente.procesar_ticket(ticket_sim)

            try:
                ticket_actualizado = self.cliente_glpi.actualizar_ticket(
                    id_ticket=id_glpi,
                    urgencia_nombre=decision.urgencia_final,
                    tecnico_nombre=decision.tecnico_asignado,
                    formulario_nombre=decision.formulario_final,
                )
                respuesta_registrada = self.cliente_glpi.registrar_respuesta_preliminar(
                    id_ticket=id_glpi,
                    respuesta_texto=decision.respuesta_preliminar,
                )
            except GLPIError as error:
                res = asdict(decision)
                res["id_ticket"] = id_glpi
                res["glpi_sincronizado"] = False
                res["glpi_error"] = (
                    f"GLPI creó el ticket #{id_glpi}, pero falló su actualización: {error}"
                )
                self.enviar_json(res, status=502)
                return

            res = asdict(decision)
            res["id_ticket"] = id_glpi
            res["glpi_sincronizado"] = ticket_actualizado and respuesta_registrada
            self.enviar_json(res)
            return

        if url.path == "/api/feedback":
            id_t = str(datos.get("id_ticket", ""))
            urg_corregida = datos.get("urgencia_corregida")
            if not id_t or urg_corregida not in ("Crítica", "Alta", "Media", "Baja"):
                self.send_error(400, "Ticket y urgencia válidos son obligatorios")
                return
            try:
                id_glpi = int(id_t)
                if id_glpi <= 0:
                    raise ValueError
            except ValueError:
                self.send_error(400, "El identificador del ticket debe ser un entero positivo")
                return

            if not self.cliente_glpi:
                self.enviar_json(
                    {"ok": False, "mensaje": SIN_CLIENTE_GLPI},
                    status=503,
                )
                return

            asunto = ""
            desc = ""
            # El panel solo corrige la urgencia: el formulario se conserva tal como lo dejó
            # el agente, o queda sin especificar si el ticket no pasó por él en esta sesión.
            formulario = datos.get("formulario_corregido")
            if not isinstance(formulario, str) or not formulario.strip():
                formulario = None

            try:
                # Se guarda la urgencia que tenía en GLPI para poder deshacer la corrección.
                glpi_tk = self.cliente_glpi.obtener_ticket(id_glpi)
                urgencia_anterior = _urgencia_ticket(glpi_tk)
                if id_t in self.agente.memoria.historial_decisiones:
                    registro = self.agente.memoria.historial_decisiones[id_t]
                    tk = registro["ticket"]
                    asunto = tk.get("asunto", "")
                    desc = tk.get("descripcion", "")
                    formulario = formulario or registro.get("decision", {}).get("formulario_final")
                else:
                    asunto = glpi_tk.get("name", "")
                    desc = glpi_tk.get("content", "")
                self.cliente_glpi.actualizar_urgencia(id_glpi, urg_corregida)
            except GLPIError as error:
                self.enviar_json(
                    {"ok": False, "mensaje": f"No se pudo actualizar la urgencia en GLPI: {error}"},
                    status=502,
                )
                return

            try:
                self.agente.memoria.registrar_feedback_humano(
                    id_ticket=id_t,
                    urgencia_humana=urg_corregida,
                    formulario_humano=formulario,
                    comentarios="Ajuste manual del tecnico desde Dashboard",
                    asunto=asunto,
                    descripcion=desc,
                    urgencia_anterior=urgencia_anterior,
                )
            except OSError as error:
                self.enviar_json(
                    {
                        "ok": False,
                        "mensaje": (
                            "La urgencia se actualizó en GLPI, pero no se pudo guardar "
                            f"el aprendizaje local: {error}"
                        ),
                        "glpi_actualizado": True,
                    },
                    status=500,
                )
                return
            self.enviar_json({
                "ok": True,
                "mensaje": "Urgencia actualizada en GLPI y corrección guardada para el aprendizaje.",
                "glpi_actualizado": True,
            })
            return

        if url.path == "/api/feedback/deshacer":
            self.deshacer_correccion(datos)
            return

        self.send_error(404, "Not Found")

    def deshacer_correccion(self, datos):
        """Anula la corrección vigente de un ticket y devuelve su urgencia anterior en GLPI."""
        id_t = str(datos.get("id_ticket", ""))
        if not id_t.isdigit() or int(id_t) <= 0:
            self.send_error(400, "El identificador del ticket debe ser un entero positivo")
            return
        if not self.cliente_glpi or not self.agente:
            self.enviar_json({"ok": False, "mensaje": SIN_CLIENTE_GLPI}, status=503)
            return

        vigente = self.agente.memoria.correcciones_vigentes().get(id_t)
        if vigente is None:
            self.enviar_json({"ok": False, "mensaje": "El ticket no tiene una corrección vigente."}, status=404)
            return

        anterior = vigente.get("urgencia_anterior")
        if anterior in URGENCIAS_GLPI.values():
            try:
                self.cliente_glpi.actualizar_urgencia(int(id_t), anterior)
            except GLPIError as error:
                self.enviar_json(
                    {"ok": False, "mensaje": f"No se pudo restaurar la urgencia en GLPI: {error}"},
                    status=502,
                )
                return

        self.agente.memoria.anular_correccion(id_t)
        mensaje = (
            f"Corrección anulada y urgencia restaurada a {anterior} en GLPI."
            if anterior in URGENCIAS_GLPI.values()
            else "Corrección anulada. No se conocía la urgencia anterior: revisa el ticket en GLPI."
        )
        self.enviar_json({"ok": True, "mensaje": mensaje, "urgencia_restaurada": anterior})

    def enviar_json(self, obj, status: int = 200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def iniciar_servidor(puerto: int = 5000, host: Optional[str] = None):
    # Por defecto solo se aceptan conexiones locales: el panel no tiene autenticación
    # y puede modificar tickets en GLPI. TRIAGENT_HOST=0.0.0.0 lo expone a la red.
    host = host or os.getenv("TRIAGENT_HOST", "127.0.0.1")
    agente = AgenteTriaje(usar_deep_learning=True)
    # Las decisiones se guardan en disco para que la cola las muestre tras reiniciar el panel.
    agente.memoria = MemoriaAgente(ruta_decisiones=RAIZ / "data" / "decisiones.jsonl")
    cliente_glpi = ClienteGLPI(modo_mock=False)
    try:
        cliente_glpi.conectar()
    except GLPIError as error:
        raise SystemExit(
            "No se pudo conectar con GLPI. Revisa que Docker esté activo, "
            f"la API legacy esté habilitada y el cliente/API tenga permiso para esta IP.\nDetalle: {error}"
        ) from error

    DashboardHandler.agente = agente
    DashboardHandler.cliente_glpi = cliente_glpi

    servidor = HTTPServer((host, puerto), DashboardHandler)
    print("\n" + "=" * 80)
    print(" PANEL WEB DEL AGENTE DE TRIAJE INICIADO CON EXITO ".center(80))
    print("=" * 80)
    print(f"  URL del Dashboard:    http://localhost:{puerto}")
    print("  Conexion GLPI:        Conectado (API legacy)")
    print(f"  Escuchando en:        {host}:{puerto}"
          + ("  (solo este equipo)" if host in ("127.0.0.1", "localhost") else "  (visible en la red)"))
    print("  Presiona Ctrl+C para detener el servidor.")
    print("=" * 80 + "\n")

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor web detenido.")
        cliente_glpi.desconectar()
        servidor.server_close()


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    iniciar_servidor(puerto)
