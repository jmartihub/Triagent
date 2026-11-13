"""Punto de entrada unificado del Agente Inteligente de Triaje (Tooli / GLPI).

Comandos disponibles:
    python main.py web          # Inicia el Dashboard Web interactivo en http://localhost:5000
    python main.py demo         # Ejecuta la demostración guiada por consola
    python main.py interactivo  # Modo interactivo en consola: ingresa tickets por teclado
    python main.py deep         # Entrena y evalúa la variante de Deep Learning (MLP)
    python main.py sla          # Entrena y evalúa los modelos de regresión para SLA
    python main.py generate     # Genera el dataset sintético con ruido
    python main.py train        # Entrena y evalúa el modelo base clásico (TF-IDF + Logística)
    python main.py all          # Ejecuta todo el ciclo en orden
"""

import os
import sys
from pathlib import Path

# Si se ejecuta con el python global del sistema, re-ejecutar automáticamente con .venv
venv_python = Path(__file__).resolve().parent / ".venv" / "bin" / "python"
if venv_python.exists() and sys.executable != str(venv_python) and "VIRTUAL_ENV" not in os.environ:
    os.execv(str(venv_python), [str(venv_python)] + sys.argv)

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


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

    if comando in ("sla", "all"):
        from triage import sla_regression
        sla_regression.main()

    if comando not in ("demo", "interactivo", "interactive", "generate", "train", "deep", "sla", "all"):
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
