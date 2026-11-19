# Triagent — Agente inteligente de triaje y priorización de tickets (Tooli / GLPI)

**Proyecto final del curso de Inteligencia Artificial** · Autores: Juan Martínez y Santiago Payares

Triagent es un agente **híbrido neuro-simbólico** que recibe las solicitudes que los estudiantes envían a la mesa de ayuda universitaria (formularios de Tooli, tickets de GLPI) y, para cada una:

1. **Asigna una urgencia** (Baja, Media, Alta o Crítica) combinando un clasificador de ML con reglas lógicas explicables.
2. **Corrige el formulario** cuando el estudiante eligió una categoría equivocada.
3. **Enruta** el ticket al grupo resolutor y al técnico adecuados según una ontología del dominio.
4. **Detecta duplicados e incidentes masivos** (caídas del campus) mediante clustering no supervisado.
5. **Estima el tiempo de resolución** y el riesgo de incumplir el SLA.
6. **Redacta una respuesta preliminar** para el estudiante y la registra en GLPI.
7. **Aprende de las correcciones** que hacen los técnicos desde el dashboard (human-in-the-loop).

> **Aviso:** los modelos se entrenan con datos sintéticos y se evalúan además con solo 24 tickets escritos a mano. Triagent es un prototipo académico: sus decisiones deben revisarse por una persona y no sustituyen a los servicios de emergencia.

---

## Contenido

- [Inicio rápido](#inicio-rápido)
- [Comandos](#comandos)
- [Cómo decide el agente](#cómo-decide-el-agente)
- [Técnicas de IA](#técnicas-de-ia)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Datos](#datos)
- [Evaluación experimental](#evaluación-experimental)
- [Dashboard web y API](#dashboard-web-y-api)
- [Integración con GLPI](#integración-con-glpi)
- [Pruebas](#pruebas)
- [Limitaciones conocidas](#limitaciones-conocidas)

---

## Inicio rápido

Requisitos: **Python 3.10+** (probado con 3.14) y, solo para el dashboard, **Docker Desktop/Engine**.

```bash
# 1. Crear y activar un entorno virtual
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows (PowerShell / cmd)

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Demostración guiada por consola (no necesita Docker ni GLPI)
python main.py demo
```

Los modelos ya entrenados están incluidos en `models/`, por lo que la demo funciona sin reentrenar. Para usar el dashboard conectado a GLPI, sigue primero la sección [Integración con GLPI](#integración-con-glpi) y luego ejecuta `python main.py web`.

---

## Comandos

Todos los comandos se ejecutan desde la raíz del proyecto con `python main.py <comando>`.

| Comando | Qué hace | Necesita GLPI |
| :--- | :--- | :---: |
| `demo` *(por defecto)* | Demostración guiada con tickets de ejemplo. | No |
| `interactivo` | Escribe tickets por teclado y ve la decisión del agente. | No |
| `web [puerto]` | Levanta GLPI con Docker Compose y abre el dashboard en `http://localhost:5000`. | Sí |
| `generate` | Genera `data/tickets_sinteticos.csv` (6.000 tickets). | No |
| `train` | Entrena y evalúa el modelo clásico (TF-IDF + Regresión Logística). | No |
| `deep` | Entrena y evalúa la red neuronal MLP. | No |
| `sla` | Genera el histórico de SLA y compara modelos de regresión. | No |
| `evaluar` | Compara modelos, reglas y agente completo en todos los conjuntos (`reports/evaluacion.json`). | No |
| `all` | Ejecuta `generate` → `train` → `deep` → `sla` → `evaluar` en orden. | No |

Las métricas de entrenamiento se escriben en `reports/metrics.json` y `reports/metrics_deep.json`; los modelos, en `models/*.joblib`.

---

## Cómo decide el agente

El orquestador ([`src/triage/agent.py`](src/triage/agent.py)) sigue el ciclo de agente de Russell & Norvig: **percibir → razonar → actuar → recordar**.

```
 Ticket (formulario elegido, apoyo, asunto, descripción, fecha)
   │
   ▼
 1. PERCEPCIÓN ───────────────────────────────────────────────────────────────
   • Clasificadores ML/DL → urgencia y formulario correcto + confianza.
   • Extracción de factores desde el texto (frases de config/senales.yaml):
       tipo (falla/duda) · alcance (individual/grupo/institucional)
       bloquea (sí/no) · plazo (inmediato/cercano/ninguno) · alternativa (sí/no)
   • Señales especiales: ticket ya resuelto, riesgo físico, navegador bloqueado en examen.
   │
   ▼
 2. RAZONAMIENTO (en este orden de precedencia) ──────────────────────────────
   a. Motor FOL: encadenamiento hacia adelante sobre los factores.
      Si varias reglas concluyen urgencias distintas, gana la más alta.
      Si la confianza del ML < 0.55 → revisión humana.
   b. Memoria de casos (CBR): si un técnico corrigió un ticket similar
      (similitud coseno ≥ 0.55), se adopta su corrección más reciente.
      Una urgencia Crítica no se rebaja así: queda en revisión humana.
   c. Anulaciones de seguridad: riesgo físico o navegador bloqueado durante
      una evaluación → Crítica + escalamiento + revisión humana.
   d. Formulario: se corrige si el modelo predice otro con confianza ≥ 0.60.
   e. Ontología: grupo resolutor, técnico y SLA según plataforma y urgencia.
   f. DBSCAN: ≥ 3 reportes similares de falla bloqueante en 3 h → incidente
      masivo, escalado a Crítica. Duplicados se vinculan al ticket original.
   g. Regresión: horas estimadas de resolución y nivel de riesgo de SLA.
   │
   ▼
 3. ACCIÓN ───────────────────────────────────────────────────────────────────
   • Urgencia final, formulario final, técnico asignado.
   • Respuesta preliminar al estudiante (SLA, autoservicio, aviso de duplicado).
   • En el dashboard: actualización del ticket y seguimiento en GLPI.
   │
   ▼
 4. MEMORIA ──────────────────────────────────────────────────────────────────
   • Trabajo: buffer temporal de tickets recientes para el clustering.
   • Largo plazo: data/feedback_log.jsonl con las correcciones de los técnicos.
```

El resultado es un `DecisionAgente` con la urgencia, el enrutamiento, el SLA, los indicadores de duplicado/incidente masivo, la respuesta preliminar y la **traza de justificación** (reglas disparadas y motivos), de modo que cada decisión es auditable.

### Rúbrica de urgencia

La urgencia "correcta" se define en [`src/triage/rubric.py`](src/triage/rubric.py) a partir de los cinco factores. Es la misma función que etiqueta los datos sintéticos y en la que se basan las reglas FOL:

| Situación | Urgencia |
| :--- | :--- |
| Afecta a un grupo o a toda la institución, bloquea y no hay alternativa | Crítica |
| Afecta a un grupo o a toda la institución (resto de casos) | Alta |
| Falla individual bloqueante, plazo inmediato, sin alternativa | Crítica |
| Falla individual bloqueante, plazo inmediato con alternativa, o sin plazo y sin alternativa | Alta |
| Falla individual bloqueante con plazo cercano | Alta (sin alternativa) / Media (con alternativa) |
| Falla individual bloqueante sin plazo, con alternativa | Media |
| Duda o falla no bloqueante con algún plazo | Media |
| Duda o falla no bloqueante sin plazo | Baja |

Las señales explícitas de peligro físico (por ejemplo, una extremidad atrapada o dificultad para respirar) fuerzan prioridad Crítica, revisión humana y una respuesta que indica pedir ayuda presencial inmediata, incluso si el ticket es duplicado.

---

## Técnicas de IA

| Técnica | Módulo | Función en el agente |
| :--- | :--- | :--- |
| **Aprendizaje supervisado** | [`train.py`](src/triage/train.py) | Modelo base: TF-IDF de n-gramas de palabras y caracteres + Regresión Logística balanceada. |
| **Deep Learning** | [`deep_model.py`](src/triage/deep_model.py) | MLP densa (128 → 64, ReLU, Adam, L2, parada temprana). Es el modelo que usa el dashboard. |
| **Lógica de primer orden** | [`fol_rules.py`](src/triage/fol_rules.py) | Cláusulas de Horn con encadenamiento hacia adelante; actúa como red de seguridad explicable sobre el ML. |
| **Ontología** | [`ontology.py`](src/triage/ontology.py), [`config/ontology.yaml`](config/ontology.yaml) | Plataformas → grupos resolutores → técnicos y políticas de SLA. |
| **Aprendizaje no supervisado** | [`clustering.py`](src/triage/clustering.py) | DBSCAN y similitud coseno en ventana de 3 h para duplicados e incidentes masivos. |
| **Regresión** | [`sla_regression.py`](src/triage/sla_regression.py) | Compara Lineal, Polinomial (grado 2) y Ridge para estimar horas de resolución y riesgo de SLA. |
| **Razonamiento basado en casos** | [`agent.py`](src/triage/agent.py) (`MemoriaAgente`) | Reutiliza correcciones humanas de tickets similares. |

---

## Estructura del repositorio

```
Triagent/
├── main.py                  # Punto de entrada (CLI)
├── demo.py                  # Demo guiada y modo interactivo
├── requirements.txt         # Dependencias (scikit-learn fijado por los modelos)
├── requirements-dev.txt     # + pytest
├── pyproject.toml           # Configuración de pytest
├── .env.example             # Plantilla de credenciales de GLPI
├── .github/workflows/       # CI: pytest en cada push / PR
├── config/
│   ├── ontology.yaml        # Plataformas, grupos, técnicos y SLA
│   ├── senales.yaml         # Frases que detectan tipo, alcance, bloqueo, plazo...
│   └── taxonomy.yaml        # Formularios y opciones de "apoyo" de Tooli
├── src/triage/
│   ├── agent.py             # Orquestador: percibir → razonar → actuar → memoria
│   ├── rubric.py            # Definición de la urgencia a partir de factores
│   ├── fol_rules.py         # Motor de inferencia FOL
│   ├── ontology.py          # Enrutamiento técnico
│   ├── clustering.py        # Duplicados e incidentes masivos (DBSCAN)
│   ├── sla_regression.py    # Estimación de tiempos y riesgo de SLA
│   ├── train.py             # Modelo clásico TF-IDF + Logística
│   ├── deep_model.py        # Red neuronal MLP
│   ├── generate.py          # Generador de tickets sintéticos
│   ├── banks.py             # Bancos de frases para el generador
│   ├── response_generator.py# Respuesta preliminar al estudiante
│   ├── glpi_client.py       # Cliente de la API REST legacy de GLPI (+ mock)
│   ├── web_dashboard.py     # Servidor HTTP y API del dashboard
│   └── static/index.html    # Interfaz del dashboard (HTML/CSS/JS)
├── data/
│   ├── tickets_sinteticos.csv   # 6.000 tickets generados
│   ├── gold_manual.csv          # 24 tickets escritos a mano (6 por urgencia)
│   ├── historico_sla.csv        # 3.000 registros sintéticos de resolución
│   └── feedback_log.jsonl       # Correcciones humanas (local, no versionado)
├── models/                  # Modelos entrenados (.joblib)
├── reports/                 # Métricas de evaluación (.json)
├── docker/docker-compose.yml# GLPI + MariaDB
├── tests/                   # Pruebas (scripts ejecutables)
└── entregables/             # Documento y diapositivas de la sustentación
```

---

## Datos

- **Tickets sintéticos** (`generate.py` + `banks.py`): 6.000 tickets con la forma de los formularios de Tooli (Fallas Técnicas TIC, Salas de Cómputo, Procesos de Pago, Soporte Durante Matrícula). Se añade ruido realista: pistas omitidas, errores de tipeo, registro informal, un 12 % de formularios equivocados y un 5 % de ruido en la etiqueta.
- **Gold de desarrollo** (`gold_manual.csv`): 24 tickets redactados a mano, seis por nivel de urgencia. Las reglas se ajustaron mirando estos tickets, así que ya no sirven como medida independiente.
- **Gold de validación** (`gold_holdout.csv`): 80 tickets redactados a mano (20 por urgencia, 5 con formulario equivocado) con los cinco factores etiquetados; la urgencia se obtiene aplicando la rúbrica a esos factores. **No se debe usar para ajustar reglas ni modelos**: si se ajusta mirando sus errores, deja de medir. Se escribieron conociendo el sistema, así que sigue siendo menos exigente que tickets reales.
- **Histórico de SLA** (`historico_sla.csv`): generado con una función conocida de urgencia, complejidad y carga de la cola.

Más ejemplos sintéticos no garantizan más precisión: el texto proviene de plantillas, así que las métricas sobre el conjunto sintético son optimistas.

---

## Evaluación experimental

### Agente completo vs. componentes

`python main.py evaluar` compara cuatro estrategias sobre los mismos tickets: el modelo clásico, el MLP, las **reglas solas** (rúbrica sobre los factores que detecta la percepción) y el **agente** completo (lo que usa el dashboard).

| Estrategia | Sintético (n=1.200) | Gold desarrollo (n=24) | Gold validación (n=80) | Críticos subestimados (validación) ↓ |
| :--- | :---: | :---: | :---: | :---: |
| Regresión Logística | 0.764 | 0.625 | 0.375 | 20 % |
| Red MLP | **0.800** | 0.667 | **0.438** | 35 % |
| Reglas solas | 0.623 | 1.000 | **0.438** | 60 % |
| Agente completo | 0.623 | 1.000 | **0.438** | 60 % |

*Exactitud de urgencia.* Lecturas:

- **El agente decide igual que las reglas.** La urgencia final sale del motor FOL, que reproduce la rúbrica sobre los factores percibidos; el modelo solo influye cuando su confianza es baja.
- **El 100 % en el gold de desarrollo es sobreajuste**: en tickets nuevos el agente baja a 44 % y deja pasar como Baja o Media el 60 % de los Críticos.
- **El cuello de botella es la percepción.** Exactitud de los factores detectados en el gold de validación: tipo 0.94, alcance 0.80, alternativa 0.82, plazo 0.70, bloquea 0.64. Frases como "hoy cierran", "ahorita", "quedan 40 min" o "a nadie le abre" no están en `config/senales.yaml`.

### Clasificación de urgencia (solo modelos)

| Modelo | Conjunto | Exactitud | Macro-F1 | Críticos subestimados ↓ |
| :--- | :--- | :---: | :---: | :---: |
| Línea base: todo "Media" | Sintético | 0.1146 | — | — |
| Regresión Logística (TF-IDF) | Sintético (test, n=1.200) | 0.7642 | 0.7219 | **6.25 %** |
| Red MLP | Sintético (test, n=1.200) | **0.8000** | **0.7492** | 7.29 % |
| Regresión Logística (TF-IDF) | Gold manual (n=24) | 0.6250 | 0.5333 | 33.33 % |
| Red MLP | Gold manual (n=24) | **0.6667** | **0.6199** | **16.67 %** |

"Críticos subestimados" es la fracción de tickets Críticos que el modelo predijo como Baja o Media (menor es mejor; no cuenta las predicciones Alta). En el conjunto gold cada clase tiene solo seis tickets, así que un ticket equivale a ~17 puntos porcentuales: los resultados son preliminares. Estas cifras corresponden al **modelo solo**; la tabla anterior compara con el agente completo.

### Formulario correcto

Ambos modelos obtienen 1.00 de exactitud en el conjunto sintético y 0.9167 en el gold.

### Regresión de SLA

`python main.py sla` compara los tres modelos y guarda el mejor. El modelo polinomial alcanza R² ≈ 0.98, pero el histórico se generó con una función cuadrática conocida, por lo que ese valor mide la capacidad de recuperar esa función, no el rendimiento con tiempos reales.

---

## Dashboard web y API

`python main.py web` sirve un dashboard en `http://localhost:5000` con navegación lateral, métricas y actividad reciente, simulador de solicitudes, cola de GLPI y catálogo de especialistas. Tiene modo claro/oscuro (recuerda la preferencia) y se adapta a pantallas pequeñas.

- El resumen considera hasta 1.000 tickets recientes.
- El indicador de cumplimiento de SLA solo se calcula cuando GLPI proporciona la fecha límite y la fecha de resolución.
- **Corregir** (en la cola) actualiza únicamente la urgencia del ticket en GLPI y después guarda la corrección para el aprendizaje local. No cambia el estado del ticket. Si GLPI rechaza el cambio, no se registra la corrección.

Endpoints que usa el dashboard:

| Método | Ruta | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/dashboard` | Tickets de GLPI y métricas resumidas. |
| `GET` | `/api/tickets` | Tickets de GLPI. |
| `GET` | `/api/ontologia` | Técnicos y políticas de SLA. |
| `POST` | `/api/triajar` | Crea el ticket en GLPI, lo procesa con el agente y escribe urgencia, técnico y respuesta preliminar. Cuerpo: `asunto`, `descripcion`, `formulario_elegido`, `apoyo`. |
| `POST` | `/api/feedback` | Corrige la urgencia en GLPI y la guarda en la memoria. Cuerpo: `id_ticket`, `urgencia_corregida`. |

> El dashboard no tiene autenticación, así que por defecto solo acepta conexiones desde el mismo equipo (`127.0.0.1`). Para abrirlo a la red local (por ejemplo, en una sustentación) define `TRIAGENT_HOST=0.0.0.0`, y hazlo solo en una red de confianza.

El tamaño de la cola (tickets no resueltos ni cerrados) que ve el dashboard alimenta el estimador de SLA del agente; mientras no se haya cargado, se asume una cola de 12 tickets.

---

## Integración con GLPI

`python main.py web` ejecuta `docker compose up -d`, espera a que GLPI responda en el puerto 8080 y luego inicia el dashboard. Docker Desktop/Engine debe estar abierto; el comando no lo inicia por sí mismo. También puedes levantar los servicios a mano:

```bash
docker compose -f docker/docker-compose.yml up -d
```

- GLPI Web: `http://localhost:8080` (credenciales iniciales `glpi` / `glpi`)
- API REST legacy: `http://localhost:8080/apirest.php`

Las imágenes están fijadas por digest y la versión de GLPI se fija con `VERSION_GLPI` (12.0.2) en `docker/docker-compose.yml`, para que todo el equipo instale exactamente la misma versión.

### Configuración inicial (una sola vez)

La instalación de GLPI y su configuración de API se guardan en volúmenes de Docker. **No uses `docker compose down -v`** si quieres conservarlas.

1. Completa el instalador web. Para MariaDB usa servidor `mariadb`, base de datos `glpi_db`, usuario `glpi_user` y contraseña `glpi_secure_password`.
2. Activa la **API legacy** en **Configuración → General → API**.
3. Crea y activa un **cliente API** que permita la IP de origen del agente y copia su **App-Token**. Si GLPI responde `ERROR_NOT_ALLOWED_IP`, autoriza la IP que aparece en el error.
4. En las preferencias del usuario de GLPI, genera o copia el **User-Token** de API. Si el inicio con contraseña está deshabilitado, este token es obligatorio.
5. Crea el archivo de configuración local y reemplaza los tokens:

   ```bash
   cp .env.example .env
   ```

   | Variable | Valor |
   | :--- | :--- |
   | `GLPI_API_URL` | URL de la API legacy (por defecto `http://localhost:8080/apirest.php`). |
   | `GLPI_APP_TOKEN` | App-Token del cliente API. |
   | `GLPI_USER_TOKEN` | User-Token del perfil. Si está definido, se usa en lugar de usuario/contraseña. |
   | `GLPI_USER`, `GLPI_PASSWORD` | Solo si no usas `GLPI_USER_TOKEN` (autenticación Basic). |
   | `TRIAGENT_HOST` | Opcional. Interfaz del dashboard; por defecto `127.0.0.1`. |

   Los valores pueden ir sin comillas o entre comillas simples o dobles. Las variables ya definidas en la terminal tienen prioridad sobre `.env`. El archivo está excluido de Git: no compartas su contenido.

6. Inicia el dashboard:

   ```bash
   python main.py web
   ```

El usuario o token configurado debe tener permiso para crear y actualizar tickets. Si la conexión falla, el servidor **no** pasa a modo simulado: muestra el error de GLPI para que corrijas la configuración. El cliente simulado (`ClienteGLPI(modo_mock=True)`) solo se usa en las pruebas.

---

## Pruebas

Las pruebas no requieren GLPI real (usan el cliente simulado). Con pytest:

```bash
pip install -r requirements-dev.txt
pytest
```

GitHub Actions ejecuta `pytest` en cada push a `main` y en cada pull request ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)).

Cada archivo también puede ejecutarse por separado como script:

```bash
python tests/test_rubric.py           # Rúbrica de urgencia
python tests/test_reasoning.py        # Ontología y motor FOL
python tests/test_priority_cases.py   # Agente vs. los 24 tickets del gold de desarrollo
python tests/test_clustering_cases.py # Duplicados e incidentes masivos
python tests/test_agent_full.py       # Ciclo completo del agente + GLPI mock
python tests/test_memoria.py          # Memoria de correcciones humanas (CBR)
python tests/test_evaluate.py         # Evaluación y consistencia del gold de validación
python tests/test_glpi_client.py      # Cliente de GLPI
python tests/test_dashboard.py        # Endpoints del dashboard
python tests/test_main.py             # Arranque y carga de .env
```


---

## Limitaciones conocidas

- **Datos:** el entrenamiento es sintético y la evaluación con texto humano se limita a 104 tickets escritos por el equipo. Antes de un uso real se necesita un conjunto etiquetado de tickets reales.
- **Rendimiento en tickets nuevos:** en el gold de validación el agente acierta el 44 % de las urgencias (ver [Evaluación experimental](#evaluación-experimental)).
- **Extracción de factores por palabras clave:** tipo, alcance, bloqueo, plazo y alternativa se detectan con las listas de frases de [`config/senales.yaml`](config/senales.yaml). Expresiones no contempladas pueden pasar desapercibidas; se pueden agregar frases en ese archivo sin tocar el código.
- **Memoria de casos:** una corrección humana sobre un ticket similar (umbral 0.55) reemplaza la urgencia deducida por las reglas. Solo cuenta la corrección más reciente de cada ticket, y una urgencia Crítica nunca se rebaja automáticamente: se mantiene y se pide revisión humana.
- **SLA:** el histórico es sintético y la carga de la cola de entrenamiento va de 1 a 44 tickets; con colas mucho mayores el modelo extrapola.
- **Seguridad:** el dashboard no tiene autenticación y las contraseñas de la base de datos están en `docker-compose.yml`. No lo expongas fuera de un entorno local.
- **Modelos serializados:** los `.joblib` dependen de la versión de scikit-learn con que se entrenaron (fijada en `requirements.txt`); si cambias de versión, reentrena con `python main.py all`.
- **Memoria local:** `data/feedback_log.jsonl` no se versiona; cada equipo acumula sus propias correcciones.
