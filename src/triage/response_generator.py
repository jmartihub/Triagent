"""Generador de Respuestas Preliminares para el Estudiante (Acción 3 del Agente).

Redacta automáticamente una respuesta personalizada, transparente y útil:
- Confirma la recepción del ticket y los parámetros asignados.
- Notifica si se corrigió el formulario para evitar confusiones.
- Informa el grupo técnico asignado y el tiempo estimado de atención por SLA.
- Ofrece pautas de autoservicio o mitigación inmediata según la plataforma afectada.
"""

from typing import Any, Dict, Optional


GUIAS_AUTOSERVICIO = {
    "accesos_cuentas": (
        "💡 **Paso sugerido mientras te atendemos:** Si olvidaste tu contraseña o tu usuario está bloqueado, "
        "puedes intentar el autoservicio de restablecimiento institucional en: "
        "https://micuenta.universidad.edu.co/recuperar ingresando tu documento de identidad."
    ),
    "red_wifi": (
        "💡 **Paso sugerido mientras te atendemos:** Asegúrate de conectar tu dispositivo a la red "
        "**'WIFI-ESTUDIANTES'** ingresando tu usuario institucional sin el '@universidad.edu.co'. "
        "Verifica también si tienes configurada una IP estática en los ajustes de red de tu equipo."
    ),
    "teams": (
        "💡 **Paso sugerido mientras te atendemos:** Si la aplicación de escritorio de Teams no inicia o da error, "
        "puedes acceder de inmediato a tus clases y entregas ingresando desde el navegador en modo incógnito "
        "a través de: https://teams.microsoft.com con tu correo institucional."
    ),
    "banner": (
        "💡 **Paso sugerido mientras te atendemos:** Si el portal de Banner se queda en blanco o no carga tu horario, "
        "te recomendamos borrar la memoria caché y cookies del navegador o intentar ingresar mediante Google Chrome / Mozilla Firefox."
    ),
    "pagos_linea": (
        "💡 **Información importante sobre pagos:** Si tu dinero fue debitado a través de PSE pero el recibo sigue "
        "pendiente, ten en cuenta que el sistema bancario puede tardar entre 2 y 24 horas en conciliar el pago. "
        "Por favor ten a mano el comprobante de débito con el código CUS por si el técnico requiere verificarlo."
    ),
    "computadores_fisicos": (
        "💡 **Aviso de sala:** Si te encuentras en una sala de cómputo presencial y el equipo presenta fallas de hardware, "
        "por favor notifícalo también al monitor de sala en el mostrador para que te reubique en una estación operativa."
    ),
    "software_salas": (
        "💡 **Aviso de licencias:** Si requieres usar software especializado (AutoCAD, SPSS, MATLAB, etc.) fuera de sala, "
        "recuerda que puedes utilizar el servicio de Sala Virtual (VDI) para conectarte remotamente a un equipo con licencia activa."
    ),
}


class GeneradorRespuestaPreliminar:
    """Construye la comunicación inicial dirigida al estudiante."""

    def generar(
        self,
        id_ticket: str,
        formulario_elegido: str,
        formulario_correcto: str,
        hubo_reenrutamiento: bool,
        urgencia: str,
        grupo_nombre: str,
        tecnico_nombre: str,
        plataforma_id: str,
        horas_sla: float,
        horas_estimadas: Optional[float] = None,
        es_duplicado: bool = False,
        id_ticket_original: Optional[str] = None,
        es_incidente_masivo: bool = False,
    ) -> str:
        lineas = []
        lineas.append(f"Hola, hemos recibido tu solicitud con identificador **#{id_ticket}**.")

        # Notificación de incidente masivo conocido
        if es_incidente_masivo:
            lineas.append(
                "\n📢 **Aviso de Evento General:** Nuestro sistema de monitoreo ha identificado que "
                "otros usuarios también están reportando una interrupción similar en este momento. "
                "Tu caso ha sido vinculado al reporte general del incidente para darle máxima prioridad "
                "con el equipo de infraestructura."
            )

        # Notificación de duplicado
        if es_duplicado and id_ticket_original:
            lineas.append(
                f"\nℹ️ **Nota de seguimiento:** Detectamos que ya tenías un ticket abierto (**#{id_ticket_original}**) "
                f"relacionado con esta misma solicitud. Ambos casos han sido asociados para que el técnico tenga todo el historial."
            )

        # Advertencia amigable de corrección de formulario
        if hubo_reenrutamiento and formulario_elegido != formulario_correcto:
            lineas.append(
                f"\n🔄 **Ajuste de Categoría:** Notamos que al crear la solicitud seleccionaste el formulario "
                f"*{formulario_elegido}*, pero por la naturaleza de tu caso corresponde a *{formulario_correcto}*. "
                f"Para agilizar tu atención, el agente ha corregido la categoría y enrutado tu caso al equipo correspondiente "
                f"sin que tengas que volver a llenar el formulario."
            )

        # Datos de triaje y asignación
        lineas.append(
            f"\n📋 **Detalles de tu asignación:**\n"
            f"- **Urgencia asignada:** {urgencia}\n"
            f"- **Área técnica:** {grupo_nombre}\n"
            f"- **Especialista asignado:** {tecnico_nombre}\n"
            f"- **Tiempo máximo de atención (SLA):** {horas_sla} horas"
        )

        if horas_estimadas:
            lineas.append(f"- **Tiempo estimado según cola actual:** ~{horas_estimadas} horas")

        # Recomendación de autoservicio
        guia = GUIAS_AUTOSERVICIO.get(plataforma_id)
        if guia:
            lineas.append(f"\n{guia}")

        lineas.append(
            "\nEl especialista asignado revisará tu caso y te responderá por este mismo medio. "
            "Gracias por comunicarte con la Mesa de Ayuda de TI."
        )

        return "\n".join(lineas)
