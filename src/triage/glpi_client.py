"""Cliente de Integración con la API REST de GLPI.

Permite al agente interactuar con una instancia real de GLPI (en Docker o servidor)
o en modo simulado/mock si el contenedor no está activo:
- Autenticación mediante HTTP Basic Auth (admin: glpi/glpi) o User-Token
- Consulta de tickets pendientes de triaje (Estado = 'Nuevo', status=1)
- Actualización de campos verificables: Urgencia (1 a 5), Estado (Asignado/En curso, status=2)
- Registro del acuse de recibo y respuesta preliminar (ITIL Followup)
"""

import base64
from dataclasses import dataclass
import json
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request


MAPA_URGENCIAS_GLPI = {
    "Baja": 2,      # GLPI: 1=Muy baja, 2=Baja, 3=Media, 4=Alta, 5=Muy alta (Crítica)
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


class ClienteGLPI:
    """Cliente para la API REST de GLPI con soporte para instancia real en Docker y modo mock."""

    def __init__(
        self,
        url_base: str = "http://localhost:8080/apirest.php",
        usuario: str = "glpi",
        password: str = "glpi",
        modo_mock: bool = False,
    ):
        self.url_base = url_base.rstrip("/")
        self.usuario = usuario
        self.password = password
        self.modo_mock = modo_mock
        self.session_token: Optional[str] = None

        # Almacenamiento en memoria para modo mock
        self.tickets_mock: Dict[int, Dict[str, Any]] = {}
        self.seguimientos_mock: Dict[int, List[str]] = {}

    def conectar(self) -> bool:
        if self.modo_mock:
            self.session_token = "mock_session_token_12345"
            return True

        auth_str = f"{self.usuario}:{self.password}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()

        req = urllib.request.Request(
            f"{self.url_base}/initSession",
            headers={
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                self.session_token = data.get("session_token")
                return True
        except Exception:
            # Fallback seguro a modo mock
            self.modo_mock = True
            self.session_token = "mock_session_token_12345"
            return False

    def obtener_tickets_nuevos(self) -> List[Dict[str, Any]]:
        """Obtiene tickets con estado 'Nuevo' (status=1 en GLPI)."""
        if self.modo_mock or not self.session_token:
            return [t for t in self.tickets_mock.values() if t.get("status") == 1]

        url = f"{self.url_base}/Ticket?is_deleted=0"
        req = urllib.request.Request(
            url,
            headers={
                "Session-Token": self.session_token,
                "Content-Type": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                todos = json.loads(resp.read().decode())
                # Filtrar los que tengan status 1 (Nuevo)
                nuevos = [t for t in todos if t.get("status") == 1]
                return nuevos
        except Exception:
            return []

    def obtener_todos_los_tickets(self, limite: int = 100) -> List[Dict[str, Any]]:
        """Obtiene el listado completo de tickets ordenados de más reciente a más antiguo."""
        if self.modo_mock or not self.session_token:
            return sorted(self.tickets_mock.values(), key=lambda t: t.get("id", 0), reverse=True)[:limite]

        url = f"{self.url_base}/Ticket?is_deleted=0&range=0-{limite}&order=DESC"
        req = urllib.request.Request(
            url,
            headers={
                "Session-Token": self.session_token,
                "Content-Type": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                todos = json.loads(resp.read().decode())
                if isinstance(todos, list):
                    return sorted(todos, key=lambda t: t.get("id", 0), reverse=True)
                return []
        except Exception:
            return sorted(self.tickets_mock.values(), key=lambda t: t.get("id", 0), reverse=True)

    def crear_ticket(self, nombre: str, contenido: str, urgencia_inicial: int = 3) -> Optional[int]:
        """Crea un ticket en GLPI (usado por el simulador de Tooli/estudiante)."""
        if self.modo_mock or not self.session_token:
            nuevo_id = max(self.tickets_mock.keys(), default=0) + 1
            self.tickets_mock[nuevo_id] = {
                "id": nuevo_id,
                "name": nombre,
                "content": contenido,
                "status": 1,
                "urgency": urgencia_inicial,
            }
            return nuevo_id

        payload = json.dumps({
            "input": {
                "name": nombre,
                "content": contenido,
                "urgency": urgencia_inicial,
                "status": 1,
            }
        }).encode()

        req = urllib.request.Request(
            f"{self.url_base}/Ticket",
            data=payload,
            headers={
                "Session-Token": self.session_token,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                res = json.loads(resp.read().decode())
                return res.get("id")
        except Exception:
            return None

    def actualizar_ticket(
        self,
        id_ticket: int,
        urgencia_nombre: str,
        tecnico_nombre: str,
        formulario_nombre: str,
    ) -> bool:
        """Escribe en GLPI la urgencia estimada y cambia el estado a en curso."""
        urg_val = MAPA_URGENCIAS_GLPI.get(urgencia_nombre, 3)

        if self.modo_mock or not self.session_token:
            if id_ticket not in self.tickets_mock:
                self.tickets_mock[id_ticket] = {"id": id_ticket, "status": 1}
            self.tickets_mock[id_ticket].update({
                "urgency": urg_val,
                "urgencia_nombre": urgencia_nombre,
                "tecnico_asignado": tecnico_nombre,
                "formulario_final": formulario_nombre,
                "status": 2,  # Asignado
            })
            return True

        payload = json.dumps({
            "input": {
                "id": id_ticket,
                "urgency": urg_val,
                "status": 2,
            }
        }).encode()

        req = urllib.request.Request(
            f"{self.url_base}/Ticket/{id_ticket}",
            data=payload,
            headers={
                "Session-Token": self.session_token,
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False

    def registrar_respuesta_preliminar(self, id_ticket: int, respuesta_texto: str) -> bool:
        """Añade un seguimiento público (ITILFollowup) visible para el estudiante."""
        if self.modo_mock or not self.session_token:
            self.seguimientos_mock.setdefault(id_ticket, []).append(respuesta_texto)
            return True

        payload = json.dumps({
            "input": {
                "items_id": id_ticket,
                "itemtype": "Ticket",
                "content": respuesta_texto,
                "is_private": 0,
            }
        }).encode()

        req = urllib.request.Request(
            f"{self.url_base}/Ticket/{id_ticket}/ITILFollowup",
            data=payload,
            headers={
                "Session-Token": self.session_token,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status in (200, 201)
        except Exception:
            return False

    def desconectar(self):
        if not self.modo_mock and self.session_token:
            try:
                req = urllib.request.Request(
                    f"{self.url_base}/killSession",
                    headers={"Session-Token": self.session_token},
                    method="GET",
                )
                urllib.request.urlopen(req, timeout=2)
            except Exception:
                pass
        self.session_token = None
