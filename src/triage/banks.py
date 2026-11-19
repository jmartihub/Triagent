"""Bancos de frases para generar tickets sintéticos en español.

Cada clave es (formulario, apoyo) con listas de síntomas para "falla" y "duda".
La opción "Otra" no tiene banco: un ticket con apoyo elegido "Otra" usa el
síntoma de su apoyo real (el estudiante no encontró su caso en la lista).
"""

FT, SC, PP, SM = (
    "Fallas Técnicas TIC",
    "Salas de Cómputo",
    "Procesos de Pago",
    "Soporte Durante Matrícula Académica",
)

SINTOMAS = {
    (FT, "Teams"): {
        "falla": [
            "no me deja unirme a las reuniones de Teams, me sale un error y se queda cargando",
            "Teams se cierra solo cada vez que abro la cámara",
            "no puedo subir mi tarea en Teams, el archivo se queda cargando y da error",
            "en Teams no me aparecen mis clases ni mis equipos",
            "al abrir el enlace de la clase aparece una página que no reconozco",
            "durante una reunión de Teams la imagen se congela por momentos",
        ],
        "duda": [
            "quisiera saber cómo instalar Teams con mi cuenta institucional",
            "no sé cómo activar la cámara en las clases de Teams",
        ],
    },
    (FT, "Red / Wi-Fi"): {
        "falla": [
            "no me conecta al wifi de la universidad, dice que no hay acceso a internet",
            "la red de la universidad está muy lenta y se cae constantemente",
            "el internet de la sala aparece conectado pero no carga ninguna página",
            "no logro conectarme a la red de estudiantes con mi usuario",
            "al conectarme al portal de la universidad varias páginas cargan de forma incompleta",
            "el portal de la red muestra una página de inicio que no reconozco",
        ],
        "duda": [
            "quisiera saber cuál es la red wifi para estudiantes y cómo conectarme",
            "me gustaría saber si hay wifi en todos los bloques",
        ],
    },
    (FT, "Banner"): {
        "falla": [
            "no puedo entrar a Banner, me dice que mi usuario es incorrecto",
            "Banner me sale en blanco después de iniciar sesión",
            "el portal de Banner da error cuando intento consultar mi horario",
            "no me carga la opción de inscripción de materias en Banner",
            "al abrir el enlace de Banner el navegador muestra una página que no reconozco",
            "la página de la evaluación tarda en cargar por momentos",
        ],
        "duda": [
            "no encuentro dónde ver mi horario en Banner",
            "quisiera saber cómo consultar mis notas en Banner",
        ],
    },
    (FT, "Correo institucional"): {
        "falla": [
            "no puedo iniciar sesión en mi correo institucional",
            "mi correo institucional no recibe los mensajes de los profesores",
            "el correo me dice que mi buzón está lleno y no puedo enviar nada",
            "no puedo enviar archivos adjuntos desde mi correo institucional",
            "recibí un enlace sospechoso que pide iniciar sesión con mi cuenta universitaria",
            "aparecieron mensajes enviados desde mi correo que yo no escribí",
        ],
        "duda": [
            "quisiera saber cómo configurar mi correo institucional en el celular",
            "cómo cambio la foto de perfil de mi correo",
        ],
    },
    (FT, "Pagos en línea"): {
        "falla": [
            "me sale un error al intentar pagar en línea y no se completa la transacción",
            "me descontaron el dinero pero el pago en línea no aparece registrado",
            "la página de pagos no carga cuando elijo PSE",
            "el botón de pagar no responde",
        ],
        "duda": [
            "quisiera saber si el pago en línea con PSE se refleja de inmediato",
            "qué bancos aparecen en la opción de pago en línea",
        ],
    },
    (FT, "Accesos y contraseñas"): {
        "falla": [
            "olvidé mi contraseña y el restablecimiento no me llega al correo",
            "mi usuario aparece bloqueado y no puedo entrar a ninguna plataforma",
            "no me carga el aula virtual con mi usuario",
            "me pide verificación y el código nunca me llega",
            "después de abrir un enlace desconocido el navegador empezó a mostrar avisos que no reconozco",
            "algunas páginas se abren solas cuando intento ingresar al portal de clases",
        ],
        "duda": [
            "quisiera saber cómo cambiar mi contraseña institucional",
            "cuánto tarda en activarse mi usuario después de matricularme",
        ],
    },
    (SC, "Acceso a software"): {
        "falla": [
            "el programa que necesito para mi clase no abre en los computadores de la sala",
            "me pide una licencia para usar el software de diseño y no me deja continuar",
            "no tengo permisos para instalar el programa que pidió el profesor",
            "el software de simulación se cierra solo al abrir mi proyecto",
            "el navegador del computador abre páginas que no solicité",
            "una ventana inesperada aparece a pantalla completa al iniciar el navegador",
            "después de instalar una extensión el navegador muestra avisos inesperados",
        ],
        "duda": [
            "quisiera saber qué programas tienen instalados en la sala de cómputo",
            "cómo puedo acceder a los programas de la sala desde mi casa",
        ],
    },
    (SC, "Funciones del computador"): {
        "falla": [
            "el computador de la sala no enciende",
            "el computador que usé se congela y se reinicia solo",
            "el teclado y el mouse del equipo no responden",
            "la pantalla del computador se ve con rayas y no se puede trabajar",
            "el navegador del equipo se quedó congelado al abrir un enlace externo",
            "aparecen avisos inesperados en el navegador del equipo",
        ],
        "duda": [
            "se puede imprimir desde los computadores de la sala",
            "quisiera saber cómo guardar mis archivos en los computadores de la sala",
        ],
    },
    (SC, "Sala virtual"): {
        "falla": [
            "no puedo entrar a la sala virtual, el enlace da error",
            "la sala virtual no me deja conectarme al escritorio remoto",
            "al iniciar sesión en la sala virtual me dice que no hay equipos disponibles",
            "la sala virtual se desconecta cada pocos minutos y pierdo mi trabajo",
            "la pantalla del escritorio remoto se congela por momentos durante una evaluación",
            "al abrir un enlace desde la sala virtual aparece una página que no reconozco",
        ],
        "duda": [
            "quisiera saber cómo funciona la sala virtual y en qué horarios está disponible",
            "cómo reservo un equipo en la sala virtual",
        ],
    },
    (PP, "Liquidación de comprobantes"): {
        "falla": [
            "no me aparece la liquidación para generar mi recibo de pago",
            "la liquidación me sale con un valor que no corresponde a mi matrícula",
            "no me deja generar el comprobante de pago, la página da error",
            "mi liquidación no incluye el descuento al que tengo derecho",
            "el portal de liquidaciones se queda en blanco después de iniciar sesión",
            "un enlace de pago que recibí no coincide con el portal institucional",
        ],
        "duda": [
            "quisiera saber cómo se calcula mi liquidación de matrícula",
            "cuándo se generan las liquidaciones del próximo semestre",
        ],
    },
    (PP, "Recibos"): {
        "falla": [
            "ya pagué pero el recibo sigue apareciendo como pendiente",
            "no puedo descargar el recibo de pago, el archivo sale dañado",
            "el recibo que generé tiene mis datos incorrectos",
            "pagué dos veces el mismo recibo por error",
            "descargué un recibo desde un enlace y no aparece en el portal institucional",
        ],
        "duda": [
            "quisiera saber cuánto demora en reflejarse un pago hecho en el banco",
            "dónde descargo el recibo de pago del semestre pasado",
        ],
    },
    (PP, "Medios de pago"): {
        "falla": [
            "el banco me rechaza el pago con el código del recibo",
            "no me aparece la opción de pagar con tarjeta",
            "intenté pagar en el banco y dicen que el recibo no existe",
            "el corresponsal bancario no reconoce el código de barras del recibo",
            "la página de pago me redirige a un formulario distinto al que uso normalmente",
        ],
        "duda": [
            "quisiera saber si puedo pagar la matrícula con tarjeta de crédito en cuotas",
            "qué bancos reciben el pago de la matrícula",
        ],
    },
    (SM, "Matrícula académica"): {
        "falla": [
            "no me deja inscribir una materia obligatoria, dice que no cumplo prerrequisitos pero sí los cumplo",
            "no me aparece abierta la inscripción de materias en mi programa",
            "me aparece un cruce de horarios que no es real",
            "el sistema no me deja retirar una materia",
            "apareció un aviso inesperado al confirmar mis materias en la inscripción",
            "el portal cerró mi sesión durante el proceso y no sé si guardó los cambios",
        ],
        "duda": [
            "quisiera saber cuántos créditos puedo inscribir este semestre",
            "cuándo abre la inscripción de materias para mi programa",
        ],
    },
    (SM, "Matrícula financiera"): {
        "falla": [
            "me aparece un bloqueo financiero por una deuda que ya pagué y no puedo matricular",
            "mi beca no aparece aplicada en la matrícula",
            "me cobran un valor adicional que no entiendo en mi estado de cuenta",
            "mi pago no se refleja y por eso no me deja matricular materias",
            "el portal financiero muestra información distinta al comprobante que descargué",
        ],
        "duda": [
            "quisiera saber cómo ver mi estado de cuenta",
            "cómo se aplican los descuentos en la matrícula",
        ],
    },
}

# --- Frases por factor de la rúbrica -------------------------------------------------
# Pueden llevar marcadores que generate.py rellena al azar:
#   {n} minutos (5-50), {h} hora del día, {d} número de días (2-5), {dia} día de la semana,
#   {evento}/{Evento} actividad con hora fija, {tramite}/{Tramite} trámite con fecha límite.
# Hay frases literales ("no puedo continuar") e implícitas ("no hay más equipos libres"):
# el modelo debe aprender el factor, no memorizar unas pocas frases.

EVENTOS = [
    "el parcial", "el quiz", "la sustentación", "el examen final", "la evaluación",
    "la exposición", "el laboratorio", "la clase", "la prueba", "el examen de inglés",
    "la entrega del proyecto", "el previo",
]
TRAMITES = [
    "el pago de la matrícula", "la inscripción de materias", "la legalización de la matrícula",
    "el pago de grado", "la entrega de documentos",
    "el retiro de materias", "la convocatoria de la beca", "el pago del curso",
]
HORAS = ["las 2", "las 3 pm", "las 5", "las 6 de la tarde", "mediodía", "las 11:59", "medianoche", "las 10"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]

ALCANCE = {
    "grupo": [
        "A todo mi grupo le pasa lo mismo.",
        "A varios compañeros de la clase les pasa igual.",
        "Somos como veinte en el salón y a todos nos sale el mismo error.",
        "No soy solo yo, mis compañeros están igual.",
        "Ninguno de los que estamos en el laboratorio puede entrar.",
        "Les pasa a todos los del curso.",
        "Mis compañeros de semestre tienen el mismo problema.",
        "En la sala ningún equipo funciona.",
        "Estamos todos los del grupo igual, nadie ha podido.",
        "Ya pregunté y a los demás también les sale.",
        "A la mitad del salón le pasa.",
        "Según el profesor, a toda la clase le sale lo mismo.",
        "Somos varios con el mismo error.",
        "a toda mi carrera le pasa",
        "Ningún compañero ha podido hacerlo.",
        "Todo el piso está igual.",
    ],
    "institucional": [
        "Parece que se cayó para toda la universidad.",
        "Nadie en el campus puede usarlo.",
        "A todos los estudiantes les aparece el mismo error.",
        "Está caído en todas las sedes.",
        "Al parecer es general, no le funciona a nadie.",
        "Es en toda la U, no solo a mí.",
        "En los grupos de WhatsApp todo el mundo dice lo mismo.",
        "Ninguna facultad tiene servicio.",
        "Se cayó el servicio completo.",
        "nadie de la universidad puede entrar",
        "Es una caída general del sistema.",
        "Tanto estudiantes como profesores estamos sin servicio.",
    ],
}

BLOQUEO = {
    True: [
        "No puedo continuar con lo que estaba haciendo.",
        "No me deja hacer absolutamente nada.",
        "Estoy completamente bloqueado.",
        "Así no puedo avanzar.",
        "No puedo cerrar la página ni volver a la actividad.",
        "El navegador no responde y no puedo continuar.",
        "La página se abre de nuevo cada vez que intento cerrarla.",
        "No he podido entrar de ninguna forma.",
        "Me saca cada vez que intento entrar.",
        "Se queda cargando y nunca abre.",
        "Me rechaza todo el tiempo.",
        "Llevo una hora intentando y nada.",
        "No hay forma de que funcione.",
        "Me sale error y no pasa de ahí.",
        "No puedo hacer el trámite.",
        "No me deja ni iniciar sesión.",
        "Intento y vuelve a fallar.",
        "Así no puedo trabajar.",
        "Se apaga apenas lo prendo.",
        "No carga nada.",
        "me tiene parado",
        "No puedo enviar nada.",
        "Me quedé por fuera.",
        "No hay manera de entrar.",
    ],
    False: [
        "No es grave, igual puedo seguir trabajando.",
        "Es más una molestia que otra cosa.",
        "No me impide trabajar pero quería reportarlo.",
        "Igual funciona, solo que lento.",
        "Funciona a ratos, se puede usar.",
        "Molesta, pero se puede usar.",
        "Al final sí me dejó, solo que se demora.",
        "No me afecta mucho.",
        "Solo lo comento para que lo revisen.",
        "Puedo seguir usándolo normal.",
        "Es un detalle, no algo urgente.",
        "Sigue funcionando, pero raro.",
    ],
}

PLAZO = {
    "inmediato": [
        "Tengo un parcial en una hora.",
        "Estoy en medio de un examen.",
        "Mi clase empieza en 15 minutos.",
        "Hoy vence el plazo para este trámite.",
        "Estoy presentando el examen ahora mismo.",
        "El parcial está en curso y debo enviarlo antes de que cierre.",
        "Me quedan pocos minutos para terminar la evaluación.",
        "La sustentación ya empezó.",
        "Tengo {evento} en {n} minutos.",
        "{Evento} empieza en {n} minutos.",
        "{Evento} es ahorita.",
        "Estoy en {evento} en este momento.",
        "Me quedan {n} minutos de {evento}.",
        "Hoy a {h} cierra {tramite}.",
        "{Tramite} vence hoy a {h}.",
        "{Tramite} se acaba hoy.",
        "Es para ya, {evento} ya empezó.",
        "En {n} min tengo {evento}.",
        "Lo necesito ya mismo.",
        "El profe está esperando.",
        "El tiempo de {evento} está corriendo.",
    ],
    "cercano": [
        "Mañana cierra el plazo.",
        "Tengo una entrega el viernes.",
        "La próxima semana tengo una sustentación.",
        "Tengo que resolverlo en los próximos días.",
        "{Tramite} cierra el {dia}.",
        "Tengo {evento} el {dia}.",
        "{Evento} es mañana.",
        "{Evento} es pasado mañana.",
        "En {d} días vence {tramite}.",
        "El plazo se vence esta semana.",
        "Tengo hasta el {dia}.",
        "Lo necesito antes del {dia}.",
        "{Tramite} es la otra semana.",
        "Me queda poco tiempo, {tramite} cierra en {d} días.",
    ],
    "ninguno": [
        "No tengo afán.",
        "No es para ya.",
        "Cuando puedan lo revisan.",
        "No hay prisa.",
        "No es urgente.",
        "Lo pueden mirar con calma.",
    ],
}

ALTERNATIVA = {
    True: [
        "Mientras tanto lo estoy haciendo desde el celular.",
        "Por ahora puedo usar el computador de un amigo.",
        "Por ahora me funciona desde otro dispositivo.",
        "Desde otro navegador sí funciona.",
        "Un compañero me presta su computador mientras tanto.",
        "Puedo ir a otra sala por ahora.",
        "Me conecté con los datos del celular.",
        "En la app sí funciona.",
        "Puedo hacerlo presencial si toca.",
        "Lo voy a mandar por correo mientras tanto.",
        "Desde la casa sí me deja.",
        "Hay otros equipos libres.",
        "puedo pagar en el banco mientras tanto",
        "El profe me deja enviarlo por otro medio.",
    ],
    False: [
        "No tengo otra forma de hacerlo.",
        "Es la única forma que tengo.",
        "No encuentro otra manera.",
        "No tengo otro computador.",
        "Los otros equipos están ocupados.",
        "Solo se puede hacer por ahí.",
        "Me queda imposible ir hasta la universidad.",
        "No tengo datos en el celular.",
        "Solo lo reciben por ese canal.",
        "No hay otra opción.",
        "Tampoco me deja desde el celular.",
        "Ya probé en otro computador y tampoco.",
    ],
}

INTROS_FALLA = [
    "", "", "", "Desde ayer ", "Desde hace unos días ", "Desde esta mañana ",
    "Hola, ", "Buenas tardes, ", "Buenos días, ", "Cordial saludo. ",
]
INTROS_DUDA = ["", "", "Hola, ", "Buenas tardes, ", "Buenos días, ", "Cordial saludo. "]
CIERRES = ["", "", "", "Gracias.", "Quedo atento.", "Muchas gracias por su ayuda.",
           "Gracias de antemano.", "porfa ayuda"]

# Los estudiantes abusan de "urgente": aparece con probabilidad apenas creciente.
P_URGENTE = {"Baja": 0.08, "Media": 0.15, "Alta": 0.25, "Crítica": 0.35}
