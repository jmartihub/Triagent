"""Cliente de integración con la API REST legacy de GLPI."""

import base64
import json
import os
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request


MAPA_URGENCIAS_GLPI = {
    "Baja": 2,
    "Media": 3,
    "Alta": 4,
    "Crítica": 5,
}

MAPA_GLPI_A_URGENCIA = {
    1: "Baja",
    2: "Baja",
    3: "Media",
    4: "Alta",
    5: "Crítica",
}


class GLPIError(RuntimeError):
    """Error de conexión o de operación devuelto por GLPI."""


class ClienteGLPI:
    """Cliente para la API legacy de GLPI y el modo simulado explícito de pruebas."""

    def __init__(
        self,
        url_base: Optional[str] = None,
        usuario: Optional[str] = None,
        password: Optional[str] = None,
        app_token: Optional[str] = None,
        user_token: Optional[str] = None,
        modo_mock: bool = False,
    ):
        self.url_base = (url_base or os.getenv(
            "GLPI_API_URL", "http://localhost:8080/apirest.php"
        )).rstrip("/")
        self.usuario = usuario if usuario is not None else os.getenv("GLPI_USER", "glpi")
        self.password = password if password is not None else os.getenv("GLPI_PASSWORD", "glpi")
        self.app_token = app_token if app_token is not None else os.getenv("GLPI_APP_TOKEN", "")
        self.user_token = user_token if user_token is not None else os.getenv("GLPI_USER_TOKEN", "")
        self.modo_mock = modo_mock
        self.session_token: Optional[str] = None
        self.tickets_mock: Dict[int, Dict[str, Any]] = {}
        self.seguimientos_mock: Dict[int, List[str]] = {}

    def _solicitar(
        self,
        endpoint: str,
        metodo: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        incluir_autenticacion: bool = False,
        timeout: int = 5,
    ) -> Any:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.session_token:
            headers["Session-Token"] = self.session_token
        if self.app_token:
            headers["App-Token"] = self.app_token
        if incluir_autenticacion:
            if self.user_token:
                headers["Authorization"] = f"user_token {self.user_token}"
            else:
                auth = base64.b64encode(f"{self.usuario}:{self.password}".encode()).decode()
                headers["Authorization"] = f"Basic {auth}"

        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.url_base}/{endpoint.lstrip('/')}",
            data=data,
            headers=headers,
            method=metodo,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode()
        except urllib.error.HTTPError as error:
            detalle = error.read().decode(errors="replace").strip()
            raise GLPIError(
                f"GLPI respondió HTTP {error.code} en {endpoint}: "
                f"{detalle or error.reason}"
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            motivo = getattr(error, "reason", error)
            raise GLPIError(f"No se pudo conectar con GLPI en {self.url_base}: {motivo}") from error

        if not body:
            return None
        try:
            respuesta = json.loads(body)
        except json.JSONDecodeError as error:
            raise GLPIError(f"GLPI devolvió una respuesta JSON inválida en {endpoint}.") from error
        if (
            isinstance(respuesta, list)
            and respuesta
            and isinstance(respuesta[0], str)
            and respuesta[0].startswith("ERROR")
        ):
            raise GLPIError(f"GLPI devolvió un error en {endpoint}: {respuesta}")
        return respuesta

    def _asegurar_sesion(self):
        if not self.modo_mock and not self.session_token:
            raise GLPIError("No hay una sesión activa con GLPI. Reinicia el dashboard para reconectar.")

    def conectar(self) -> bool:
        if self.modo_mock:
            self.session_token = "mock_session_token_12345"
            return True

        respuesta = self._solicitar(
            "initSession",
            incluir_autenticacion=True,
            timeout=8,
        )
        if (
            not isinstance(respuesta, dict)
            or not isinstance(respuesta.get("session_token"), str)
            or not respuesta["session_token"]
        ):
            raise GLPIError("GLPI no devolvió un session_token al iniciar sesión.")
        self.session_token = respuesta["session_token"]
        return True

    def obtener_ticket(self, id_ticket: int) -> Dict[str, Any]:
        if self.modo_mock:
            return self.tickets_mock.get(id_ticket, {})
        self._asegurar_sesion()
        respuesta = self._solicitar(f"Ticket/{id_ticket}")
        if not isinstance(respuesta, dict):
            raise GLPIError(f"GLPI devolvió datos inválidos para el ticket {id_ticket}.")
        return respuesta

    def obtener_tickets_nuevos(self) -> List[Dict[str, Any]]:
        """Obtiene tickets con estado Nuevo (status=1 en GLPI)."""
        if self.modo_mock:
            return [ticket for ticket in self.tickets_mock.values() if ticket.get("status") == 1]
        self._asegurar_sesion()
        respuesta = self._solicitar("Ticket?is_deleted=0&range=0-999")
        if not isinstance(respuesta, list):
            raise GLPIError("GLPI devolvió un listado de tickets con formato inesperado.")
        return [ticket for ticket in respuesta if ticket.get("status") == 1]

    def obtener_todos_los_tickets(self, limite: int = 100) -> List[Dict[str, Any]]:
        """Obtiene los tickets más recientes de GLPI."""
        if limite <= 0:
            return []
        if self.modo_mock:
            return sorted(
                self.tickets_mock.values(),
                key=lambda ticket: ticket.get("id", 0),
                reverse=True,
            )[:limite]
        self._asegurar_sesion()
        respuesta = self._solicitar(
            f"Ticket?is_deleted=0&range=0-{limite - 1}&order=DESC"
        )
        if not isinstance(respuesta, list):
            raise GLPIError("GLPI devolvió un listado de tickets con formato inesperado.")
        return sorted(respuesta, key=lambda ticket: int(ticket.get("id", 0)), reverse=True)

    def crear_ticket(self, nombre: str, contenido: str, urgencia_inicial: int = 3) -> int:
        """Crea un ticket y devuelve su identificador real de GLPI."""
        if self.modo_mock:
            nuevo_id = max(self.tickets_mock.keys(), default=0) + 1
            self.tickets_mock[nuevo_id] = {
                "id": nuevo_id,
                "name": nombre,
                "content": contenido,
                "status": 1,
                "urgency": urgencia_inicial,
            }
            return nuevo_id
        self._asegurar_sesion()
        respuesta = self._solicitar(
            "Ticket",
            metodo="POST",
            payload={
                "input": {
                    "name": nombre,
                    "content": contenido,
                    "urgency": urgencia_inicial,
                    "status": 1,
                }
            },
        )
        if not isinstance(respuesta, dict) or not respuesta.get("id"):
            raise GLPIError(f"GLPI no confirmó la creación del ticket: {respuesta!r}")
        return int(respuesta["id"])

    def actualizar_ticket(
        self,
        id_ticket: int,
        urgencia_nombre: str,
        tecnico_nombre: str = "",
        formulario_nombre: str = "",
    ) -> bool:
        """Actualiza la urgencia y pone el ticket en curso en GLPI."""
        urgencia = MAPA_URGENCIAS_GLPI.get(urgencia_nombre, 3)
        if self.modo_mock:
            if id_ticket not in self.tickets_mock:
                self.tickets_mock[id_ticket] = {"id": id_ticket, "status": 1}
            self.tickets_mock[id_ticket].update({"urgency": urgencia, "status": 2})
            return True
        self._asegurar_sesion()
        self._solicitar(
            f"Ticket/{id_ticket}",
            metodo="PUT",
            payload={"input": {"id": id_ticket, "urgency": urgencia, "status": 2}},
        )
        return True

    def actualizar_urgencia(self, id_ticket: int, urgencia_nombre: str) -> bool:
        """Cambia únicamente la urgencia de un ticket existente en GLPI."""
        urgencia = MAPA_URGENCIAS_GLPI.get(urgencia_nombre)
        if urgencia is None:
            raise GLPIError(f"Urgencia no válida para GLPI: {urgencia_nombre}")
        if self.modo_mock:
            if id_ticket not in self.tickets_mock:
                self.tickets_mock[id_ticket] = {"id": id_ticket, "status": 1}
            self.tickets_mock[id_ticket]["urgency"] = urgencia
            return True
        self._asegurar_sesion()
        self._solicitar(
            f"Ticket/{id_ticket}",
            metodo="PUT",
            payload={"input": {"id": id_ticket, "urgency": urgencia}},
        )
        return True

    def registrar_respuesta_preliminar(self, id_ticket: int, respuesta_texto: str) -> bool:
        """Añade un seguimiento público al ticket."""
        if self.modo_mock:
            self.seguimientos_mock.setdefault(id_ticket, []).append(respuesta_texto)
            return True
        self._asegurar_sesion()
        self._solicitar(
            f"Ticket/{id_ticket}/ITILFollowup",
            metodo="POST",
            payload={
                "input": {
                    "items_id": id_ticket,
                    "itemtype": "Ticket",
                    "content": respuesta_texto,
                    "is_private": 0,
                }
            },
        )
        return True

    def desconectar(self):
        if not self.modo_mock and self.session_token:
            try:
                self._solicitar("killSession", timeout=2)
            except GLPIError as error:
                print(f"Advertencia: no se pudo cerrar la sesión de GLPI: {error}")
        self.session_token = None
