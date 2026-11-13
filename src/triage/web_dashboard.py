"""Panel Web Interactivo del Agente Inteligente de Triaje (Tooli / GLPI).

Servidor HTTP ligero en Python (sin dependencias pesadas de frontend) que proporciona
una interfaz web moderna, visual y reactiva en http://localhost:5000:
- Simulador de Solicitud de Tooli (estudiante envía ticket).
- Visualización en tiempo real del ciclo del Agente:
  * Percepción probabilística ML/DL
  * Deducción formal FOL y red de seguridad
  * Asignación Ontológica de técnicos y cálculo de SLA por regresión
  * Detección no supervisada de brotes/duplicados por DBSCAN
- Monitor de la cola de GLPI en Docker con sincronización bidireccional.
- Panel de Retroalimentación Humana (Human-in-the-loop) para registrar correcciones del técnico.
"""

from dataclasses import asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from triage.agent import AgenteTriaje
from triage.glpi_client import ClienteGLPI

HTML_INDEX = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mesa de Ayuda TI - Agente Inteligente de Triaje</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .badge-critica { background: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
    .badge-alta { background: #ffedd5; color: #9a3412; border: 1px solid #fb923c; }
    .badge-media { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
    .badge-baja { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
  </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen">
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Encabezado -->
    <header class="flex flex-col md:flex-row items-center justify-between border-b border-slate-800 pb-5 mb-6">
      <div>
        <div class="flex items-center gap-3">
          <span class="text-3xl">🤖</span>
          <h1 class="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-indigo-400 bg-clip-text text-transparent">
            Agente Inteligente de Triaje y Priorización
          </h1>
        </div>
        <p class="text-sm text-slate-400 mt-1">
          Soporte TI Universitario (Tooli / GLPI) · Proyecto Final de Inteligencia Artificial
        </p>
      </div>
      <div class="flex items-center gap-3 mt-4 md:mt-0">
        <span id="glpi-status" class="px-3 py-1 text-xs rounded-full bg-emerald-950 text-emerald-400 border border-emerald-700 font-medium">
          ● GLPI Docker Activo (Port 8080)
        </span>
        <a href="http://localhost:8080" target="_blank" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 transition">
          Abrir GLPI Oficial ↗
        </a>
      </div>
    </header>

    <!-- Pestañas de Navegación -->
    <div class="flex gap-2 border-b border-slate-800 pb-2 mb-6 text-sm">
      <button onclick="cambiarPestana('simulador')" id="tab-simulador" class="tab-btn px-4 py-2 font-medium rounded-lg bg-indigo-600 text-white">
        📝 Simulador de Tickets (Tooli)
      </button>
      <button onclick="cambiarPestana('cola')" id="tab-cola" class="tab-btn px-4 py-2 font-medium rounded-lg text-slate-400 hover:text-slate-200">
        📋 Monitor de Cola GLPI (<span id="count-tickets">0</span>)
      </button>
      <button onclick="cambiarPestana('ontologia')" id="tab-ontologia" class="tab-btn px-4 py-2 font-medium rounded-lg text-slate-400 hover:text-slate-200">
        🏛️ Ontología y Técnicos
      </button>
    </div>

    <!-- PESTAÑA 1: SIMULADOR DE TICKETS -->
    <section id="sec-simulador" class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Formulario de entrada -->
      <div class="lg:col-span-5 bg-slate-800/80 p-6 rounded-2xl border border-slate-700 shadow-xl">
        <h2 class="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <span>✍️</span> Enviar Solicitud del Estudiante
        </h2>
        <form id="form-ticket" onsubmit="enviarTicket(event)" class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">Formulario Seleccionado en Tooli</label>
            <select id="formulario_elegido" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500">
              <option value="Fallas Técnicas TIC">Fallas Técnicas TIC</option>
              <option value="Procesos de Pago">Procesos de Pago</option>
              <option value="Salas de Cómputo">Salas de Cómputo</option>
              <option value="Soporte Durante Matrícula Académica">Soporte Durante Matrícula Académica</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">¿Qué apoyo necesitas?</label>
            <select id="apoyo" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500">
              <option value="Teams">Teams</option>
              <option value="Red / Wi-Fi">Red / Wi-Fi</option>
              <option value="Banner">Banner / Portal</option>
              <option value="Correo institucional">Correo institucional</option>
              <option value="Pagos en línea">Pagos en línea</option>
              <option value="Accesos y contraseñas">Accesos y contraseñas</option>
              <option value="Acceso a software">Acceso a software (Salas)</option>
              <option value="Funciones del computador">Funciones del computador</option>
              <option value="Liquidación de comprobantes">Liquidación de comprobantes</option>
              <option value="Matrícula académica">Matrícula académica</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">Asunto</label>
            <input type="text" id="asunto" required placeholder="Ej: No puedo ingresar al portal" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500" value="No puedo entrar a la plataforma">
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">Descripción detallada</label>
            <textarea id="descripcion" rows="4" required class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500" placeholder="Explica tu problema...">No me deja entrar a la plataforma y presento un examen parcial en una hora. No tengo otra forma de presentarlo.</textarea>
          </div>
          <div class="pt-2 flex gap-2">
            <button type="submit" id="btn-enviar" class="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2.5 rounded-lg transition shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2">
              <span>🚀</span> Triajar y Enviar a GLPI
            </button>
            <button type="button" onclick="cargarEjemplo('brote')" class="bg-slate-700 hover:bg-slate-600 px-3 py-2 text-xs rounded-lg text-slate-300" title="Cargar caso de Wi-Fi masivo">
              Caso Brote
            </button>
            <button type="button" onclick="cargarEjemplo('error_form')" class="bg-slate-700 hover:bg-slate-600 px-3 py-2 text-xs rounded-lg text-slate-300" title="Cargar error de formulario">
              Caso Facturación
            </button>
          </div>
        </form>
      </div>

      <!-- Panel de Razonamiento y Resultado en Vivo -->
      <div class="lg:col-span-7 bg-slate-800/80 p-6 rounded-2xl border border-slate-700 shadow-xl flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between border-b border-slate-700 pb-3 mb-4">
            <h2 class="text-lg font-semibold text-slate-200 flex items-center gap-2">
              <span>🧠</span> Decisión y Razonamiento del Agente
            </h2>
            <span id="ticket-id-tag" class="text-xs text-slate-400 font-mono">Esperando ticket...</span>
          </div>

          <!-- Alerta de seguridad FOL -->
          <div id="alert-fol" class="hidden mb-4 p-3 rounded-xl bg-amber-950/80 border border-amber-600/60 text-amber-200 text-xs flex items-start gap-2">
            <span class="text-base">🚨</span>
            <div>
              <strong class="font-semibold">Red de Seguridad FOL Activada:</strong>
              <span id="alert-fol-text"></span>
            </div>
          </div>

          <!-- Alerta de Incidente Masivo -->
          <div id="alert-masivo" class="hidden mb-4 p-3 rounded-xl bg-rose-950/80 border border-rose-600/60 text-rose-200 text-xs flex items-start gap-2">
            <span class="text-base">📢</span>
            <div>
              <strong class="font-semibold">Alerta No Supervisada (DBSCAN):</strong>
              <span id="alert-masivo-text"></span>
            </div>
          </div>

          <!-- Métricas del Triaje -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <div class="bg-slate-900/90 p-3 rounded-xl border border-slate-700/60">
              <span class="text-[10px] text-slate-400 block uppercase">Urgencia Final</span>
              <span id="res-urgencia" class="text-sm font-bold px-2 py-0.5 rounded mt-1 inline-block">-</span>
            </div>
            <div class="bg-slate-900/90 p-3 rounded-xl border border-slate-700/60">
              <span class="text-[10px] text-slate-400 block uppercase">Formulario</span>
              <span id="res-formulario" class="text-xs font-semibold text-slate-200 mt-1 block truncate">-</span>
            </div>
            <div class="bg-slate-900/90 p-3 rounded-xl border border-slate-700/60">
              <span class="text-[10px] text-slate-400 block uppercase">Técnico Asignado</span>
              <span id="res-tecnico" class="text-xs font-semibold text-cyan-300 mt-1 block truncate">-</span>
            </div>
            <div class="bg-slate-900/90 p-3 rounded-xl border border-slate-700/60">
              <span class="text-[10px] text-slate-400 block uppercase">SLA / Cola Est.</span>
              <span id="res-sla" class="text-xs font-semibold text-slate-200 mt-1 block">-</span>
            </div>
          </div>

          <!-- Deducciones de Lógica de Primer Orden -->
          <div class="mb-4">
            <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Trazabilidad Deductiva (FOL):</h3>
            <ul id="res-fol-list" class="bg-slate-900/80 rounded-xl p-3 text-xs font-mono text-cyan-300/90 space-y-1 max-h-36 overflow-y-auto border border-slate-800">
              <li class="text-slate-500">Sin datos de inferencia previa</li>
            </ul>
          </div>

          <!-- Respuesta Preliminar al Estudiante -->
          <div>
            <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Respuesta Preliminar Generada (Acción 3):</h3>
            <div id="res-respuesta" class="bg-slate-900/90 rounded-xl p-3 text-xs text-slate-300 whitespace-pre-line border border-slate-800 max-h-40 overflow-y-auto">
              Presiona "Triajar y Enviar a GLPI" para generar una respuesta automática.
            </div>
          </div>
        </div>

        <div class="pt-4 border-t border-slate-800 mt-4 flex items-center justify-between text-xs text-slate-400">
          <span id="sync-glpi-msg">Estatus: Listo para procesar</span>
          <span class="text-slate-500">GLPI API REST v1.0</span>
        </div>
      </div>
    </section>

    <!-- PESTAÑA 2: MONITOR DE COLA GLPI -->
    <section id="sec-cola" class="hidden bg-slate-800/80 p-6 rounded-2xl border border-slate-700 shadow-xl">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-semibold text-slate-200">Tickets Registrados en GLPI</h2>
          <p class="text-xs text-slate-400">Sincronización en vivo con la base de datos MariaDB</p>
        </div>
        <button onclick="cargarColaTickets()" class="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-1.5 rounded-lg transition">
          🔄 Actualizar Cola
        </button>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-300">
          <thead class="bg-slate-900/80 text-slate-400 uppercase text-[10px]">
            <tr>
              <th class="p-3">ID</th>
              <th class="p-3">Asunto / Título</th>
              <th class="p-3">Fecha</th>
              <th class="p-3">Estado</th>
              <th class="p-3">Urgencia</th>
              <th class="p-3">Acciones (Human-in-the-loop)</th>
            </tr>
          </thead>
          <tbody id="tabla-tickets" class="divide-y divide-slate-700/50">
            <tr><td colspan="6" class="p-4 text-center text-slate-500">Cargando tickets...</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- PESTAÑA 3: ONTOLOGÍA Y TÉCNICOS -->
    <section id="sec-ontologia" class="hidden space-y-6">
      <div class="bg-slate-800/80 p-6 rounded-2xl border border-slate-700 shadow-xl">
        <h2 class="text-lg font-semibold text-slate-200 mb-1">Red de Especialistas de Soporte TI</h2>
        <p class="text-xs text-slate-400 mb-4">Mapeo ontológico entre plataformas universitarias y competencias técnicas</p>
        <div id="grid-tecnicos" class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Tarjetas generadas por JS -->
        </div>
      </div>
    </section>
  </div>

  <script>
    const NIVELES_COLOR = {
      'Crítica': 'badge-critica',
      'Alta': 'badge-alta',
      'Media': 'badge-media',
      'Baja': 'badge-baja'
    };

    function cambiarPestana(nombre) {
      document.querySelectorAll('.tab-btn').forEach(b => {
        b.className = 'tab-btn px-4 py-2 font-medium rounded-lg text-slate-400 hover:text-slate-200';
      });
      document.getElementById('tab-' + nombre).className = 'tab-btn px-4 py-2 font-medium rounded-lg bg-indigo-600 text-white';

      document.getElementById('sec-simulador').classList.add('hidden');
      document.getElementById('sec-cola').classList.add('hidden');
      document.getElementById('sec-ontologia').classList.add('hidden');
      document.getElementById('sec-' + nombre).classList.remove('hidden');

      if (nombre === 'cola') cargarColaTickets();
      if (nombre === 'ontologia') cargarOntologia();
    }

    async function enviarTicket(e) {
      e.preventDefault();
      const btn = document.getElementById('btn-enviar');
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span> Procesando...';

      const payload = {
        formulario_elegido: document.getElementById('formulario_elegido').value,
        apoyo: document.getElementById('apoyo').value,
        asunto: document.getElementById('asunto').value,
        descripcion: document.getElementById('descripcion').value,
      };

      try {
        const resp = await fetch('/api/triajar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await resp.json();
        renderizarResultado(data);
      } catch (err) {
        alert('Error al conectar con el agente: ' + err);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>🚀</span> Triajar y Enviar a GLPI';
      }
    }

    function renderizarResultado(d) {
      document.getElementById('ticket-id-tag').innerText = '#' + d.id_ticket + ' (Registrado en GLPI)';

      // Urgencia
      const urgEl = document.getElementById('res-urgencia');
      urgEl.innerText = d.urgencia_final;
      urgEl.className = 'text-sm font-bold px-2 py-0.5 rounded mt-1 inline-block ' + (NIVELES_COLOR[d.urgencia_final] || 'bg-slate-700');

      // Formulario
      const formEl = document.getElementById('res-formulario');
      formEl.innerText = d.formulario_final + (d.hubo_cambio_formulario ? ' ⚠️ [Corregido]' : '');

      // Tecnico y SLA
      document.getElementById('res-tecnico').innerText = d.tecnico_asignado;
      document.getElementById('res-sla').innerText = d.tiempo_sla_horas + 'h (Cola: ~' + d.horas_estimadas_resolucion + 'h)';

      // Alerta FOL
      const folDiv = document.getElementById('alert-fol');
      if (d.seguridad_ml_activada) {
        folDiv.classList.remove('hidden');
        document.getElementById('alert-fol-text').innerText = 'El modelo estadístico dudó, pero el árbitro formal FOL rescató la urgencia.';
      } else {
        folDiv.classList.add('hidden');
      }

      // Alerta Masivo
      const masivoDiv = document.getElementById('alert-masivo');
      if (d.es_incidente_masivo) {
        masivoDiv.classList.remove('hidden');
        document.getElementById('alert-masivo-text').innerText = 'Agrupado con otros reportes en ' + d.id_incidente_masivo;
      } else {
        masivoDiv.classList.add('hidden');
      }

      // Lista FOL
      const listEl = document.getElementById('res-fol-list');
      listEl.innerHTML = d.justificacion_fol.map(f => `<li>• ${f}</li>`).join('') || '<li>• Inferencia directa estándar</li>';

      // Respuesta
      document.getElementById('res-respuesta').innerText = d.respuesta_preliminar;
      document.getElementById('sync-glpi-msg').innerText = '✓ Sincronizado con GLPI (ID: #' + d.id_ticket + ')';
    }

    async function cargarColaTickets() {
      const tbody = document.getElementById('tabla-tickets');
      tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-slate-500">Consultando GLPI...</td></tr>';
      try {
        const resp = await fetch('/api/tickets');
        const tickets = await resp.json();
        document.getElementById('count-tickets').innerText = tickets.length;

        if (tickets.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-slate-500">No hay tickets pendientes en GLPI. Envía uno desde el simulador.</td></tr>';
          return;
        }

        tbody.innerHTML = tickets.map(t => {
          const urgNombre = t.urgency === 5 ? 'Crítica' : (t.urgency === 4 ? 'Alta' : (t.urgency === 3 ? 'Media' : 'Baja'));
          const estadoNombre = t.status === 1 ? 'Nuevo' : (t.status === 2 ? 'En curso / Asignado' : 'Resuelto');
          return `
            <tr class="hover:bg-slate-700/30">
              <td class="p-3 font-mono font-bold text-slate-400">#${t.id}</td>
              <td class="p-3 font-medium text-slate-200">${t.name}</td>
              <td class="p-3 text-slate-400">${t.date || '-'}</td>
              <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] ${t.status === 1 ? 'bg-indigo-900/60 text-indigo-300' : 'bg-emerald-900/60 text-emerald-300'}">${estadoNombre}</span></td>
              <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${NIVELES_COLOR[urgNombre] || 'bg-slate-700'}">${urgNombre}</span></td>
              <td class="p-3">
                <button onclick="corregirHumano(${t.id})" class="text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 px-2 py-1 rounded">
                  ✏️ Corregir (Feedback)
                </button>
              </td>
            </tr>
          `;
        }).join('');
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-rose-400">Error al consultar GLPI: ${err}</td></tr>`;
      }
    }

    async function corregirHumano(id) {
      const nuevaUrg = prompt('Ingresa la corrección de urgencia (Crítica, Alta, Media, Baja):', 'Alta');
      if (!nuevaUrg) return;
      try {
        await fetch('/api/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_ticket: id, urgencia_corregida: nuevaUrg })
        });
        alert('Retroalimentación humana guardada en data/feedback_log.jsonl.');
        cargarColaTickets();
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    async function cargarOntologia() {
      const cont = document.getElementById('grid-tecnicos');
      try {
        const resp = await fetch('/api/ontologia');
        const data = await resp.json();
        cont.innerHTML = data.tecnicos.map(t => `
          <div class="bg-slate-900/90 p-4 rounded-xl border border-slate-700">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-2xl">👨‍💻</span>
              <div>
                <h4 class="font-bold text-sm text-slate-200">${t.nombre}</h4>
                <p class="text-xs text-indigo-400">${t.rol}</p>
              </div>
            </div>
            <p class="text-xs text-slate-400 mb-2">Grupo: <span class="text-slate-300">${t.grupo}</span></p>
            <div class="text-[10px] text-slate-500">
              Especialidades: ${t.especialidades.map(e => `<span class="bg-slate-800 px-1.5 py-0.5 rounded text-slate-300 mr-1">${e}</span>`).join('')}
            </div>
          </div>
        `).join('');
      } catch (e) {
        cont.innerHTML = `<p class="text-rose-400">Error: ${e}</p>`;
      }
    }

    function cargarEjemplo(tipo) {
      if (tipo === 'brote') {
        document.getElementById('formulario_elegido').value = 'Fallas Técnicas TIC';
        document.getElementById('apoyo').value = 'Red / Wi-Fi';
        document.getElementById('asunto').value = 'Se cayó el wifi en el bloque C';
        document.getElementById('descripcion').value = 'Toda la red de estudiantes del bloque C no funciona, examen suspendido.';
      } else if (tipo === 'error_form') {
        document.getElementById('formulario_elegido').value = 'Fallas Técnicas TIC';
        document.getElementById('apoyo').value = 'Pagos en línea';
        document.getElementById('asunto').value = 'Error en descuento de matrícula';
        document.getElementById('descripcion').value = 'Mi liquidación no incluye el descuento al que tengo derecho y necesito pagar en tesorería.';
      }
    }

    // Inicializar
    cargarColaTickets();
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    agente: AgenteTriaje = None
    cliente_glpi: ClienteGLPI = None

    def log_message(self, format, *args):
        pass  # Evitar saturar la consola

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)

        if url.path == "/" or url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_INDEX.encode("utf-8"))
            return

        if url.path == "/api/tickets":
            tickets = []
            if self.cliente_glpi:
                tickets = self.cliente_glpi.obtener_tickets_nuevos()
                # Si no hay tickets nuevos, traer los tickets existentes de GLPI
                if not tickets and not self.cliente_glpi.modo_mock and self.cliente_glpi.session_token:
                    try:
                        req = urllib.request.Request(
                            f"{self.cliente_glpi.url_base}/Ticket?is_deleted=0",
                            headers={"Session-Token": self.cliente_glpi.session_token},
                        )
                        with urllib.request.urlopen(req, timeout=3) as r:
                            tickets = json.loads(r.read().decode())
                    except Exception:
                        pass
            self.enviar_json(tickets)
            return

        if url.path == "/api/ontologia":
            datos = {
                "tecnicos": self.agente.ontologia.tecnicos if self.agente else [],
                "sla": self.agente.ontologia.sla if self.agente else {},
            }
            self.enviar_json(datos)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            datos = json.loads(post_body)
        except Exception:
            datos = {}

        if url.path == "/api/triajar":
            asunto = datos.get("asunto", "")
            descripcion = datos.get("descripcion", "")
            form = datos.get("formulario_elegido", "Fallas Técnicas TIC")
            apoyo = datos.get("apoyo", "Otra")

            # 1. Crear ticket en GLPI
            id_glpi = None
            if self.cliente_glpi:
                id_glpi = self.cliente_glpi.crear_ticket(asunto, descripcion)

            ticket_sim = {
                "id": str(id_glpi or f"WEB_{int(datetime.now().timestamp())}"),
                "formulario_elegido": form,
                "apoyo": apoyo,
                "asunto": asunto,
                "descripcion": descripcion,
                "fecha_apertura": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

            # 2. Triajar con el Agente
            decision = self.agente.procesar_ticket(ticket_sim)

            # 3. Escribir de vuelta en GLPI
            if self.cliente_glpi and id_glpi:
                self.cliente_glpi.actualizar_ticket(
                    id_ticket=id_glpi,
                    urgencia_nombre=decision.urgencia_final,
                    tecnico_nombre=decision.tecnico_asignado,
                    formulario_nombre=decision.formulario_final,
                )
                self.cliente_glpi.registrar_respuesta_preliminar(
                    id_ticket=id_glpi,
                    respuesta_texto=decision.respuesta_preliminar,
                )

            res = asdict(decision)
            self.enviar_json(res)
            return

        if url.path == "/api/feedback":
            id_t = str(datos.get("id_ticket", ""))
            urg_corregida = datos.get("urgencia_corregida", "Alta")
            self.agente.memoria.registrar_feedback_humano(
                id_ticket=id_t,
                urgencia_humana=urg_corregida,
                formulario_humano="Fallas Técnicas TIC",
                comentarios="Ajuste manual del técnico desde Dashboard",
            )
            self.enviar_json({"ok": True})
            return

        self.send_error(404, "Not Found")

    def enviar_json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def iniciar_servidor(puerto: int = 5000):
    agente = AgenteTriaje(usar_deep_learning=True)
    cliente_glpi = ClienteGLPI(modo_mock=False)
    conectado = cliente_glpi.conectar()
    modo_str = "GLPI Docker Real (http://localhost:8080)" if conectado and not cliente_glpi.modo_mock else "Modo Simulado / Mock"

    DashboardHandler.agente = agente
    DashboardHandler.cliente_glpi = cliente_glpi

    servidor = HTTPServer(("0.0.0.0", puerto), DashboardHandler)
    print("\n" + "=" * 80)
    print(" 🚀 PANEL WEB DEL AGENTE DE TRIAJE INICIADO CON ÉXITO ".center(80))
    print("=" * 80)
    print(f"• URL del Dashboard:    http://localhost:{puerto}")
    print(f"• Conexión GLPI:        {modo_str}")
    print("• Abre la URL en tu navegador para ver la interfaz interactiva.")
    print("• Presiona Ctrl+C para detener el servidor.")
    print("=" * 80 + "\n")

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor web detenido.")
        cliente_glpi.desconectar()
        servidor.server_close()


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    iniciar_servidor(puerto)
