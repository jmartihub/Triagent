# Agente Inteligente de Triaje y Priorización de Tickets (Tooli / GLPI)

**Proyecto Final - Curso de Inteligencia Artificial**  
*Autores: Juan Martínez & Santiago Payares*

Agente híbrido inteligente (Neuro-Simbólico) para la clasificación, priorización y enrutamiento automático de tickets en la mesa de ayuda universitaria (Tooli / GLPI). Integra el ciclo completo de un agente inteligente: **Percepción**, **Razonamiento**, **Acción** y **Memoria/Aprendizaje**.

---

## 🚀 Cómo correr el proyecto

```bash
# 1. Instalar dependencias (en entorno virtual)
pip install -r requirements.txt

# 2. Ejecutar la demostración guiada (3 casos clave para la sustentación)
python main.py demo

# 3. Probar en vivo en modo interactivo (redacta cualquier ticket por teclado)
python main.py interactivo

# 4. Entrenar y evaluar todos los modelos (ML clásico, Deep Learning, Regresión SLA)
python main.py all

# 5. Ejecutar toda la suite de pruebas unitarias y de integración
python tests/test_rubric.py
python tests/test_reasoning.py
python tests/test_agent_full.py
```

Otros comandos individuales:
- `python main.py deep`: Entrena y evalúa la variante de Deep Learning (Red Neuronal Multicapa MLP).
- `python main.py sla`: Entrena y compara los modelos estadísticos de regresión (Lineal vs Polinomial vs Ridge) para tiempos de resolución y riesgo SLA.
- `python main.py generate`: Genera el dataset sintético con ruido controlado (`data/tickets_sinteticos.csv`).
- `python main.py train`: Entrena el modelo clásico supervisado (TF-IDF + Regresión Logística).

---

## 🏛️ Arquitectura del Agente (Mapeada a la Rúbrica)

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

## 📚 Técnicas del Curso de IA Implementadas

| Técnica del Curso | Módulo en el Código | Justificación y Función en el Agente |
| :--- | :--- | :--- |
| **Lógica de Primer Orden (FOL)** | `src/triage/fol_rules.py` | Reglas deductivas de Horn para deducir urgencia y actuar como **red de seguridad auditada** cuando el modelo ML se equivoca en un caso crítico. |
| **Ontologías** | `src/triage/ontology.py`, `config/ontology.yaml` | Grafo jerárquico de conocimiento: mapea plataformas (Teams, Banner, Wi-Fi) a grupos de soporte, técnicos y políticas de SLA. |
| **Deep Learning** | `src/triage/deep_model.py` | Red Neuronal Multicapa (MLP) densa (128 $\to$ 64 neuronas) con activaciones ReLU y optimizador Adam para capturar relaciones semánticas no lineales. |
| **Aprendizaje Supervisado** | `src/triage/train.py` | Modelo clásico de referencia (TF-IDF a nivel de n-gramas de palabras y caracteres + Regresión Logística balanceada). |
| **Aprendizaje No Supervisado** | `src/triage/clustering.py` | Algoritmo **DBSCAN** y similitud coseno en ventana temporal para agrupar reportes duplicados y descubrir incidentes masivos en campus sin etiquetas. |
| **Modelos Matemáticos de Regresión** | `src/triage/sla_regression.py` | Comparativa de **Regresión Lineal vs Polinomial (Grado 2) vs Ridge** para predecir tiempo de atención en cola y riesgo de incumplir el SLA ($R^2 = 0.98$). |

---

## 📊 Comparativa Experimental

### Urgencia: Modelo Clásico vs Deep Learning

| Modelo | Conjunto | Accuracy | Macro-F1 | Críticos Subestimados (Error más grave) |
| :--- | :--- | :--- | :--- | :--- |
| **Regresión Logística (TF-IDF)** | Sintético (Test) | 0.73 | 0.70 | 14.7% |
| **Deep Learning (Red MLP)** | Sintético (Test) | **0.80** | **0.76** | **13.1%** |
| **Regresión Logística (TF-IDF)** | Gold Manual (24 tickets) | 0.50 | 0.46 | 33.3% |
| **Deep Learning (Red MLP)** | Gold Manual (24 tickets) | **0.54** | **0.50** | 66.7% (ML solo) $\to$ **0.0% con Red FOL** |

> **Hallazgo fundamental de diseño**: La red neuronal y el modelo supervisado por sí solos pueden fallar ante redacciones informales inéditas en casos críticos. **La Red de Seguridad en Lógica de Primer Orden (FOL) y la Ontología rescatan estos casos**, garantizando que ninguna falla bloqueante con examen próximo quede desatendida.

---

## 🐳 Despliegue de GLPI con Docker

Para correr una instancia local de GLPI conectada a MariaDB:

```bash
docker compose -f docker/docker-compose.yml up -d
```
- GLPI Web: `http://localhost:8080` (credenciales iniciales: `glpi` / `glpi`)
- API REST: `http://localhost:8080/apirest.php`
