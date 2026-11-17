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
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sys
import urllib.parse

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from triage.agent import AgenteTriaje
from triage.glpi_client import ClienteGLPI, GLPIError


URGENCIAS_GLPI = {
    1: "Baja",
    2: "Baja",
    3: "Media",
    4: "Alta",
    5: "Crítica",
}
ESTADOS_GLPI = {
    1: "Nuevo",
    2: "En curso / Asignado",
    3: "Planificado",
    4: "En espera",
    5: "Resuelto",
    6: "Cerrado",
}


def _urgencia_ticket(ticket):
    urgencia = ticket.get("urgency")
    try:
        return URGENCIAS_GLPI.get(int(urgencia))
    except (TypeError, ValueError):
        if isinstance(urgencia, str):
            urgencia_normalizada = urgencia.strip().casefold()
            return next(
                (nombre for nombre in URGENCIAS_GLPI.values() if nombre.casefold() == urgencia_normalizada),
                None,
            )
        return None


def _estado_ticket(ticket):
    estado = ticket.get("status")
    try:
        return int(estado)
    except (TypeError, ValueError):
        if isinstance(estado, str):
            estado_normalizado = estado.strip().casefold()
            return next(
                (codigo for codigo, nombre in ESTADOS_GLPI.items() if nombre.casefold() == estado_normalizado),
                None,
            )
        return None


def _fecha_glpi(valor):
    if not isinstance(valor, str) or not valor.strip():
        return None
    try:
        fecha = datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
        if fecha.tzinfo:
            fecha = fecha.astimezone(timezone.utc).replace(tzinfo=None)
        return fecha
    except ValueError:
        return None


def resumir_tickets(tickets):
    """Calcula métricas únicamente con los datos que GLPI devuelve."""
    urgencias = {"Crítica": 0, "Alta": 0, "Media": 0, "Baja": 0}
    activos = 0
    resueltos = 0
    sla_evaluados = 0
    sla_cumplidos = 0

    for ticket in tickets:
        estado = _estado_ticket(ticket)
        if estado in (5, 6):
            resueltos += 1
            fecha_limite = _fecha_glpi(ticket.get("time_to_resolve"))
            fecha_resolucion = _fecha_glpi(ticket.get("solvedate"))
            if fecha_limite and fecha_resolucion:
                sla_evaluados += 1
                sla_cumplidos += fecha_resolucion <= fecha_limite
        else:
            activos += 1

        urgencia = _urgencia_ticket(ticket)
        if urgencia:
            urgencias[urgencia] += 1

    return {
        "total": len(tickets),
        "activos": activos,
        "resueltos": resueltos,
        "urgencias": urgencias,
        "sin_urgencia": len(tickets) - sum(urgencias.values()),
        "sla": {
            "cumplimiento_pct": round(sla_cumplidos * 100 / sla_evaluados, 1) if sla_evaluados else None,
            "evaluados": sla_evaluados,
        },
    }


HTML_INDEX = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mesa de Ayuda TI - Agente de Triaje y Priorización</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    :root {
      color-scheme: dark;
      font-size: 17px;
      --scroll-track: #0f172a;
      --scroll-thumb: #475569;
    }

    html { scrollbar-width: thin; scrollbar-color: var(--scroll-thumb) var(--scroll-track); }
    body { font-size: 17px; }
    .text-xs { font-size: 0.875rem !important; line-height: 1.25rem; }
    .text-\\[10px\\] { font-size: 0.75rem !important; line-height: 1rem; }
    .text-\\[11px\\] { font-size: 0.8125rem !important; line-height: 1.125rem; }

    * { scrollbar-width: thin; scrollbar-color: var(--scroll-thumb) var(--scroll-track); }
    *::-webkit-scrollbar { width: 10px; height: 10px; }
    *::-webkit-scrollbar-track { background: var(--scroll-track); border-radius: 9999px; }
    *::-webkit-scrollbar-thumb {
      background: var(--scroll-thumb);
      border: 2px solid var(--scroll-track);
      border-radius: 9999px;
    }
    *::-webkit-scrollbar-thumb:hover { background: #64748b; }

    .badge-critica { background: #450a0a; color: #fca5a5; border: 1px solid #991b1b; }
    .badge-alta { background: #431407; color: #fdba74; border: 1px solid #9a3412; }
    .badge-media { background: #172554; color: #93c5fd; border: 1px solid #1e40af; }
    .badge-baja { background: #064e3b; color: #86efac; border: 1px solid #166534; }

    body.theme-light {
      color-scheme: light;
      background: #f1f5f9 !important;
      color: #0f172a !important;
      --scroll-track: #e2e8f0;
      --scroll-thumb: #94a3b8;
    }
    .theme-light .bg-slate-950 { background-color: #ffffff !important; }
    .theme-light .bg-slate-900 { background-color: #f8fafc !important; }
    .theme-light .bg-slate-800 { background-color: #e2e8f0 !important; }
    .theme-light .text-white { color: #0f172a !important; }
    .theme-light .text-slate-100 { color: #0f172a !important; }
    .theme-light .text-slate-200 { color: #1e293b !important; }
    .theme-light .text-slate-300 { color: #334155 !important; }
    .theme-light .text-slate-400 { color: #475569 !important; }
    .theme-light .text-slate-500 { color: #64748b !important; }
    .theme-light .border-slate-800,
    .theme-light .border-slate-700 { border-color: #cbd5e1 !important; }
    .theme-light .hover\\:bg-slate-700:hover,
    .theme-light .hover\\:bg-slate-950:hover { background-color: #e2e8f0 !important; }
    .theme-light .text-rose-400 { color: #be123c !important; }
    .theme-light .text-amber-400 { color: #b45309 !important; }
    .theme-light .text-blue-400 { color: #1d4ed8 !important; }
    .theme-light .text-emerald-400 { color: #047857 !important; }
    .theme-light [class*="text-rose-400/"] { color: #9f1239 !important; }
    .theme-light [class*="text-amber-400/"] { color: #92400e !important; }
    .theme-light [class*="text-blue-400/"] { color: #1e40af !important; }
    .theme-light [class*="text-emerald-400/"] { color: #065f46 !important; }
    .theme-light [class*="bg-rose-950"] { background-color: #fff1f2 !important; }
    .theme-light [class*="bg-amber-950"] { background-color: #fffbeb !important; }
    .theme-light [class*="bg-blue-950"] { background-color: #eff6ff !important; }
    .theme-light [class*="border-rose-950"],
    .theme-light [class*="border-rose-800"] { border-color: #fecdd3 !important; }
    .theme-light [class*="border-amber-950"],
    .theme-light [class*="border-amber-800"] { border-color: #fde68a !important; }
    .theme-light [class*="border-blue-800"] { border-color: #bfdbfe !important; }
    .theme-light .badge-critica { background: #fee2e2; color: #991b1b; border-color: #fca5a5; }
    .theme-light .badge-alta { background: #ffedd5; color: #9a3412; border-color: #fdba74; }
    .theme-light .badge-media { background: #dbeafe; color: #1e40af; border-color: #93c5fd; }
    .theme-light .badge-baja { background: #d1fae5; color: #065f46; border-color: #6ee7b7; }

    .app-shell {
      --surface: #ffffff;
      --surface-muted: #f7f8fa;
      --line: #e4e7ec;
      --ink: #344054;
      --muted: #667085;
      display: grid;
      grid-template-columns: 248px minmax(0, 1fr);
      min-height: 100vh;
      background: #f4f5f7;
    }
    .sidebar {
      display: flex;
      flex-direction: column;
      gap: 2rem;
      padding: 1.5rem 1rem;
      background: #fbfbfc;
      border-right: 1px solid var(--line);
    }
    .sidebar-brand { display: flex; align-items: center; gap: 0.75rem; padding: 0 0.5rem; }
    .brand-mark {
      display: grid;
      place-items: center;
      width: 2.5rem;
      height: 2.5rem;
      border-radius: 0.8rem;
      background: #e8edf5;
      color: #52657f;
      font-size: 0.9rem;
      font-weight: 700;
      letter-spacing: 0.04em;
    }
    .sidebar-brand-title { color: #344054; font-size: 1rem; font-weight: 700; }
    .sidebar-brand-subtitle { color: #87909e; font-size: 0.72rem; margin-top: 0.1rem; }
    .sidebar-nav-label, .eyebrow {
      color: #87909e;
      font-size: 0.68rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .sidebar-nav-label { padding: 0 0.75rem; margin-bottom: 0.6rem; }
    .sidebar-nav { display: grid; gap: 0.35rem; }
    .sidebar-link {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      width: 100%;
      padding: 0.7rem 0.75rem;
      border: 1px solid transparent;
      border-radius: 0.65rem;
      background: transparent;
      color: #667085;
      font: inherit;
      font-size: 0.88rem;
      text-align: left;
      cursor: pointer;
      transition: background-color 140ms ease, color 140ms ease, border-color 140ms ease;
    }
    .sidebar-link:hover { background: #f0f2f5; color: #344054; }
    .sidebar-link.active { background: #e9eef6; border-color: #dce4ef; color: #425675; font-weight: 600; }
    .nav-index {
      display: grid;
      place-items: center;
      width: 1.55rem;
      height: 1.55rem;
      border-radius: 0.45rem;
      background: #f0f2f5;
      color: #808a99;
      font-size: 0.68rem;
      font-variant-numeric: tabular-nums;
    }
    .sidebar-link.active .nav-index { background: #dce5f1; color: #52657f; }
    .nav-count {
      margin-left: auto;
      color: #87909e;
      font-size: 0.76rem;
      font-variant-numeric: tabular-nums;
    }
    .sidebar-footer {
      display: flex;
      align-items: center;
      gap: 0.55rem;
      margin-top: auto;
      padding: 0.85rem 0.75rem;
      border-top: 1px solid var(--line);
      color: #7a8492;
      font-size: 0.77rem;
    }
    .connection-dot { width: 0.5rem; height: 0.5rem; border-radius: 50%; background: #94b9a2; }
    .workspace { display: flex; flex-direction: column; min-width: 0; height: 100vh; }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      min-height: 6rem;
      padding: 1rem 2rem;
      background: rgba(255, 255, 255, 0.82);
      border-bottom: 1px solid var(--line);
    }
    .topbar h1 { margin-top: 0.2rem; color: #344054; font-size: 1.3rem; font-weight: 650; letter-spacing: -0.02em; }
    .topbar-actions { display: flex; align-items: center; justify-content: flex-end; gap: 0.65rem; }
    .workspace-content { min-height: 0; flex: 1; overflow: auto; padding: 1.5rem 2rem 2rem; }
    .view-section { max-width: 1440px; margin: 0 auto; }
    .view-section[hidden] { display: none !important; }
    .summary-view { display: grid; gap: 1rem; }
    .summary-view > .bg-slate-900 { margin: 0; }
    .summary-heading { color: #344054; font-size: 1rem; font-weight: 650; }
    .summary-subheading { color: #7a8492; font-size: 0.82rem; margin-top: 0.25rem; }
    .summary-kpis { grid-template-columns: repeat(6, minmax(0, 1fr)); }
    .dashboard-overview-grid { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(280px, 1fr); gap: 1rem; }
    .summary-subcard { min-width: 0; padding: 1.1rem 1.2rem; background: #fff; border: 1px solid #e4e7ec; border-radius: 0.75rem; }
    .subcard-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.8rem; padding-bottom: 0.8rem; border-bottom: 1px solid #edf0f3; }
    .recent-ticket-list { display: grid; }
    .activity-row { display: flex; align-items: center; gap: 0.8rem; min-width: 0; padding: 0.75rem 0; border-bottom: 1px solid #edf0f3; }
    .activity-row:last-child { border-bottom: 0; }
    .activity-id { flex: 0 0 auto; color: #8490a0; font-family: ui-monospace, monospace; font-size: 0.74rem; }
    .activity-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 0.2rem; }
    .activity-subject { overflow: hidden; color: #344054; font-size: 0.83rem; font-weight: 550; text-overflow: ellipsis; white-space: nowrap; }
    .activity-meta { color: #818b99; font-size: 0.72rem; }
    .activity-urgency { flex: 0 0 auto; padding: 0.2rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 600; }
    .badge-unclassified { background: #f0f2f5; color: #737f8f; }
    .status-breakdown { display: grid; gap: 1.1rem; padding-top: 1.1rem; }
    .status-breakdown-row { display: grid; gap: 0.45rem; }
    .status-breakdown-label { display: flex; justify-content: space-between; color: #687385; font-size: 0.8rem; }
    .status-breakdown-label strong { color: #3b4656; font-variant-numeric: tabular-nums; font-weight: 650; }
    .status-track { height: 0.42rem; overflow: hidden; background: #f0f2f5; border-radius: 9999px; }
    .status-fill { display: block; width: 0; height: 100%; border-radius: inherit; transition: width 180ms ease; }
    .status-new { background: #a8b8cd; }
    .status-progress { background: #aec4b3; }
    .status-waiting { background: #d7c8a9; }
    .status-done { background: #b8c5d2; }
    .tickets-panel { display: flex; flex-direction: column; min-height: 0; }
    .tickets-table-wrap { max-height: calc(100vh - 16rem); overflow: auto; }
    .theme-light .topbar-actions .bg-slate-800 { background: #f3f4f6; color: #5b6472; border-color: #e1e4e9; }
    .theme-light .topbar-actions .hover\\:bg-slate-700:hover { background: #e9edf2; }
    .theme-light .app-shell { background: #f4f5f7; }
    .theme-dark .app-shell {
      --surface: #111827;
      --surface-muted: #1f2937;
      --line: #334155;
      --ink: #e2e8f0;
      --muted: #94a3b8;
      background: #0f172a;
    }
    .theme-dark .sidebar { background: #111827; border-color: #334155; }
    .theme-dark .sidebar-brand-title,
    .theme-dark .topbar h1,
    .theme-dark .summary-heading { color: #e2e8f0; }
    .theme-dark .sidebar-brand-subtitle,
    .theme-dark .sidebar-nav-label,
    .theme-dark .eyebrow,
    .theme-dark .summary-subheading { color: #94a3b8; }
    .theme-dark .brand-mark,
    .theme-dark .nav-index { background: #1f2937; color: #cbd5e1; }
    .theme-dark .sidebar-link { color: #cbd5e1; }
    .theme-dark .sidebar-link:hover { background: #1f2937; color: #f8fafc; }
    .theme-dark .sidebar-link.active { background: #263449; border-color: #3b4b62; color: #e2e8f0; }
    .theme-dark .sidebar-link.active .nav-index { background: #34445b; color: #e2e8f0; }
    .theme-dark .sidebar-footer { border-color: #334155; color: #94a3b8; }
    .theme-dark .topbar { background: #111827; border-color: #334155; }
    .theme-dark .topbar-actions .bg-slate-800 { background: #1f2937; color: #cbd5e1; border-color: #475569; }
    .theme-dark .topbar-actions .hover\\:bg-slate-700:hover { background: #334155; }
    .theme-dark .connection-dot { background: #86a990; }
    .theme-dark .summary-subcard { background: #111827; border-color: #334155; }
    .theme-dark .subcard-heading,
    .theme-dark .activity-row { border-color: #293548; }
    .theme-dark .activity-subject { color: #e2e8f0; }
    .theme-dark .activity-id,
    .theme-dark .activity-meta,
    .theme-dark .status-breakdown-label { color: #94a3b8; }
    .theme-dark .badge-unclassified { background: #293548; color: #aab6c5; }
    .theme-dark .status-breakdown-label strong { color: #cbd5e1; }
    .theme-dark .status-track { background: #1f2937; }
    .theme-dark .status-new { background: #7185a0; }
    .theme-dark .status-progress { background: #718f7b; }
    .theme-dark .status-waiting { background: #9f8c68; }
    .theme-dark .status-done { background: #718396; }
    .theme-dark .bg-rose-600 { background-color: #9e6d76 !important; }
    .theme-dark .bg-amber-600 { background-color: #9b835e !important; }
    .theme-dark .bg-blue-600 { background-color: #6f87a2 !important; }
    .theme-dark .bg-slate-600 { background-color: #64748b !important; }
    .theme-dark .badge-critica { background: #43343b; color: #d5aeb4; border-color: #674c55; }
    .theme-dark .badge-alta { background: #463d31; color: #d5c09d; border-color: #716044; }
    .theme-dark .badge-media { background: #303e50; color: #b4c4d7; border-color: #4a6078; }
    .theme-dark .badge-baja { background: #30443a; color: #b4cbb9; border-color: #4d6957; }
    .theme-dark .text-rose-400 { color: #d5aeb4 !important; }
    .theme-dark .text-amber-400 { color: #d5c09d !important; }
    .theme-dark .text-blue-400 { color: #b4c4d7 !important; }
    .theme-dark .text-emerald-400 { color: #b4cbb9 !important; }
    .theme-light .bg-blue-700 { background-color: #9fb6cf !important; color: #26384d !important; }
    .theme-light .hover\\:bg-blue-600:hover { background-color: #8fa9c4 !important; }
    .theme-light .bg-rose-600 { background-color: #d7a4aa !important; }
    .theme-light .bg-amber-600 { background-color: #ddc49a !important; }
    .theme-light .bg-blue-600 { background-color: #a4bad2 !important; }
    .theme-light .bg-slate-600 { background-color: #b7c0cc !important; }
    .theme-light .text-rose-400 { color: #a96d76 !important; }
    .theme-light .text-amber-400 { color: #9a7a47 !important; }
    .theme-light .text-blue-400 { color: #657f9f !important; }
    .theme-light .text-emerald-400 { color: #638b72 !important; }
    .theme-light .border-rose-950 { border-color: #eedbdd !important; }
    .theme-light .border-amber-950 { border-color: #eee5d5 !important; }
    .theme-light .border-blue-950 { border-color: #dce5ef !important; }
    .theme-light .border-emerald-950 { border-color: #dce9df !important; }
    .theme-light [class*="text-rose-400/"] { color: #ae7a80 !important; }
    .theme-light [class*="text-amber-400/"] { color: #a38a64 !important; }
    .theme-light [class*="text-blue-400/"] { color: #7188a4 !important; }
    .theme-light [class*="text-emerald-400/"] { color: #789681 !important; }
    .theme-light .bg-rose-950\\/40 { background-color: #f7ecee !important; }
    .theme-light .bg-amber-950\\/40 { background-color: #f7f2e8 !important; }
    .theme-light .bg-blue-950\\/40 { background-color: #edf2f7 !important; }
    .theme-light .border-rose-800\\/80 { border-color: #ead4d7 !important; }
    .theme-light .border-amber-800\\/80 { border-color: #e9dfc9 !important; }
    .theme-light .border-blue-800\\/80 { border-color: #d8e2ed !important; }

    @media (max-width: 900px) {
      .app-shell { grid-template-columns: 210px minmax(0, 1fr); }
      .topbar { padding-right: 1.25rem; padding-left: 1.25rem; }
      .workspace-content { padding-right: 1.25rem; padding-left: 1.25rem; }
      .summary-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .dashboard-overview-grid { grid-template-columns: 1fr; }
      .tickets-table { min-width: 0 !important; }
      .queue-date-cell,
      .queue-status { white-space: normal !important; overflow-wrap: anywhere; }
    }
    @media (max-width: 680px) {
      .app-shell { display: flex; flex-direction: column; min-height: 100vh; }
      .sidebar { gap: 0.8rem; padding: 0.8rem; border-right: 0; border-bottom: 1px solid var(--line); }
      .sidebar-brand { padding: 0 0.25rem; }
      .sidebar-brand-subtitle, .sidebar-nav-label, .sidebar-footer { display: none; }
      .sidebar-nav { display: flex; gap: 0.35rem; overflow-x: auto; }
      .sidebar-link { flex: 0 0 auto; width: auto; padding: 0.55rem 0.65rem; font-size: 0.78rem; }
      .nav-index { display: none; }
      .nav-count { margin-left: 0.2rem; }
      .workspace { height: auto; min-height: 0; }
      .topbar { align-items: flex-start; min-height: 0; padding: 1rem; }
      .topbar h1 { font-size: 1.1rem; }
      .topbar-actions { flex-wrap: wrap; }
      .workspace-content { overflow: visible; padding: 1rem; }
    }
    @media (max-width: 640px) {
      .summary-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .queue-date-column { display: none; }
      .tickets-table th:nth-child(1) { width: 10%; }
      .tickets-table th:nth-child(2) { width: 40%; }
      .tickets-table th:nth-child(4) { width: 20%; }
      .tickets-table th:nth-child(5) { width: 12%; }
      .tickets-table th:nth-child(6) { width: 18%; }
    }
  </style>
</head>
<body class="theme-light bg-slate-950 text-slate-200 min-h-screen font-sans">
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-mark" aria-hidden="true">TA</span>
        <div>
          <div class="sidebar-brand-title">Triagent</div>
          <div class="sidebar-brand-subtitle">Mesa de ayuda TI</div>
        </div>
      </div>
      <div>
        <div class="sidebar-nav-label">Espacio de trabajo</div>
        <nav class="sidebar-nav" aria-label="Navegación principal">
          <button type="button" id="nav-resumen" class="sidebar-link active" aria-current="page" onclick="cambiarPestana('resumen')">
            <span class="nav-index">01</span> Resumen
          </button>
          <button type="button" id="nav-simulador" class="sidebar-link" onclick="cambiarPestana('simulador')">
            <span class="nav-index">02</span> Nuevo ticket
          </button>
          <button type="button" id="nav-cola" class="sidebar-link" onclick="cambiarPestana('cola')">
            <span class="nav-index">03</span> Cola GLPI <span id="count-tickets" class="nav-count">0</span>
          </button>
          <button type="button" id="nav-ontologia" class="sidebar-link" onclick="cambiarPestana('ontologia')">
            <span class="nav-index">04</span> Especialistas
          </button>
        </nav>
      </div>
      <div class="sidebar-footer">
        <span class="connection-dot" aria-hidden="true"></span>
        <span>Agente de triaje</span>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div>
          <p class="eyebrow">Panel de gestión</p>
          <h1 id="page-title">Resumen general</h1>
        </div>
        <div class="topbar-actions">
          <button id="btn-theme" type="button" onclick="cambiarTema()" aria-pressed="true" aria-label="Cambiar a modo oscuro" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded border border-slate-700 transition">
            Modo oscuro
          </button>
          <span id="glpi-status" class="px-2.5 py-1.5 text-xs rounded bg-slate-900 text-slate-400 border border-slate-800 font-mono">
            GLPI: Consultando...
          </span>
          <a href="http://localhost:8080" target="_blank" rel="noreferrer" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded border border-slate-700 transition">
            Abrir GLPI
          </a>
        </div>
      </header>

      <main class="workspace-content">
        <section id="sec-resumen" class="view-section summary-view">
          <div class="mb-6 bg-slate-900 border border-slate-800 rounded-lg p-4">
      <div class="flex items-center justify-between pb-3 mb-3 border-b border-slate-800">
        <div>
          <h2 class="summary-heading">
            Estado de la mesa de ayuda
          </h2>
          <p class="summary-subheading">Indicadores de hasta 1.000 tickets recientes de GLPI</p>
        </div>
        <button onclick="cargarMetricasYCola()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded border border-slate-700 transition">
          Actualizar
        </button>
      </div>

      <div class="summary-kpis grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
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
          <span id="kpi-sla" class="text-[10px] text-emerald-400/70 block mt-0.5">SLA: N/D</span>
        </div>
      </div>

      <!-- Barra de distribución visual de urgencias -->
      <div>
        <div class="flex justify-between text-[10px] text-slate-400 mb-1">
          <span>Distribución por urgencia</span>
          <span id="distribucion-label">Consultando tickets...</span>
        </div>
        <div class="w-full h-2 bg-slate-950 rounded-full overflow-hidden flex">
          <div id="bar-critica" style="width: 0%" class="bg-rose-600 transition-all duration-300" title="Crítica"></div>
          <div id="bar-alta" style="width: 0%" class="bg-amber-600 transition-all duration-300" title="Alta"></div>
          <div id="bar-media" style="width: 0%" class="bg-blue-600 transition-all duration-300" title="Media"></div>
          <div id="bar-baja" style="width: 0%" class="bg-slate-600 transition-all duration-300" title="Baja"></div>
        </div>
      </div>
    </div>

          <div class="dashboard-overview-grid">
            <section class="summary-subcard">
              <div class="subcard-heading">
                <div>
                  <h2 class="summary-heading">Actividad reciente</h2>
                  <p class="summary-subheading">Últimos tickets registrados en GLPI</p>
                </div>
                <button type="button" class="text-xs text-slate-400 hover:text-slate-200" onclick="cambiarPestana('cola')">
                  Ver cola
                </button>
              </div>
              <div id="recent-tickets" class="recent-ticket-list">
                <p class="text-xs text-slate-500">Consultando tickets...</p>
              </div>
            </section>

            <section class="summary-subcard">
              <div class="subcard-heading">
                <div>
                  <h2 class="summary-heading">Estado de solicitudes</h2>
                  <p class="summary-subheading">Distribución del periodo consultado</p>
                </div>
              </div>
              <div class="status-breakdown">
                <div class="status-breakdown-row">
                  <div class="status-breakdown-label"><span>Nuevos</span><strong id="estado-nuevo-val">0</strong></div>
                  <div class="status-track"><span id="estado-nuevo-bar" class="status-fill status-new"></span></div>
                </div>
                <div class="status-breakdown-row">
                  <div class="status-breakdown-label"><span>En curso</span><strong id="estado-curso-val">0</strong></div>
                  <div class="status-track"><span id="estado-curso-bar" class="status-fill status-progress"></span></div>
                </div>
                <div class="status-breakdown-row">
                  <div class="status-breakdown-label"><span>En espera</span><strong id="estado-espera-val">0</strong></div>
                  <div class="status-track"><span id="estado-espera-bar" class="status-fill status-waiting"></span></div>
                </div>
                <div class="status-breakdown-row">
                  <div class="status-breakdown-label"><span>Resueltos o cerrados</span><strong id="estado-resuelto-val">0</strong></div>
                  <div class="status-track"><span id="estado-resuelto-bar" class="status-fill status-done"></span></div>
                </div>
              </div>
            </section>
          </div>
        </section>

    <!-- PESTANA 1: SIMULADOR DE TICKETS -->
    <section id="sec-simulador" class="view-section grid grid-cols-1 lg:grid-cols-12 gap-6" hidden>
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
    <section id="sec-cola" class="view-section tickets-panel bg-slate-900 p-5 rounded-lg border border-slate-800" hidden>
      <div class="mb-4 border-b border-slate-800 pb-3">
        <div>
          <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider">Tickets Recientes Registrados en GLPI</h2>
          <p class="text-xs text-slate-400">Hasta 1.000 solicitudes, con estado y urgencia actuales</p>
        </div>
      </div>
      <!-- Filtros Rapidos y Buscador -->
      <div class="flex flex-col lg:flex-row gap-3 items-start lg:items-center justify-between mb-4 text-xs">
        <div class="flex gap-1.5 flex-wrap">
          <button onclick="filtrarTickets('todos')" id="filtro-todos" class="filter-btn px-2.5 py-1 rounded bg-slate-800 text-white border border-slate-700 font-medium">Todos</button>
          <button onclick="filtrarTickets('Crítica')" id="filtro-critica" class="filter-btn px-2.5 py-1 rounded bg-slate-950 text-slate-400 border border-slate-800">Crítica</button>
          <button onclick="filtrarTickets('Alta')" id="filtro-alta" class="filter-btn px-2.5 py-1 rounded bg-slate-950 text-slate-400 border border-slate-800">Alta</button>
          <button onclick="filtrarTickets('Media')" id="filtro-media" class="filter-btn px-2.5 py-1 rounded bg-slate-950 text-slate-400 border border-slate-800">Media</button>
          <button onclick="filtrarTickets('Baja')" id="filtro-baja" class="filter-btn px-2.5 py-1 rounded bg-slate-950 text-slate-400 border border-slate-800">Baja</button>
          <button onclick="filtrarTickets('Nuevo')" id="filtro-nuevo" class="filter-btn px-2.5 py-1 rounded bg-slate-950 text-slate-400 border border-slate-800">Nuevos</button>
          <button onclick="filtrarTickets('En curso')" id="filtro-encurso" class="filter-btn px-2.5 py-1 rounded bg-slate-950 text-slate-400 border border-slate-800">En curso</button>
        </div>
        <div class="w-full sm:w-64">
          <input type="text" id="busqueda-ticket" oninput="buscarTicket()" placeholder="Filtrar por asunto, ID..." class="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-slate-600 text-xs">
        </div>
      </div>

      <div class="tickets-table-wrap overflow-x-auto rounded border border-slate-800">
        <table class="tickets-table w-full min-w-[900px] table-fixed text-left text-xs text-slate-300">
          <thead class="bg-slate-950 text-slate-400 uppercase text-[10px]">
            <tr>
              <th class="w-[8%] px-3 py-2.5">ID</th>
              <th class="w-[29%] px-3 py-2.5">Asunto</th>
              <th class="queue-date-column w-[17%] px-3 py-2.5">Fecha</th>
              <th class="w-[16%] px-3 py-2.5">Estado</th>
              <th class="w-[12%] px-3 py-2.5">Urgencia</th>
              <th class="w-[18%] px-3 py-2.5">Feedback</th>
            </tr>
          </thead>
          <tbody id="tabla-tickets" class="divide-y divide-slate-800">
            <tr><td colspan="6" class="px-3 py-4 text-center text-slate-500">Cargando tickets...</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- PESTANA 3: ONTOLOGIA Y TECNICOS -->
    <section id="sec-ontologia" class="view-section space-y-6" hidden>
      <div class="bg-slate-900 p-5 rounded-lg border border-slate-800">
        <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-1">Catálogo Ontológico de Técnicos y Especialidades</h2>
        <p class="text-xs text-slate-400 mb-4">Mapeo entre plataformas y competencias de enrutamiento</p>
        <div id="grid-tecnicos" class="grid grid-cols-1 md:grid-cols-3 gap-3">
          <!-- Tarjetas generadas por JS -->
        </div>
      </div>
    </section>
      </main>
    </div>
  </div>

  <script>
    const NIVELES_COLOR = {
      'Crítica': 'badge-critica',
      'Alta': 'badge-alta',
      'Media': 'badge-media',
      'Baja': 'badge-baja'
    };
    const ESTADOS = {
      1: 'Nuevo',
      2: 'En curso',
      3: 'Planificado',
      4: 'En espera',
      5: 'Resuelto',
      6: 'Cerrado'
    };
    let ticketsCargados = [];
    let filtroActual = 'todos';

    function aplicarTema(tema) {
      const claro = tema === 'light';
      document.body.classList.toggle('theme-light', claro);
      document.body.classList.toggle('theme-dark', !claro);
      const boton = document.getElementById('btn-theme');
      boton.innerText = claro ? 'Modo oscuro' : 'Modo claro';
      boton.setAttribute('aria-pressed', String(claro));
      boton.setAttribute('aria-label', claro ? 'Cambiar a modo oscuro' : 'Cambiar a modo claro');
      localStorage.setItem('triagent-theme-v2', claro ? 'light' : 'dark');
    }

    function cambiarTema() {
      aplicarTema(document.body.classList.contains('theme-light') ? 'dark' : 'light');
    }

    function escaparHTML(valor) {
      return String(valor ?? '').replace(/[&<>"']/g, caracter => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      })[caracter]);
    }

    async function obtenerJSON(url, opciones) {
      const resp = await fetch(url, opciones);
      const datos = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(datos.mensaje || datos.error || `Error HTTP ${resp.status}`);
      return datos;
    }

    function cambiarPestana(nombre) {
      const secciones = ['resumen', 'simulador', 'cola', 'ontologia'];
      const titulos = {
        resumen: 'Resumen general',
        simulador: 'Procesar una solicitud',
        cola: 'Cola de tickets GLPI',
        ontologia: 'Especialistas y áreas'
      };
      secciones.forEach(seccion => {
        document.getElementById(`sec-${seccion}`).hidden = seccion !== nombre;
        const enlace = document.getElementById(`nav-${seccion}`);
        const activo = seccion === nombre;
        enlace.classList.toggle('active', activo);
        if (activo) enlace.setAttribute('aria-current', 'page');
        else enlace.removeAttribute('aria-current');
      });
      document.getElementById('page-title').innerText = titulos[nombre];
      if (nombre === 'cola') cargarMetricasYCola();
      if (nombre === 'ontologia') cargarOntologia();
    }

    async function cargarMetricasYCola() {
      const label = document.getElementById('distribucion-label');
      label.innerText = 'Consultando tickets...';
      try {
        const data = await obtenerJSON('/api/dashboard');
        ticketsCargados = data.tickets || [];
        renderizarMetricas(data.metricas);
        renderizarResumenActividad(ticketsCargados);
        document.getElementById('glpi-status').innerText = data.glpi_mock
          ? 'GLPI: Modo simulado'
          : 'GLPI: Conectado';
        document.getElementById('glpi-status').className = data.glpi_mock
          ? 'px-2.5 py-1 text-xs rounded bg-slate-900 text-amber-400 border border-amber-800 font-mono'
          : 'px-2.5 py-1 text-xs rounded bg-slate-900 text-emerald-400 border border-emerald-800 font-mono';
        document.getElementById('count-tickets').innerText = ticketsCargados.length;
        renderizarTickets();
      } catch (err) {
        label.innerText = `Error al consultar GLPI: ${err.message}`;
        const estado = document.getElementById('glpi-status');
        estado.innerText = 'GLPI: Error';
        estado.title = err.message;
        estado.className = 'px-2.5 py-1 text-xs rounded bg-slate-900 text-rose-400 border border-rose-800 font-mono';
      }
    }

    function renderizarMetricas(m) {
      if (!m) throw new Error('La respuesta de métricas está incompleta');
      const niveles = ['Crítica', 'Alta', 'Media', 'Baja'];
      document.getElementById('kpi-total').innerText = m.total;
      document.getElementById('kpi-activos').innerText = `${m.activos} activos`;
      document.getElementById('kpi-resueltos').innerText = m.resueltos;
      document.getElementById('kpi-sla').innerText = m.sla.cumplimiento_pct === null
        ? `SLA: N/D (${m.sla.evaluados} evaluables)`
        : `SLA: ${m.sla.cumplimiento_pct}% (${m.sla.evaluados} evaluables)`;

      niveles.forEach((nivel, indice) => {
        const id = ['critica', 'alta', 'media', 'baja'][indice];
        const cantidad = m.urgencias[nivel] || 0;
        const porcentaje = m.total ? cantidad * 100 / m.total : 0;
        document.getElementById(`kpi-${id}`).innerText = cantidad;
        document.getElementById(`kpi-${id}-pct`).innerText = `${porcentaje.toFixed(1)}% del total`;
        document.getElementById(`bar-${id}`).style.width = `${porcentaje}%`;
      });
      document.getElementById('distribucion-label').innerText =
        `${m.total} tickets · ${m.sin_urgencia} sin urgencia clasificada`;
    }

    function renderizarResumenActividad(tickets) {
      const lista = document.getElementById('recent-tickets');
      const recientes = tickets.slice(0, 5);
      lista.innerHTML = recientes.length
        ? recientes.map(ticket => {
          const urgencia = urgenciaNombre(ticket.urgency) || 'Sin clasificar';
          const estado = ESTADOS[Number(ticket.status)] || 'Desconocido';
          const badge = NIVELES_COLOR[urgencia] || 'badge-unclassified';
          return `
            <article class="activity-row">
              <span class="activity-id">#${escaparHTML(ticket.id)}</span>
              <div class="activity-main">
                <span class="activity-subject" title="${escaparHTML(ticket.name || ticket.content || '(Sin asunto)')}">${escaparHTML(ticket.name || ticket.content || '(Sin asunto)')}</span>
                <span class="activity-meta">${escaparHTML(estado)} · ${escaparHTML(ticket.date || 'Fecha no disponible')}</span>
              </div>
              <span class="activity-urgency ${badge}">${escaparHTML(urgencia)}</span>
            </article>
          `;
        }).join('')
        : '<p class="text-xs text-slate-500 py-4">No hay tickets disponibles para mostrar.</p>';

      const conteos = { nuevo: 0, curso: 0, espera: 0, resuelto: 0 };
      tickets.forEach(ticket => {
        const estado = Number(ticket.status);
        if (estado === 1) conteos.nuevo += 1;
        else if (estado === 2 || estado === 3) conteos.curso += 1;
        else if (estado === 4) conteos.espera += 1;
        else if (estado === 5 || estado === 6) conteos.resuelto += 1;
      });
      Object.entries(conteos).forEach(([estado, cantidad]) => {
        document.getElementById(`estado-${estado}-val`).innerText = cantidad;
        document.getElementById(`estado-${estado}-bar`).style.width =
          `${tickets.length ? cantidad * 100 / tickets.length : 0}%`;
      });
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
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.mensaje || data.glpi_error || data.error || `Error HTTP ${resp.status}`);
        renderizarResultado(data);
        await cargarMetricasYCola();
      } catch (err) {
        alert('No se pudo procesar el ticket: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.innerText = 'Procesar y Enviar a GLPI';
      }
    }

    function renderizarResultado(d) {
      document.getElementById('ticket-id-tag').innerText = `Ticket #${d.id_ticket}`;

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
      listEl.innerHTML = (d.justificacion_fol || []).map(f => `<li>${escaparHTML(f)}</li>`).join('') || '<li>Inferencia directa estándar</li>';

      // Respuesta
      document.getElementById('res-respuesta').innerText = d.respuesta_preliminar;
      document.getElementById('sync-glpi-msg').innerText = d.glpi_sincronizado
        ? `Sincronizado con GLPI (ID: #${d.id_ticket})`
        : (d.glpi_error || 'Ticket procesado, pero no se pudo sincronizar con GLPI');
    }

    function filtrarTickets(filtro) {
      filtroActual = filtro;
      document.querySelectorAll('.filter-btn').forEach(boton => {
        const activo = boton.id === `filtro-${filtro.toLocaleLowerCase().replace('í', 'i').replace(' ', '')}`;
        boton.className = `filter-btn px-2.5 py-1 rounded border ${activo
          ? 'bg-slate-800 text-white border-slate-700 font-medium'
          : 'bg-slate-950 text-slate-400 border-slate-800'}`;
      });
      renderizarTickets();
    }

    function buscarTicket() {
      renderizarTickets();
    }

    function renderizarTickets() {
      const tbody = document.getElementById('tabla-tickets');
      const consulta = document.getElementById('busqueda-ticket').value.trim().toLocaleLowerCase();
      const filtrados = ticketsCargados.filter(ticket => {
        const urgencia = urgenciaNombre(ticket.urgency);
        const estado = Number(ticket.status);
        const cumpleFiltro = filtroActual === 'todos'
          || filtroActual === urgencia
          || (filtroActual === 'Nuevo' && estado === 1)
          || (filtroActual === 'En curso' && [2, 3, 4].includes(estado));
        const texto = `${ticket.id ?? ''} ${ticket.name ?? ''} ${ticket.content ?? ''}`.toLocaleLowerCase();
        return cumpleFiltro && texto.includes(consulta);
      });

      document.getElementById('count-tickets').innerText = filtrados.length;
      if (!filtrados.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="p-3 text-center text-slate-500">${
          ticketsCargados.length ? 'No hay tickets que coincidan con el filtro.' : 'No hay tickets registrados en GLPI.'
        }</td></tr>`;
        return;
      }

      tbody.innerHTML = filtrados.map(ticket => {
        const urgencia = urgenciaNombre(ticket.urgency) || 'Sin clasificar';
        const estado = Number(ticket.status);
        const estadoNombre = ESTADOS[estado] || 'Desconocido';
        const id = Number.parseInt(ticket.id, 10);
        const botonFeedback = Number.isSafeInteger(id)
          ? `<button onclick="corregirHumano(${id})" title="Corregir la urgencia" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-2 py-1 rounded border border-slate-700 transition whitespace-nowrap">Corregir</button>`
          : '<span class="text-slate-500">No disponible</span>';
        return `
          <tr class="hover:bg-slate-950">
            <td class="px-3 py-2.5 font-mono text-slate-400">${escaparHTML(`#${ticket.id}`)}</td>
            <td class="px-3 py-2.5 font-medium text-slate-200 truncate" title="${escaparHTML(ticket.name || ticket.content || '(Sin asunto)')}">${escaparHTML(ticket.name || ticket.content || '(Sin asunto)')}</td>
            <td class="queue-date-column queue-date-cell px-3 py-2.5 text-slate-400 font-mono">${escaparHTML(ticket.date || '-')}</td>
            <td class="px-3 py-2.5"><span class="queue-status px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">${estadoNombre}</span></td>
            <td class="px-3 py-2.5"><span class="px-1 py-0.5 rounded text-[10px] font-semibold whitespace-nowrap ${NIVELES_COLOR[urgencia] || 'bg-slate-800 text-slate-400'}">${urgencia}</span></td>
            <td class="px-3 py-2.5">${botonFeedback}</td>
          </tr>
        `;
      }).join('');
    }

    function urgenciaNombre(valor) {
      const numero = Number(valor);
      if (numero === 1 || numero === 2) return 'Baja';
      if (numero === 3) return 'Media';
      if (numero === 4) return 'Alta';
      if (numero === 5) return 'Crítica';
      return Object.keys(NIVELES_COLOR).find(nivel => nivel.toLocaleLowerCase() === String(valor).toLocaleLowerCase()) || null;
    }

    async function corregirHumano(id) {
      const nuevaUrg = prompt('Ingresa la corrección de urgencia (Crítica, Alta, Media, Baja):', 'Alta');
      if (!nuevaUrg) return;
      try {
        const res = await obtenerJSON('/api/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_ticket: id, urgencia_corregida: nuevaUrg })
        });
        if (!res.ok) throw new Error(res.mensaje || 'No se pudo registrar la corrección');
        alert('Corrección registrada. El agente ahora utilizará este aprendizaje para casos similares.');
        await cargarMetricasYCola();
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    async function cargarOntologia() {
      const cont = document.getElementById('grid-tecnicos');
      try {
        const data = await obtenerJSON('/api/ontologia');
        cont.innerHTML = data.tecnicos.map(t => `
          <div class="bg-slate-950 p-3.5 rounded border border-slate-800">
            <h4 class="font-bold text-xs text-slate-200">${escaparHTML(t.nombre)}</h4>
            <p class="text-[11px] text-slate-400 mb-2">${escaparHTML(t.rol)}</p>
            <p class="text-[11px] text-slate-500 mb-2">Grupo: <span class="text-slate-300">${escaparHTML(t.grupo)}</span></p>
            <div class="text-[10px] text-slate-400">
              Especialidades: ${t.especialidades.map(e => `<span class="bg-slate-900 border border-slate-800 px-1 py-0.5 rounded text-slate-300 mr-1">${escaparHTML(e)}</span>`).join('')}
            </div>
          </div>
        `).join('');
      } catch (e) {
        cont.innerHTML = `<p class="text-rose-400">${escaparHTML(`Error: ${e}`)}</p>`;
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

    aplicarTema(localStorage.getItem('triagent-theme-v2') || 'light');
    cargarMetricasYCola();
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    agente: AgenteTriaje = None
    cliente_glpi: ClienteGLPI = None

    def log_message(self, format, *args):
        pass

    def obtener_tickets_dashboard(self):
        if not self.cliente_glpi:
            return []
        return self.cliente_glpi.obtener_todos_los_tickets(limite=1000)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)

        if url.path == "/" or url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_INDEX.encode("utf-8"))
            return

        if url.path == "/api/dashboard":
            try:
                tickets = self.obtener_tickets_dashboard()
            except GLPIError as error:
                self.enviar_json({"error": str(error), "glpi_mock": False}, status=502)
                return
            self.enviar_json({
                "tickets": tickets,
                "metricas": resumir_tickets(tickets),
                "glpi_mock": not self.cliente_glpi or self.cliente_glpi.modo_mock,
            })
            return

        if url.path == "/api/tickets":
            try:
                self.enviar_json(self.obtener_tickets_dashboard())
            except GLPIError as error:
                self.enviar_json({"error": str(error)}, status=502)
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
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error(400, "Invalid JSON")
            return
        if not isinstance(datos, dict):
            self.send_error(400, "JSON object required")
            return

        if url.path == "/api/triajar":
            asunto = datos.get("asunto", "")
            descripcion = datos.get("descripcion", "")
            if not isinstance(asunto, str) or not asunto.strip() or not isinstance(descripcion, str) or not descripcion.strip():
                self.send_error(400, "Asunto y descripción son obligatorios")
                return
            form = datos.get("formulario_elegido", "Fallas Técnicas TIC")
            apoyo = datos.get("apoyo", "Otra")
            if not isinstance(form, str) or not isinstance(apoyo, str):
                self.send_error(400, "Formulario y apoyo deben ser texto")
                return

            if not self.cliente_glpi:
                self.enviar_json(
                    {"ok": False, "mensaje": "No hay un cliente de GLPI configurado."},
                    status=503,
                )
                return
            try:
                id_glpi = self.cliente_glpi.crear_ticket(asunto, descripcion)
            except GLPIError as error:
                self.enviar_json({"ok": False, "mensaje": str(error)}, status=502)
                return

            ticket_sim = {
                "id": str(id_glpi),
                "formulario_elegido": form,
                "apoyo": apoyo,
                "asunto": asunto,
                "descripcion": descripcion,
                "fecha_apertura": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

            decision = self.agente.procesar_ticket(ticket_sim)

            try:
                ticket_actualizado = self.cliente_glpi.actualizar_ticket(
                    id_ticket=id_glpi,
                    urgencia_nombre=decision.urgencia_final,
                    tecnico_nombre=decision.tecnico_asignado,
                    formulario_nombre=decision.formulario_final,
                )
                respuesta_registrada = self.cliente_glpi.registrar_respuesta_preliminar(
                    id_ticket=id_glpi,
                    respuesta_texto=decision.respuesta_preliminar,
                )
            except GLPIError as error:
                res = asdict(decision)
                res["id_ticket"] = id_glpi
                res["glpi_sincronizado"] = False
                res["glpi_error"] = (
                    f"GLPI creó el ticket #{id_glpi}, pero falló su actualización: {error}"
                )
                self.enviar_json(res, status=502)
                return

            res = asdict(decision)
            res["id_ticket"] = id_glpi
            res["glpi_sincronizado"] = ticket_actualizado and respuesta_registrada
            self.enviar_json(res)
            return

        if url.path == "/api/feedback":
            id_t = str(datos.get("id_ticket", ""))
            urg_corregida = datos.get("urgencia_corregida")
            if not id_t or urg_corregida not in ("Crítica", "Alta", "Media", "Baja"):
                self.send_error(400, "Ticket y urgencia válidos son obligatorios")
                return
            asunto = ""
            desc = ""

            if str(id_t) in self.agente.memoria.historial_decisiones:
                tk = self.agente.memoria.historial_decisiones[str(id_t)]["ticket"]
                asunto = tk.get("asunto", "")
                desc = tk.get("descripcion", "")
            elif self.cliente_glpi and self.cliente_glpi.session_token:
                try:
                    glpi_tk = self.cliente_glpi.obtener_ticket(int(id_t))
                    asunto = glpi_tk.get("name", "")
                    desc = glpi_tk.get("content", "")
                except (ValueError, GLPIError) as error:
                    self.enviar_json(
                        {"ok": False, "mensaje": f"No se pudo consultar el ticket en GLPI: {error}"},
                        status=502,
                    )
                    return

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

    def enviar_json(self, obj, status: int = 200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def iniciar_servidor(puerto: int = 5000):
    agente = AgenteTriaje(usar_deep_learning=True)
    cliente_glpi = ClienteGLPI(modo_mock=False)
    try:
        cliente_glpi.conectar()
    except GLPIError as error:
        raise SystemExit(
            "No se pudo conectar con GLPI. Revisa que Docker esté activo, "
            f"la API legacy esté habilitada y el cliente/API tenga permiso para esta IP.\nDetalle: {error}"
        ) from error

    DashboardHandler.agente = agente
    DashboardHandler.cliente_glpi = cliente_glpi

    servidor = HTTPServer(("0.0.0.0", puerto), DashboardHandler)
    print("\n" + "=" * 80)
    print(" PANEL WEB DEL AGENTE DE TRIAJE INICIADO CON EXITO ".center(80))
    print("=" * 80)
    print(f"  URL del Dashboard:    http://localhost:{puerto}")
    print("  Conexion GLPI:        Conectado (API legacy)")
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
