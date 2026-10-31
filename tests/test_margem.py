from datetime import date
from decimal import Decimal

from trixter.margem import calcular_margem, consultar_margem_mes


def test_contribuicao_desconta_so_o_variavel_e_o_fixo_vem_depois():
    resumo = calcular_margem(
        [
            {"categoria": "Prestação de Serviços", "valor": 8000},
            {"categoria": "Vendas de Produtos", "valor": 2000},
        ],
        [
            {"categoria": "Mercadorias e Insumos", "classificacao": "Variável", "valor": 1500},
            {"categoria": "Marketing", "classificacao": "variavel", "valor": 500},
            {"categoria": "Folha de Pagamento", "classificacao": "Fixo", "valor": 6000},
            {"categoria": "Tarifas", "classificacao": None, "valor": 100},
            {"categoria": "Zero", "classificacao": "Fixo", "valor": 0},
        ],
    )
    assert resumo["receita"] == 10000
    assert resumo["variavel"] == 2000
    assert resumo["fixo"] == 6000
    assert resumo["nao_classificado"] == 100
    assert resumo["contribuicao"] == 8000
    assert resumo["depois_do_fixo"] == 2000
    assert resumo["participacao_contribuicao"] == Decimal("0.8")
    assert resumo["participacao_depois_do_fixo"] == Decimal("0.2")
    assert [item["categoria"] for item in resumo["categorias"][:2]] == [
        "Prestação de Serviços", "Vendas de Produtos",
    ]
    assert [item["categoria"] for item in resumo["categorias"] if item["lado"] == "gasto"] == [
        "Mercadorias e Insumos", "Marketing", "Folha de Pagamento", "Tarifas",
    ]


def test_sem_receita_a_margem_fica_negativa_e_sem_percentual():
    resumo = calcular_margem(
        [],
        [{"categoria": "Folha de Pagamento", "classificacao": "Fixo", "valor": 1000}],
    )
    assert resumo["contribuicao"] == 0
    assert resumo["depois_do_fixo"] == -1000
    assert resumo["participacao_contribuicao"] is None
    assert resumo["categorias"][0]["participacao"] is None


def test_consulta_separa_o_mes_e_a_categoria_da_receita():
    class Cursor:
        def __init__(self):
            self.consultas = []
            self.vez = 0
        def execute(self, sql, *args):
            self.consultas.append((sql, args))
        def fetchall(self):
            self.vez += 1
            if self.vez == 1:
                return [("Folha de Pagamento", "Fixo", 6000), ("Marketing", "Variável", 1000)]
            return [("Prestação de Serviços", 10000)]
    cursor = Cursor()
    resumo = consultar_margem_mes(cursor, "empresa", date(2026, 12, 15))
    assert cursor.consultas[0][1] == ("empresa", date(2026, 12, 1), date(2027, 1, 1))
    assert "dbo.gastos" in cursor.consultas[0][0]
    assert "dbo.receitas" in cursor.consultas[1][0]
    assert resumo["contribuicao"] == 9000
    assert resumo["depois_do_fixo"] == 3000
    assert resumo["categorias"][0]["categoria"] == "Prestação de Serviços"


def test_tela_margem_mostra_o_que_sobra_depois_do_fixo():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from decimal import Decimal
from trixter.margem import exibir_margem
exibir_margem({
    "receita": Decimal("10000"),
    "variavel": Decimal("2000"),
    "fixo": Decimal("6000"),
    "nao_classificado": Decimal("100"),
    "contribuicao": Decimal("8000"),
    "depois_do_fixo": Decimal("2000"),
    "participacao_contribuicao": Decimal("0.8"),
    "participacao_depois_do_fixo": Decimal("0.2"),
    "categorias": [
        {"lado": "receita", "categoria": "Servicos", "classificacao": "", "valor": Decimal("10000"), "participacao": Decimal("1")},
        {"lado": "gasto", "categoria": "Marketing", "classificacao": "Variavel", "valor": Decimal("2000"), "participacao": Decimal("0.2")},
    ],
}, "Despesa")
''').run()
    assert not app.exception
    assert app.subheader[0].value == "Margem de contribuição do mês"
    assert any("receita do mês menos as despesas variáveis" in getattr(item, "value", "") for item in app.caption)
    assert any("não é o lucro líquido" in getattr(item, "value", "") for item in app.caption)
    assert any("sem classificação" in getattr(item, "value", "") for item in app.caption)
    assert any("80%" in getattr(item, "value", "") for item in app.markdown)
    assert any("sobram" in getattr(item, "value", "") for item in app.markdown)
    assert app.dataframe[0].value["Categoria"].iloc[0] == "Servicos"
    assert app.dataframe[0].value["Lado"].iloc[1] == "Despesa"


def test_tela_sem_receita_explica_o_percentual_e_o_nao_classificado():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from decimal import Decimal
from trixter.margem import exibir_margem
exibir_margem({
    "receita": Decimal("0"),
    "variavel": Decimal("0"),
    "fixo": Decimal("0"),
    "nao_classificado": Decimal("100"),
    "contribuicao": Decimal("0"),
    "depois_do_fixo": Decimal("0"),
    "participacao_contribuicao": None,
    "participacao_depois_do_fixo": None,
    "categorias": [
        {"lado": "gasto", "categoria": "Tarifas", "classificacao": "Não classificado", "valor": Decimal("100"), "participacao": None},
    ],
}, "Despesa")
''').run()
    assert not app.exception
    assert any("percentual da margem de contribuição não é calculado" in getattr(item, "value", "") for item in app.info)
    assert any("sem classificação" in getattr(item, "value", "") for item in app.markdown)
    assert app.metric[0].value == "R$ 0,00"
