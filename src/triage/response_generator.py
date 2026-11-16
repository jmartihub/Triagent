"""Generador de Respuestas Preliminares para el Estudiante (Accion 3 del Agente).

Redacta de forma sobria y profesional una respuesta con:
- Confirmacion de recepcion y parametros de ticket.
- Aviso formal si se corrigio el formulario de entrada.
- Informacion del especialista asignado y politica SLA.
- Pautas de autoservicio segun la plataforma afectada.
"""

from typing import Any, Dict, Optional


GUIAS_AUTOSERVICIO = {
    "accesos_cuentas": (
        "[Paso sugerido mientras te atendemos]: Si olvidaste tu contraseña o tu usuario está bloqueado, "
        "puedes intentar el autoservicio de restablecimiento institucional en: "
        "https://micuenta.universidad.edu.co/recuperar ingresando tu documento de identidad."
    ),
    "red_wifi": (
        "[Paso sugerido mientras te atendemos]: Asegúrate de conectar tu dispositivo a la red "
        "'WIFI-ESTUDIANTES' ingresando tu usuario institucional sin el dominio @universidad.edu.co. "
        "Verifica también si tienes configurada una IP estática en los ajustes de red de tu equipo."
    ),
    "teams": (
        "[Paso sugerido mientras te atendemos]: Si la aplicación de escritorio de Teams no inicia o da error, "
        "puedes acceder a tus clases y entregas ingresando desde el navegador en modo incógnito "
        "a través de: https://teams.microsoft.com con tu correo institucional."
    ),
    "banner": (
        "[Paso sugerido mientras te atendemos]: Si el portal de Banner no carga tu horario, "
        "te recomendamos borrar la memoria caché y cookies del navegador o intentar ingresar mediante Google Chrome / Mozilla Firefox."
    ),
    "pagos_linea": (
        "[Informacion sobre pagos]: Si tu dinero fue debitado a través de PSE pero el recibo sigue "
        "pendiente, ten en cuenta que el sistema bancario puede tardar entre 2 y 24 horas en conciliar el pago. "
        "Por favor ten a mano el comprobante de débito con el código CUS por si el técnico requiere verificarlo."
    ),
    "computadores_fisicos": (
        "[Aviso de sala]: Si te encuentras en una sala de cómputo presencial y el equipo presenta fallas de hardware, "
        "por favor notifícalo también al monitor de sala en el mostrador para que te reubique en una estación operativa."
    ),
    "software_salas": (
        "[Aviso de licencias]: Si requieres usar software especializado (AutoCAD, SPSS, MATLAB, etc.) fuera de sala, "
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
        lineas.append(f"Hola, hemos recibido tu solicitud con identificador #{id_ticket}.")

        # Notificación de incidente masivo conocido
        if es_incidente_masivo:
            lineas.append(
                "\n[Aviso de Evento General]: Nuestro sistema de monitoreo ha identificado reportes "
                "concurrentes relacionados con una interrupción similar en este momento. "
                "Tu caso ha sido vinculado al reporte general del incidente para atención prioritaria."
            )

        # Notificación de duplicado
        if es_duplicado and id_ticket_original:
            lineas.append(
                f"\n[Nota de seguimiento]: Se identificó una solicitud abierta previa (#{id_ticket_original}) "
                f"relacionada con este requerimiento. Ambos casos han sido asociados en el expediente."
            )

        # Advertencia amigable de corrección de formulario
        if hubo_reenrutamiento and formulario_elegido != formulario_correcto:
            lineas.append(
                f"\n[Ajuste de Categoria]: Al crear la solicitud seleccionaste el formulario "
                f"'{formulario_elegido}', pero por la naturaleza técnica del caso corresponde a '{formulario_correcto}'. "
                f"Para agilizar tu atención, el sistema ha corregido la categoría y derivado el caso al equipo responsable."
            )

        # Datos de triaje y asignación
        lineas.append(
            f"\n[Detalles de Asignacion]:\n"
            f"- Urgencia asignada: {urgencia}\n"
            f"- Area tecnica: {grupo_nombre}\n"
            f"- Especialista asignado: {tecnico_nombre}\n"
            f"- Tiempo maximo de atencion (SLA): {horas_sla} horas"
        )

        if horas_estimadas:
            lineas.append(f"- Tiempo estimado segun cola actual: ~{horas_estimadas} horas")

        # Recomendación de autoservicio
        guia = GUIAS_AUTOSERVICIO.get(plataforma_id)
        if guia:
            lineas.append(f"\n{guia}")

        lineas.append(
            "\nEl especialista asignado revisará tu caso y te responderá por este medio. "
            "Mesa de Ayuda de Tecnologías de la Información."
        )

        return "\n".join(lineas)
