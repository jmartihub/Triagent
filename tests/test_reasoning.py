import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from triage.ontology import OntologiaTI
from triage.fol_rules import MotorInferenciaFOL


def test_ontology_routing():
    onto = OntologiaTI()

    # Caso 1: Falla en Teams crítica
    asig = onto.enrutar_ticket(
        formulario="Fallas Técnicas TIC",
        apoyo="Teams",
        urgencia="Crítica",
        asunto="Teams caído",
        descripcion="No puedo unirme al examen",
    )
    assert asig.grupo_id == "sistemas_academicos"
    assert asig.tiempo_max_resolucion_horas == 2.0
    assert "Carolina Gómez" in asig.tecnico_nombre
    assert len(asig.explicacion_ontologica) > 20

    # Caso 2: Wi-Fi campus
    asig_wifi = onto.enrutar_ticket(
        formulario="Fallas Técnicas TIC",
        apoyo="Red / Wi-Fi",
        urgencia="Alta",
    )
    assert asig_wifi.grupo_id == "infraestructura_redes"
    assert asig_wifi.tiempo_max_resolucion_horas == 8.0
    assert "Andrés Morales" in asig_wifi.tecnico_nombre

    print("✓ Ontología: Enrutamiento y SLA correctos")


def test_fol_inference():
    motor = MotorInferenciaFOL(umbral_confianza_minima=0.60)

    # Caso 1: Falla grupal bloqueante -> deducción Crítica + Escalamiento
    res = motor.razonar(
        id_ticket="tk_001",
        tipo="falla",
        alcance="grupo",
        bloquea=True,
        plazo="ninguno",
        alternativa=False,
        urgencia_predicha_ml="Media",  # ML subestima
        confianza_ml=0.90,
    )
    assert res.urgencia_deducida == "Crítica"
    assert res.escalamiento_inmediato is True
    assert res.seguridad_ml_activada is True
    assert "FOL-R01" in res.reglas_disparadas
    assert "FOL-ESC01" in res.reglas_disparadas

    # Caso 2: Confianza ML baja (< umbral) -> activa revisión humana
    res_baja = motor.razonar(
        id_ticket="tk_002",
        tipo="duda",
        alcance="individual",
        bloquea=False,
        plazo="ninguno",
        alternativa=True,
        urgencia_predicha_ml="Baja",
        confianza_ml=0.45,  # Baja confianza
    )
    assert res_baja.requiere_revision_humana is True
    assert res_baja.seguridad_ml_activada is True

    # Caso 3: Duda sin plazo -> Baja
    res_duda = motor.razonar(
        id_ticket="tk_003",
        tipo="duda",
        alcance="individual",
        bloquea=False,
        plazo="ninguno",
        alternativa=False,
        confianza_ml=0.85,
    )
    assert res_duda.urgencia_deducida == "Baja"
    assert "FOL-R03" in res_duda.reglas_disparadas

    print("✓ FOL: Inferencia deductiva, cláusulas de Horn y red de seguridad correctas")


if __name__ == "__main__":
    test_ontology_routing()
    test_fol_inference()
    print("\nTodos los tests de razonamiento pasaron exitosamente.")
