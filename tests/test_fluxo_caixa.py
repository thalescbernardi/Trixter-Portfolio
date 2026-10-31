from datetime import date, datetime
from decimal import Decimal

import pandas as pd

from trixter.fluxo_caixa import (
    consultar_caixa_previsto, exibir_caixa_previsto, ocorrencias_recorrencia,
    projetar_caixa, resumir_por_dia, criar_grafico,
)


def test_agrega_dia_e_acumula_em_ordem():
    dados = pd.DataFrame([
        ("2026-09-03", "Saída", Decimal("150.25")),
        ("2026-09-01", "Entrada", Decimal("100.10")),
        ("2026-09-01", "Entrada", Decimal("20.05")),
    ], columns=["data", "tipo", "valor"])
    resumo = resumir_por_dia(dados)
    assert len(resumo) == 2
    assert list(resumo["Saldo acumulado"]) == [Decimal("120.15"), Decimal("-30.10")]
    assert criar_grafico(resumo).data[2].mode == "lines+markers"


def test_dia_unico_sem_entrada_nao_cria_linha_vertical():
    dados = pd.DataFrame([
        ("2026-09-01", "Saída", Decimal("10")),
        ("2026-09-01", "Saída", Decimal("20")),
    ], columns=["data", "tipo", "valor"])
    resumo = resumir_por_dia(dados)
    assert resumo.iloc[0]["Entrada"] == 0
    assert resumo.iloc[0]["Saldo acumulado"] == -30
    figura = criar_grafico(resumo)
    assert figura.layout.xaxis.type == "category"
    assert figura.data[2].mode == "markers"
    assert list(figura.data[2].x) == ["01/09/2026"]


def test_recorrencia_mensal_ajusta_dia_e_ignora_o_que_ja_passou():
    aluguel = {
        "ativa": 1, "tipo": "Gasto", "descricao": "Aluguel", "valor": Decimal("1000"),
        "frequencia": "Mensal", "proxima_execucao": datetime(2026, 1, 31, 15, 0), "dia": 31,
    }
    datas = ocorrencias_recorrencia(aluguel, date(2026, 1, 31), date(2026, 4, 30))
    assert datas == [date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]
    assert ocorrencias_recorrencia({**aluguel, "ativa": 0}, date(2026, 1, 1), date(2026, 12, 31)) == []
    assert ocorrencias_recorrencia({**aluguel, "frequencia": "Quinzenal"}, date(2026, 1, 1), date(2026, 12, 31)) == []


def test_semanal_atrasada_comeca_no_proximo_dia_util_da_serie():
    serie = {
        "tipo": "Receita", "valor": 10, "frequencia": "Semanal",
        "proxima_execucao": "2026-09-01", "descricao": "Contrato",
    }
    assert ocorrencias_recorrencia(serie, date(2026, 10, 5), date(2026, 10, 20)) == [
        date(2026, 10, 6), date(2026, 10, 13), date(2026, 10, 20),
    ]


def test_projecao_soma_as_duas_origens_e_marca_o_dia_negativo():
    hoje = date(2026, 10, 5)
    recorrencias = [{
        "ativa": True, "tipo": "Despesa", "descricao": "Folha", "valor": "800",
        "frequencia": "Mensal", "proxima_execucao": date(2026, 10, 10), "dia": 10,
    }]
    planejamentos = [
        {"tipo": "Receita", "descricao": "Contrato", "valor": 500, "data": date(2026, 10, 5)},
        {"tipo": "Gasto", "descricao": "Marketing", "valor": 200, "data": "20/10/2026"},
        {"tipo": "Receita", "descricao": "Fora", "valor": 9000, "data": date(2026, 12, 1)},
    ]
    trinta = projetar_caixa(300, recorrencias, planejamentos, hoje, 30)
    assert trinta["ate"] == date(2026, 11, 4)
    assert [(item["data"], item["origem"], item["tipo"]) for item in trinta["movimentos"]] == [
        (date(2026, 10, 10), "Recorrência", "Saída"),
        (date(2026, 10, 20), "Planejamento", "Saída"),
    ]
    assert trinta["saidas"] == 1000
    assert trinta["entradas"] == 0
    assert trinta["saldo_final"] == -700
    assert trinta["primeiro_dia_negativo"] == date(2026, 10, 10)
    assert not trinta["ja_negativo"]
    noventa = projetar_caixa(300, recorrencias, planejamentos, hoje, 90)
    assert date(2026, 12, 1) in [item["data"] for item in noventa["movimentos"]]
    assert noventa["entradas"] == 9000


def test_compromisso_pago_sai_e_atrasado_entra_na_projecao():
    hoje = date(2026, 10, 5)
    planejamentos = [
        {"tipo": "Gasto", "descricao": "Aluguel vencido", "valor": 400, "data": date(2026, 10, 1), "situacao": None},
        {"tipo": "Receita", "descricao": "Contrato quitado", "valor": 900, "data": date(2026, 10, 20), "situacao": "Recebido"},
        {"tipo": "Despesa", "descricao": "Internet", "valor": 100, "data": date(2026, 10, 8), "situacao": "Pago"},
    ]
    previsto = projetar_caixa(1000, [], planejamentos, hoje, 30)
    assert [(item["origem"], item["vencimento"], item["data"]) for item in previsto["movimentos"]] == [
        ("Atrasado", date(2026, 10, 1), date(2026, 10, 6)),
    ]
    assert previsto["saidas"] == 400
    assert previsto["entradas"] == 0
    assert previsto["saldo_final"] == 600


def test_mesmo_dia_compensa_antes_de_marcar_negativo_e_saldo_ja_negativo():
    hoje = date(2026, 10, 5)
    movimentos = [
        {"tipo": "Gasto", "descricao": "Saída", "valor": 100, "data": date(2026, 10, 6)},
        {"tipo": "Receita", "descricao": "Entrada", "valor": 80, "data": date(2026, 10, 6)},
    ]
    projetado = projetar_caixa(50, [], movimentos, hoje, 30)
    assert projetado["saldo_final"] == 30
    assert projetado["primeiro_dia_negativo"] is None
    ja_negativo = projetar_caixa(-10, [], [], hoje, 30)
    assert ja_negativo["ja_negativo"]
    assert ja_negativo["primeiro_dia_negativo"] is None
    assert ja_negativo["saldo_final"] == -10
    assert ja_negativo["movimentos"] == []


def test_consulta_separa_30_e_90_dias():
    hoje = date(2026, 10, 5)
    class Cursor:
        def execute(self, sql, *params):
            self.sql = sql
            self.params = params
        @property
        def description(self):
            if "recorrencias" in self.sql:
                return [(nome,) for nome in (
                    "tipo", "categoria", "descricao", "valor", "frequencia",
                    "proxima_execucao", "ativa", "dia", "mes",
                )]
            return [(nome,) for nome in ("tipo", "categoria", "descricao", "valor", "data")]
        def fetchall(self):
            if "recorrencias" in self.sql:
                return [("Gasto", "Aluguel", "Sala", 1000, "Mensal", date(2026, 10, 10), 1, 10, None)]
            return [("Receita", "Serviço", "Contrato", 5000, date(2026, 10, 20))]
    trinta, noventa = consultar_caixa_previsto(Cursor(), "empresa", 100, hoje)
    assert trinta["dias"] == 30 and noventa["dias"] == 90
    assert trinta["primeiro_dia_negativo"] == date(2026, 10, 10)
    assert trinta["saldo_final"] == 4100
    assert noventa["saidas"] == 3000
    assert noventa["saldo_final"] == 2100


def test_tela_prevista_avisa_o_dia_negativo_e_lista_o_periodo_maior():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from datetime import date
from decimal import Decimal
from trixter.fluxo_caixa import exibir_caixa_previsto
exibir_caixa_previsto([
    {
        "dias": 30, "ate": date(2026, 11, 4),
        "entradas": Decimal("0"), "saidas": Decimal("100"), "saldo_final": Decimal("-40"),
        "primeiro_dia_negativo": date(2026, 10, 10), "ja_negativo": False,
        "movimentos": [],
    },
    {
        "dias": 90, "ate": date(2027, 1, 3),
        "entradas": Decimal("10"), "saidas": Decimal("100"), "saldo_final": Decimal("-30"),
        "primeiro_dia_negativo": date(2026, 10, 10), "ja_negativo": False,
            "movimentos": [{
            "data": date(2026, 10, 10), "origem": "Recorrencia",
            "descricao": "Aluguel", "tipo": "Saida", "valor": Decimal("100"),
        }],
    },
])
''').run()
    assert not app.exception
    assert app.warning[0].value == "O saldo previsto fica negativo em 10/10/2026."
    assert app.dataframe[0].value["Descrição"].iloc[0] == "Aluguel"
