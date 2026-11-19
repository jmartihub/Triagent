import importlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

virtual_env_anterior = os.environ.get("VIRTUAL_ENV")
os.environ["VIRTUAL_ENV"] = "test"
try:
    main = importlib.import_module("main")
finally:
    if virtual_env_anterior is None:
        os.environ.pop("VIRTUAL_ENV", None)
    else:
        os.environ["VIRTUAL_ENV"] = virtual_env_anterior


def test_web_inicia_compose_y_espera_a_glpi():
    with patch("main.subprocess.run") as ejecutar:
        with patch(
            "main.socket.create_connection",
            side_effect=[OSError("not ready"), MagicMock()],
        ) as conectar:
            with patch("main.time.sleep") as dormir:
                main.iniciar_servicios_glpi()

    comando = ejecutar.call_args.args[0]
    assert comando[:3] == ["docker", "compose", "-f"]
    assert comando[-2:] == ["up", "-d"]
    assert ejecutar.call_args.kwargs["check"] is True
    assert ejecutar.call_args.kwargs["timeout"] == 300
    assert conectar.call_count == 2
    dormir.assert_called_once_with(1)


def test_web_muestra_fallo_al_iniciar_docker_compose():
    fallo = subprocess.CalledProcessError(
        1,
        ["docker", "compose"],
        stderr="Docker daemon is unavailable",
    )
    with patch("main.subprocess.run", side_effect=fallo):
        try:
            main.iniciar_servicios_glpi()
        except SystemExit as error:
            assert "Docker daemon is unavailable" in str(error)
        else:
            raise AssertionError("Expected Compose startup failure to be reported")


def test_cargar_entorno_local_respeta_la_terminal_y_lee_token():
    with tempfile.TemporaryDirectory() as directorio:
        archivo = Path(directorio) / ".env"
        archivo.write_text(
            "GLPI_API_URL=http://glpi.local/apirest.php\nGLPI_APP_TOKEN='app-token'\n",
            encoding="utf-8",
        )
        with patch.dict(os.environ, {"GLPI_API_URL": "http://terminal/apirest.php"}, clear=True):
            main.cargar_entorno_local(archivo)
            assert os.environ["GLPI_API_URL"] == "http://terminal/apirest.php"
            assert os.environ["GLPI_APP_TOKEN"] == "app-token"


def test_relanzar_con_venv_solo_acepta_comandos_y_puertos_validos():
    assert main.argumentos_validados([]) == []
    assert main.argumentos_validados(["WEB", "5000"]) == ["web", "5000"]
    assert main.argumentos_validados(["interactivo"]) == ["interactivo"]
    assert main.argumentos_validados(["web", "5000; rm -rf /"]) is None
    assert main.argumentos_validados(["web", "70000"]) is None
    assert main.argumentos_validados(["--desconocido"]) is None
    assert main.argumentos_validados(["demo", "1", "2"]) is None


if __name__ == "__main__":
    test_relanzar_con_venv_solo_acepta_comandos_y_puertos_validos()
    test_web_inicia_compose_y_espera_a_glpi()
    test_web_muestra_fallo_al_iniciar_docker_compose()
    test_cargar_entorno_local_respeta_la_terminal_y_lee_token()
    print("main startup tests passed")
