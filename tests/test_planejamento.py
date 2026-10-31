from datetime import date
import sqlite3

import pytest

from trixter.planejamento import consultar_base_simulador, consultar_planejamento_anual


@pytest.fixture
def cursor():
    with sqlite3.connect(":memory:") as banco:
        banco.execute("ATTACH DATABASE ':memory:' AS dbo")
        banco.create_function("MONTH", 1, lambda valor: int(valor[5:7]))
        for tabela in ("gastos", "receitas", "planejamentos"):
            banco.execute(f"CREATE TABLE dbo.{tabela} (id_usuario TEXT, data TEXT, valor NUMERIC, tipo TEXT)")
        class Cursor:
            def execute(self, sql, *args):
                self.resultado = banco.execute(sql, tuple(a.isoformat() if isinstance(a, date) else a for a in args))
            def fetchone(self): return self.resultado.fetchone()
            def fetchall(self): return self.resultado.fetchall()
        yield Cursor()


def test_anual_separa_realizado_planejado_e_recorrente(cursor):
    for tipo in ("Despesa", "Gasto"):
        cursor.execute("INSERT INTO dbo.planejamentos VALUES (?, ?, ?, ?)", "a", "2026-09-01", 500, tipo)
    cursor.execute("INSERT INTO dbo.receitas VALUES ('a', '2026-09-01', 20000, NULL)")
    cursor.execute("INSERT INTO dbo.gastos VALUES ('a', '2026-09-01', 11150, NULL)")
    cursor.execute("INSERT INTO dbo.planejamentos VALUES ('a', '2026-09-01', 18000, 'Receita')")
    cursor.execute("INSERT INTO dbo.planejamentos VALUES ('b', '2026-09-01', 99999, 'Receita')")
    recorrencias = [{"ativa": True, "tipo": "Gasto", "valor": 100}]
    dados = consultar_planejamento_anual(cursor, "a", 2026, recorrencias, lambda r, m, a: int(m == 10))
    assert len(dados) == 12
    setembro = dados.iloc[8]
    assert setembro["gastos_planejados"] == 1000
    assert setembro["receitas_planejadas"] == 18000
    assert setembro["saldo_realizadas"] == 8850
    assert setembro["saldo_planejadas"] == 17000
    assert setembro["gastos_recorrentes"] == 0
    assert dados.iloc[9]["gastos_recorrentes"] == 100


def test_media_mes_sem_movimento_e_virada_ano(cursor):
    cursor.execute("INSERT INTO dbo.receitas VALUES ('a', '2025-10-01', 900, NULL)")
    cursor.execute("INSERT INTO dbo.gastos VALUES ('a', '2025-12-31', 300, NULL)")
    cursor.execute("INSERT INTO dbo.receitas VALUES ('a', '2026-01-01', 99999, NULL)")
    cursor.execute("INSERT INTO dbo.receitas VALUES ('b', '2025-10-01', 99999, NULL)")
    assert consultar_base_simulador(cursor, "a", date(2026, 1, 15)) == (
        300, 100, True, date(2025, 10, 1), date(2026, 1, 1)
    )
    assert consultar_base_simulador(cursor, "novo", date(2026, 1, 15))[:3] == (0, 0, False)


def test_detalhe_categoria_planejamento_parcial_e_isolamento(cursor):
    from trixter.planejamento import consultar_comparacao_categorias
    for tabela in ("receitas", "gastos", "planejamentos"):
        cursor.execute(f"ALTER TABLE dbo.{tabela} ADD categoria TEXT")
    cursor.execute("INSERT INTO dbo.gastos VALUES ('a', '2026-09-01', 900, NULL, 'Marketing')")
    cursor.execute("INSERT INTO dbo.gastos VALUES ('a', '2026-09-01', 2000, NULL, 'Aluguel')")
    cursor.execute("INSERT INTO dbo.planejamentos VALUES ('a', '2026-09-01', 600, 'Despesa', 'Marketing')")
    cursor.execute("INSERT INTO dbo.planejamentos VALUES ('a', '2026-09-01', 400, 'Gasto', 'Marketing')")
    cursor.execute("INSERT INTO dbo.planejamentos VALUES ('b', '2026-09-01', 9999, 'Despesa', 'Marketing')")
    cursor.execute("INSERT INTO dbo.receitas VALUES ('a', '2026-09-01', 100, NULL, 'Marketing')")
    detalhes = consultar_comparacao_categorias(cursor, "a", 2026)
    gastos = detalhes[detalhes["tipo"] == "Gasto"].set_index("Categoria")
    assert gastos.loc["Marketing", "Planejado"] == 1000
    assert gastos.loc["Marketing", "Diferença"] == -100
    assert not gastos.loc["Aluguel", "Tem planejamento"]
    assert gastos.loc["Aluguel", "Diferença"] is None
    assert detalhes[detalhes["tipo"] == "Receita"]["Realizado"].sum() == 100


def test_tela_anual_renderiza_uma_vez_sem_dados():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from trixter.planejamento import consultar_planejamento_anual, exibir_planejamento_anual
class Cursor:
    def execute(self, *args): pass
    def fetchall(self): return []
dados = consultar_planejamento_anual(Cursor(), 'a', 2026, [], lambda *args: 0)
exibir_planejamento_anual(dados, 2026, 'Despesa')
''').run()
    assert not app.exception
    assert len(app.metric) == 3
    assert len(app.dataframe) == 2
    for opcao in ("Planejamento manual", "Recorrências futuras"):
        app.radio[0].set_value(opcao).run()
        assert not app.exception
        assert len(app.metric) == 3


def test_reserva_cobre_meses_de_custo_fixo_e_o_faturamento_necessario():
    from decimal import Decimal
    from trixter.planejamento import simular_reserva
    coberta = simular_reserva(10000, 2000, 3, 2500)
    assert coberta["meses_cobertos"] == Decimal(5)
    assert coberta["reserva_desejada"] == Decimal(6000)
    assert coberta["falta"] == 0
    assert coberta["faturamento_para_cobrir"] == Decimal(2000)
    assert coberta["falta_mensal"] == 0
    curta = simular_reserva(-1000, 2000, 3, 1500)
    assert curta["meses_cobertos"] == 0
    assert curta["falta"] == Decimal(7000)
    assert curta["falta_mensal"] == Decimal(500)
    assert simular_reserva(1000, 0, 3, 1000)["meses_cobertos"] is None


def test_custo_fixo_mensal_divide_a_base_em_tres_meses():
    from datetime import date
    from trixter.planejamento import consultar_custo_fixo_mensal
    class Cursor:
        def execute(self, sql, *args):
            self.sql = sql
            self.args = args
        def fetchone(self):
            return (6000,)
    cursor = Cursor()
    media = consultar_custo_fixo_mensal(cursor, "empresa", date(2026, 7, 1), date(2026, 10, 1))
    assert media == 2000
    assert "N'Fixo'" in cursor.sql
    assert cursor.args == ("empresa", date(2026, 7, 1), date(2026, 10, 1))


def test_tela_reserva_mostra_o_faturamento_para_cobrir_o_fixo():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from trixter.planejamento import exibir_reserva_simulador
exibir_reserva_simulador(3000, 2000, 1500)
''').run()
    assert not app.exception
    assert app.number_input[0].value == 3
    assert "Falta para a reserva" in [metrica.label for metrica in app.metric]
    assert any("cobrir o custo fixo" in getattr(item, "value", "") for item in app.markdown)
    assert app.warning


def test_tela_reserva_de_emergencia_fala_de_gasto_fixo():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from trixter.planejamento import exibir_reserva_simulador
exibir_reserva_simulador(3000, 2000, 1500, "Pessoa F\\u00edsica")
''').run()
    assert not app.exception
    assert app.subheader[0].value == "Reserva de emergência"
    assert app.metric[0].label == "Gasto fixo mensal"
    assert any("cobrir o gasto fixo" in getattr(item, "value", "") for item in app.markdown)
