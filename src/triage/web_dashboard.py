"""Panel Web del Agente de Triaje y Priorizacion (Tooli / GLPI).

Servidor HTTP en Python para la interfaz institucional de gestion y control:
- Simulador de Solicitud de Tooli (estudiante envia ticket).
- Visualizacion en tiempo real del ciclo del Agente:
  * Percepcion probabilistica ML/DL
  * Deduccion formal FOL y red de seguridad
  * Asignacion Ontologica de tecnicos y calculo de SLA por regresion
  * Deteccion no supervisada de brotes/duplicados por DBSCAN
  * Aprendizaje activo por casos (CBR) desde correcciones humanas
- Monitor de la cola de GLPI con sincronizacion bidireccional.
- Panel de Retroalimentacion Humana (Human-in-the-loop).
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
  <title>Mesa de Ayuda TI - Agente de Triaje y Priorización</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .badge-critica { background: #450a0a; color: #fca5a5; border: 1px solid #991b1b; }
    .badge-alta { background: #431407; color: #fdba74; border: 1px solid #9a3412; }
    .badge-media { background: #172554; color: #93c5fd; border: 1px solid #1e40af; }
    .badge-baja { background: #064e3b; color: #86efac; border: 1px solid #166534; }
  </style>
</head>
<body class="bg-slate-950 text-slate-200 min-h-screen font-sans">
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Encabezado Institucional -->
    <header class="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-slate-800 pb-5 mb-6">
      <div>
        <h1 class="text-xl font-bold text-slate-100 tracking-tight">
          Mesa de Ayuda TI · Agente de Triaje y Priorización
        </h1>
        <p class="text-xs text-slate-400 mt-1">
          Integración Tooli / GLPI · Arquitectura Híbrida (Neuro-Simbólica) · Proyecto Final IA
        </p>
      </div>
      <div class="flex items-center gap-3 mt-4 md:mt-0">
        <span id="glpi-status" class="px-2.5 py-1 text-xs rounded bg-slate-900 text-emerald-400 border border-emerald-800 font-mono">
          GLPI: Conectado (Port 8080)
        </span>
        <a href="http://localhost:8080" target="_blank" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1 rounded border border-slate-700 transition">
          Consola GLPI
        </a>
      </div>
    </header>

    <!-- Panel de Resumen Administrativo (KPIs y Metricas) -->
    <div class="mb-6 bg-slate-900 border border-slate-800 rounded-lg p-4">
      <div class="flex items-center justify-between pb-3 mb-3 border-b border-slate-800">
        <div>
          <h2 class="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Resumen Administrativo · Estado de la Mesa de Ayuda
          </h2>
          <p class="text-[11px] text-slate-500">Métricas consolidadas de tickets, distribución de urgencias y carga operativa</p>
        </div>
        <button onclick="cargarMetricasYCola()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1 rounded border border-slate-700 transition">
          Actualizar Datos
        </button>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
        <!-- Total -->
        <div class="bg-slate-950 p-3 rounded border border-slate-800">
          <span class="text-[10px] uppercase font-medium text-slate-400 block">Total Tickets</span>
          <span id="kpi-total" class="text-lg font-bold text-slate-100 font-mono">0</span>
          <span id="kpi-activos" class="text-[10px] text-slate-400 block mt-0.5">0 activos</span>
        </div>
        <!-- Críticos -->
        <div class="bg-slate-950 p-3 rounded border border-rose-950">
          <span class="text-[10px] uppercase font-medium text-rose-400 block">Crítica</span>
          <span id="kpi-critica" class="text-lg font-bold text-rose-400 font-mono">0</span>
          <span id="kpi-critica-pct" class="text-[10px] text-rose-400/70 block mt-0.5">0% del total</span>
        </div>
        <!-- Altos -->
        <div class="bg-slate-950 p-3 rounded border border-amber-950">
          <span class="text-[10px] uppercase font-medium text-amber-400 block">Alta</span>
          <span id="kpi-alta" class="text-lg font-bold text-amber-400 font-mono">0</span>
          <span id="kpi-alta-pct" class="text-[10px] text-amber-400/70 block mt-0.5">0% del total</span>
        </div>
        <!-- Medios -->
        <div class="bg-slate-950 p-3 rounded border border-blue-950">
          <span class="text-[10px] uppercase font-medium text-blue-400 block">Media</span>
          <span id="kpi-media" class="text-lg font-bold text-blue-400 font-mono">0</span>
          <span id="kpi-media-pct" class="text-[10px] text-blue-400/70 block mt-0.5">0% del total</span>
        </div>
        <!-- Bajos -->
        <div class="bg-slate-950 p-3 rounded border border-slate-800">
          <span class="text-[10px] uppercase font-medium text-slate-300 block">Baja</span>
          <span id="kpi-baja" class="text-lg font-bold text-slate-300 font-mono">0</span>
          <span id="kpi-baja-pct" class="text-[10px] text-slate-400 block mt-0.5">0% del total</span>
        </div>
        <!-- Resueltos / Cumplimiento -->
        <div class="bg-slate-950 p-3 rounded border border-emerald-950">
          <span class="text-[10px] uppercase font-medium text-emerald-400 block">Resueltos</span>
          <span id="kpi-resueltos" class="text-lg font-bold text-emerald-400 font-mono">0</span>
          <span id="kpi-sla" class="text-[10px] text-emerald-400/70 block mt-0.5">SLA: 95.2%</span>
        </div>
      </div>

      <!-- Barra de distribución visual de urgencias -->
      <div>
        <div class="flex justify-between text-[10px] text-slate-400 mb-1">
          <span>Distribución por Severidad</span>
          <span id="distribucion-label">Calculando...</span>
        </div>
        <div class="w-full h-2 bg-slate-950 rounded-full overflow-hidden flex">
          <div id="bar-critica" style="width: 0%" class="bg-rose-600 transition-all duration-300" title="Crítica"></div>
          <div id="bar-alta" style="width: 0%" class="bg-amber-600 transition-all duration-300" title="Alta"></div>
          <div id="bar-media" style="width: 0%" class="bg-blue-600 transition-all duration-300" title="Media"></div>
          <div id="bar-baja" style="width: 0%" class="bg-slate-600 transition-all duration-300" title="Baja"></div>
        </div>
      </div>
    </div>

    <!-- Navegacion por Pestanas -->
    <div class="flex gap-2 border-b border-slate-800 pb-2 mb-6 text-xs">
      <button onclick="cambiarPestana('simulador')" id="tab-simulador" class="tab-btn px-4 py-2 font-medium rounded bg-slate-800 text-white border border-slate-700">
        Simulador de Solicitudes (Tooli)
      </button>
      <button onclick="cambiarPestana('cola')" id="tab-cola" class="tab-btn px-4 py-2 font-medium rounded text-slate-400 hover:text-slate-200 border border-transparent">
        Monitor de Cola GLPI (<span id="count-tickets">0</span>)
      </button>
      <button onclick="cambiarPestana('ontologia')" id="tab-ontologia" class="tab-btn px-4 py-2 font-medium rounded text-slate-400 hover:text-slate-200 border border-transparent">
        Ontología y Especialistas
      </button>
    </div>

    <!-- PESTANA 1: SIMULADOR DE TICKETS -->
    <section id="sec-simulador" class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Formulario de entrada -->
      <div class="lg:col-span-5 bg-slate-900 p-5 rounded-lg border border-slate-800">
        <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">
          Entrada: Solicitud de Usuario
        </h2>
        <form id="form-ticket" onsubmit="enviarTicket(event)" class="space-y-4 text-xs">
          <div>
            <label class="block font-medium text-slate-400 mb-1">Formulario en Tooli</label>
            <select id="formulario_elegido" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-slate-500">
              <option value="Fallas Técnicas TIC">Fallas Técnicas TIC</option>
              <option value="Procesos de Pago">Procesos de Pago</option>
              <option value="Salas de Cómputo">Salas de Cómputo</option>
              <option value="Soporte Durante Matrícula Académica">Soporte Durante Matrícula Académica</option>
            </select>
          </div>
          <div>
            <label class="block font-medium text-slate-400 mb-1">Subcategoría / Apoyo Requerido</label>
            <select id="apoyo" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-slate-500">
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
            <label class="block font-medium text-slate-400 mb-1">Asunto</label>
            <input type="text" id="asunto" required placeholder="Ej: No puedo ingresar al portal" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-slate-500" value="No puedo entrar a la plataforma">
          </div>
          <div>
            <label class="block font-medium text-slate-400 mb-1">Descripción detallada</label>
            <textarea id="descripcion" rows="4" required class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-slate-500" placeholder="Descripción del incidente...">No me deja entrar a la plataforma y presento un examen parcial en una hora. No tengo otra forma de presentarlo.</textarea>
          </div>
          <div class="pt-2 flex flex-col sm:flex-row gap-2">
            <button type="submit" id="btn-enviar" class="flex-1 bg-blue-700 hover:bg-blue-600 text-white font-medium py-2 rounded transition">
              Procesar y Enviar a GLPI
            </button>
            <button type="button" onclick="cargarEjemplo('brote')" class="bg-slate-800 hover:bg-slate-700 px-3 py-2 rounded text-slate-300 border border-slate-700">
              Ejemplo Red
            </button>
            <button type="button" onclick="cargarEjemplo('error_form')" class="bg-slate-800 hover:bg-slate-700 px-3 py-2 rounded text-slate-300 border border-slate-700">
              Ejemplo Pagos
            </button>
          </div>
        </form>
      </div>

      <!-- Panel de Razonamiento del Agente -->
      <div class="lg:col-span-7 bg-slate-900 p-5 rounded-lg border border-slate-800 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between border-b border-slate-800 pb-2 mb-4">
            <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider">
              Salida: Razonamiento y Decisión del Agente
            </h2>
            <span id="ticket-id-tag" class="text-xs text-slate-400 font-mono">Esperando entrada...</span>
          </div>

          <!-- Alerta de seguridad FOL -->
          <div id="alert-fol" class="hidden mb-3 p-3 rounded bg-amber-950/40 border border-amber-800/80 text-amber-300 text-xs">
            <strong class="font-semibold block mb-0.5">[AVISO DE SEGURIDAD FOL]</strong>
            <span id="alert-fol-text"></span>
          </div>

          <!-- Alerta de Aprendizaje Humano -->
          <div id="alert-cbr" class="hidden mb-3 p-3 rounded bg-blue-950/40 border border-blue-800/80 text-blue-300 text-xs">
            <strong class="font-semibold block mb-0.5">[APRENDIZAJE ACTIVO DESDE FEEDBACK]</strong>
            <span id="alert-cbr-text"></span>
          </div>

          <!-- Alerta de Incidente Masivo -->
          <div id="alert-masivo" class="hidden mb-3 p-3 rounded bg-rose-950/40 border border-rose-800/80 text-rose-300 text-xs">
            <strong class="font-semibold block mb-0.5">[ALERTA DBSCAN: INCIDENTE MASIVO]</strong>
            <span id="alert-masivo-text"></span>
          </div>

          <!-- Alerta de Ticket Duplicado -->
          <div id="alert-duplicado" class="hidden mb-3 p-3 rounded bg-amber-950/40 border border-amber-800/80 text-amber-300 text-xs">
            <strong class="font-semibold block mb-0.5">[TICKET DUPLICADO DETECTADO]</strong>
            <span id="alert-duplicado-text"></span>
          </div>

          <!-- Metricas de Clasificacion -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
            <div class="bg-slate-950 p-2.5 rounded border border-slate-800">
              <span class="text-[10px] text-slate-400 block uppercase">Urgencia</span>
              <span id="res-urgencia" class="text-xs font-semibold px-2 py-0.5 rounded mt-1 inline-block">-</span>
            </div>
            <div class="bg-slate-950 p-2.5 rounded border border-slate-800">
              <span class="text-[10px] text-slate-400 block uppercase">Formulario Destino</span>
              <span id="res-formulario" class="text-xs font-semibold text-slate-200 mt-1 block truncate">-</span>
            </div>
            <div class="bg-slate-950 p-2.5 rounded border border-slate-800">
              <span class="text-[10px] text-slate-400 block uppercase">Especialista</span>
              <span id="res-tecnico" class="text-xs font-semibold text-slate-200 mt-1 block truncate">-</span>
            </div>
            <div class="bg-slate-950 p-2.5 rounded border border-slate-800">
              <span class="text-[10px] text-slate-400 block uppercase">SLA / Tiempo Cola</span>
              <span id="res-sla" class="text-xs font-semibold text-slate-200 mt-1 block">-</span>
            </div>
          </div>

          <!-- Deducciones de Logica de Primer Orden -->
          <div class="mb-4">
            <h3 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Trazabilidad Deductiva (FOL):</h3>
            <ul id="res-fol-list" class="bg-slate-950 rounded p-2.5 text-xs font-mono text-slate-300 space-y-1 max-h-32 overflow-y-auto border border-slate-800">
              <li class="text-slate-500">Sin datos de inferencia</li>
            </ul>
          </div>

          <!-- Respuesta Preliminar al Estudiante -->
          <div>
            <h3 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Respuesta Preliminar al Estudiante (Acción 3):</h3>
            <div id="res-respuesta" class="bg-slate-950 rounded p-2.5 text-xs text-slate-300 whitespace-pre-line border border-slate-800 max-h-36 overflow-y-auto font-mono">
              Esperando procesamiento de ticket...
            </div>
          </div>
        </div>

        <div class="pt-3 border-t border-slate-800 mt-4 flex items-center justify-between text-xs text-slate-400">
          <span id="sync-glpi-msg">Estado: Listo</span>
          <span class="text-slate-500 font-mono">API REST GLPI v1.0</span>
        </div>
      </div>
    </section>

    <!-- PESTANA 2: MONITOR DE COLA GLPI -->
    <section id="sec-cola" class="hidden bg-slate-900 p-5 rounded-lg border border-slate-800">
      <div class="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
        <div>
          <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider">Tickets Registrados en GLPI</h2>
          <p class="text-xs text-slate-400">Lectura directa de tickets activos en la base de datos MariaDB</p>
        </div>
      <!-- Filtros Rapidos y Buscador -->
      <div class="flex flex-col sm:flex-row gap-2 items-center justify-between mb-3 text-xs">
        <div class="flex gap-1.5 flex-wrap">
          <button onclick="filtrarTickets('todos')" id="filtro-todos" class="px-2.5 py-1 rounded bg-slate-800 text-white border border-slate-700 font-medium">Todos</button>
          <button onclick="filtrarTickets('Crítica')" id="filtro-critica" class="px-2.5 py-1 rounded bg-slate-950 text-rose-400 border border-slate-800 hover:border-rose-800">Crítica</button>
          <button onclick="filtrarTickets('Alta')" id="filtro-alta" class="px-2.5 py-1 rounded bg-slate-950 text-amber-400 border border-slate-800 hover:border-amber-800">Alta</button>
          <button onclick="filtrarTickets('Media')" id="filtro-media" class="px-2.5 py-1 rounded bg-slate-950 text-blue-400 border border-slate-800 hover:border-blue-800">Media</button>
          <button onclick="filtrarTickets('Baja')" id="filtro-baja" class="px-2.5 py-1 rounded bg-slate-950 text-slate-300 border border-slate-800 hover:border-slate-600">Baja</button>
          <button onclick="filtrarTickets('Nuevo')" id="filtro-nuevo" class="px-2.5 py-1 rounded bg-slate-950 text-slate-400 border border-slate-800 hover:border-slate-600">Nuevos</button>
          <button onclick="filtrarTickets('En curso')" id="filtro-encurso" class="px-2.5 py-1 rounded bg-slate-950 text-slate-400 border border-slate-800 hover:border-slate-600">En curso</button>
        </div>
        <div class="w-full sm:w-64">
          <input type="text" id="busqueda-ticket" oninput="buscarTicket()" placeholder="Filtrar por asunto, ID..." class="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-slate-600 text-xs">
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-300">
          <thead class="bg-slate-950 text-slate-400 uppercase text-[10px]">
            <tr>
              <th class="p-2.5">ID</th>
              <th class="p-2.5">Asunto</th>
              <th class="p-2.5">Fecha</th>
              <th class="p-2.5">Estado</th>
              <th class="p-2.5">Urgencia</th>
              <th class="p-2.5">Retroalimentación Humana</th>
            </tr>
          </thead>
          <tbody id="tabla-tickets" class="divide-y divide-slate-800">
            <tr><td colspan="6" class="p-4 text-center text-slate-500">Cargando tickets...</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- PESTANA 3: ONTOLOGIA Y TECNICOS -->
    <section id="sec-ontologia" class="hidden space-y-6">
      <div class="bg-slate-900 p-5 rounded-lg border border-slate-800">
        <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-1">Catálogo Ontológico de Técnicos y Especialidades</h2>
        <p class="text-xs text-slate-400 mb-4">Mapeo entre plataformas y competencias de enrutamiento</p>
        <div id="grid-tecnicos" class="grid grid-cols-1 md:grid-cols-3 gap-3">
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
        b.className = 'tab-btn px-4 py-2 font-medium rounded text-slate-400 hover:text-slate-200 border border-transparent';
      });
      document.getElementById('tab-' + nombre).className = 'tab-btn px-4 py-2 font-medium rounded bg-slate-800 text-white border border-slate-700';

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
      btn.innerText = 'Procesando...';

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
        alert('Error al conectar con el servidor: ' + err);
      } finally {
        btn.disabled = false;
        btn.innerText = 'Procesar y Enviar a GLPI';
      }
    }

    function renderizarResultado(d) {
      document.getElementById('ticket-id-tag').innerText = 'Ticket #' + d.id_ticket + ' (GLPI)';

      // Urgencia
      const urgEl = document.getElementById('res-urgencia');
      urgEl.innerText = d.urgencia_final;
      urgEl.className = 'text-xs font-semibold px-2 py-0.5 rounded mt-1 inline-block ' + (NIVELES_COLOR[d.urgencia_final] || 'bg-slate-800');

      // Formulario
      const formEl = document.getElementById('res-formulario');
      formEl.innerText = d.formulario_final + (d.hubo_cambio_formulario ? ' [Re-enrutado]' : '');

      // Tecnico y SLA
      document.getElementById('res-tecnico').innerText = d.tecnico_asignado;
      document.getElementById('res-sla').innerText = d.tiempo_sla_horas + 'h (Cola: ~' + d.horas_estimadas_resolucion + 'h)';

      // Alerta FOL
      const folDiv = document.getElementById('alert-fol');
      if (d.seguridad_ml_activada) {
        folDiv.classList.remove('hidden');
        document.getElementById('alert-fol-text').innerText = 'El modelo probabilístico dudó o subestimó el caso. El árbitro formal FOL prevaleció por política de SLA.';
      } else {
        folDiv.classList.add('hidden');
      }

      // Alerta CBR (Aprendizaje activo humano)
      const cbrDiv = document.getElementById('alert-cbr');
      if (d.aprendizaje_humano_aplicado) {
        cbrDiv.classList.remove('hidden');
        document.getElementById('alert-cbr-text').innerText = 'El agente detectó similitud con una corrección humana previa y adoptó la experiencia del técnico.';
      } else {
        cbrDiv.classList.add('hidden');
      }

      // Alerta Masivo
      const masivoDiv = document.getElementById('alert-masivo');
      if (d.es_incidente_masivo) {
        masivoDiv.classList.remove('hidden');
        document.getElementById('alert-masivo-text').innerText = 'Agrupado con reportes concurrentes de falla en ' + d.id_incidente_masivo;
      } else {
        masivoDiv.classList.add('hidden');
      }

      // Alerta Duplicado
      const dupDiv = document.getElementById('alert-duplicado');
      if (d.es_duplicado && d.ticket_original_id) {
        dupDiv.classList.remove('hidden');
        document.getElementById('alert-duplicado-text').innerText = 'Se identificó solicitud recurrente asociada al ticket previo #' + d.ticket_original_id + '. Se mantiene su urgencia (' + d.urgencia_final + ') y se vinculan en el expediente.';
      } else {
        dupDiv.classList.add('hidden');
      }

      // Lista FOL
      const listEl = document.getElementById('res-fol-list');
      listEl.innerHTML = d.justificacion_fol.map(f => `<li>${f}</li>`).join('') || '<li>Inferencia directa estándar</li>';

      // Respuesta
      document.getElementById('res-respuesta').innerText = d.respuesta_preliminar;
      document.getElementById('sync-glpi-msg').innerText = 'Sincronizado con GLPI (ID: #' + d.id_ticket + ')';
    }

    async function cargarColaTickets() {
      const tbody = document.getElementById('tabla-tickets');
      tbody.innerHTML = '<tr><td colspan="6" class="p-3 text-center text-slate-500">Consultando GLPI...</td></tr>';
      try {
        const resp = await fetch('/api/tickets');
        const tickets = await resp.json();
        document.getElementById('count-tickets').innerText = tickets.length;

        if (tickets.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="p-3 text-center text-slate-500">No hay tickets registrados en GLPI.</td></tr>';
          return;
        }

        tbody.innerHTML = tickets.map(t => {
          const urgNombre = t.urgency === 5 ? 'Crítica' : (t.urgency === 4 ? 'Alta' : (t.urgency === 3 ? 'Media' : 'Baja'));
          const estadoNombre = t.status === 1 ? 'Nuevo' : (t.status === 2 ? 'En curso / Asignado' : 'Resuelto');
          return `
            <tr class="hover:bg-slate-950">
              <td class="p-2.5 font-mono text-slate-400">#${t.id}</td>
              <td class="p-2.5 font-medium text-slate-200">${t.name}</td>
              <td class="p-2.5 text-slate-400 font-mono">${t.date || '-'}</td>
              <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] ${t.status === 1 ? 'bg-slate-800 text-slate-300' : 'bg-slate-800 text-slate-300'}">${estadoNombre}</span></td>
              <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-semibold ${NIVELES_COLOR[urgNombre] || 'bg-slate-800'}">${urgNombre}</span></td>
              <td class="p-2.5">
                <button onclick="corregirHumano(${t.id})" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-2 py-1 rounded border border-slate-700 transition">
                  Corregir (Feedback)
                </button>
              </td>
            </tr>
          `;
        }).join('');
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="p-3 text-center text-rose-400">Error al consultar GLPI: ${err}</td></tr>`;
      }
    }

    async function corregirHumano(id) {
      const nuevaUrg = prompt('Ingresa la corrección de urgencia (Crítica, Alta, Media, Baja):', 'Alta');
      if (!nuevaUrg) return;
      try {
        const resp = await fetch('/api/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_ticket: id, urgencia_corregida: nuevaUrg })
        });
        const res = await resp.json();
        alert('Corrección registrada. El agente ahora utilizará este aprendizaje para casos similares.');
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
          <div class="bg-slate-950 p-3.5 rounded border border-slate-800">
            <h4 class="font-bold text-xs text-slate-200">${t.nombre}</h4>
            <p class="text-[11px] text-slate-400 mb-2">${t.rol}</p>
            <p class="text-[11px] text-slate-500 mb-2">Grupo: <span class="text-slate-300">${t.grupo}</span></p>
            <div class="text-[10px] text-slate-400">
              Especialidades: ${t.especialidades.map(e => `<span class="bg-slate-900 border border-slate-800 px-1 py-0.5 rounded text-slate-300 mr-1">${e}</span>`).join('')}
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

    cargarColaTickets();
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    agente: AgenteTriaje = None
    cliente_glpi: ClienteGLPI = None

    def log_message(self, format, *args):
        pass

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

            decision = self.agente.procesar_ticket(ticket_sim)

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
            asunto = ""
            desc = ""

            if str(id_t) in self.agente.memoria.historial_decisiones:
                tk = self.agente.memoria.historial_decisiones[str(id_t)]["ticket"]
                asunto = tk.get("asunto", "")
                desc = tk.get("descripcion", "")
            elif self.cliente_glpi and self.cliente_glpi.session_token:
                try:
                    req = urllib.request.Request(
                        f"{self.cliente_glpi.url_base}/Ticket/{id_t}",
                        headers={"Session-Token": self.cliente_glpi.session_token},
                    )
                    with urllib.request.urlopen(req, timeout=3) as r:
                        glpi_tk = json.loads(r.read().decode())
                        asunto = glpi_tk.get("name", "")
                        desc = glpi_tk.get("content", "")
                except Exception:
                    pass

            self.agente.memoria.registrar_feedback_humano(
                id_ticket=id_t,
                urgencia_humana=urg_corregida,
                formulario_humano="Fallas Técnicas TIC",
                comentarios="Ajuste manual del tecnico desde Dashboard",
                asunto=asunto,
                descripcion=desc,
            )
            self.enviar_json({"ok": True, "mensaje": "Correccion registrada en la memoria activa del agente."})
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
    print(" PANEL WEB DEL AGENTE DE TRIAJE INICIADO CON EXITO ".center(80))
    print("=" * 80)
    print(f"  URL del Dashboard:    http://localhost:{puerto}")
    print(f"  Conexion GLPI:        {modo_str}")
    print("  Panel institucional sin gradientes ni emojis.")
    print("  Presiona Ctrl+C para detener el servidor.")
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
