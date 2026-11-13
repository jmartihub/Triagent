import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from triage.rubric import Factores, urgencia


def test_ejemplos_de_la_rubrica():
    # Crítica: bloquea con plazo inmediato y sin alternativa.
    assert urgencia(Factores("falla", "individual", True, "inmediato", False)) == "Crítica"
    # Crítica: afecta a un grupo y bloquea.
    assert urgencia(Factores("falla", "grupo", True, "ninguno", False)) == "Crítica"
    # Alta: bloquea a una persona con plazo cercano y sin alternativa.
    assert urgencia(Factores("falla", "individual", True, "cercano", False)) == "Alta"
    # Media: bloquea pero hay alternativa y plazo cercano.
    assert urgencia(Factores("falla", "individual", True, "cercano", True)) == "Media"
    # Baja: duda sin plazo.
    assert urgencia(Factores("duda", "individual", False, "ninguno", False)) == "Baja"
    # Una duda con plazo sube a Media.
    assert urgencia(Factores("duda", "individual", False, "cercano", False)) == "Media"


if __name__ == "__main__":
    test_ejemplos_de_la_rubrica()
    print("rubric ok")
