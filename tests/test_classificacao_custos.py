from datetime import date
from decimal import Decimal

from trixter.classificacao import (
    consultar_custos_mes, frase_natureza, resumir_custos,
)


def test_resumo_separa_fixo_variavel_e_o_que_falta_classificar():
    resumo = resumir_custos([
        {"categoria": "Folha", "classificacao": "Fixo", "valor": 6000},
        {"categoria": "Folha", "classificacao": "Fixo", "valor": 500},
        {"categoria": "Marketing", "classificacao": "variavel", "valor": 900},
        {"categoria": "Outros", "classificacao": None, "valor": 100},
        {"categoria": "Tarifa", "classificacao": "estranha", "valor": 40},
        {"categoria": "Zero", "classificacao": "Fixo", "valor": 0},
    ], receita=0)
    assert resumo["fixo"] == 6500
    assert resumo["variavel"] == 900
    assert resumo["nao_classificado"] == 140
    assert resumo["participacao_fixo"] is None
    assert [item["categoria"] for item in resumo["categorias"]] == ["Folha", "Marketing", "Outros", "Tarifa"]


def test_participacao_usa_a_receita_do_mes():
    resumo = resumir_custos(
        [{"categoria": "Aluguel", "classificacao": "Fixo", "valor": "2000"}],
        receita="10000",
    )
    assert resumo["participacao_fixo"] == Decimal("0.2")
    assert resumo["participacao_variavel"] == 0


def test_frases_de_orcamento():
    assert frase_natureza(0, 0, 0) == ""
    assert "é fixo" in frase_natureza(100, 100, 0)
    assert "é variável" in frase_natureza(100, 0, 100)
    assert "não está classificado" in frase_natureza(100, 0, 0)
    assert frase_natureza(100, 80, 20) == "Desse total, R$ 80,00 é fixo e R$ 20,00 é variável."


def test_consulta_limita_o_mes_e_a_virada_de_ano():
    class Cursor:
        def __init__(self):
            self.consultas = []
            self.sql = ""
        def execute(self, sql, *args):
            self.sql = sql
            self.consultas.append(args)
        def fetchall(self):
            return [("Folha", "Fixo", 6000), ("Marketing", "Variável", 900)]
        def fetchone(self):
            return (10000,)
    cursor = Cursor()
    resumo = consultar_custos_mes(cursor, "empresa", date(2026, 12, 15))
    assert cursor.consultas[0] == ("empresa", date(2026, 12, 1), date(2027, 1, 1))
    assert cursor.consultas[1] == ("empresa", date(2026, 12, 1), date(2027, 1, 1))
    assert "GETDATE" not in cursor.sql
    assert resumo["fixo"] == 6000
    assert resumo["participacao_fixo"] == Decimal("0.6")


def test_tela_custos_mostra_o_peso_na_receita():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from decimal import Decimal
from trixter.classificacao import exibir_custos_mes
exibir_custos_mes({
    "fixo": Decimal("6000"), "variavel": Decimal("900"), "nao_classificado": Decimal("0"),
    "total": Decimal("6900"), "receita": Decimal("10000"),
    "participacao_fixo": Decimal("0.6"), "participacao_variavel": Decimal("0.09"),
    "categorias": [{"classificacao": "Fixo", "categoria": "Folha", "valor": Decimal("6000")}],
}, "Despesa")
''').run()
    assert not app.exception
    assert app.subheader[0].value == "Despesas fixas e variáveis"
    assert any("60%" in getattr(item, "value", "") for item in app.markdown)
    assert app.dataframe[0].value["Categoria"].iloc[0] == "Folha"
