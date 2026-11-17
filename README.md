# Agente inteligente de triaje y priorización de tickets (Tooli / GLPI)

**Proyecto final del curso de Inteligencia Artificial**

Autores: Juan Martínez y Santiago Payares

Sistema híbrido neuro-simbólico para clasificar, priorizar y enrutar solicitudes de la mesa de ayuda universitaria. Integra percepción, razonamiento, acción y memoria para procesar tickets de Tooli y GLPI.

---

## Inicio rápido

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar la demostración guiada
python main.py demo

# Iniciar el dashboard conectado a GLPI
python main.py web
```

Otros comandos disponibles:

```bash
# Procesar tickets desde la consola
python main.py interactivo

# Entrenar y evaluar todos los modelos
python main.py all

# Ejecutar las pruebas
python tests/test_rubric.py
python tests/test_reasoning.py
python tests/test_agent_full.py
python tests/test_clustering_cases.py
python tests/test_dashboard.py
python tests/test_priority_cases.py
python tests/test_glpi_client.py
python tests/test_main.py
```

El dashboard ofrece navegación lateral, resumen de métricas y actividad reciente, simulador de solicitudes, cola de GLPI y catálogo de especialistas. El resumen considera hasta 1.000 tickets recientes. El indicador de SLA se calcula únicamente cuando GLPI proporciona tanto la fecha límite como la fecha de resolución. El panel ofrece modos claro y oscuro, conserva la preferencia de tema y adapta la interfaz a pantallas pequeñas.

La asignación de prioridad considera señales de interrupción, diferencia consultas de fallas y distingue fechas futuras de actividades inmediatas. Una falla grupal bloqueante con alternativa temporal se clasifica como Alta; sin alternativa, como Crítica. `tests/test_priority_cases.py` compara las reglas con las 24 muestras de `data/gold_manual.csv`. Esta evaluación mide ese conjunto y no garantiza el mismo rendimiento con tickets reales.

Comandos de entrenamiento individuales:

- `python main.py deep`: entrena y evalúa la red neuronal multicapa.
- `python main.py sla`: compara modelos de regresión para estimar tiempos de resolución y riesgo de SLA.
- `python main.py generate`: genera `data/tickets_sinteticos.csv`.
- `python main.py train`: entrena el modelo supervisado TF-IDF y Regresión Logística.

---

## Arquitectura del agente

```
        ┌────────────────────────────────────────────────────────┐
        │                 ENTORNO (Tooli / GLPI)                 │
        │   Estudiante envía ticket (Asunto, Descripción, etc.)  │
        └──────────────────────────┬─────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. PERCEPCIÓN                                                           │
│  • Supervisado & Deep Learning (MLP con capas ocultas 128 -> 64):       │
│    - Clasificación probabilística de Urgencia y Formulario correcto.    │
│    - Extracción de factores latentes del texto libre y cálculo de duda. │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. RAZONAMIENTO Y PLANIFICACIÓN                                         │
│  • Ontología de Dominio (config/ontology.yaml, src/triage/ontology.py): │
│    - Modela Plataformas, Grupos Resolutores, Técnicos y Políticas SLA.  │
│  • Motor de Lógica de Primer Orden - FOL (src/triage/fol_rules.py):     │
│    - Cláusulas de Horn con encadenamiento hacia adelante.               │
│    - Red de Seguridad Explicable: rescata casos críticos subestimados   │
│      por el modelo de ML o retiene en revisión si la confianza es baja. │
│  • Modelo No Supervisado - Clustering (src/triage/clustering.py):       │
│    - DBSCAN sobre ventana temporal para detectar duplicados y caídas    │
│      masivas en campus (Outages).                                       │
│  • Modelo Estadístico de Regresión (src/triage/sla_regression.py):      │
│    - Estima tiempo de resolución en horas y evalúa el riesgo de SLA.    │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. ACCIÓN (Efectores y Resultados Verificables)                         │
│  • Acción 1: Fija la urgencia definitiva (Crítica, Alta, Media, Baja).  │
│  • Acción 2: Enruta al técnico especialista adecuado según la ontología.│
│  • Acción 3: Genera una respuesta preliminar personalizada con SLA y    │
│    guías de autoservicio para el estudiante.                            │
│  • Re-enrutamiento: Corrige el formulario si el estudiante se equivocó. │
│  • Cliente GLPI: Escribe los resultados por API REST / Mock de prueba.  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. MEMORIA Y APRENDIZAJE                                                │
│  • Memoria de trabajo: Buffer temporal para análisis no supervisado.    │
│  • Memoria a largo plazo: data/feedback_log.jsonl para capturar         │
│    correcciones de técnicos humanos (Human-in-the-loop).                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Técnicas de inteligencia artificial

| Técnica | Módulo | Función |
| :--- | :--- | :--- |
| **Lógica de Primer Orden (FOL)** | `src/triage/fol_rules.py` | Reglas deductivas de Horn para deducir urgencia y actuar como **red de seguridad auditada** cuando el modelo ML se equivoca en un caso crítico. |
| **Ontologías** | `src/triage/ontology.py`, `config/ontology.yaml` | Grafo jerárquico de conocimiento: mapea plataformas (Teams, Banner, Wi-Fi) a grupos de soporte, técnicos y políticas de SLA. |
| **Deep Learning** | `src/triage/deep_model.py` | Red Neuronal Multicapa (MLP) densa (128 $\to$ 64 neuronas) con activaciones ReLU y optimizador Adam para capturar relaciones semánticas no lineales. |
| **Aprendizaje Supervisado** | `src/triage/train.py` | Modelo clásico de referencia (TF-IDF a nivel de n-gramas de palabras y caracteres + Regresión Logística balanceada). |
| **Aprendizaje No Supervisado** | `src/triage/clustering.py` | Algoritmo **DBSCAN** y similitud coseno en ventana temporal para agrupar reportes duplicados y descubrir incidentes masivos en campus sin etiquetas. |
| **Modelos Matemáticos de Regresión** | `src/triage/sla_regression.py` | Comparativa de **Regresión Lineal vs Polinomial (Grado 2) vs Ridge** para predecir tiempo de atención en cola y riesgo de incumplir el SLA ($R^2 = 0.98$). |

---

## Evaluación experimental

### Clasificación de urgencia

| Modelo | Conjunto | Exactitud | Macro-F1 | Casos críticos subestimados |
| :--- | :--- | :--- | :--- | :--- |
| **Regresión Logística (TF-IDF)** | Sintético (Test) | 0.73 | 0.70 | 14.7% |
| **Deep Learning (Red MLP)** | Sintético (Test) | **0.80** | **0.76** | **13.1%** |
| **Regresión Logística (TF-IDF)** | Gold Manual (24 tickets) | 0.50 | 0.46 | 33.3% |
| **Deep Learning (Red MLP)** | Gold Manual (24 tickets) | **0.54** | **0.50** | 66.7% (ML solo) $\to$ **0.0% con Red FOL** |

> **Hallazgo de diseño:** los modelos supervisados pueden fallar ante redacciones nuevas o informales. Las reglas FOL y la ontología complementan la predicción y ayudan a priorizar los casos bloqueantes urgentes; no sustituyen la revisión humana.

---

## Despliegue e integración con GLPI

`python main.py web` inicia automáticamente los servicios de GLPI con Docker Compose, espera a que el puerto local responda y después conecta el dashboard. Docker Engine/Desktop debe estar abierto.

También se pueden iniciar los servicios por separado:

```bash
docker compose -f docker/docker-compose.yml up -d
```
- GLPI Web: `http://localhost:8080` (credenciales iniciales: `glpi` / `glpi`)
- API REST legacy: `http://localhost:8080/apirest.php`

La instalación de GLPI y la configuración de su API se hacen una sola vez y permanecen en los volúmenes de Docker. **No uses `docker compose down -v`** si quieres conservarlas.

1. En la primera ejecución, completa el instalador web. Para la conexión a MariaDB usa servidor `mariadb`, base de datos `glpi_db`, usuario `glpi_user` y contraseña `glpi_secure_password`.
2. En GLPI, activa la **API legacy** en **Configuración → General → API**.
3. En esa configuración, crea y activa un cliente API que permita la IP de origen del agente. Si GLPI muestra `ERROR_NOT_ALLOWED_IP`, autoriza la IP indicada en el error. Copia el **App-Token** de este cliente.
4. En las preferencias del usuario de GLPI, genera o copia el **User-Token** de API. Si el inicio con contraseña está deshabilitado, este token de usuario es necesario además del App-Token.
5. Crea el archivo local de configuración:

   ```bash
   cp .env.example .env
   ```

   En `.env`, reemplaza `GLPI_APP_TOKEN` por el token del cliente API y `GLPI_USER_TOKEN` por el token del perfil de usuario. Ambos valores van sin comillas; también se aceptan comillas simples o dobles. El archivo está excluido de Git; no compartas ni confirmes su contenido.
6. Después de esa configuración inicial, basta con iniciar el dashboard desde la raíz del proyecto:

   ```bash
   python main.py web
   ```

Este comando también levanta los contenedores si están detenidos; no inicia Docker Engine/Desktop por sí mismo.

El dashboard lee `.env` automáticamente; también respeta variables de entorno que ya estén definidas en la terminal. Si `GLPI_USER_TOKEN` está configurado, se usa para autenticar en lugar de usuario/contraseña; si no, se usa autenticación Basic. El App-Token se envía en ambos casos. El servidor no inicia en modo simulado si falla la conexión: muestra el error de GLPI para que puedas corregir la configuración. Los tests usan el mock solo cuando lo solicitan explícitamente.
