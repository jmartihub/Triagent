"""Pruebas unitarias de clustering, duplicados e incidentes masivos."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from triage.agent import AgenteTriaje
from triage.clustering import DetectorIncidentesNoSupervisado


def test_duda_reiterada_no_es_incidente_masivo():
    agente = AgenteTriaje(usar_deep_learning=False)
    ticket_duda = {
        "id": "T_O365_01",
        "formulario_elegido": "Correo institucional",
        "apoyo": "Correo institucional",
        "asunto": "Office 365",
        "descripcion": "Como instalo office 365 con mi correo institucional?",
    }

    # 1er envío: Baja, no duplicado, no masivo
    d1 = agente.procesar_ticket(ticket_duda)
    assert d1.urgencia_final == "Baja"
    assert d1.es_duplicado is False
    assert d1.es_incidente_masivo is False

    # 2do al 5to envío: Se mantiene Baja, marcado como duplicado, NO es incidente masivo
    for i in range(2, 6):
        t_dup = dict(ticket_duda)
        t_dup["id"] = f"T_O365_0{i}"
        d_dup = agente.procesar_ticket(t_dup)
        assert d_dup.urgencia_final == "Baja", f"El intento {i} no debe inflar la urgencia a Crítica"
        assert d_dup.es_duplicado is True, f"El intento {i} debe detectarse como duplicado"
        assert d_dup.ticket_original_id == "T_O365_01"
        assert d_dup.es_incidente_masivo is False, f"Las dudas repetidas NUNCA deben ser incidentes masivos"

    print("[OK] Duda reiterada: Se mantiene Baja y no se declara falso incidente masivo")


def test_brote_fallas_requiere_minimo_tres_reportes():
    detector = DetectorIncidentesNoSupervisado(min_muestras_masivo=3)

    t1 = {"id": "WIFI_01", "formulario_elegido": "Fallas Técnicas TIC", "apoyo": "Red / Wi-Fi", "asunto": "Sin internet", "descripcion": "No hay wifi en el bloque C."}
    t2 = {"id": "WIFI_02", "formulario_elegido": "Fallas Técnicas TIC", "apoyo": "Red / Wi-Fi", "asunto": "Se cayó la red", "descripcion": "Bloque C sin internet de la universidad."}
    t3 = {"id": "WIFI_03", "formulario_elegido": "Fallas Técnicas TIC", "apoyo": "Red / Wi-Fi", "asunto": "Wifi caído", "descripcion": "La red de estudiantes del bloque C no responde."}

    r1 = detector.analizar_ticket(t1, tipo="falla")
    assert r1.es_incidente_masivo is False

    r2 = detector.analizar_ticket(t2, tipo="falla")
    assert r2.es_incidente_masivo is False  # 2 reportes no bastan para declarar caída masiva

    r3 = detector.analizar_ticket(t3, tipo="falla")
    assert r3.es_incidente_masivo is True  # Al 3er reporte concurrente se confirma el incidente masivo
    assert r3.tamano_cluster_masivo == 3

    print("[OK] Brote de fallas: Requiere al menos 3 reportes concurrentes para declarar alerta masiva")


def test_escalamiento_masivo_actualiza_sla_y_asignacion():
    agente = AgenteTriaje(usar_deep_learning=True)
    tickets = [
        ("wifi no conecta", "Mi computador no logra conectarse a la red wifi y no tengo internet."),
        ("no hay wifi", "No puedo usar internet porque el wifi no conecta en mi dispositivo."),
        ("internet caido", "La red wifi no funciona en mi equipo y no puedo conectarme."),
    ]

    decisiones = []
    for i, (asunto, descripcion) in enumerate(tickets):
        decisiones.append(agente.procesar_ticket({
            "id": f"ESCALAMIENTO_{i}",
            "formulario_elegido": "Fallas Técnicas TIC",
            "apoyo": "Red / Wi-Fi",
            "asunto": asunto,
            "descripcion": descripcion,
            "fecha_apertura": f"2026-11-15 10:{i * 5:02d}",
        }))

    ultima = decisiones[-1]
    sla_critico = agente.ontologia.obtener_politica_sla("Crítica")["tiempo_max_resolucion_horas"]
    assert ultima.es_incidente_masivo is True
    assert ultima.urgencia_final == "Crítica"
    assert ultima.tiempo_sla_horas == sla_critico

    print("[OK] Escalamiento masivo: SLA y enrutamiento reflejan la prioridad final")


if __name__ == "__main__":
    test_duda_reiterada_no_es_incidente_masivo()
    test_brote_fallas_requiere_minimo_tres_reportes()
    test_escalamiento_masivo_actualiza_sla_y_asignacion()
    print("\nTodos los tests de clustering pasaron exitosamente.")
