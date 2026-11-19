"""Script de Demostración Interactiva del Agente de Triaje para la Sustentación.

Permite ejecutar los casos de prueba clave requeridos por la rúbrica docente:
1. Caso de la propuesta: "no puedo entrar a la plataforma y presento un parcial en una hora"
2. Caso de formulario equivocado: estudiante que paga en línea en el formulario de Fallas Técnicas
3. Caso de incidente masivo no supervisado: brote de tickets sobre Wi-Fi agrupados por DBSCAN
4. Caso interactivo: el evaluador o estudiante puede redactar cualquier ticket en vivo
"""

import sys
import time
from pathlib import Path
import json

RAIZ = Path(__file__).resolve().parent

sys.path.insert(0, str(RAIZ / "src"))

from triage.agent import AgenteTriaje, DecisionAgente


def imprimir_encabezado(titulo: str):
    print("\n" + "=" * 80)
    print(f" {titulo.center(78)} ")
    print("=" * 80)


def mostrar_paso(paso: str, descripcion: str):
    print(f"\n[{paso.upper()}] {descripcion}")
    time.sleep(0.3)


def renderizar_decision(decision: DecisionAgente, ticket: dict):
    print("\n" + "─" * 80)
    print("[RESUMEN DE LA ACCION VERIFICABLE DEL AGENTE]")
    print("─" * 80)
    print(f"• ID Ticket:              #{decision.id_ticket}")
    print(f"• Formulario Original:    {ticket.get('formulario_elegido')}")
    print(f"• Formulario Definitivo:  {decision.formulario_final}" +
          (" [CORREGIDO POR EL AGENTE]" if decision.hubo_cambio_formulario else " [OK]"))
    print(f"• Urgencia Final:         {decision.urgencia_final}")
    print(f"• Red de Seguridad FOL:   " +
          ("ACTIVADA (FOL corrigio subestimacion de ML)" if decision.seguridad_ml_activada else "Inferencia estandar"))
    print(f"• Grupo Asignado:         {decision.grupo_asignado}")
    print(f"• Tecnico Especialista:   {decision.tecnico_asignado} ({decision.tecnico_correo})")
    print(f"• Tiempo Max SLA:         {decision.tiempo_sla_horas} horas")
    print(f"• Tiempo Estimado Cola:   {decision.horas_estimadas_resolucion} horas (Riesgo: {decision.nivel_riesgo_sla})")

    if decision.es_incidente_masivo:
        print(f"• [INCIDENTE MASIVO]      ASOCIADO AL INCIDENTE MAESTRO {decision.id_incidente_masivo}")
    if decision.es_duplicado:
        print(f"• [DUPLICADO DETECTADO]   Vinculado al ticket #{decision.ticket_original_id}")
    if decision.requiere_revision_humana:
        print(f"• [REVISION HUMANA]       Marcado para confirmacion del tecnico (baja certeza inicial)")

    print("\n" + "─" * 80)
    print("[TRAZA FORMAL DE RAZONAMIENTO: LOGICA DE PRIMER ORDEN & ONTOLOGIA]")
    print("─" * 80)
    print("• Explicacion Ontologica:")
    print(f"  {decision.explicacion_ontologica}")
    print("• Deducciones FOL (Clausulas aplicadas):")
    for d in decision.justificacion_fol:
        print(f"  - {d}")

    print("\n" + "─" * 80)
    print("[RESPUESTA PRELIMINAR GENERADA PARA EL ESTUDIANTE (ACCION 3)]")
    print("─" * 80)
    print(decision.respuesta_preliminar)
    print("─" * 80)


def caso_propuesta(agente: AgenteTriaje):
    imprimir_encabezado("CASO 1: CASO DE LA PROPUESTA (EXAMEN EN UNA HORA)")
    ticket = {
        "id": "DEMO_001",
        "formulario_elegido": "Fallas Técnicas TIC",
        "apoyo": "Banner",
        "asunto": "No puedo entrar a la plataforma",
        "descripcion": "No me deja entrar a la plataforma y presento un examen parcial en una hora. No tengo otra forma de presentarlo.",
        "tiene_adjunto": 0,
        "fecha_apertura": "2026-11-13 10:15",
    }
    mostrar_paso("1. Situación Inicial & Percepción", f"Estudiante crea ticket en Tooli:\n   Asunto: '{ticket['asunto']}'\n   Descripción: '{ticket['descripcion']}'")
    percepciones = agente.percibir(ticket)
    print(f"   Percepción ML: Urgencia={percepciones['pred_urg']} (conf: {percepciones['conf_urg']:.2f}) | Factores: Tipo={percepciones['tipo']}, Plazo={percepciones['plazo']}, Bloquea={percepciones['bloquea']}")

    mostrar_paso("2. Razonamiento", "Aplicando Ontología de Servicios + Motor Deductivo FOL + Regresión de SLA...")
    decision = agente.procesar_ticket(ticket)

    mostrar_paso("3. Acción y Resultado", "El agente publica la urgencia, enruta al técnico y genera acuse preliminar.")
    renderizar_decision(decision, ticket)


def caso_formulario_equivocado(agente: AgenteTriaje):
    imprimir_encabezado("CASO 2: FORMULARIO EQUIVOCADO (ERROR HUMANO CORREGIDO)")
    ticket = {
        "id": "DEMO_002",
        "formulario_elegido": "Fallas Técnicas TIC",  # Eligió fallas técnicas
        "apoyo": "Pagos en línea",
        "asunto": "Descuento de matrícula y recibo",
        "descripcion": "Mi liquidación no incluye el descuento al que tengo derecho y necesito que me generen el comprobante de pago corregido para el banco.",
        "tiene_adjunto": 1,
        "fecha_apertura": "2026-11-13 10:20",
    }
    mostrar_paso("1. Situación Inicial", f"Estudiante reporta en 'Fallas Técnicas TIC' un trámite de facturación.\n   Descripción: '{ticket['descripcion']}'")
    decision = agente.procesar_ticket(ticket)
    mostrar_paso("2. Acción", "El agente detecta desvío semántico, corrige a 'Procesos de Pago' y deriva a Tesorería.")
    renderizar_decision(decision, ticket)


def caso_incidente_masivo(agente: AgenteTriaje):
    imprimir_encabezado("CASO 3: DETECCIÓN NO SUPERVISADA DE INCIDENTE MASIVO (CLUSTERING)")
    print("Simulando ráfaga de 3 estudiantes reportando caída de Wi-Fi en el campus...")

    tickets_brote = [
        {"id": "BROTE_01", "formulario_elegido": "Fallas Técnicas TIC", "apoyo": "Red / Wi-Fi", "asunto": "Sin internet", "descripcion": "No hay wifi en todo el bloque C y nadie puede conectarse.", "fecha_apertura": "2026-11-13 11:00"},
        {"id": "BROTE_02", "formulario_elegido": "Fallas Técnicas TIC", "apoyo": "Red / Wi-Fi", "asunto": "Se cayó la red", "descripcion": "En el bloque C se cayó el internet de la universidad por completo.", "fecha_apertura": "2026-11-13 11:05"},
        {"id": "BROTE_03", "formulario_elegido": "Fallas Técnicas TIC", "apoyo": "Red / Wi-Fi", "asunto": "Wifi caído en el bloque", "descripcion": "Toda la red de estudiantes del bloque C no funciona, examen suspendido.", "fecha_apertura": "2026-11-13 11:10"},
    ]

    for i, t in enumerate(tickets_brote, 1):
        print(f"\n→ Ingresando ticket {i}/3: #{t['id']} ('{t['asunto']}')")
        dec = agente.procesar_ticket(t)
        if dec.es_incidente_masivo:
            print(f"  [ALERTA DBSCAN] Agrupado {t['id']} en el incidente masivo '{dec.id_incidente_masivo}'!")
        else:
            print(f"  [OK] Procesado individualmente como {dec.urgencia_final}")

    renderizar_decision(dec, tickets_brote[-1])


def modo_interactivo(agente: AgenteTriaje):
    imprimir_encabezado("MODO INTERACTIVO: PRUEBA EN VIVO")
    print("Ingresa los datos de cualquier ticket para ver al agente en acción:\n")
    asunto = input("Asunto del ticket: ").strip() or "Problema en el portal"
    descripcion = input("Descripción detallada: ").strip() or "No me deja ingresar a ver mis materias"
    form = input("Formulario elegido (default: Fallas Técnicas TIC): ").strip() or "Fallas Técnicas TIC"
    apoyo = input("Apoyo seleccionado (default: Banner): ").strip() or "Banner"

    ticket = {
        "id": "EN_VIVO_001",
        "formulario_elegido": form,
        "apoyo": apoyo,
        "asunto": asunto,
        "descripcion": descripcion,
        "tiene_adjunto": 0,
        "fecha_apertura": time.strftime("%Y-%m-%d %H:%M"),
    }

    decision = agente.procesar_ticket(ticket)
    renderizar_decision(decision, ticket)


def main():
    agente = AgenteTriaje(usar_deep_learning=True)

    if len(sys.argv) > 1:
        op = sys.argv[1].lower()
        if op == "propuesta":
            caso_propuesta(agente)
            return
        elif op == "formulario":
            caso_formulario_equivocado(agente)
            return
        elif op == "masivo":
            caso_incidente_masivo(agente)
            return
        elif op == "interactivo":
            modo_interactivo(agente)
            return

    # Si no se pasa argumento, corre los 3 casos guiados
    imprimir_encabezado("DEMOSTRACIÓN DEL AGENTE INTELIGENTE DE TRIAJE (PROYECTO FINAL IA)")
    caso_propuesta(agente)
    caso_formulario_equivocado(agente)
    caso_incidente_masivo(agente)

    print("\n" + "=" * 80)
    print("DEMOSTRACIÓN COMPLETADA EXITOSAMENTE")
    print("Tip: Para probar con texto libre interactivo ejecuta: python demo.py interactivo")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    # Si se ejecuta con el python global y existe .venv, relanza con el del venv
    # (vía main.py, que acepta los mismos comandos: "demo" e "interactivo").
    from main import reejecutar_con_venv
    reejecutar_con_venv()
    main()
