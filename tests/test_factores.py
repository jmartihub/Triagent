import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from triage.agent import AgenteTriaje, combinar_factores, factores_por_frases, limpiar_texto

MODELO = {"tipo": "falla", "alcance": "grupo", "bloquea": True, "plazo": "cercano", "alternativa": False}


def frases(texto):
    return factores_por_frases(limpiar_texto(texto))


def test_sin_frases_decide_el_modelo():
    assert combinar_factores(frases("algo raro pasa con la plataforma"), MODELO) == MODELO
    print("[OK] Factores: sin frases explícitas decide el modelo")


def test_frase_explicita_manda_sobre_el_modelo():
    combinados = combinar_factores(frases("no funciona pero puedo seguir trabajando desde el celular"), MODELO)
    assert combinados["bloquea"] is False
    assert combinados["alternativa"] is True
    print("[OK] Factores: una frase explícita manda sobre el modelo")


def test_alcance_y_plazo_toman_el_valor_mas_grave():
    combinados = combinar_factores(frases("no carga y la entrega es mañana"), dict(MODELO, plazo="inmediato"))
    assert combinados["plazo"] == "inmediato"
    combinados = combinar_factores(frases("a nadie le funciona, caida general"), MODELO)
    assert combinados["alcance"] == "institucional"
    print("[OK] Factores: alcance y plazo toman el valor más grave entre frase y modelo")


def test_incidente_resuelto_ignora_el_modelo():
    combinados = combinar_factores(frases("no abria pero ya funciona"), MODELO)
    assert combinados["bloquea"] is False and combinados["plazo"] == "ninguno"
    print("[OK] Factores: un incidente ya resuelto no se reabre por el modelo")


def test_alternativa_negada_no_cuenta_como_alternativa():
    assert frases("no tengo otro computador")["evidencia"]["con_alternativa"] is False
    assert frases("sin otro dispositivo a la mano")["evidencia"]["con_alternativa"] is False
    assert frases("puedo usar otro computador")["evidencia"]["con_alternativa"] is True
    print("[OK] Factores: una alternativa negada no cuenta como alternativa")


def test_agente_usa_los_modelos_de_factores():
    agente = AgenteTriaje(usar_deep_learning=True)
    assert agente.percepcion_factores is not None
    percepcion = agente.percibir({"asunto": "Banner", "descripcion": "no abre", "apoyo": "Banner"})
    assert set(percepcion["factores_modelo"]) == set(MODELO)
    print("[OK] Factores: el agente carga y usa los modelos por factor")


if __name__ == "__main__":
    test_sin_frases_decide_el_modelo()
    test_frase_explicita_manda_sobre_el_modelo()
    test_alcance_y_plazo_toman_el_valor_mas_grave()
    test_incidente_resuelto_ignora_el_modelo()
    test_alternativa_negada_no_cuenta_como_alternativa()
    test_agente_usa_los_modelos_de_factores()
    print("\nTodos los tests de factores pasaron exitosamente.")
