"""Interacoes isoladas do Orcamento, sem servidor web ou banco real."""
import pytest
from streamlit.testing.v1 import AppTest


SCRIPT = r'''
import streamlit as st
from unittest.mock import patch
from trixter.orcamento import exibir_orcamento

if "registros" not in st.session_state:
    st.session_state.registros = [
        ["a", "u1", "Mercado", 1, 2026, 500.0],
        ["b", "u1", "Transporte", 1, 2026, 700.0],
        ["c", "u2", "Mercado", 1, 2026, 900.0],
    ]
    st.session_state.consultas = []
    st.session_state.commits = 0
    st.session_state.usuario_atual = {"id_usuario": "u1"}

class Cursor:
    description = [(c,) for c in ["id_orcamento", "id_usuario", "categoria", "mes", "ano", "valor_limite"]]
    def execute(self, sql, *args):
        self.sql = " ".join(sql.split())
        self.args = args
        st.session_state.consultas.append((self.sql, args))
        if self.sql.startswith("UPDATE"):
            for row in st.session_state.registros:
                if (row[0], row[1]) == args[1:]: row[5] = args[0]
        elif self.sql.startswith("DELETE"):
            st.session_state.registros = [row for row in st.session_state.registros if tuple(row[:2]) != args]
        elif self.sql.startswith("INSERT"):
            st.session_state.registros.append(list(args))
        return self
    def fetchall(self):
        return [tuple(row) for row in st.session_state.registros if row[1] == self.args[0]]
    def fetchone(self): return (250.0, 250.0, 0.0)
    def close(self): pass

class Conexao:
    def cursor(self): return Cursor()
    def close(self): pass
    def commit(self): st.session_state.commits += 1

with patch("trixter.orcamento.consultar_custos_mes", return_value={}), \
     patch("trixter.orcamento.exibir_custos_mes"), \
     patch("trixter.orcamento.listar_categorias", return_value=["Mercado", "Transporte"]):
    exibir_orcamento(Conexao, "Pessoa F\u00edsica", "Gasto", "o")
'''


@pytest.fixture
def app(monkeypatch):
    import pyodbc
    def recusar(*args, **kwargs):
        raise AssertionError("Conexao real proibida neste teste")
    monkeypatch.setattr(pyodbc, "connect", recusar)
    tela = AppTest.from_string(SCRIPT).run()
    assert not tela.exception
    return tela


def botao(app, rotulo):
    return next(item for item in app.button if item.label == rotulo)


def escritas(app):
    return [(sql, args) for sql, args in app.session_state.consultas
            if sql.startswith(("INSERT", "UPDATE", "DELETE"))]


def editar(app):
    app.button(key="btn_alterar_orcamento").click().run()
    assert not app.exception
    assert app.session_state.orcamento_em_edicao == ("u1", "a")


def test_editor_permanece_e_salva_apenas_registro_do_usuario(app):
    editar(app)
    app.number_input(key="novo_valor_limite").set_value(600.0).run()
    app.run()
    assert not app.exception
    assert app.number_input(key="novo_valor_limite").value == 600.0
    assert not escritas(app)
    botao(app, "Confirmar Altera\u00e7\u00e3o").click().run()
    assert not app.exception
    sql, args = escritas(app)[0]
    assert "WHERE id_orcamento = ? AND id_usuario = ?" in sql
    assert args == (600.0, "a", "u1")
    assert [row[5] for row in app.session_state.registros] == [600, 700, 900]
    assert "orcamento_em_edicao" not in app.session_state
    assert not any(item.label == "Novo valor limite:" for item in app.number_input)
    assert any("alterado com sucesso" in item.value for item in app.success)
    assert any(item.label == "Limite" and "600,00" in item.value for item in app.metric)
    app.run()
    assert len(escritas(app)) == 1


def test_troca_de_selecao_invalida_editor_e_carrega_novo_limite(app):
    editar(app)
    app.number_input(key="novo_valor_limite").set_value(650.0).run()
    app.selectbox(key="orcamento_selecionado").select("Transporte - 01/2026").run()
    assert not app.exception
    assert "orcamento_em_edicao" not in app.session_state
    assert not any(item.label == "Novo valor limite:" for item in app.number_input)
    app.button(key="btn_alterar_orcamento").click().run()
    assert app.session_state.orcamento_em_edicao == ("u1", "b")
    assert app.number_input(key="novo_valor_limite").value == 700.0
    assert not escritas(app)


@pytest.mark.parametrize("ultimo", [False, True])
def test_exclusao_descarta_editor_e_selecao_removida(app, ultimo):
    if ultimo:
        app.session_state.registros = [row for row in app.session_state.registros if row[0] != "b"]
        app.run()
    editar(app)
    botao(app, "Excluir Or\u00e7amento Selecionado").click().run()
    assert not app.exception
    assert "orcamento_em_edicao" not in app.session_state
    assert not any(item.label == "Novo valor limite:" for item in app.number_input)
    sql, args = escritas(app)[0]
    assert "WHERE id_orcamento = ? AND id_usuario = ?" in sql
    assert args == ("a", "u1")
    assert all(row[0] != "a" for row in app.session_state.registros)
    assert any(row[0] == "c" for row in app.session_state.registros)
    if not ultimo:
        assert app.selectbox(key="orcamento_selecionado").value == "Transporte - 01/2026"


def test_troca_de_usuario_invalida_edicao_mesmo_com_rotulo_igual(app):
    editar(app)
    app.session_state.usuario_atual = {"id_usuario": "u2"}
    app.run()
    assert not app.exception
    assert "orcamento_em_edicao" not in app.session_state
    assert not any(item.label == "Novo valor limite:" for item in app.number_input)
    assert not escritas(app)


def test_registro_removido_invalida_editor(app):
    editar(app)
    app.session_state.registros = [row for row in app.session_state.registros if row[0] != "a"]
    app.run()
    assert not app.exception
    assert "orcamento_em_edicao" not in app.session_state
    assert not escritas(app)


def test_duplicidade_nao_insere_nem_confirma_transacao(app):
    app.number_input(key="valor_limite_orcamento").set_value(500.0).run()
    botao(app, "Salvar Or\u00e7amento").click().run()
    assert not app.exception
    assert any("J\u00e1 existe" in item.value for item in app.warning)
    assert not escritas(app)
    assert app.session_state.commits == 0
    assert len(app.session_state.registros) == 3


def test_cadastro_valido_continua_parametrizado(app):
    app.number_input(key="valor_limite_orcamento").set_value(400.0).run()
    app.selectbox(key="mes_orcamento").select(2).run()
    botao(app, "Salvar Or\u00e7amento").click().run()
    assert not app.exception
    sql, args = escritas(app)[0]
    assert sql.startswith("INSERT INTO dbo.orcamentos")
    assert sql.count("?") == 6
    assert args[1:] == ("u1", "Mercado", 2, 2026, 400.0)
    assert len(app.session_state.registros) == 4


@pytest.mark.parametrize("edicao", [False, True])
def test_limite_zero_continua_bloqueado(app, edicao):
    if edicao:
        editar(app)
        app.number_input(key="novo_valor_limite").set_value(0.0).run()
        rotulo = "Confirmar Altera\u00e7\u00e3o"
    else:
        rotulo = "Salvar Or\u00e7amento"
    botao(app, rotulo).click().run()
    assert not app.exception
    assert app.error
    assert not escritas(app)
    if edicao:
        assert app.session_state.orcamento_em_edicao == ("u1", "a")


def test_percentual_textual_e_barra_usam_escala_correta(app):
    assert any(item.value == "50% do or\u00e7amento utilizado." for item in app.markdown)
    assert app.get("progress")[0].proto.value == 50
    assert any("50%" in item.value for item in app.success)
    assert not any("0.5%" in item.value for item in app.markdown)
