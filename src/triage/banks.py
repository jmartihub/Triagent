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

ALCANCE = {
    "grupo": [
        "A todo mi grupo le pasa lo mismo.",
        "A varios compañeros de la clase les pasa igual.",
        "Somos como veinte en el salón y a todos nos sale el mismo error.",
    ],
    "institucional": [
        "Parece que se cayó para toda la universidad.",
        "Nadie en el campus puede usarlo.",
        "A todos los estudiantes les aparece el mismo error.",
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
    ],
    False: [
        "No es grave, igual puedo seguir trabajando.",
        "Es más una molestia que otra cosa.",
        "No me impide trabajar pero quería reportarlo.",
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
    ],
    "cercano": [
        "Mañana cierra el plazo.",
        "Tengo una entrega el viernes.",
        "La próxima semana tengo una sustentación.",
        "Tengo que resolverlo en los próximos días.",
    ],
    "ninguno": ["No tengo afán.", "No es para ya."],
}

ALTERNATIVA = {
    True: [
        "Mientras tanto lo estoy haciendo desde el celular.",
        "Por ahora puedo usar el computador de un amigo.",
        "Por ahora me funciona desde otro dispositivo.",
    ],
    False: [
        "No tengo otra forma de hacerlo.",
        "Es la única forma que tengo.",
        "No encuentro otra manera.",
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
