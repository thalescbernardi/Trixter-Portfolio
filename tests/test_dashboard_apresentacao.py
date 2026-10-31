"""Dashboard com conexao simulada: formatos, filtros e indicadores."""
from datetime import date
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest


SCRIPT = r'''
import streamlit as st
from datetime import date
from unittest.mock import patch
from trixter import dashboard as d
st.session_state.usuario_atual = {"id_usuario": "ficticio"}
st.session_state.setdefault("data_inicio_dashboard", date(2026, 10, 1))
st.session_state.setdefault("data_fim_dashboard", date(2026, 10, 31))
st.session_state.setdefault("dados", [
    ("r1", date(2026, 10, 1), "Receita", 650.0, "Servicos", "Ficticio"),
    ("g1", date(2026, 10, 31), "Gasto", 250.0, "Casa", "Ficticio"),
    ("fora1", date(2026, 9, 30), "Receita", 999.0, "Fora", "Ficticio"),
    ("fora2", date(2026, 11, 1), "Gasto", 999.0, "Fora", "Ficticio"),
])
class Cursor:
    description = [(c,) for c in ("id_transacao", "data", "tipo", "valor", "categoria", "descricao")]
    def execute(self, sql, *args):
        assert args == ("ficticio", "ficticio")
        assert sql.count("WHERE id_usuario = ?") == 2
    def fetchall(self): return st.session_state.dados
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def close(self): pass
def grafico(fig, **kwargs): st.session_state.figura = fig
with patch.object(d.st, "plotly_chart", side_effect=grafico):
    d.exibir_dashboard(Conn, st.session_state.get("termo", "Gasto"))
'''


@pytest.fixture
def app(monkeypatch):
    import pyodbc
    monkeypatch.setattr(pyodbc, "connect", Mock(side_effect=AssertionError("SQL real proibido")))
    tela = AppTest.from_string(SCRIPT).run()
    assert not tela.exception
    return tela


def indicadores(app):
    return {item.label: item.value for item in app.metric}


def test_datas_brasileiras_preservam_valores_e_limites_inclusivos(app):
    for chave, valor in [("data_inicio_dashboard", date(2026, 10, 1)),
                         ("data_fim_dashboard", date(2026, 10, 31))]:
        widget = app.date_input(key=chave)
        assert widget.proto.format == "DD/MM/YYYY"
        assert widget.value == valor
    valores = indicadores(app)
    assert valores["Receitas do Período"] == "R$ 650,00"
    assert valores["Gastos do Período"] == "R$ 250,00"
    assert valores["Saldo do Período"] == "R$ 400,00"
    assert valores["Transações"] == "2"
    assert valores["Receita Comprometida"] == "38,5%"
    app.date_input(key="data_fim_dashboard").set_value(date(2026, 10, 30)).run()
    assert not app.exception
    assert indicadores(app)["Gastos do Período"] == "R$ 0,00"
    assert indicadores(app)["Transações"] == "1"


@pytest.mark.parametrize("receita,gasto,esperado", [
    (650.0, 250.0, "38,5%"), (100.0, 150.0, "150,0%"),
    (100.0, 0.0, "0,0%"), (0.0, 250.0, "0,0%"),
])
def test_receita_comprometida_preserva_formula_e_regra_sem_receitas(app, receita, gasto, esperado):
    app.session_state.dados = [
        ("r", date(2026, 10, 5), "Receita", receita, "Categoria", "Ficticio"),
        ("g", date(2026, 10, 5), "Gasto", gasto, "Categoria", "Ficticio"),
    ]
    app.run()
    assert not app.exception
    assert indicadores(app)["Receita Comprometida"] == esperado


def test_graficos_resumo_e_categoria_preservam_valores_e_nomenclatura_pj(app):
    assert sorted(float(y) for trace in app.session_state.figura.data for y in trace.y) == [250.0, 650.0]
    app.selectbox(key="tipo_visualizacao_dashboard").select("Categoria").run()
    assert not app.exception
    assert sorted(float(y) for trace in app.session_state.figura.data for y in trace.y) == [250.0, 650.0]
    app.session_state.termo = "Despesa"
    app.run()
    assert indicadores(app)["Despesas do Período"] == "R$ 250,00"
    assert indicadores(app)["Receita Comprometida"] == "38,5%"
