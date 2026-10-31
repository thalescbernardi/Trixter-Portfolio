"""Ciclo de navegacao das preferencias, com persistencia ficticia."""
import pytest
from streamlit.testing.v1 import AppTest


SCRIPT = r'''
import streamlit as st
from unittest.mock import patch
from trixter import configuracoes as c
st.session_state.setdefault("banco", {"u1": (1, 5, 0, 1), "u2": (0, None, 1, 0)})
st.session_state.setdefault("consultas", [])
usuario = st.selectbox("Usuario ficticio", ["u1", "u2"], key="usuario_teste")
st.session_state.usuario_atual = {"id_usuario": usuario}
modulo = st.radio("Modulo ficticio", ["Config", "Outro"], key="modulo_teste")
class Cursor:
    def execute(self, sql, *args):
        self.args = args
        st.session_state.consultas.append((" ".join(sql.split()), args))
        assert "WHERE id_usuario = ?" in sql
        if "UPDATE" in sql: st.session_state.banco[args[-1]] = tuple(args[:-1])
    def fetchone(self): return st.session_state.banco[self.args[0]]
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def commit(self): pass
    def close(self): pass
if modulo == "Config":
    with patch.object(c, "exigir_operacao", return_value=True):
        c.exibir_configuracoes(Conn)
'''


@pytest.fixture
def app(monkeypatch):
    import pyodbc
    from unittest.mock import Mock
    monkeypatch.setattr(pyodbc, "connect", Mock(side_effect=AssertionError("SQL real proibido")))
    tela = AppTest.from_string(SCRIPT).run()
    assert not tela.exception
    return tela


def preferencias(app):
    return tuple(app.checkbox(key=chave).value for chave in (
        "config_receber_relatorio", "config_receber_alertas", "config_receber_resumo"))


def navegar(app, modulo):
    app.radio(key="modulo_teste").set_value(modulo).run()
    assert not app.exception


def test_retorno_recarrega_preferencias_quando_widgets_foram_removidos(app):
    assert preferencias(app) == (True, False, True)
    app.checkbox(key="config_receber_alertas").check().run()
    navegar(app, "Outro")
    assert app.session_state._config_usuario == "u1"
    assert "config_receber_relatorio" not in app.session_state
    navegar(app, "Config")
    assert preferencias(app) == (True, False, True)
    assert app.number_input(key="config_dia_relatorio").value == 5
    assert len(app.session_state.consultas) == 2


def test_interacoes_internas_preservam_edicoes_sem_reler_banco(app):
    app.checkbox(key="config_receber_alertas").check().run()
    app.number_input(key="config_dia_relatorio").set_value(12).run()
    app.checkbox(key="config_receber_resumo").uncheck().run()
    assert not app.exception
    assert preferencias(app) == (True, True, False)
    assert app.number_input(key="config_dia_relatorio").value == 12
    assert len(app.session_state.consultas) == 1


def test_salvar_e_retornar_mantem_dados_persistidos_da_mesma_conta(app):
    app.checkbox(key="config_receber_alertas").check().run()
    app.checkbox(key="config_receber_resumo").uncheck().run()
    app.number_input(key="config_dia_relatorio").set_value(12).run()
    next(b for b in app.button if b.label == "Salvar prefer\u00eancias").click().run()
    assert not app.exception
    assert app.session_state.banco["u1"] == (1, 12, 1, 0)
    assert app.session_state.banco["u2"] == (0, None, 1, 0)
    sql, args = app.session_state.consultas[-1]
    assert sql.startswith("UPDATE dbo.usuarios")
    assert args == (1, 12, 1, 0, "u1")
    navegar(app, "Outro")
    navegar(app, "Config")
    assert preferencias(app) == (True, True, False)
    assert app.number_input(key="config_dia_relatorio").value == 12


def test_trocar_usuario_descarta_edicao_e_carrega_preferencias_corretas(app):
    app.checkbox(key="config_receber_alertas").check().run()
    app.selectbox(key="usuario_teste").select("u2").run()
    assert not app.exception
    assert preferencias(app) == (False, True, False)
    assert app.session_state._config_usuario == "u2"
    assert app.session_state.consultas[-1][1] == ("u2",)
    app.selectbox(key="usuario_teste").select("u1").run()
    assert preferencias(app) == (True, False, True)


def test_tres_preferencias_independentes_e_relatorio_desligado_sem_dia(app):
    app.checkbox(key="config_receber_relatorio").uncheck().run()
    assert preferencias(app) == (False, False, True)
    app.run()
    assert preferencias(app) == (False, False, True)
    next(b for b in app.button if b.label == "Salvar prefer\u00eancias").click().run()
    assert not app.exception
    assert app.session_state.banco["u1"] == (0, None, 0, 1)
