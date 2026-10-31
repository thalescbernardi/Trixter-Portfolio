"""Apresentacao financeira com dados ficticios e sem conexoes reais."""
import ast
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def sem_banco_real(monkeypatch):
    import pyodbc
    monkeypatch.setattr(pyodbc, "connect", Mock(side_effect=AssertionError("SQL real proibido")))


HISTORICO = r'''
import streamlit as st
from datetime import datetime
from unittest.mock import patch
from trixter import historico_tela as h
from trixter.relatorios import formatar_moeda

st.session_state.usuario_atual = {"id_usuario": "ficticio"}
class Cursor:
    description = [(nome,) for nome in ("id_transacao", "id_usuario", "data", "descricao", "valor", "categoria", "tipo", "classificacao", "cliente")]
    def execute(self, sql, *args):
        assert args == ("ficticio", "ficticio")
        assert sql.count("WHERE id_usuario = ?") == 2
        assert "ORDER BY data DESC" in sql
    def fetchall(self):
        return [
            ("r3", "ficticio", datetime(2026, 9, 3), "Ficticio", 30.0, "Categoria", "Receita", None, None),
            ("g1", "ficticio", datetime(2026, 9, 2), "Ficticio", 7.0, "Categoria", "Gasto", None, None),
            ("r1", "ficticio", datetime(2026, 9, 1), "Ficticio", 10.0, "Categoria", "Receita", None, None),
            ("r2", "ficticio", datetime(2026, 9, 1), "Ficticio", 15.0, "Categoria", "Receita", None, None),
        ]
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def close(self): pass
def capturar(figura, **kwargs):
    st.session_state.figura_historico = figura
with patch.object(h.st, "plotly_chart", side_effect=capturar):
    h.exibir_historico(Conn, "Pessoa F\u00edsica", "Gasto", formatar_moeda)
'''


@pytest.mark.parametrize("filtro", ["Todos", "Receita", "Gasto"])
def test_datas_do_historico_sem_mudar_agrupamentos_ou_valores(filtro):
    app = AppTest.from_string(HISTORICO).run()
    assert not app.exception
    if filtro != "Todos":
        next(w for w in app.selectbox if w.label == "Filtrar por tipo de transa\u00e7\u00e3o:").select(filtro).run()
    assert not app.exception
    figura = app.session_state.figura_historico
    for chave in ("filtro_data_inicial", "filtro_data_final"):
        assert app.date_input(key=chave).proto.format == "DD/MM/YYYY"
    assert figura.layout.xaxis.tickformat == "%d/%m/%Y"
    assert figura.layout.xaxis.hoverformat == "%d/%m/%Y"
    esperados = {
        "Receita": ([datetime(2026, 9, 1), datetime(2026, 9, 3)], [25, 30]),
        "Gasto": ([datetime(2026, 9, 2)], [7]),
    }
    tipos = ["Receita", "Gasto"] if filtro == "Todos" else [filtro]
    assert len(figura.data) == len(tipos)
    for trace, tipo in zip(figura.data, tipos):
        assert "%{x|%d/%m/%Y}" in trace.hovertemplate
        assert "%H" not in trace.hovertemplate
        datas, valores = esperados[tipo]
        assert list(pd.to_datetime(trace.x).to_pydatetime()) == datas
        assert list(trace.y) == valores
    assert app.dataframe[0].value["Data"].str.fullmatch(r"\d{2}/\d{2}/\d{4}").all()


def test_fluxo_de_um_dia_apresenta_as_duas_mensagens():
    app = AppTest.from_string(r'''
import streamlit as st
from datetime import datetime
from unittest.mock import patch
from trixter import fluxo_tela as f
st.session_state.usuario_atual = {"id_usuario": "ficticio"}
class Cursor:
    description = [(nome,) for nome in ("data", "tipo", "valor")]
    def execute(self, sql, *args):
        assert all(arg == "ficticio" for arg in args)
    def fetchone(self): return (50.0,)
    def fetchall(self): return [(datetime(2026, 9, 1), "Entrada", 50.0)]
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def close(self): pass
with patch.object(f, "consultar_caixa_previsto", return_value=[]), patch.object(f, "exibir_caixa_previsto"):
    f.exibir_fluxo_caixa(Conn, "Pessoa F\u00edsica", "Gasto")
''').run()
    assert not app.exception
    assert any(item.value == "Entradas e saídas por dia com movimentação. O saldo acumula todo o histórico registrado."
               for item in app.caption)
    assert any(item.value == "Há movimentações em apenas um dia. A evolução aparecerá quando houver outras datas."
               for item in app.info)
    assert app.dataframe[0].value["Data"].tolist() == ["01/09/2026"]


def test_menu_resumo_financeiro_preserva_destino_e_key():
    raiz = Path(__file__).resolve().parents[1]
    arvore = ast.parse((raiz / "Gerenciador de Gastos V2.py").read_text(encoding="utf-8"))
    botao = next(n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                 and any(k.arg == "key" and isinstance(k.value, ast.Constant)
                         and k.value.value == "btn_visualizar_saldo" for k in n.keywords))
    assert botao.args[0].value == "Resumo Financeiro"
    argumentos = next(k.value for k in botao.keywords if k.arg == "args")
    assert argumentos.elts[0].value == "visualizar_saldo"


@pytest.mark.parametrize("referencia,percentual", [(4500, "14,4%"), (500, "130,0%")])
def test_resumo_compara_receitas_sem_atribuir_origem_ou_limitar_percentual(referencia, percentual):
    from trixter import saldo
    st = Mock()
    st.session_state.usuario_atual = {"id_usuario": "ficticio", "renda_mensal": referencia}
    coluna, resultado = Mock(), Mock()
    st.columns.return_value = (coluna, resultado)
    conexao = Mock()
    with patch.object(saldo, "st", st), patch.object(saldo, "consultar_resumo", return_value=(0, 650, 50)):
        saldo.exibir_saldo(Mock(return_value=conexao), "Pessoa Física", "Gasto")
    texto = coluna.markdown.call_args.args[0]
    assert percentual in texto
    assert "R$ 650,00 em receitas registradas de" in texto
    assert "de renda informada." in texto
    assert "recebidos de" not in texto
    assert "Resultado do mês" in resultado.markdown.call_args.args[0]
    assert "R$ 600,00" in resultado.markdown.call_args.args[0]
    if referencia == 4500:
        assert "R$ 650,00 em receitas registradas de R$ 4.500,00 de renda informada." in texto
