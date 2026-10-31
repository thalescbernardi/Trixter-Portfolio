from datetime import date
from decimal import Decimal

from trixter.compromissos import (
    baixar_compromisso, preparar_compromissos, situacao_efetiva,
)


def test_situacao_deriva_previsto_e_atrasado_e_respeita_a_baixa():
    hoje = date(2026, 10, 5)
    assert situacao_efetiva(date(2026, 10, 5), None, hoje) == "Previsto"
    assert situacao_efetiva(date(2026, 10, 6), None, hoje) == "Previsto"
    assert situacao_efetiva("01/10/2026", None, hoje) == "Atrasado"
    assert situacao_efetiva(date(2026, 10, 1), "Recebido", hoje) == "Recebido"
    assert situacao_efetiva(date(2026, 10, 20), "pago", hoje) == "Pago"


def test_resumo_separa_receber_e_pagar():
    resumo = preparar_compromissos([
        {"id_planejamento": "1", "tipo": "Receita", "categoria": "Serviço", "descricao": "Contrato", "valor": 1000, "data": date(2026, 10, 1), "situacao": None},
        {"id_planejamento": "2", "tipo": "Despesa", "categoria": "Aluguel", "descricao": "Sala", "valor": 400, "data": date(2026, 10, 20), "situacao": None},
        {"id_planejamento": "3", "tipo": "Gasto", "categoria": "Internet", "descricao": "Link", "valor": 100, "data": date(2026, 10, 2), "situacao": "Pago"},
    ], date(2026, 10, 5))
    assert resumo["totais"]["A receber atrasado"] == 1000
    assert resumo["totais"]["A pagar previsto"] == 400
    assert resumo["totais"]["A pagar atrasado"] == 0
    assert [item["situacao"] for item in resumo["itens"]] == ["Atrasado", "Pago", "Previsto"]


def test_baixa_grava_o_realizado_e_nao_repete():
    class Cursor:
        def __init__(self, rowcount):
            self.chamadas = []
            self.rowcount = rowcount
        def execute(self, sql, *args):
            self.chamadas.append((sql, args))
        def close(self):
            pass
    class Conexao:
        def __init__(self, cursor):
            self.cursor_interno = cursor
            self.commitou = False
            self.desfez = False
        def cursor(self):
            return self.cursor_interno
        def commit(self):
            self.commitou = True
        def rollback(self):
            self.desfez = True
        def close(self):
            pass
    item = {
        "id_planejamento": "p1", "direcao": "receber", "data": date(2026, 10, 1),
        "descricao": "Contrato", "valor": Decimal("1000"), "categoria": "Serviço",
        "cliente": " Aurora  Serviços ",
    }
    cursor = Cursor(1)
    conexao = Conexao(cursor)
    assert baixar_compromisso(lambda: conexao, "empresa", item)
    assert "INSERT INTO dbo.receitas" in cursor.chamadas[0][0]
    assert cursor.chamadas[0][1][-1] == "Aurora Serviços"
    assert cursor.chamadas[1][1][0] == "Recebido"
    assert conexao.commitou
    repetido = Cursor(0)
    conexao_repetida = Conexao(repetido)
    assert not baixar_compromisso(lambda: conexao_repetida, "empresa", item)
    assert conexao_repetida.desfez
    assert not conexao_repetida.commitou


def test_tela_compromissos_mostra_os_quatro_totais():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from datetime import date
from decimal import Decimal
from trixter.compromissos import exibir_compromissos
exibir_compromissos({
    "totais": {
        "A receber previsto": Decimal("0"),
        "A receber atrasado": Decimal("1000"),
        "A pagar previsto": Decimal("400"),
        "A pagar atrasado": Decimal("0"),
    },
    "itens": [{
        "data": date(2026, 10, 1), "direcao": "receber", "categoria": "Servico",
        "descricao": "Contrato", "valor": Decimal("1000"), "situacao": "Atrasado",
    }],
})
''').run()
    assert not app.exception
    assert [metrica.label for metrica in app.metric] == [
        "A receber previsto", "A receber atrasado", "A pagar previsto", "A pagar atrasado",
    ]
    assert app.dataframe[0].value["Situação"].iloc[0] == "Atrasado"
