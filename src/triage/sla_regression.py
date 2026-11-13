"""Modelo Estadístico de Regresión para Estimación de Tiempo de Resolución y Riesgo de SLA.

Entrena y evalúa modelos matemáticos de regresión:
- Regresión Lineal múltiple
- Regresión Polinomial / Cuadrática
- Regresión Regularizada (Ridge)

Variables predictoras:
- Nivel de Urgencia (Crítica=0, Alta=1, Media=2, Baja=3)
- Tipo de Solicitud (falla=1, duda=0)
- Complejidad de la Plataforma (peso según criticidad técnica)
- Carga actual de la cola de soporte (número de tickets pendientes)

Salida:
- Horas estimadas para la resolución
- Evaluación del riesgo de incumplimiento del SLA asignado
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

RAIZ = Path(__file__).resolve().parents[2]

PESO_COMPLEJIDAD_PLATAFORMA = {
    "red_wifi": 3.5,
    "banner": 3.0,
    "pagos_linea": 2.8,
    "teams": 2.2,
    "sala_virtual": 2.0,
    "liquidacion_matricula": 2.0,
    "software_salas": 1.5,
    "computadores_fisicos": 1.2,
    "accesos_cuentas": 1.0,
    "correo": 0.8,
}

URGENCIA_ENCODING = {"Crítica": 0, "Alta": 1, "Media": 2, "Baja": 3}


def generar_datos_historicos_sla(n: int = 2500, semilla: int = 42) -> pd.DataFrame:
    """Genera datos históricos simulados de tickets resueltos con tiempos reales de atención."""
    rng = np.random.default_rng(semilla)

    urgencias = rng.choice(["Crítica", "Alta", "Media", "Baja"], size=n, p=[0.12, 0.18, 0.45, 0.25])
    es_falla = rng.binomial(1, 0.75, size=n)
    plataformas = rng.choice(list(PESO_COMPLEJIDAD_PLATAFORMA.keys()), size=n)
    complejidad = np.array([PESO_COMPLEJIDAD_PLATAFORMA[p] for p in plataformas])
    carga_cola = rng.integers(1, 45, size=n)

    # Fórmula del tiempo base de resolución (horas) con efectos cuadráticos y no lineales de cola:
    # A mayor urgencia (Crítica=0), mayor prioridad -> menor tiempo de espera.
    # A mayor cola y complejidad, el tiempo sube no linealmente.
    base_horas = {
        "Crítica": 1.0,   # SLA límite: 2.0h
        "Alta": 4.5,      # SLA límite: 8.0h
        "Media": 14.0,    # SLA límite: 24.0h
        "Baja": 38.0,     # SLA límite: 72.0h
    }

    t_base = np.array([base_horas[u] for u in urgencias])
    efecto_cola = 0.15 * carga_cola + 0.004 * (carga_cola ** 2)
    efecto_complejidad = 1.2 * complejidad * es_falla
    ruido = rng.normal(0, 1.5, size=n)

    horas_reales = np.maximum(0.25, t_base + efecto_cola + efecto_complejidad + ruido)

    df = pd.DataFrame({
        "urgencia": urgencias,
        "urgencia_cod": [URGENCIA_ENCODING[u] for u in urgencias],
        "es_falla": es_falla,
        "plataforma": plataformas,
        "complejidad": complejidad,
        "carga_cola": carga_cola,
        "horas_resolucion": np.round(horas_reales, 2),
    })
    return df


class EstimadorSLA:
    def __init__(self):
        self.modelo = None
        self.metricas = {}

    def entrenar(self, df: pd.DataFrame) -> Dict[str, Any]:
        X = df[["urgencia_cod", "es_falla", "complejidad", "carga_cola"]]
        y = df["horas_resolucion"]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Comparación de modelos: Lineal vs Polinomial Cuadrático vs Ridge
        modelos = {
            "Lineal": LinearRegression(),
            "Polinomial_Grado2": Pipeline([
                ("poly", PolynomialFeatures(degree=2, include_bias=False)),
                ("scaler", StandardScaler()),
                ("reg", LinearRegression()),
            ]),
            "Ridge": Pipeline([
                ("poly", PolynomialFeatures(degree=2, include_bias=False)),
                ("scaler", StandardScaler()),
                ("reg", Ridge(alpha=1.0)),
            ]),
        }

        resultados = {}
        mejor_r2 = -float("inf")
        mejor_modelo = None
        mejor_nombre = ""

        for nombre, mod in modelos.items():
            mod.fit(X_train, y_train)
            pred = mod.predict(X_test)
            r2 = r2_score(y_test, pred)
            mae = mean_absolute_error(y_test, pred)
            rmse = np.sqrt(mean_squared_error(y_test, pred))

            resultados[nombre] = {
                "R2": round(float(r2), 4),
                "MAE_horas": round(float(mae), 4),
                "RMSE_horas": round(float(rmse), 4),
            }

            if r2 > mejor_r2:
                mejor_r2 = r2
                mejor_modelo = mod
                mejor_nombre = nombre

        self.modelo = mejor_modelo
        self.metricas = {
            "comparativa": resultados,
            "mejor_modelo": mejor_nombre,
            "R2": resultados[mejor_nombre]["R2"],
            "MAE_horas": resultados[mejor_nombre]["MAE_horas"],
        }
        return self.metricas

    def predecir(
        self,
        urgencia: str,
        es_falla: bool,
        plataforma_id: str,
        carga_cola: int = 10,
        limite_sla_horas: float = 24.0,
    ) -> Dict[str, Any]:
        """Calcula el tiempo esperado de resolución y clasifica el riesgo de exceder el SLA."""
        urg_cod = URGENCIA_ENCODING.get(urgencia, 2)
        comp = PESO_COMPLEJIDAD_PLATAFORMA.get(plataforma_id, 1.5)
        fila = pd.DataFrame([{
            "urgencia_cod": urg_cod,
            "es_falla": int(es_falla),
            "complejidad": comp,
            "carga_cola": carga_cola,
        }])

        pred_horas = max(0.2, float(self.modelo.predict(fila)[0]))
        margen = limite_sla_horas - pred_horas

        if pred_horas > limite_sla_horas:
            nivel_riesgo = "Alto (Riesgo Crítico de Incumplimiento)"
        elif margen < (limite_sla_horas * 0.25):
            nivel_riesgo = "Moderado (Cerca del Límite)"
        else:
            nivel_riesgo = "Bajo (En Holgura)"

        return {
            "horas_estimadas": round(pred_horas, 2),
            "limite_sla_horas": limite_sla_horas,
            "margen_horas": round(margen, 2),
            "nivel_riesgo_sla": nivel_riesgo,
        }

    def guardar(self, ruta: Path):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"modelo": self.modelo, "metricas": self.metricas}, ruta)

    @classmethod
    def cargar(cls, ruta: Path) -> "EstimadorSLA":
        datos = joblib.load(ruta)
        est = cls()
        est.modelo = datos["modelo"]
        est.metricas = datos["metricas"]
        return est


def main():
    df = generar_datos_historicos_sla(n=3000)
    ruta_csv = RAIZ / "data" / "historico_sla.csv"
    df.to_csv(ruta_csv, index=False)
    print(f"Datos históricos de SLA generados en {ruta_csv} (n={len(df)})")

    est = EstimadorSLA()
    metricas = est.entrenar(df)
    print("Métricas de regresión de SLA:")
    for mod, vals in metricas["comparativa"].items():
        print(f"  {mod}: R²={vals['R2']} | MAE={vals['MAE_horas']}h | RMSE={vals['RMSE_horas']}h")
    print(f"\nMejor modelo seleccionado: {metricas['mejor_modelo']}")

    ruta_modelo = RAIZ / "models" / "sla_regression.joblib"
    est.guardar(ruta_modelo)
    print(f"Modelo guardado en {ruta_modelo}")


if __name__ == "__main__":
    main()
