"""Punto de entrada unificado del Agente Inteligente de Triaje (Tooli / GLPI).

Comandos disponibles:
    python main.py web          # Inicia el Dashboard Web interactivo en http://localhost:5000
    python main.py demo         # Ejecuta la demostración guiada por consola
    python main.py interactivo  # Modo interactivo en consola: ingresa tickets por teclado
    python main.py deep         # Entrena y evalúa la variante de Deep Learning (MLP)
    python main.py factores     # Entrena un clasificador por factor de la rúbrica
    python main.py sla          # Entrena y evalúa los modelos de regresión para SLA
    python main.py evaluar      # Compara modelos, reglas y agente completo en todos los conjuntos
    python main.py generate     # Genera el dataset sintético con ruido
    python main.py train        # Entrena y evalúa el modelo base clásico (TF-IDF + Logística)
    python main.py all          # Ejecuta todo el ciclo en orden
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def cargar_entorno_local(archivo=None):
    archivo = archivo or Path(__file__).resolve().parent / ".env"
    if not archivo.exists():
        return

    for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        clave, separador, valor = linea.partition("=")
        clave = clave.strip()
        if not separador or not clave:
            raise SystemExit(f"Formato inválido en {archivo}, línea {numero}; se esperaba CLAVE=valor.")
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
            valor = valor[1:-1]
        os.environ.setdefault(clave, valor)


cargar_entorno_local()

# Si se ejecuta con el python global del sistema, re-ejecutar automáticamente con .venv
def _python_del_venv():
    venv = Path(__file__).resolve().parent / ".venv"
    for candidato in (venv / "Scripts" / "python.exe", venv / "bin" / "python"):
        if candidato.exists():
            return candidato
    return None


def reejecutar_con_venv():
    """Si se ejecuta con el python global y existe .venv, relanza el comando con el del venv."""
    venv_python = _python_del_venv()
    if (
        not venv_python
        or "VIRTUAL_ENV" in os.environ
        or Path(sys.executable).resolve() == venv_python.resolve()
    ):
        return
    argumentos = argumentos_validados(sys.argv[1:])
    if argumentos is None:
        return  # Argumentos desconocidos: main() mostrará la ayuda sin relanzar nada.
    comando = [str(venv_python), str(Path(__file__).resolve()), *argumentos]
    if os.name == "nt":
        # En Windows os.execv no reemplaza el proceso y rompe la consola; se usa un subproceso.
        sys.exit(subprocess.call(comando))
    os.execv(str(venv_python), comando)


COMANDOS = {
    nombre: nombre
    for nombre in (
        "demo", "interactivo", "interactive", "web", "dashboard", "front",
        "generate", "train", "deep", "factores", "sla", "all", "evaluar",
    )
}


def argumentos_validados(argumentos):
    """Devuelve los argumentos como valores conocidos (comando y puerto) o None si no son válidos."""
    if not argumentos:
        return []
    comando = COMANDOS.get(argumentos[0].lower())
    if comando is None or len(argumentos) > 2:
        return None
    if len(argumentos) == 1:
        return [comando]
    if not argumentos[1].isdigit() or not 1 <= int(argumentos[1]) <= 65535:
        return None
    return [comando, str(int(argumentos[1]))]

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def iniciar_servicios_glpi():
    raiz = Path(__file__).resolve().parent
    compose = raiz / "docker" / "docker-compose.yml"
    comando = ["docker", "compose", "-f", str(compose), "up", "-d"]

    try:
        subprocess.run(
            comando,
            cwd=raiz,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError as error:
        raise SystemExit("No se encontró Docker. Instala Docker Desktop/Engine y vuelve a intentarlo.") from error
    except subprocess.TimeoutExpired as error:
        raise SystemExit("Docker Compose tardó más de 5 minutos en iniciar los servicios.") from error
    except subprocess.CalledProcessError as error:
        detalle = (error.stderr or error.stdout).strip()
        raise SystemExit(
            "No se pudieron iniciar los servicios de GLPI con Docker Compose."
            + (f"\nDetalle: {detalle}" if detalle else "")
        ) from error

    print("Servicios Docker de GLPI iniciados; esperando a que responda en localhost:8080...")
    for _ in range(120):
        try:
            with socket.create_connection(("127.0.0.1", 8080), timeout=1):
                return
        except OSError:
            time.sleep(1)

    raise SystemExit(
        "Los contenedores se iniciaron, pero GLPI no respondió en http://localhost:8080 "
        "después de 120 segundos. Revisa `docker compose -f docker/docker-compose.yml logs glpi mariadb`."
    )


def main():
    comando = sys.argv[1].lower() if len(sys.argv) > 1 else "demo"

    if comando == "demo":
        import demo
        demo.main()
        return

    if comando in ("interactivo", "interactive"):
        import demo
        from triage.agent import AgenteTriaje
        demo.modo_interactivo(AgenteTriaje(usar_deep_learning=True))
        return

    if comando in ("web", "dashboard", "front"):
        iniciar_servicios_glpi()
        from triage import web_dashboard
        puerto = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
        web_dashboard.iniciar_servidor(puerto)
        return

    if comando in ("generate", "all"):
        from triage import generate
        generate.main()

    if comando in ("train", "all"):
        from triage import train
        train.main()

    if comando in ("deep", "all"):
        from triage import deep_model
        deep_model.main()

    if comando in ("factores", "all"):
        from triage import factor_model
        factor_model.main()

    if comando in ("sla", "all"):
        from triage import sla_regression
        sla_regression.main()

    if comando in ("evaluar", "all"):
        from triage import evaluate
        evaluate.main()

    if comando not in ("demo", "interactivo", "interactive", "generate", "train", "deep", "factores", "sla", "all", "evaluar"):
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    reejecutar_con_venv()
    main()
