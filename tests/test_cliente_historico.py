"""Edição do cliente de receitas já registradas no histórico, com dados fictícios."""
import sqlite3
from datetime import datetime

from streamlit.testing.v1 import AppTest

from trixter.historico_tela import (
    atualizar_cliente_receita,
    concluir_atualizacao_cliente_receita,
    identidade_movimentacao,
)
from trixter.sessao import encerrar_sessao_local

_R1 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1"
_R2 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2"
_GASTO = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1"
_MESMO = "cccccccc-cccc-cccc-cccc-ccccccccccc3"
_OUTRA = "dddddddd-dddd-dddd-dddd-ddddddddddd4"


def _banco():
    banco = sqlite3.connect(":memory:")
    banco.execute("ATTACH DATABASE ':memory:' AS dbo")
    banco.execute(
        """
        CREATE TABLE dbo.receitas (
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
    banco.execute(
        """
        CREATE TABLE dbo.gastos (
            id_transacao TEXT,
            id_usuario TEXT,
            descricao TEXT,
            valor NUMERIC
        )
        """
    )
    banco.execute(
        """
        CREATE TABLE dbo.planejamentos (
            id_planejamento TEXT,
            id_usuario TEXT,
            descricao TEXT,
            cliente TEXT
        )
        """
    )
    banco.execute(
        """
        CREATE TABLE dbo.recorrencias (
            id_recorrencia TEXT,
            id_usuario TEXT,
            descricao TEXT
        )
        """
    )
    return banco


class _Cursor:
    def __init__(self, banco, falhar_close=False, falhar_execute=False):
        self.banco = banco
        self.sql = ""
        self.args = ()
        self.falhar_close = falhar_close
        self.falhar_execute = falhar_execute
        self.fechado = False

    def execute(self, sql, *args):
        if self.falhar_execute:
            raise RuntimeError("execute secreto")
        self.sql = " ".join(sql.split())
        self.args = args
        self.resultado = self.banco.execute(sql, args)
        self.rowcount = self.resultado.rowcount

    def close(self):
        self.fechado = True
        if self.falhar_close:
            raise RuntimeError("close secreto")


class _Conexao:
    def __init__(
        self,
        banco,
        falhar_close_cursor=False,
        falhar_close_conexao=False,
        falhar_commit=False,
        falhar_rollback=False,
        falhar_execute=False,
    ):
        self.banco = banco
        self.cursor_interno = _Cursor(banco, falhar_close_cursor, falhar_execute)
        self.commitou = False
        self.desfez = False
        self.fechada = False
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


def _inserir_receita(banco, identificador, usuario, cliente, descricao="Sala"):
    banco.execute(
        """
        INSERT INTO dbo.receitas
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (identificador, usuario, "2026-10-20", "Aluguel", descricao, 50, "Variável", cliente),
    )


def _vizinhos(banco):
    banco.execute(
        "INSERT INTO dbo.gastos VALUES (?, ?, ?, ?)",
        ("gasto-vizinho", "conta-a", "Mercado", 10),
    )
    banco.execute(
        "INSERT INTO dbo.planejamentos VALUES (?, ?, ?, ?)",
        ("plano-vizinho", "conta-a", "Sala", "Aurora"),
    )
    banco.execute(
        "INSERT INTO dbo.recorrencias VALUES (?, ?, ?)",
        ("recor-vizinho", "conta-a", "Mensal"),
    )


def _receita(banco, identificador="tx-1"):
    return banco.execute(
        """
        SELECT data, categoria, descricao, valor, classificacao, cliente
        FROM dbo.receitas
        WHERE id_transacao = ?
        """,
        (identificador,),
    ).fetchone()


def _gravar(banco, identificador, usuario, cliente):
    banco.commit()
    conexao = _Conexao(banco)
    situacao = concluir_atualizacao_cliente_receita(
        lambda: conexao, identificador, usuario, cliente
    )
    return conexao, situacao


def test_receita_manual_atualiza_somente_o_cliente():
    banco = _banco()
    _inserir_receita(banco, "tx-1", "conta-a", "Aurora Serviços")
    _vizinhos(banco)
    conexao, situacao = _gravar(banco, "tx-1", "conta-a", "  Beta   Serviços  ")
    assert situacao == "atualizado"
    assert conexao.commitou
    assert not conexao.desfez
    assert _receita(banco) == ("2026-10-20", "Aluguel", "Sala", 50, "Variável", "Beta Serviços")
    assert "UPDATE dbo.receitas" in conexao.cursor_interno.sql
    assert conexao.cursor_interno.sql.count("SET") == 1
    assert "SET cliente = ?" in conexao.cursor_interno.sql
    assert "id_usuario = ?" in conexao.cursor_interno.sql
    assert conexao.cursor_interno.args == ("Beta Serviços", "tx-1", "conta-a")
    assert "planejamentos" not in conexao.cursor_interno.sql
    assert "gastos" not in conexao.cursor_interno.sql
    assert "recorrencias" not in conexao.cursor_interno.sql
    assert banco.execute("SELECT descricao, valor FROM dbo.gastos").fetchone() == ("Mercado", 10)
    assert banco.execute("SELECT descricao, cliente FROM dbo.planejamentos").fetchone() == (
        "Sala",
        "Aurora",
    )
    assert banco.execute("SELECT descricao FROM dbo.recorrencias").fetchone() == ("Mensal",)


def test_receita_de_baixa_atualiza_somente_o_cliente():
    banco = _banco()
    _inserir_receita(banco, "tx-baixa", "conta-a", "Cliente da baixa", "Honorários")
    conexao, situacao = _gravar(banco, "tx-baixa", "conta-a", "Cliente corrigido")
    assert situacao == "atualizado"
    assert conexao.commitou
    assert _receita(banco, "tx-baixa") == (
        "2026-10-20",
        "Aluguel",
        "Honorários",
        50,
        "Variável",
        "Cliente corrigido",
    )


def test_receita_importada_ou_recorrente_comeca_sem_cliente():
    banco = _banco()
    _inserir_receita(banco, "tx-1", "conta-a", None)
    assert _receita(banco)[5] is None
    conexao, situacao = _gravar(banco, "tx-1", "conta-a", "Aurora")
    assert situacao == "atualizado"
    assert conexao.commitou
    assert _receita(banco)[5] == "Aurora"
    assert _receita(banco)[:5] == ("2026-10-20", "Aluguel", "Sala", 50, "Variável")


def test_cliente_longo_fica_em_80_e_vazio_vira_null():
    banco = _banco()
    _inserir_receita(banco, "tx-1", "conta-a", "Aurora")
    conexao, situacao = _gravar(banco, "tx-1", "conta-a", "A" * 81)
    assert situacao == "atualizado"
    assert _receita(banco)[5] == "A" * 80
    assert conexao.cursor_interno.args[0] == "A" * 80
    conexao, situacao = _gravar(banco, "tx-1", "conta-a", "   ")
    assert situacao == "atualizado"
    assert conexao.commitou
    assert _receita(banco)[5] is None
    assert conexao.cursor_interno.args[0] is None


def test_outra_conta_e_id_inexistente_fazem_rollback():
    banco = _banco()
    _inserir_receita(banco, "tx-1", "conta-b", "Aurora")
    banco.commit()

    outra = _Conexao(banco)
    assert concluir_atualizacao_cliente_receita(
        lambda: outra, "tx-1", "conta-a", "Beta"
    ) == "ausente"
    assert outra.desfez
    assert not outra.commitou
    assert _receita(banco)[5] == "Aurora"
    assert outra.cursor_interno.args[-2:] == ("tx-1", "conta-a")

    ausente = _Conexao(banco)
    assert concluir_atualizacao_cliente_receita(
        lambda: ausente, "tx-ausente", "conta-b", "Beta"
    ) == "ausente"
    assert ausente.desfez
    assert not ausente.commitou
    assert _receita(banco)[5] == "Aurora"

    class CursorVazio:
        def execute(self, sql, *args):
            raise AssertionError("nao deveria gravar")

        def close(self):
            pass

    class ConexaoVazia:
        def __init__(self):
            self.desfez = False
            self.commitou = False

        def cursor(self):
            return CursorVazio()

        def commit(self):
            self.commitou = True

        def rollback(self):
            self.desfez = True

        def close(self):
            pass

    vazia = ConexaoVazia()
    assert concluir_atualizacao_cliente_receita(
        lambda: vazia, "  ", "conta-a", "Beta"
    ) == "ausente"
    assert vazia.desfez
    assert not vazia.commitou


def test_duas_linhas_nao_confirmam_a_atualizacao():
    banco = _banco()
    _inserir_receita(banco, "tx-1", "conta-a", "Aurora")
    _inserir_receita(banco, "tx-1", "conta-a", "Outra")
    banco.commit()
    conexao = _Conexao(banco)
    assert concluir_atualizacao_cliente_receita(
        lambda: conexao, "tx-1", "conta-a", "Beta"
    ) == "ausente"
    assert conexao.desfez
    assert not conexao.commitou
    assert banco.execute("SELECT cliente FROM dbo.receitas ORDER BY cliente").fetchall() == [
        ("Aurora",),
        ("Outra",),
    ]


def test_falha_no_banco_desfaz():
    class Cursor:
        def execute(self, sql, *args):
            raise RuntimeError("falha ficticia")

        def close(self):
            pass

    class Conexao:
        def __init__(self):
            self.commitou = False
            self.desfez = False

        def cursor(self):
            return Cursor()

        def commit(self):
            self.commitou = True

        def rollback(self):
            self.desfez = True

        def close(self):
            pass

    conexao = Conexao()
    assert concluir_atualizacao_cliente_receita(
        lambda: conexao, "tx-1", "conta-a", "Beta"
    ) == "falha"
    assert conexao.desfez
    assert not conexao.commitou


def test_falha_de_close_depois_do_commit_preserva_atualizado():
    for falha_cursor, falha_conexao in ((True, False), (False, True), (True, True)):
        banco = _banco()
        _inserir_receita(banco, "tx-1", "conta-a", "Aurora")
        banco.commit()
        conexao = _Conexao(
            banco,
            falhar_close_cursor=falha_cursor,
            falhar_close_conexao=falha_conexao,
        )
        assert concluir_atualizacao_cliente_receita(
            lambda: conexao, "tx-1", "conta-a", "  Beta   Serviços  "
        ) == "atualizado"
        assert conexao.commitou
        assert not conexao.desfez
        assert conexao.cursor_interno.fechado
        assert conexao.fechada
        assert _receita(banco)[5] == "Beta Serviços"
        assert _receita(banco)[:5] == ("2026-10-20", "Aluguel", "Sala", 50, "Variável")


def test_falha_de_close_depois_de_nenhuma_linha_preserva_ausente():
    banco = _banco()
    _inserir_receita(banco, "tx-1", "conta-b", "Aurora")
    banco.commit()
    conexao = _Conexao(banco, falhar_close_cursor=True, falhar_close_conexao=True)
    assert concluir_atualizacao_cliente_receita(
        lambda: conexao, "tx-1", "conta-a", "Beta"
    ) == "ausente"
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert _receita(banco)[5] == "Aurora"


def test_duas_linhas_com_falha_de_close_desfazem_e_permanecem_ausentes():
    banco = _banco()
    _inserir_receita(banco, "tx-1", "conta-a", "Aurora")
    _inserir_receita(banco, "tx-1", "conta-a", "Outra")
    banco.commit()
    conexao = _Conexao(banco, falhar_close_cursor=True, falhar_close_conexao=True)
    assert concluir_atualizacao_cliente_receita(
        lambda: conexao, "tx-1", "conta-a", "Beta"
    ) == "ausente"
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert banco.execute(
        "SELECT cliente FROM dbo.receitas ORDER BY cliente"
    ).fetchall() == [("Aurora",), ("Outra",)]


def test_falha_de_execute_seguida_de_close_continua_falha():
    banco = _banco()
    _inserir_receita(banco, "tx-1", "conta-a", "Aurora")
    banco.commit()
    conexao = _Conexao(
        banco,
        falhar_execute=True,
        falhar_close_cursor=True,
        falhar_close_conexao=True,
    )
    assert concluir_atualizacao_cliente_receita(
        lambda: conexao, "tx-1", "conta-a", "Beta"
    ) == "falha"
    assert not conexao.commitou
    assert conexao.desfez
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert _receita(banco)[5] == "Aurora"


def test_falha_de_commit_seguida_de_close_continua_falha():
    banco = _banco()
    _inserir_receita(banco, "tx-1", "conta-a", "Aurora")
    banco.commit()
    conexao = _Conexao(
        banco,
        falhar_commit=True,
        falhar_close_cursor=True,
        falhar_close_conexao=True,
    )
    assert concluir_atualizacao_cliente_receita(
        lambda: conexao, "tx-1", "conta-a", "Beta"
    ) == "falha"
    assert not conexao.commitou
    assert conexao.desfez
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert _receita(banco)[5] == "Aurora"


def test_falha_no_rollback_devolve_falha():
    banco = _banco()
    _inserir_receita(banco, "tx-1", "conta-b", "Aurora")
    banco.commit()
    conexao = _Conexao(banco, falhar_rollback=True)
    assert concluir_atualizacao_cliente_receita(
        lambda: conexao, "tx-1", "conta-a", "Beta"
    ) == "falha"
    assert not conexao.commitou
    assert _receita(banco)[5] == "Aurora"


def test_funcao_nao_grava_sem_executar_para_id_vazio():
    class Cursor:
        def execute(self, sql, *args):
            raise AssertionError(sql)

        def close(self):
            pass

    assert atualizar_cliente_receita(Cursor(), "", "conta-a", "Beta") is False
    assert atualizar_cliente_receita(Cursor(), "tx-1", "", "Beta") is False


def _linha(ident, tipo, descricao, cliente):
    return (
        ident, "usuario-teste", datetime(2026, 10, 20), descricao, 50.0,
        "Aluguel", tipo, None, cliente,
    )


def _script(linhas):
    texto = repr(list(linhas))
    outra = repr([
        (
            _OUTRA, "outra-conta", datetime(2026, 10, 21), "Outra", 80.0,
            "Serviço", "Receita", None, "Cliente da outra conta",
        )
    ])
    return f"""
import datetime
import streamlit as st
from trixter.historico_tela import exibir_historico

def formatar_moeda(valor):
    return f"R$ {{valor:.2f}}"

st.session_state.setdefault("usuario_atual", {{"id_usuario": "usuario-teste"}})
st.session_state.setdefault("linhas", {texto})
st.session_state.setdefault("chamadas", [])
st.session_state.setdefault("commits", 0)
st.session_state.setdefault("rollbacks", 0)

class Cursor:
    description = [(c,) for c in (
        "id_transacao", "id_usuario", "data", "descricao", "valor",
        "categoria", "tipo", "classificacao", "cliente"
    )]
    def execute(self, sql, *args):
        st.session_state.chamadas.append((" ".join(sql.split()), args))
        self.rowcount = 1
    def fetchall(self):
        return list(st.session_state.linhas)
    def close(self):
        pass

class Conexao:
    def cursor(self):
        return Cursor()
    def commit(self):
        st.session_state.commits += 1
    def rollback(self):
        st.session_state.rollbacks += 1
    def close(self):
        pass

if st.session_state.pop("invalidar_selecao", False):
    st.session_state.historico_movimentacao_selecionada = "Receita|id-de-outra-conta"
    st.session_state.editando_movimentacao = ("outra-conta", "id-de-outra-conta", "Receita")
    st.session_state.historico_cliente = "Rascunho de outra conta"

if st.session_state.pop("trocar_conta", False):
    st.session_state.usuario_atual = {{"id_usuario": "outra-conta"}}
    st.session_state.linhas = {outra}
    st.session_state.historico_movimentacao_selecionada = "Receita|{_R1}"
    st.session_state.historico_cliente = "Rascunho da conta anterior"
    st.session_state.historico_cliente_id = "usuario-teste|Receita|{_R1}"
    st.session_state.editando_movimentacao = ("usuario-teste", "{_R1}", "Receita")

exibir_historico(lambda: Conexao(), "Pessoa Física", "Gasto", formatar_moeda)
"""


def _app(linhas):
    return AppTest.from_string(_script(linhas)).run()


def _updates(app):
    return [
        (sql, args)
        for sql, args in app.session_state.chamadas
        if sql.startswith("UPDATE") or sql.startswith("DELETE")
    ]


def _botao(app, texto):
    return next(botao for botao in app.button if botao.label == texto)


def _abrir(app):
    app.button(key="btn_alterar_transacao").click().run()
    assert not app.exception
    return app


def test_despesa_nao_mostra_nem_grava_cliente():
    app = _abrir(_app([_linha(_GASTO, "Gasto", "Mercado", None)]))
    assert not any(campo.key == "historico_cliente" for campo in app.text_input)
    assert not any(botao.label == "Salvar cliente" for botao in app.button)
    _botao(app, "Salvar Alterações").click().run()
    sql, args = _updates(app)[-1]
    assert "UPDATE dbo.gastos" in sql
    assert "SET cliente" not in sql
    assert "cliente = ?" not in sql
    assert args[-2:] == (_GASTO, "usuario-teste")


def test_alteracao_financeira_da_receita_nao_grava_cliente():
    app = _abrir(_app([_linha(_R1, "Receita", "Sala", "Aurora")]))
    assert app.text_input(key="historico_cliente").value == "Aurora"
    _botao(app, "Salvar Alterações").click().run()
    sql, args = _updates(app)[-1]
    assert "UPDATE dbo.receitas" in sql
    assert "classificacao = ?" in sql
    assert "SET cliente" not in sql
    assert args[-2:] == (_R1, "usuario-teste")


def test_duas_receitas_iguais_gravam_o_cliente_da_selecionada():
    app = _abrir(_app([
        _linha(_R1, "Receita", "Sala", "Aurora"),
        _linha(_R2, "Receita", "Outra sala", "Beta"),
    ]))
    assert app.text_input(key="historico_cliente").value == "Aurora"
    app.selectbox(key="historico_movimentacao_selecionada").set_value(
        identidade_movimentacao("Receita", _R2)
    ).run()
    _abrir(app)
    assert app.text_input(key="historico_cliente").value == "Beta"
    app.text_input(key="historico_cliente").set_value("Nova Beta").run()
    _botao(app, "Salvar cliente").click().run()
    assert not app.exception
    sql, args = _updates(app)[-1]
    assert sql.startswith("UPDATE dbo.receitas")
    assert "SET cliente = ?" in sql
    assert "data = ?" not in sql
    assert "categoria = ?" not in sql
    assert "valor = ?" not in sql
    assert "descricao = ?" not in sql
    assert "classificacao = ?" not in sql
    assert "planejamentos" not in sql
    assert "gastos" not in sql
    assert "recorrencias" not in sql
    assert args == ("Nova Beta", _R2, "usuario-teste")
    assert app.session_state.commits == 1
    assert app.session_state.rollbacks == 0
    assert any("Cliente atualizado." in aviso.value for aviso in app.success)


def test_receita_e_gasto_com_o_mesmo_id_nao_confundem_o_cliente():
    app = _abrir(_app([
        _linha(_MESMO, "Receita", "Da receita", "Cliente da receita"),
        _linha(_MESMO, "Gasto", "Do gasto", None),
    ]))
    assert app.text_input(key="historico_cliente").value == "Cliente da receita"
    app.selectbox(key="historico_movimentacao_selecionada").set_value(
        identidade_movimentacao("Gasto", _MESMO)
    ).run()
    _abrir(app)
    assert not any(campo.key == "historico_cliente" for campo in app.text_input)
    app.selectbox(key="historico_movimentacao_selecionada").set_value(
        identidade_movimentacao("Receita", _MESMO)
    ).run()
    _abrir(app)
    assert app.text_input(key="historico_cliente").value == "Cliente da receita"
    app.text_input(key="historico_cliente").set_value("   ").run()
    _botao(app, "Salvar cliente").click().run()
    sql, args = _updates(app)[-1]
    assert "UPDATE dbo.receitas" in sql
    assert "dbo.gastos" not in sql
    assert args == (None, _MESMO, "usuario-teste")


def test_rerun_mantem_o_texto_da_mesma_receita():
    app = _abrir(_app([_linha(_R1, "Receita", "Sala", "Aurora")]))
    app.text_input(key="historico_cliente").set_value("Ainda digitando").run()
    app.run()
    assert not app.exception
    assert app.text_input(key="historico_cliente").value == "Ainda digitando"
    assert _updates(app) == []
    assert app.session_state.commits == 0


def test_troca_de_conta_nao_reutiliza_o_cliente():
    app = _abrir(_app([_linha(_R1, "Receita", "Sala", "Aurora")]))
    app.text_input(key="historico_cliente").set_value("Rascunho da conta anterior").run()
    app.session_state.trocar_conta = True
    _botao(app, "Salvar cliente").click().run()
    assert not app.exception
    assert _updates(app) == []
    assert app.session_state.commits == 0
    assert app.session_state.rollbacks == 0
    assert app.session_state.usuario_atual["id_usuario"] == "outra-conta"
    _abrir(app)
    assert app.text_input(key="historico_cliente").value == "Cliente da outra conta"


def test_selecao_invalida_nao_grava_o_cliente():
    app = _abrir(_app([_linha(_R1, "Receita", "Sala", "Aurora")]))
    app.session_state.invalidar_selecao = True
    _botao(app, "Salvar cliente").click().run()
    assert not app.exception
    assert _updates(app) == []
    assert app.session_state.commits == 0
    assert app.session_state.rollbacks == 0
    assert "historico_cliente" not in app.session_state
    assert "editando_movimentacao" not in app.session_state


def test_encerrar_sessao_apaga_as_chaves_do_cliente():
    estado = {
        "usuario_logado": True,
        "usuario_atual": {"id_usuario": "usuario-teste"},
        "historico_cliente": "Aurora",
        "historico_cliente_id": f"usuario-teste|Receita|{_R1}",
        "historico_cliente_sucesso": "Cliente atualizado.",
        "historico_cliente_aviso": "Não foi possível salvar o cliente.",
    }
    encerrar_sessao_local(estado)
    assert "historico_cliente" not in estado
    assert "historico_cliente_id" not in estado
    assert "historico_cliente_sucesso" not in estado
    assert "historico_cliente_aviso" not in estado
