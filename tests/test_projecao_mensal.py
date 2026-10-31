import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

from trixter.planejamento import compor_gasto_categoria, compor_projecao_mensal
from trixter.recorrencias import calcular_recorrencias_periodo, ocorrencias_no_mes


def _recorrencia(**extras):
    dados = {
        "id_recorrencia": "r1",
        "tipo": "Gasto",
        "valor": 80,
        "frequencia": "Mensal",
        "dia": 20,
        "proxima_execucao": date(2026, 10, 20),
        "ativa": True,
        "categoria": "Internet",
    }
    dados.update(extras)
    return dados


def test_realizado_entra_uma_vez():
    receitas = [{"valor": 90, "data": date(2026, 10, 12), "categoria": "Serviço"}]
    gastos = [{"valor": 200, "data": date(2026, 10, 12), "categoria": "Mercado"}]
    projecao = compor_projecao_mensal(receitas, gastos, [], [], 10, 2026)
    assert projecao["receitas_realizadas"] == Decimal(90)
    assert projecao["gastos_realizados"] == Decimal(200)
    assert projecao["receitas_planos_abertos"] == 0
    assert projecao["gastos_planos_abertos"] == 0
    assert projecao["receitas_recorrentes_pendentes"] == 0
    assert projecao["gastos_recorrentes_pendentes"] == 0
    assert projecao["receitas_projetadas"] == Decimal(90)
    assert projecao["gastos_projetados"] == Decimal(200)


def test_compromisso_baixado_nao_volta_como_pendente():
    planos = [
        {"tipo": "Receita", "valor": 90, "data": date(2026, 10, 12), "situacao": "Recebido", "categoria": "Serviço"},
        {"tipo": "Despesa", "valor": 200, "data": date(2026, 10, 12), "situacao": "Pago", "categoria": "Mercado"},
    ]
    receitas = [{"valor": 90, "data": date(2026, 10, 12), "categoria": "Serviço"}]
    gastos = [{"valor": 200, "data": date(2026, 10, 12), "categoria": "Mercado"}]
    projecao = compor_projecao_mensal(receitas, gastos, planos, [], 10, 2026)
    assert projecao["receitas_planos_abertos"] == 0
    assert projecao["gastos_planos_abertos"] == 0
    assert projecao["receitas_projetadas"] == Decimal(90)
    assert projecao["gastos_projetados"] == Decimal(200)


def test_planejamento_em_aberto_entra_na_projecao():
    planos = [
        {"tipo": "Receita", "valor": 90, "data": date(2026, 10, 20), "situacao": None, "categoria": "Serviço"},
        {"tipo": "Despesa", "valor": 40, "data": date(2026, 10, 20), "situacao": "", "categoria": "Internet"},
    ]
    projecao = compor_projecao_mensal([], [], planos, [], 10, 2026)
    assert projecao["receitas_planos_abertos"] == Decimal(90)
    assert projecao["gastos_planos_abertos"] == Decimal(40)
    assert projecao["receitas_projetadas"] == Decimal(90)
    assert projecao["gastos_projetados"] == Decimal(40)


def test_recorrencia_futura_pendente_entra_na_projecao():
    projecao = compor_projecao_mensal([], [], [], [_recorrencia()], 10, 2026)
    assert projecao["gastos_recorrentes_pendentes"] == Decimal(80)
    assert projecao["gastos_projetados"] == Decimal(80)
    assert projecao["gastos_realizados"] == 0


def test_recorrencia_ja_efetivada_nao_duplica():
    avancada = _recorrencia(proxima_execucao=date(2026, 11, 20))
    lançado = [{
        "valor": 80,
        "data": date(2026, 10, 20),
        "categoria": "Internet",
        "id_recorrencia": "r1",
    }]
    projecao = compor_projecao_mensal([], lançado, [], [avancada], 10, 2026)
    assert projecao["gastos_realizados"] == Decimal(80)
    assert projecao["gastos_recorrentes_pendentes"] == 0
    assert projecao["gastos_projetados"] == Decimal(80)

    presa = _recorrencia(proxima_execucao=date(2026, 10, 20))
    ainda_presa = compor_projecao_mensal([], lançado, [], [presa], 10, 2026)
    assert ainda_presa["gastos_recorrentes_pendentes"] == 0
    assert ainda_presa["gastos_projetados"] == Decimal(80)


def test_lancamento_manual_semelhante_nao_cancela_recorrencia():
    manual = [{
        "valor": 80,
        "data": date(2026, 10, 20),
        "categoria": "Internet",
        "id_recorrencia": None,
    }]
    projecao = compor_projecao_mensal([], manual, [], [_recorrencia()], 10, 2026)
    assert projecao["gastos_realizados"] == Decimal(80)
    assert projecao["gastos_recorrentes_pendentes"] == Decimal(80)
    assert projecao["gastos_projetados"] == Decimal(160)


def test_recorrencia_inativa_fica_de_fora():
    projecao = compor_projecao_mensal([], [], [], [_recorrencia(ativa=False)], 10, 2026)
    assert projecao["gastos_recorrentes_pendentes"] == 0
    assert projecao["gastos_projetados"] == 0


def test_mes_sem_ocorrencia_nao_recebe_valor():
    anual = _recorrencia(
        frequencia="Anual",
        dia=10,
        mes=10,
        proxima_execucao=date(2026, 10, 10),
    )
    outubro = compor_projecao_mensal([], [], [], [anual], 10, 2026)
    novembro = compor_projecao_mensal([], [], [], [anual], 11, 2026)
    assert outubro["gastos_recorrentes_pendentes"] == Decimal(80)
    assert novembro["gastos_recorrentes_pendentes"] == 0


def test_receita_segue_a_mesma_regra_do_gasto():
    receita = _recorrencia(tipo="Receita", categoria="Contrato", id_recorrencia="rec")
    aberta = compor_projecao_mensal([], [], [], [receita], 10, 2026)
    assert aberta["receitas_recorrentes_pendentes"] == Decimal(80)
    assert aberta["receitas_projetadas"] == Decimal(80)

    efetivada = [{
        "valor": 80,
        "data": date(2026, 10, 20),
        "categoria": "Contrato",
        "id_recorrencia": "rec",
    }]
    ponteiro_avancado = _recorrencia(
        tipo="Receita",
        categoria="Contrato",
        id_recorrencia="rec",
        proxima_execucao=date(2026, 11, 20),
    )
    fechada = compor_projecao_mensal(efetivada, [], [], [ponteiro_avancado], 10, 2026)
    assert fechada["receitas_realizadas"] == Decimal(80)
    assert fechada["receitas_recorrentes_pendentes"] == 0
    assert fechada["receitas_projetadas"] == Decimal(80)

    manual = [{"valor": 80, "data": date(2026, 10, 20), "categoria": "Contrato"}]
    semelhante = compor_projecao_mensal(manual, [], [], [receita], 10, 2026)
    assert semelhante["receitas_projetadas"] == Decimal(160)


def test_troca_de_mes_recalcula_e_o_seletor_permanece_no_fragmento():
    planos = [{
        "tipo": "Despesa",
        "valor": 40,
        "data": date(2026, 10, 20),
        "situacao": None,
        "categoria": "Internet",
    }]
    outubro = compor_projecao_mensal([], [], planos, [], 10, 2026)
    novembro = compor_projecao_mensal([], [], planos, [], 11, 2026)
    assert outubro["gastos_projetados"] == Decimal(40)
    assert novembro["gastos_projetados"] == 0

    texto = Path("trixter/planejamento_mensal.py").read_text(encoding="utf-8")
    arvore = ast.parse(texto)
    funcao = next(
        no for no in arvore.body
        if isinstance(no, ast.FunctionDef) and no.name == "exibir_indicadores_do_mes"
    )
    linhas = texto.splitlines(keepends=True)
    inicio = sum(len(linha) for linha in linhas[:funcao.lineno - 1])
    trecho = "".join(linhas[funcao.lineno - 1:funcao.end_lineno])
    assert "@st.fragment" in texto[:inicio]
    assert 'key="mes_planejamento"' in trecho
    assert 'key="ano_planejamento"' in trecho
    assert "st.rerun()" not in trecho
    assert "montar_cartoes_projecao(" in trecho
    assert "Receitas projetadas" in texto[:inicio]
    assert "Saldo projetado" in texto[:inicio]


def test_componentes_somam_o_projetado_e_a_categoria_usa_a_mesma_regra():
    receitas = [{"valor": 90, "data": date(2026, 10, 12), "categoria": "Serviço"}]
    gastos = [{"valor": 30, "data": date(2026, 10, 12), "categoria": "Internet", "id_recorrencia": "outra"}]
    planos = [
        {"tipo": "Receita", "valor": 10, "data": date(2026, 10, 18), "situacao": None, "categoria": "Serviço"},
        {"tipo": "Despesa", "valor": 15, "data": date(2026, 10, 18), "situacao": None, "categoria": "Internet"},
        {"tipo": "Despesa", "valor": 99, "data": date(2026, 10, 18), "situacao": "Pago", "categoria": "Internet"},
    ]
    recorrencias = [
        _recorrencia(),
        _recorrencia(tipo="Receita", id_recorrencia="rr", categoria="Contrato", valor=25),
    ]
    projecao = compor_projecao_mensal(receitas, gastos, planos, recorrencias, 10, 2026)
    assert projecao["receitas_projetadas"] == (
        projecao["receitas_realizadas"]
        + projecao["receitas_planos_abertos"]
        + projecao["receitas_recorrentes_pendentes"]
    )
    assert projecao["gastos_projetados"] == (
        projecao["gastos_realizados"]
        + projecao["gastos_planos_abertos"]
        + projecao["gastos_recorrentes_pendentes"]
    )
    assert projecao["saldo_projetado"] == (
        projecao["receitas_projetadas"] - projecao["gastos_projetados"]
    )
    fatia = compor_gasto_categoria(gastos, planos, recorrencias, "Internet", 10, 2026)
    assert fatia["realizado"] == Decimal(30)
    assert fatia["planejado_manual"] == Decimal(15)
    assert fatia["recorrentes_previstos"] == Decimal(80)
    assert fatia["projetado"] == fatia["realizado"] + fatia["recorrentes_previstos"] + fatia["planejado_manual"]
    assert fatia["projetado"] == Decimal(125)


def test_legenda_soma_os_componentes_ja_calculados():
    from trixter.planejamento_mensal import composicao_exibida

    receitas = [{"valor": 90, "data": date(2026, 10, 12), "categoria": "Serviço"}]
    gastos = [{"valor": 30, "data": date(2026, 10, 12), "categoria": "Internet"}]
    planos = [
        {"tipo": "Receita", "valor": 10, "data": date(2026, 10, 18), "situacao": None, "categoria": "Serviço"},
        {"tipo": "Despesa", "valor": 15, "data": date(2026, 10, 18), "situacao": None, "categoria": "Internet"},
    ]
    recorrencias = [
        _recorrencia(),
        _recorrencia(tipo="Receita", id_recorrencia="rr", categoria="Contrato", valor=25),
    ]
    projecao = compor_projecao_mensal(receitas, gastos, planos, recorrencias, 10, 2026)
    for direcao in ("receitas", "gastos"):
        realizado, pendente, projetado = composicao_exibida(projecao, direcao)
        assert realizado == projecao[f"{direcao}_realizadas" if direcao == "receitas" else f"{direcao}_realizados"]
        assert pendente == (
            projecao[f"{direcao}_planos_abertos"]
            + projecao[f"{direcao}_recorrentes_pendentes"]
        )
        assert projetado == realizado + pendente
    assert projecao["saldo_projetado"] == (
        projecao["receitas_projetadas"] - projecao["gastos_projetados"]
    )


def test_painel_da_categoria_mostra_os_valores_recebidos():
    from trixter.planejamento_mensal import montar_paineis_categoria

    html_paineis = montar_paineis_categoria([
        {
            "categoria": "Lazer",
            "percentual": 0.4,
            "limite": 500,
            "realizado": 200,
            "restante": 300,
            "projetado": 200,
            "recorrentes": 0,
            "manual": 0,
        },
        {
            "categoria": "Mercado",
            "percentual": 1,
            "limite": 100,
            "realizado": 100,
            "restante": 0,
            "projetado": 100,
            "recorrentes": 0,
            "manual": 0,
        },
    ])
    assert html_paineis.count("class='trixter-categoria'") == 2
    assert "Lazer" in html_paineis and "Mercado" in html_paineis
    assert "40%" in html_paineis and "100%" in html_paineis
    assert "R$ 500,00" in html_paineis and "R$ 0,00" in html_paineis
    for rotulo in ("Limite", "Realizado", "Restante", "Projetado", "Recorrentes previstos", "Planejado manual"):
        assert rotulo in html_paineis
    assert "@media (max-width: 760px)" in html_paineis
    assert "<progress" not in html_paineis
    assert " | " not in html_paineis


def test_grafico_mensal_coloca_as_series_lado_a_lado():
    from trixter.planejamento_mensal import criar_grafico_projecao_mensal

    dados = [
        {"categoria": "Internet", "limite": 100, "realizado": 30, "projetado": 125},
        {"categoria": "Mercado", "limite": 50, "realizado": 10, "projetado": 10},
    ]
    figura = criar_grafico_projecao_mensal(dados)
    assert figura.layout.barmode == "group"
    assert figura.layout.height == 250
    assert [traco.name for traco in figura.data] == ["Limite", "Realizado", "Projetado"]
    assert all(traco.width is None for traco in figura.data)
    unica = criar_grafico_projecao_mensal(dados[:1])
    assert unica.layout.barmode == "group"
    assert unica.layout.width == 460
    assert unica.layout.height == 230
    assert [traco.width for traco in unica.data] == [0.12, 0.12, 0.12]
    assert [traco.offset for traco in unica.data] == [-0.21, -0.06, 0.09]
    assert list(unica.data[0].x) == ["Internet"]
    assert list(figura.data[0].y) == [100, 50]
    assert list(figura.data[1].y) == [30, 10]
    assert list(figura.data[2].y) == [125, 10]
    assert list(figura.data[0].x) == ["Internet", "Mercado"]
    assert figura.layout.xaxis.range is None


def test_cartoes_guardam_o_detalhe_e_formatam_zero():
    from decimal import Decimal
    from trixter.planejamento_mensal import montar_cartoes_projecao

    projecao = {
        "receitas_projetadas": Decimal(0),
        "gastos_projetados": Decimal("10.5"),
        "saldo_projetado": Decimal("-10.5"),
    }
    html_cartoes = montar_cartoes_projecao(
        projecao, "Despesas projetadas", Decimal(0), Decimal(0), Decimal("10.5"), Decimal(0),
    )
    assert html_cartoes.count("class='trixter-cartao-rotulo'") == 3
    assert "Receitas projetadas" in html_cartoes
    assert "R$ 0,00" in html_cartoes
    assert html_cartoes.count("Previsto pendente") == 2
    saldo = html_cartoes.split("Saldo projetado", 1)[1]
    assert "Previsto pendente" not in saldo
    assert "Realizado" not in saldo
    assert "@media (max-width: 760px)" in html_cartoes


def test_vencida_entra_so_se_a_proxima_execucao_ainda_aponta_para_ela():
    vencida = _recorrencia(dia=1, proxima_execucao=date(2026, 10, 1))
    assert ocorrencias_no_mes(vencida, 10, 2026) == [date(2026, 10, 1)]
    assert calcular_recorrencias_periodo(vencida, 10, 2026, date(2026, 10, 12)) == 0
    projecao = compor_projecao_mensal([], [], [], [vencida], 10, 2026)
    assert projecao["gastos_recorrentes_pendentes"] == Decimal(80)

    ja_avancada = _recorrencia(dia=1, proxima_execucao=date(2026, 11, 1))
    assert ocorrencias_no_mes(ja_avancada, 10, 2026) == []
    sem_historico = compor_projecao_mensal([], [], [], [ja_avancada], 10, 2026)
    assert sem_historico["gastos_recorrentes_pendentes"] == 0
