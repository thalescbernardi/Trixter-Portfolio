"""Confirmação transacional do UPDATE e do DELETE financeiros do histórico."""
import sqlite3
from datetime import datetime

import pytest
from streamlit.testing.v1 import AppTest

from trixter.historico_tela import concluir_gravacao_financeira
from trixter.sessao import encerrar_sessao_local

_UPDATE = """
UPDATE dbo.receitas
SET data = ?, categoria = ?, valor = ?, descricao = ?, classificacao = ?
WHERE id_transacao = ?
AND id_usuario = ?
"""
_DELETE = """
DELETE FROM dbo.receitas
WHERE id_transacao = ?
AND id_usuario = ?
"""
_UPDATE_GASTO = """
UPDATE dbo.gastos
SET data = ?, categoria = ?, valor = ?, descricao = ?, classificacao = ?
WHERE id_transacao = ?
AND id_usuario = ?
"""
_DELETE_GASTO = """
DELETE FROM dbo.gastos
WHERE id_transacao = ?
AND id_usuario = ?
"""
_AUSENTE = "Não foi possível encontrar ou atualizar essa movimentação."
_FALHA_EXCLUSAO = "Não foi possível excluir a movimentação agora."
_FALHA_ALTERACAO = "Não foi possível alterar a movimentação agora."


def _banco():
    banco = sqlite3.connect(":memory:")
    banco.execute("ATTACH DATABASE ':memory:' AS dbo")
    for tabela in ("receitas", "gastos"):
        banco.execute(
            f"""
            CREATE TABLE dbo.{tabela} (
                id_transacao TEXT,
                id_usuario TEXT,
                data TEXT,
                categoria TEXT,
                descricao TEXT,
                valor NUMERIC,
                classificacao TEXT,
                cliente TEXT
            )
            """
        )
    return banco


def _inserir(banco, tabela, identificador, usuario, valor=50, cliente="Aurora"):
    banco.execute(
        f"INSERT INTO dbo.{tabela} VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (identificador, usuario, "2026-10-20", "Aluguel", "Sala", valor, "Variável", cliente),
    )


def _linhas(banco, tabela):
    return banco.execute(
        f"""
        SELECT id_transacao, id_usuario, data, categoria, descricao, valor,
               classificacao, cliente
        FROM dbo.{tabela}
        ORDER BY id_usuario, valor
        """
    ).fetchall()


class _Cursor:
    def __init__(self, banco, rowcount=None, falhar=False, falhar_close=False):
        self.banco = banco
        self.rowcount_forcado = rowcount
        self.falhar = falhar
        self.falhar_close = falhar_close
        self.fechado = False
        self.sql = ""
        self.args = ()

    def execute(self, sql, *args):
        if self.falhar:
            raise RuntimeError("execute secreto")
        self.sql = " ".join(sql.split())
        self.args = args
        resultado = self.banco.execute(sql, args)
        self.rowcount = self.rowcount_forcado if self.rowcount_forcado is not None else resultado.rowcount

    def close(self):
        self.fechado = True
        if self.falhar_close:
            raise RuntimeError("close secreto")


class _Conexao:
    def __init__(
        self,
        banco,
        rowcount=None,
        falhar_execute=False,
        falhar_commit=False,
        falhar_rollback=False,
        falhar_close_cursor=False,
        falhar_close_conexao=False,
    ):
        self.banco = banco
        self.cursor_interno = _Cursor(banco, rowcount, falhar_execute, falhar_close_cursor)
        self.fechada = False
        self.commitou = False
        self.desfez = False
        self.falhar_commit = falhar_commit
        self.falhar_rollback = falhar_rollback
        self.falhar_close_conexao = falhar_close_conexao

    def cursor(self):
        return self.cursor_interno

    def commit(self):
        if self.falhar_commit:
            raise RuntimeError("commit secreto")
        self.commitou = True
        self.banco.commit()

    def rollback(self):
        self.desfez = True
        if self.falhar_rollback:
            raise RuntimeError("rollback secreto")
        self.banco.rollback()

    def close(self):
        self.fechada = True
        if self.falhar_close_conexao:
            raise RuntimeError("close secreto")


def _comandos():
    return [
        ("alteracao", _UPDATE, ("2026-10-21", "Serviço", 80, "Sala nova", "Fixo", "tx-1", "conta-a")),
        ("exclusao", _DELETE, ("tx-1", "conta-a")),
    ]


@pytest.mark.parametrize("operacao,sql,parametros", _comandos())
def test_uma_linha_confirma_commit(operacao, sql, parametros):
    banco = _banco()
    _inserir(banco, "receitas", "tx-1", "conta-a")
    _inserir(banco, "gastos", "tx-1", "conta-a", valor=10, cliente="Gasto")
    banco.commit()
    conexao = _Conexao(banco)
    assert concluir_gravacao_financeira(lambda: conexao, sql, parametros) == "confirmado"
    assert conexao.commitou
    assert not conexao.desfez
    assert conexao.fechada
    assert conexao.cursor_interno.fechado
    assert conexao.cursor_interno.args[-2:] == ("tx-1", "conta-a")
    assert "cliente = ?" not in conexao.cursor_interno.sql
    if operacao == "alteracao":
        assert _linhas(banco, "receitas") == [
            ("tx-1", "conta-a", "2026-10-21", "Serviço", "Sala nova", 80, "Fixo", "Aurora"),
        ]
    else:
        assert _linhas(banco, "receitas") == []
    assert _linhas(banco, "gastos") == [
        ("tx-1", "conta-a", "2026-10-20", "Aluguel", "Sala", 10, "Variável", "Gasto"),
    ]


@pytest.mark.parametrize("operacao,sql,parametros", _comandos())
def test_nenhuma_linha_desfaz_sem_sucesso(operacao, sql, parametros):
    banco = _banco()
    _inserir(banco, "receitas", "tx-1", "conta-b")
    banco.commit()
    antes = _linhas(banco, "receitas")
    conexao = _Conexao(banco)
    assert concluir_gravacao_financeira(lambda: conexao, sql, parametros) == "ausente"
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.fechada
    assert conexao.cursor_interno.fechado
    assert _linhas(banco, "receitas") == antes


@pytest.mark.parametrize("operacao,sql,parametros", _comandos())
def test_duas_linhas_desfazem_a_gravacao(operacao, sql, parametros):
    banco = _banco()
    _inserir(banco, "receitas", "tx-1", "conta-a", valor=50)
    _inserir(banco, "receitas", "tx-1", "conta-a", valor=70)
    banco.commit()
    antes = _linhas(banco, "receitas")
    conexao = _Conexao(banco)
    assert concluir_gravacao_financeira(lambda: conexao, sql, parametros) == "falha"
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.fechada
    assert _linhas(banco, "receitas") == antes


@pytest.mark.parametrize("operacao,sql,parametros", _comandos())
def test_rowcount_desconhecido_desfaz(operacao, sql, parametros):
    banco = _banco()
    _inserir(banco, "receitas", "tx-1", "conta-a")
    banco.commit()
    antes = _linhas(banco, "receitas")
    conexao = _Conexao(banco, rowcount=-1)
    assert concluir_gravacao_financeira(lambda: conexao, sql, parametros) == "falha"
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.fechada
    assert conexao.cursor_interno.fechado
    assert _linhas(banco, "receitas") == antes


@pytest.mark.parametrize("operacao,sql,parametros", _comandos())
def test_excecao_no_execute_desfaz_e_fecha(operacao, sql, parametros):
    banco = _banco()
    conexao = _Conexao(banco, falhar_execute=True)
    assert concluir_gravacao_financeira(lambda: conexao, sql, parametros) == "falha"
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.fechada
    assert conexao.cursor_interno.fechado


@pytest.mark.parametrize("operacao,sql,parametros", _comandos())
def test_excecao_no_commit_nao_confirma(operacao, sql, parametros):
    banco = _banco()
    _inserir(banco, "receitas", "tx-1", "conta-a")
    banco.commit()
    antes = _linhas(banco, "receitas")
    conexao = _Conexao(banco, falhar_commit=True)
    assert concluir_gravacao_financeira(lambda: conexao, sql, parametros) == "falha"
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.fechada
    assert _linhas(banco, "receitas") == antes


@pytest.mark.parametrize("operacao,sql,parametros", _comandos())
def test_excecao_no_rollback_nao_confirma(operacao, sql, parametros):
    banco = _banco()
    _inserir(banco, "receitas", "tx-1", "conta-a", valor=50)
    _inserir(banco, "receitas", "tx-1", "conta-a", valor=70)
    banco.commit()
    conexao = _Conexao(banco, falhar_rollback=True)
    assert concluir_gravacao_financeira(lambda: conexao, sql, parametros) == "falha"
    assert not conexao.commitou
    assert conexao.fechada
    assert conexao.cursor_interno.fechado


@pytest.mark.parametrize("operacao,sql,parametros", _comandos())
@pytest.mark.parametrize(
    "falha_cursor,falha_conexao",
    [(True, False), (False, True), (True, True)],
)
def test_falha_de_close_depois_do_commit_preserva_confirmado(
    operacao, sql, parametros, falha_cursor, falha_conexao
):
    banco = _banco()
    _inserir(banco, "receitas", "tx-1", "conta-a")
    banco.commit()
    conexao = _Conexao(
        banco,
        falhar_close_cursor=falha_cursor,
        falhar_close_conexao=falha_conexao,
    )
    assert concluir_gravacao_financeira(lambda: conexao, sql, parametros) == "confirmado"
    assert conexao.commitou
    assert not conexao.desfez
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    if operacao == "alteracao":
        assert _linhas(banco, "receitas")[0][2:7] == (
            "2026-10-21", "Serviço", "Sala nova", 80, "Fixo",
        )
    else:
        assert _linhas(banco, "receitas") == []


@pytest.mark.parametrize("operacao,sql,parametros", _comandos())
@pytest.mark.parametrize(
    "linhas,esperado",
    [(0, "ausente"), (2, "falha")],
)
@pytest.mark.parametrize(
    "falha_cursor,falha_conexao",
    [(True, False), (False, True)],
)
def test_falha_de_close_depois_do_rollback_preserva_o_resultado(
    operacao, sql, parametros, linhas, esperado, falha_cursor, falha_conexao
):
    banco = _banco()
    if linhas == 0:
        _inserir(banco, "receitas", "tx-1", "conta-b")
    else:
        _inserir(banco, "receitas", "tx-1", "conta-a", valor=50)
        _inserir(banco, "receitas", "tx-1", "conta-a", valor=70)
    banco.commit()
    antes = _linhas(banco, "receitas")
    conexao = _Conexao(
        banco,
        falhar_close_cursor=falha_cursor,
        falhar_close_conexao=falha_conexao,
    )
    assert concluir_gravacao_financeira(lambda: conexao, sql, parametros) == esperado
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert _linhas(banco, "receitas") == antes


@pytest.mark.parametrize("operacao,sql,parametros", _comandos())
def test_falha_de_execute_seguida_de_close_continua_falha(operacao, sql, parametros):
    banco = _banco()
    conexao = _Conexao(
        banco,
        falhar_execute=True,
        falhar_close_cursor=True,
        falhar_close_conexao=True,
    )
    assert concluir_gravacao_financeira(lambda: conexao, sql, parametros) == "falha"
    assert not conexao.commitou
    assert conexao.desfez
    assert conexao.cursor_interno.fechado
    assert conexao.fechada


@pytest.mark.parametrize("operacao,sql,parametros", _comandos())
def test_falha_de_commit_seguida_de_close_continua_falha(operacao, sql, parametros):
    banco = _banco()
    _inserir(banco, "receitas", "tx-1", "conta-a")
    banco.commit()
    antes = _linhas(banco, "receitas")
    conexao = _Conexao(
        banco,
        falhar_commit=True,
        falhar_close_cursor=True,
        falhar_close_conexao=True,
    )
    assert concluir_gravacao_financeira(lambda: conexao, sql, parametros) == "falha"
    assert not conexao.commitou
    assert conexao.desfez
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert _linhas(banco, "receitas") == antes


def test_receita_e_gasto_com_o_mesmo_id_seguem_a_tabela_do_tipo():
    banco = _banco()
    _inserir(banco, "receitas", "mesmo", "conta-a", valor=50, cliente="Da receita")
    _inserir(banco, "gastos", "mesmo", "conta-a", valor=10, cliente=None)
    banco.commit()
    alteracao = _Conexao(banco)
    assert concluir_gravacao_financeira(
        lambda: alteracao,
        _UPDATE,
        ("2026-10-21", "Serviço", 90, "Sala nova", "Fixo", "mesmo", "conta-a"),
    ) == "confirmado"
    assert _linhas(banco, "gastos")[0][5:] == (10, "Variável", None)
    assert _linhas(banco, "receitas")[0][7] == "Da receita"
    exclusao = _Conexao(banco)
    assert concluir_gravacao_financeira(
        lambda: exclusao, _DELETE_GASTO, ("mesmo", "conta-a")
    ) == "confirmado"
    assert _linhas(banco, "gastos") == []
    assert _linhas(banco, "receitas")[0][2:5] == ("2026-10-21", "Serviço", "Sala nova")


def _tela(tipo="Receita"):
    return f"""
import datetime
import streamlit as st
from trixter.historico_tela import exibir_historico

def formatar_moeda(valor):
    return f"R$ {{valor:.2f}}"

st.session_state.setdefault("usuario_atual", {{"id_usuario": "usuario-teste"}})
st.session_state.setdefault("chamadas", [])
st.session_state.setdefault("commits", 0)
st.session_state.setdefault("rollbacks", 0)
st.session_state.setdefault("fechamentos", 0)

class Cursor:
    description = [(c,) for c in (
        "id_transacao", "id_usuario", "data", "descricao", "valor",
        "categoria", "tipo", "classificacao", "cliente"
    )]
    def execute(self, sql, *args):
        texto = " ".join(sql.split())
        st.session_state.chamadas.append((texto, args))
        if st.session_state.get("falhar_execute") and (
            texto.startswith("UPDATE") or texto.startswith("DELETE")
        ):
            raise RuntimeError("execute secreto")
        self.rowcount = st.session_state.get("forcar_rowcount", 1)
    def fetchall(self):
        return [(
            "tx-1", "usuario-teste", datetime.datetime(2026, 10, 20),
            "Sala", 50.0, "Aluguel", {tipo!r}, None, "Aurora",
        )]
    def close(self):
        st.session_state.fechamentos += 1

class Conexao:
    def cursor(self):
        return Cursor()
    def commit(self):
        if st.session_state.get("falhar_commit"):
            raise RuntimeError("commit secreto")
        st.session_state.commits += 1
    def rollback(self):
        st.session_state.rollbacks += 1
        if st.session_state.get("falhar_rollback"):
            raise RuntimeError("rollback secreto")
    def close(self):
        st.session_state.fechamentos += 1

exibir_historico(lambda: Conexao(), "Pessoa Física", "Gasto", formatar_moeda)
"""


def _app(tipo="Receita"):
    return AppTest.from_string(_tela(tipo)).run()


def _textos(app):
    blocos = list(app.success) + list(app.warning) + list(app.error) + list(app.info)
    return " ".join(bloco.value for bloco in blocos)


def _botao(app, texto):
    return next(botao for botao in app.button if botao.label == texto)


def _salvar(app):
    app.button(key="btn_alterar_transacao").click().run()
    _botao(app, "Salvar Alterações").click().run()
    return app


@pytest.mark.parametrize("acao", ["exclusao", "alteracao"])
def test_tela_confirma_somente_uma_linha(acao):
    app = _app()
    app.session_state.forcar_rowcount = 1
    if acao == "exclusao":
        _botao(app, "Excluir Movimentação Selecionada").click().run()
        assert any("excluída com sucesso" in item.value for item in app.success)
    else:
        _salvar(app)
        assert any("alterada com sucesso" in item.value for item in app.success)
    assert app.session_state.commits == 1
    assert app.session_state.rollbacks == 0
    assert not app.exception


@pytest.mark.parametrize("acao", ["exclusao", "alteracao"])
def test_tela_avisa_quando_nenhuma_linha_e_afetada(acao):
    app = _app()
    app.session_state.forcar_rowcount = 0
    app.session_state.movimentacao_excluida_sucesso = True
    app.session_state.movimentacao_alterada_sucesso = True
    if acao == "exclusao":
        _botao(app, "Excluir Movimentação Selecionada").click().run()
    else:
        _salvar(app)
    assert not app.exception
    assert any(_AUSENTE in item.value for item in app.warning)
    for chave in ("movimentacao_excluida_sucesso", "movimentacao_alterada_sucesso"):
        assert chave not in app.session_state or app.session_state[chave] is not True
    assert app.session_state.commits == 0
    assert app.session_state.rollbacks == 1


@pytest.mark.parametrize("acao,falha", [("exclusao", _FALHA_EXCLUSAO), ("alteracao", _FALHA_ALTERACAO)])
def test_tela_nao_confirma_duas_linhas_nem_contagem_desconhecida(acao, falha):
    for contagem in (2, -1):
        app = _app()
        app.session_state.forcar_rowcount = contagem
        if acao == "exclusao":
            _botao(app, "Excluir Movimentação Selecionada").click().run()
        else:
            _salvar(app)
        assert not app.exception
        assert falha in _textos(app)
        assert "com sucesso" not in _textos(app)
        assert "revert" not in _textos(app).lower()
        assert app.session_state.commits == 0
        assert app.session_state.rollbacks == 1


@pytest.mark.parametrize("acao", ["exclusao", "alteracao"])
def test_tela_oculta_excecoes_e_fecha_recursos(acao):
    app = _app()
    app.session_state.falhar_execute = True
    antes = app.session_state.fechamentos
    if acao == "exclusao":
        _botao(app, "Excluir Movimentação Selecionada").click().run()
        falha = _FALHA_EXCLUSAO
    else:
        _salvar(app)
        falha = _FALHA_ALTERACAO
    assert not app.exception
    assert falha in _textos(app)
    assert "secreto" not in _textos(app)
    assert "com sucesso" not in _textos(app)
    assert app.session_state.commits == 0
    assert app.session_state.rollbacks == 1
    assert app.session_state.fechamentos > antes

    app = _app()
    app.session_state.falhar_commit = True
    if acao == "exclusao":
        _botao(app, "Excluir Movimentação Selecionada").click().run()
    else:
        _salvar(app)
    assert not app.exception
    assert "secreto" not in _textos(app)
    assert "com sucesso" not in _textos(app)
    assert app.session_state.commits == 0
    assert app.session_state.rollbacks == 1

    app = _app()
    app.session_state.forcar_rowcount = 2
    app.session_state.falhar_rollback = True
    if acao == "exclusao":
        _botao(app, "Excluir Movimentação Selecionada").click().run()
    else:
        _salvar(app)
    assert not app.exception
    assert "secreto" not in _textos(app)
    assert "com sucesso" not in _textos(app)
    assert app.session_state.commits == 0


def test_salvar_cliente_nao_dispara_a_gravacao_financeira():
    app = _app()
    app.button(key="btn_alterar_transacao").click().run()
    _botao(app, "Salvar cliente").click().run()
    escritas = [
        sql for sql, _ in app.session_state.chamadas
        if sql.startswith("UPDATE") or sql.startswith("DELETE")
    ]
    assert len(escritas) == 1
    assert escritas[0].startswith("UPDATE dbo.receitas")
    assert "SET cliente = ?" in escritas[0]
    assert "data = ?" not in escritas[0]
    assert "movimentacao_alterada_sucesso" not in app.session_state
    assert "movimentacao_excluida_sucesso" not in app.session_state


def test_encerrar_sessao_apaga_os_avisos_financeiros():
    estado = {
        "usuario_logado": True,
        "usuario_atual": {"id_usuario": "usuario-teste"},
        "movimentacao_excluida_aviso": _FALHA_EXCLUSAO,
        "movimentacao_alterada_aviso": _FALHA_ALTERACAO,
        "movimentacao_excluida_sucesso": True,
        "movimentacao_alterada_sucesso": True,
    }
    encerrar_sessao_local(estado)
    assert "movimentacao_excluida_aviso" not in estado
    assert "movimentacao_alterada_aviso" not in estado
    assert "movimentacao_excluida_sucesso" not in estado
    assert "movimentacao_alterada_sucesso" not in estado
