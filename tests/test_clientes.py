from datetime import date
from decimal import Decimal

from trixter.clientes import (
    atrasos_por_cliente, concentrar_clientes, consultar_concentracao_mes, normalizar_cliente,
)


def test_nome_do_cliente_ignora_espaco_e_vazio():
    assert normalizar_cliente("  Aurora   Serviços ") == "Aurora Serviços"
    assert normalizar_cliente("   ") is None
    assert len(normalizar_cliente("A" * 90)) == 80
    assert normalizar_cliente(None) is None


def test_concentracao_separa_quem_nao_tem_nome():
    resumo = concentrar_clientes([
        {"cliente": "Aurora", "valor": 7000},
        {"cliente": "  Aurora ", "valor": 0},
        {"cliente": "Beta", "valor": 2000},
        {"cliente": None, "valor": 1000},
    ])
    assert resumo["total"] == 10000
    assert resumo["itens"][0]["cliente"] == "Aurora"
    assert resumo["itens"][0]["percentual"] == Decimal("0.7")
    assert resumo["itens"][-1]["cliente"] == "Sem cliente"


def test_atraso_soma_so_o_recebimento_vencido():
    atrasos = atrasos_por_cliente([
        {"situacao": "Atrasado", "direcao": "receber", "cliente": "Aurora", "valor": 400},
        {"situacao": "Atrasado", "direcao": "receber", "cliente": "Aurora", "valor": 100},
        {"situacao": "Atrasado", "direcao": "pagar", "cliente": "Aurora", "valor": 999},
        {"situacao": "Previsto", "direcao": "receber", "cliente": "Beta", "valor": 50},
    ])
    assert atrasos == [{"cliente": "Aurora", "valor": Decimal(500)}]


def test_consulta_concentracao_limita_o_mes():
    class Cursor:
        def execute(self, sql, *args):
            self.args = args
            assert "cliente" in sql
        def fetchall(self):
            return [("Aurora", 7000), (None, 3000)]
    cursor = Cursor()
    resumo = consultar_concentracao_mes(cursor, "empresa", date(2026, 12, 15))
    assert cursor.args == ("empresa", date(2026, 12, 1), date(2027, 1, 1))
    assert resumo["itens"][0]["percentual"] == Decimal("0.7")
    assert resumo["total"] == 10000


def test_tela_concentracao_mostra_o_maior_cliente():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from decimal import Decimal
from trixter.clientes import exibir_concentracao
exibir_concentracao({
    "total": Decimal("10000"),
    "itens": [
        {"cliente": "Aurora", "valor": Decimal("7000"), "percentual": Decimal("0.7")},
        {"cliente": "Sem cliente", "valor": Decimal("3000"), "percentual": Decimal("0.3")},
    ],
})
''').run()
    assert not app.exception
    assert any("70%" in getattr(item, "value", "") for item in app.markdown)
    assert app.dataframe[0].value["Cliente"].iloc[0] == "Aurora"
