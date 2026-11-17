import base64
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from triage.glpi_client import ClienteGLPI, GLPIError


class FakeResponse:
    def __init__(self, value):
        self.body = value if isinstance(value, bytes) else json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


def test_conectar_y_listar_tickets_usa_api_legacy_y_tokens():
    respuestas = [
        FakeResponse({"session_token": "session-1"}),
        FakeResponse([{"id": 2, "status": 1}, {"id": 1, "status": 2}]),
    ]
    cliente = ClienteGLPI(
        url_base="http://glpi.test/apirest.php",
        usuario="api-user",
        password="api-password",
        app_token="app-token",
    )

    with patch("triage.glpi_client.urllib.request.urlopen", side_effect=respuestas) as abrir:
        assert cliente.conectar() is True
        assert cliente.obtener_tickets_nuevos() == [{"id": 2, "status": 1}]

    inicializacion = abrir.call_args_list[0].args[0]
    assert inicializacion.full_url == "http://glpi.test/apirest.php/initSession"
    assert inicializacion.get_header("Authorization") == (
        "Basic " + base64.b64encode(b"api-user:api-password").decode()
    )
    consulta = abrir.call_args_list[1].args[0]
    assert consulta.get_header("Session-token") == "session-1"
    assert consulta.get_header("App-token") == "app-token"


def test_conectar_usa_user_token_y_app_token_sin_basic_auth():
    respuesta = FakeResponse({"session_token": "session-2"})
    cliente = ClienteGLPI(
        url_base="http://glpi.test/apirest.php",
        usuario="api-user",
        password="api-password",
        app_token="app-token",
        user_token="user-token",
    )

    with patch("triage.glpi_client.urllib.request.urlopen", return_value=respuesta) as abrir:
        assert cliente.conectar() is True

    solicitud = abrir.call_args.args[0]
    assert solicitud.get_header("Authorization") == "user_token user-token"
    assert solicitud.get_header("App-token") == "app-token"


def test_error_de_api_no_activa_modo_simulado():
    error = urllib.error.HTTPError(
        "http://glpi.test/apirest.php/initSession",
        400,
        "Bad Request",
        {},
        io.BytesIO(b'["ERROR","API Disabled"]'),
    )
    cliente = ClienteGLPI(url_base="http://glpi.test/apirest.php")

    with patch("triage.glpi_client.urllib.request.urlopen", side_effect=error):
        try:
            cliente.conectar()
        except GLPIError as caught:
            assert "API Disabled" in str(caught)
        else:
            raise AssertionError("Expected the API error to be raised")

    assert cliente.modo_mock is False
    assert cliente.session_token is None


def test_crear_actualizar_y_seguir_ticket_en_glpi():
    respuestas = [
        FakeResponse({"session_token": "session-1"}),
        FakeResponse({"id": 41}),
        FakeResponse(b""),
        FakeResponse({"id": 5}),
    ]
    cliente = ClienteGLPI(url_base="http://glpi.test/apirest.php")

    with patch("triage.glpi_client.urllib.request.urlopen", side_effect=respuestas) as abrir:
        cliente.conectar()
        ticket_id = cliente.crear_ticket("No abre el portal", "Error de acceso")
        actualizado = cliente.actualizar_ticket(ticket_id, "Alta")
        respuesta = cliente.registrar_respuesta_preliminar(ticket_id, "Estamos revisando.")

    assert ticket_id == 41
    assert actualizado is True
    assert respuesta is True
    solicitudes = abrir.call_args_list
    assert solicitudes[1].args[0].get_method() == "POST"
    assert json.loads(solicitudes[1].args[0].data) == {
        "input": {
            "name": "No abre el portal",
            "content": "Error de acceso",
            "urgency": 3,
            "status": 1,
        }
    }
    assert solicitudes[2].args[0].get_method() == "PUT"
    assert json.loads(solicitudes[2].args[0].data) == {
        "input": {"id": 41, "urgency": 4, "status": 2}
    }
    assert solicitudes[3].args[0].full_url.endswith("/Ticket/41/ITILFollowup")


def test_mock_solo_se_usa_si_se_solicita_explicita_y_directamente():
    cliente = ClienteGLPI(modo_mock=True)
    assert cliente.conectar() is True
    assert cliente.crear_ticket("Prueba", "Descripción") == 1
    assert cliente.obtener_todos_los_tickets() == [
        {"id": 1, "name": "Prueba", "content": "Descripción", "status": 1, "urgency": 3}
    ]


if __name__ == "__main__":
    test_conectar_y_listar_tickets_usa_api_legacy_y_tokens()
    test_conectar_usa_user_token_y_app_token_sin_basic_auth()
    test_error_de_api_no_activa_modo_simulado()
    test_crear_actualizar_y_seguir_ticket_en_glpi()
    test_mock_solo_se_usa_si_se_solicita_explicita_y_directamente()
    print("GLPI client tests passed")
