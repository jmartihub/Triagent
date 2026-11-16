"""Módulo de Ontología de Soporte TI.

Implementa la representación formal del conocimiento de la mesa de ayuda:
- Jerarquía de servicios y plataformas
- Grupos resolutores especializados
- Competencias y roles de los técnicos
- Políticas de SLA y tiempos máximos de atención
- Generación de explicaciones audibles del enrutamiento
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

RAIZ = Path(__file__).resolve().parents[2]


@dataclass
class AsignacionTecnica:
    grupo_id: str
    grupo_nombre: str
    tecnico_id: str
    tecnico_nombre: str
    tecnico_correo: str
    plataforma_id: str
    plataforma_nombre: str
    tiempo_max_resolucion_horas: float
    tiempo_primera_respuesta_minutos: int
    explicacion_ontologica: str


class OntologiaTI:
    def __init__(self, ruta_config: Optional[Path] = None):
        self.ruta = ruta_config or (RAIZ / "config" / "ontology.yaml")
        self.datos: Dict[str, Any] = yaml.safe_load(self.ruta.read_text(encoding="utf-8"))
        self.servicios = self.datos.get("servicios_plataformas", {})
        self.grupos = self.datos.get("grupos_soporte", {})
        self.tecnicos = self.datos.get("tecnicos", [])
        self.sla = self.datos.get("politicas_sla", {})
        self.mapeo_apoyo = self.datos.get("mapeo_apoyo_plataforma", {})

    def identificar_plataforma(self, apoyo: str, asunto: str = "", descripcion: str = "") -> str:
        """Determina la entidad de plataforma basándose en el apoyo seleccionado o texto."""
        if apoyo in self.mapeo_apoyo:
            return self.mapeo_apoyo[apoyo]

        texto = f"{asunto} {descripcion}".lower()
        if "teams" in texto:
            return "teams"
        if any(w in texto for w in ["wifi", "wi-fi", "red", "internet", "conexion", "switch"]):
            return "red_wifi"
        if any(w in texto for w in ["banner", "materia", "horario", "moodle", "aula virtual", "campus virtual", "nota"]):
            return "banner"
        if any(w in texto for w in ["correo", "buzon", "office", "office 365", "m365", "outlook", "word", "excel", "onedrive"]):
            return "correo"
        if any(w in texto for w in ["pago", "pse", "recibo", "tarjeta", "banco", "factura", "liquidacion", "descuento", "matricula financiera"]):
            return "pagos_linea"
        if any(w in texto for w in ["vdi", "sala virtual", "remoto", "escritorio remoto"]):
            return "sala_virtual"
        if any(w in texto for w in ["autocad", "spss", "matlab", "licencia", "software"]):
            return "software_salas"
        if any(w in texto for w in ["sala", "computador", "laboratorio", "pantalla", "teclado", "mouse", "impresora"]):
            return "computadores_fisicos"
        if any(w in texto for w in ["clave", "contraseña", "usuario", "autenticador", "acceso", "login", "cuenta"]):
            return "accesos_cuentas"

        return "accesos_cuentas"

    def resolver_grupo(self, plataforma_id: str, tipo_solicitud: str = "falla") -> Dict[str, Any]:
        """Deduce el grupo resolutor responsable a partir de las relaciones ontológicas."""
        if tipo_solicitud == "duda":
            # Dudas informativas sin falla crítica pueden ser atendidas por Mesa Nivel 1
            # a menos que sean muy especializadas
            pass

        info_plat = self.servicios.get(plataforma_id)
        if info_plat and "grupo_responsable" in info_plat:
            grupo_id = info_plat["grupo_responsable"]
            return {"id": grupo_id, **self.grupos.get(grupo_id, {})}

        # Por defecto mesa de ayuda nivel 1
        return {"id": "mesa_ayuda_nivel_1", **self.grupos.get("mesa_ayuda_nivel_1", {})}

    def seleccionar_tecnico(self, grupo_id: str, plataforma_id: str, urgencia: str) -> Dict[str, Any]:
        """Selecciona al técnico con mayor afinidad de competencias para el incidente."""
        candidatos = [t for t in self.tecnicos if t["grupo"] == grupo_id]

        if not candidatos:
            # Fallback a técnico general de nivel 1
            candidatos = [t for t in self.tecnicos if t["grupo"] == "mesa_ayuda_nivel_1"]
            if not candidatos:
                candidatos = self.tecnicos

        # Filtrar por especialidad en la plataforma
        especialistas = [t for t in candidatos if plataforma_id in t.get("especialidades", [])]
        if especialistas:
            candidatos = especialistas

        # Si es Crítica o Alta, priorizar nivel de experiencia >= 2 si existe
        if urgencia in ("Crítica", "Alta"):
            experimentados = [t for t in candidatos if t.get("nivel", 1) >= 2]
            if experimentados:
                candidatos = experimentados

        # Escoger el primer candidato disponible
        return candidatos[0]

    def obtener_politica_sla(self, urgencia: str) -> Dict[str, Any]:
        """Retorna los parámetros de SLA según el nivel de urgencia."""
        return self.sla.get(urgencia, self.sla.get("Media", {}))

    def enrutar_ticket(
        self,
        formulario: str,
        apoyo: str,
        urgencia: str,
        asunto: str = "",
        descripcion: str = "",
        tipo: str = "falla",
    ) -> AsignacionTecnica:
        """Ciclo completo de enrutamiento basado en conocimiento ontológico."""
        plataforma_id = self.identificar_plataforma(apoyo, asunto, descripcion)
        plataforma_info = self.servicios.get(plataforma_id, {})
        plataforma_nombre = plataforma_info.get("nombre", plataforma_id)

        grupo_info = self.resolver_grupo(plataforma_id, tipo)
        grupo_id = grupo_info["id"]
        grupo_nombre = grupo_info.get("nombre", grupo_id)

        tecnico = self.seleccionar_tecnico(grupo_id, plataforma_id, urgencia)
        politica = self.obtener_politica_sla(urgencia)

        explicacion = (
            f"El ticket trata sobre la plataforma '{plataforma_nombre}', cuya gestión pertenece "
            f"al grupo especializado '{grupo_nombre}'. Con urgencia '{urgencia}', la política SLA "
            f"establece máximo {politica.get('tiempo_max_resolucion_horas', 24)}h de resolución. "
            f"Se enruta al técnico {tecnico['nombre']} ({tecnico['rol']}) por afinidad de competencias."
        )

        return AsignacionTecnica(
            grupo_id=grupo_id,
            grupo_nombre=grupo_nombre,
            tecnico_id=tecnico["id"],
            tecnico_nombre=tecnico["nombre"],
            tecnico_correo=tecnico["correo"],
            plataforma_id=plataforma_id,
            plataforma_nombre=plataforma_nombre,
            tiempo_max_resolucion_horas=politica.get("tiempo_max_resolucion_horas", 24.0),
            tiempo_primera_respuesta_minutos=politica.get("tiempo_primera_respuesta_minutos", 60),
            explicacion_ontologica=explicacion,
        )
