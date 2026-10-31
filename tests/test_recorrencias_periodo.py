from datetime import date

from trixter.recorrencias import ajustar_dia_mes, calcular_recorrencias_periodo


def test_dia_pedido_cabe_no_mes():
    assert ajustar_dia_mes(2026, 5, 10) == 10
    assert ajustar_dia_mes(2026, 4, 31) == 30
    assert ajustar_dia_mes(2026, 2, 31) == 28
    assert ajustar_dia_mes(2024, 2, 31) == 29


def test_mes_atual_comeca_a_contar_amanha():
    hoje = date(2026, 10, 5)
    mensal = {"proxima_execucao": date(2026, 10, 10), "frequencia": "Mensal", "dia": 10}
    assert calcular_recorrencias_periodo(mensal, 10, 2026, hoje) == 1
    hoje_no_dia = {"proxima_execucao": date(2026, 10, 5), "frequencia": "Mensal", "dia": 5}
    assert calcular_recorrencias_periodo(hoje_no_dia, 10, 2026, hoje) == 0
    ja_passou = {"proxima_execucao": date(2026, 10, 1), "frequencia": "Mensal", "dia": 1}
    assert calcular_recorrencias_periodo(ja_passou, 10, 2026, hoje) == 0


def test_outro_mes_conta_desde_o_dia_primeiro():
    hoje = date(2026, 10, 5)
    setembro = {"proxima_execucao": date(2026, 9, 1), "frequencia": "Mensal", "dia": 1}
    assert calcular_recorrencias_periodo(setembro, 9, 2026, hoje) == 1
    fevereiro = {"proxima_execucao": date(2026, 1, 31), "frequencia": "Mensal", "dia": 31}
    assert calcular_recorrencias_periodo(fevereiro, 2, 2026, hoje) == 1


def test_diaria_semanal_e_anual():
    hoje = date(2026, 10, 5)
    diaria = {"proxima_execucao": date(2026, 10, 6), "frequencia": "Diária"}
    assert calcular_recorrencias_periodo(diaria, 10, 2026, hoje) == 26
    semanal = {"proxima_execucao": date(2026, 10, 6), "frequencia": "Semanal"}
    assert calcular_recorrencias_periodo(semanal, 10, 2026, hoje) == 4
    anual = {
        "proxima_execucao": date(2026, 10, 10),
        "frequencia": "Anual",
        "dia": 10,
        "mes": 10,
    }
    assert calcular_recorrencias_periodo(anual, 10, 2026, hoje) == 1
    assert calcular_recorrencias_periodo(anual, 11, 2026, hoje) == 0
