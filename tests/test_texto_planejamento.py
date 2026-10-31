"""Edição de descrição e cliente do planejamento, sem dados reais."""
import sqlite3

from streamlit.testing.v1 import AppTest

from trixter.planejamento import (
    atualizar_texto_planejamento,
    concluir_atualizacao_texto_planejamento,
)
from trixter.sessao import encerrar_sessao_local

_PRIMEIRO = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1"
_SEGUNDO = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2"


def _banco():
    banco = sqlite3.connect(":memory:")
    banco.execute("ATTACH DATABASE ':memory:' AS dbo")
    banco.execute(
        """
        CREATE TABLE dbo.planejamentos (
            id_planejamento TEXT,
            id_usuario TEXT,
            tipo TEXT,
            categoria TEXT,
            descricao TEXT,
            valor NUMERIC,
            data TEXT,
            cliente TEXT,
            situacao TEXT
        )
        """
    )
    banco.execute(
        """
        CREATE TABLE dbo.receitas (
            id_transacao TEXT,
            id_usuario TEXT,
            descricao TEXT,
            cliente TEXT,
            valor NUMERIC
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
    return banco


class _Cursor:
    def __init__(self, banco):
        self.banco = banco

    def execute(self, sql, *args):
        self.sql = sql
        self.args = args
        self.resultado = self.banco.execute(sql, args)
        self.rowcount = self.resultado.rowcount

    def close(self):
        pass


def _inserir_planejamento(banco, identificador, usuario, tipo, descricao, cliente, situacao, valor=400):
    banco.execute(
        """
        INSERT INTO dbo.planejamentos
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (identificador, usuario, tipo, "Aluguel", descricao, valor, "2026-10-20", cliente, situacao),
    )


def test_receita_pendente_grava_descricao_e_cliente():
    banco = _banco()
    _inserir_planejamento(banco, "plano-1", "conta-a", "Receita", "Sala", "Aurora", None)
    cursor = _Cursor(banco)
    assert atualizar_texto_planejamento(
        cursor, "plano-1", "conta-a", "  Sala nova  ", "  Beta  ", True
    )
    linha = banco.execute(
        "SELECT descricao, cliente, valor, situacao, categoria FROM dbo.planejamentos"
    ).fetchone()
    assert linha == ("Sala nova", "Beta", 400, None, "Aluguel")
    assert "UPDATE dbo.planejamentos" in cursor.sql
    assert "cliente = ?" in cursor.sql
    assert "receitas" not in cursor.sql
    assert "gastos" not in cursor.sql


def test_receita_recebida_nao_altera_o_lancamento():
    banco = _banco()
    _inserir_planejamento(banco, "plano-1", "conta-a", "Receita", "Sala", "Aurora", "Recebido")
    banco.execute(
        "INSERT INTO dbo.receitas VALUES (?, ?, ?, ?, ?)",
        ("tx-1", "conta-a", "Sala", "Aurora", 400),
    )
    cursor = _Cursor(banco)
    assert atualizar_texto_planejamento(
        cursor, "plano-1", "conta-a", "Sala corrigida", "Beta", True
    )
    planejamento = banco.execute(
        "SELECT descricao, cliente, valor, situacao FROM dbo.planejamentos"
    ).fetchone()
    assert planejamento == ("Sala corrigida", "Beta", 400, "Recebido")
    assert banco.execute("SELECT descricao, cliente, valor FROM dbo.receitas").fetchone() == (
        "Sala",
        "Aurora",
        400,
    )


def test_despesa_pendente_e_paga_nao_alteram_cliente():
    banco = _banco()
    _inserir_planejamento(banco, "plano-1", "conta-a", "Despesa", "Sala", "NaoMexer", None)
    _inserir_planejamento(banco, "plano-2", "conta-a", "Despesa", "Outra", "TambemNao", "Pago", 80)
    banco.execute(
        "INSERT INTO dbo.gastos VALUES (?, ?, ?, ?)",
        ("tx-2", "conta-a", "Outra", 80),
    )
    cursor = _Cursor(banco)
    assert atualizar_texto_planejamento(
        cursor, "plano-1", "conta-a", "Sala corrigida", "Cliente indevido", False
    )
    assert "cliente" not in cursor.sql.lower()
    assert atualizar_texto_planejamento(
        cursor, "plano-2", "conta-a", "Outra corrigida", "Cliente indevido", False
    )
    linhas = banco.execute(
        "SELECT id_planejamento, descricao, cliente, situacao, valor FROM dbo.planejamentos ORDER BY id_planejamento"
    ).fetchall()
    assert linhas == [
        ("plano-1", "Sala corrigida", "NaoMexer", None, 400),
        ("plano-2", "Outra corrigida", "TambemNao", "Pago", 80),
    ]
    assert banco.execute("SELECT descricao, valor FROM dbo.gastos").fetchone() == ("Outra", 80)


def test_cliente_longo_fica_em_80_e_vazio_vira_null():
    banco = _banco()
    _inserir_planejamento(banco, "plano-1", "conta-a", "Receita", "Sala", "Aurora", None)
    cursor = _Cursor(banco)
    nome = "A" * 81
    assert atualizar_texto_planejamento(cursor, "plano-1", "conta-a", "Sala", nome, True)
    assert banco.execute("SELECT cliente FROM dbo.planejamentos").fetchone()[0] == "A" * 80
    assert atualizar_texto_planejamento(cursor, "plano-1", "conta-a", "Sala", "   ", True)
    assert banco.execute("SELECT cliente FROM dbo.planejamentos").fetchone()[0] is None


def test_descricao_vazia_permanece_vazia():
    banco = _banco()
    _inserir_planejamento(banco, "plano-1", "conta-a", "Receita", "Sala", "Aurora", None)
    cursor = _Cursor(banco)
    assert atualizar_texto_planejamento(cursor, "plano-1", "conta-a", "   ", "Aurora", True)
    assert banco.execute("SELECT descricao FROM dbo.planejamentos").fetchone()[0] == ""


def test_inexistente_e_outra_conta_fazem_rollback():
    banco = _banco()
    _inserir_planejamento(banco, "plano-1", "conta-b", "Receita", "Sala", "Aurora", None)

    class Conexao:
        def __init__(self):
            self.cursor_interno = _Cursor(banco)
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

    outra = Conexao()
    assert concluir_atualizacao_texto_planejamento(
        lambda: outra, "plano-1", "conta-a", "Nova", "Beta", True
    ) == "ausente"
    assert outra.desfez
    assert not outra.commitou
    assert banco.execute("SELECT descricao FROM dbo.planejamentos").fetchone()[0] == "Sala"

    ausente = Conexao()
    assert concluir_atualizacao_texto_planejamento(
        lambda: ausente, "plano-ausente", "conta-a", "Nova", "Beta", True
    ) == "ausente"
    assert ausente.desfez
    assert not ausente.commitou
    assert concluir_atualizacao_texto_planejamento(
        lambda: Conexao(), "", "conta-a", "Nova", "Beta", True
    ) == "ausente"


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
    assert concluir_atualizacao_texto_planejamento(
        lambda: conexao, "plano-1", "conta-a", "Nova", "Beta", True
    ) == "falha"
    assert conexao.desfez
    assert not conexao.commitou


class _CursorGravacao:
    def __init__(self, banco, falhar_close=False, falhar_execute=False):
        self.banco = banco
        self.sql = ""
        self.falhar_close = falhar_close
        self.falhar_execute = falhar_execute
        self.fechado = False

    def execute(self, sql, *args):
        if self.falhar_execute:
            raise RuntimeError("execute secreto")
        self.sql = sql
        self.resultado = self.banco.execute(sql, args)
        self.rowcount = self.resultado.rowcount

    def close(self):
        self.fechado = True
        if self.falhar_close:
            raise RuntimeError("close secreto")


class _ConexaoGravacao:
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
        self.cursor_interno = _CursorGravacao(banco, falhar_close_cursor, falhar_execute)
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


def test_falha_de_close_depois_do_commit_preserva_atualizado():
    for falha_cursor, falha_conexao in ((True, False), (False, True), (True, True)):
        banco = _banco()
        _inserir_planejamento(banco, "plano-1", "conta-a", "Receita", "Sala", "Aurora", None)
        banco.execute(
            "INSERT INTO dbo.receitas VALUES (?, ?, ?, ?, ?)",
            ("tx-1", "conta-a", "Sala", "Aurora", 400),
        )
        banco.execute(
            "INSERT INTO dbo.gastos VALUES (?, ?, ?, ?)",
            ("tx-2", "conta-a", "Mercado", 80),
        )
        banco.commit()
        conexao = _ConexaoGravacao(
            banco,
            falhar_close_cursor=falha_cursor,
            falhar_close_conexao=falha_conexao,
        )
        assert concluir_atualizacao_texto_planejamento(
            lambda: conexao, "plano-1", "conta-a", "Sala nova", "Beta", True
        ) == "atualizado"
        assert conexao.commitou
        assert not conexao.desfez
        assert conexao.cursor_interno.fechado
        assert conexao.fechada
        assert banco.execute(
            "SELECT descricao, cliente, valor FROM dbo.planejamentos"
        ).fetchone() == ("Sala nova", "Beta", 400)
        assert banco.execute(
            "SELECT descricao, cliente, valor FROM dbo.receitas"
        ).fetchone() == ("Sala", "Aurora", 400)
        assert banco.execute("SELECT descricao, valor FROM dbo.gastos").fetchone() == (
            "Mercado",
            80,
        )


def test_nenhuma_linha_com_falha_de_close_permanece_ausente():
    banco = _banco()
    _inserir_planejamento(banco, "plano-1", "conta-b", "Receita", "Sala", "Aurora", None)
    banco.commit()
    conexao = _ConexaoGravacao(banco, falhar_close_cursor=True, falhar_close_conexao=True)
    assert concluir_atualizacao_texto_planejamento(
        lambda: conexao, "plano-1", "conta-a", "Nova", "Beta", True
    ) == "ausente"
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert banco.execute("SELECT descricao FROM dbo.planejamentos").fetchone()[0] == "Sala"


def test_duas_linhas_com_falha_de_close_desfazem_a_atualizacao():
    banco = _banco()
    _inserir_planejamento(banco, "plano-1", "conta-a", "Receita", "Primeira", "Aurora", None)
    _inserir_planejamento(banco, "plano-1", "conta-a", "Receita", "Segunda", "Outra", None, 80)
    banco.commit()
    conexao = _ConexaoGravacao(banco, falhar_close_cursor=True, falhar_close_conexao=True)
    assert concluir_atualizacao_texto_planejamento(
        lambda: conexao, "plano-1", "conta-a", "Nova", "Beta", True
    ) == "ausente"
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert banco.execute(
        "SELECT descricao, cliente, valor FROM dbo.planejamentos ORDER BY descricao"
    ).fetchall() == [("Primeira", "Aurora", 400), ("Segunda", "Outra", 80)]


def test_falha_de_execute_seguida_de_close_continua_falha_no_texto():
    banco = _banco()
    _inserir_planejamento(banco, "plano-1", "conta-a", "Receita", "Sala", "Aurora", None)
    banco.commit()
    conexao = _ConexaoGravacao(
        banco,
        falhar_execute=True,
        falhar_close_cursor=True,
        falhar_close_conexao=True,
    )
    assert concluir_atualizacao_texto_planejamento(
        lambda: conexao, "plano-1", "conta-a", "Nova", "Beta", True
    ) == "falha"
    assert not conexao.commitou
    assert conexao.desfez
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert banco.execute("SELECT descricao FROM dbo.planejamentos").fetchone()[0] == "Sala"


def test_falha_de_commit_seguida_de_close_continua_falha_no_texto():
    banco = _banco()
    _inserir_planejamento(banco, "plano-1", "conta-a", "Receita", "Sala", "Aurora", None)
    banco.commit()
    conexao = _ConexaoGravacao(
        banco,
        falhar_commit=True,
        falhar_close_cursor=True,
        falhar_close_conexao=True,
    )
    assert concluir_atualizacao_texto_planejamento(
        lambda: conexao, "plano-1", "conta-a", "Nova", "Beta", True
    ) == "falha"
    assert not conexao.commitou
    assert conexao.desfez
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert banco.execute("SELECT descricao, cliente FROM dbo.planejamentos").fetchone() == (
        "Sala",
        "Aurora",
    )


def test_falha_no_rollback_do_texto_devolve_falha():
    banco = _banco()
    _inserir_planejamento(banco, "plano-1", "conta-b", "Receita", "Sala", "Aurora", None)
    banco.commit()
    conexao = _ConexaoGravacao(banco, falhar_rollback=True)
    assert concluir_atualizacao_texto_planejamento(
        lambda: conexao, "plano-1", "conta-a", "Nova", "Beta", True
    ) == "falha"
    assert not conexao.commitou
    assert banco.execute("SELECT descricao FROM dbo.planejamentos").fetchone()[0] == "Sala"


def test_identificador_invalido_nao_executa_a_atualizacao():
    class Cursor:
        def execute(self, sql, *args):
            raise AssertionError(sql)

        def close(self):
            self.fechado = True

    class Conexao:
        def __init__(self):
            self.cursor_interno = Cursor()
            self.commitou = False
            self.fechada = False

        def cursor(self):
            return self.cursor_interno

        def commit(self):
            self.commitou = True

        def rollback(self):
            return None

        def close(self):
            self.fechada = True

    conexao = Conexao()
    assert concluir_atualizacao_texto_planejamento(
        lambda: conexao, "plano-1", "  ", "Nova", "Beta", True
    ) == "ausente"
    assert not conexao.commitou
    assert conexao.fechada


def test_encerrar_sessao_apaga_as_chaves_do_texto():
    estado = {
        "usuario_logado": True,
        "usuario_atual": {"id_usuario": "conta-a"},
        "planejamento_mensal_descricao": "Sala",
        "planejamento_mensal_cliente": "Aurora",
        "planejamento_mensal_campos_id": _PRIMEIRO,
        "planejamento_texto_sucesso": "Descrição atualizada.",
        "planejamento_texto_aviso": "Não foi possível salvar esses dados.",
    }
    encerrar_sessao_local(estado)
    assert "planejamento_mensal_descricao" not in estado
    assert "planejamento_mensal_cliente" not in estado
    assert "planejamento_mensal_campos_id" not in estado
    assert "planejamento_texto_sucesso" not in estado
    assert "planejamento_texto_aviso" not in estado


def _script_correcao(registros):
    linhas = ",\n".join(repr(registro) for registro in registros)
    return f"""
import streamlit as st
from trixter.planejamento_mensal import (
    exibir_correcao_texto_planejamento,
    selecionar_planejamento,
)

class Cursor:
    def __init__(self, dono):
        self.dono = dono
        self.rowcount = 0
    def execute(self, sql, *args):
        self.rowcount = 1
        self.dono.chamadas.append((" ".join(sql.split()), args))
    def close(self):
        pass

class Conexao:
    def __init__(self):
        self.chamadas = []
        self.commitou = 0
        self.desfez = 0
        self.cursor_interno = Cursor(self)
    def cursor(self):
        return self.cursor_interno
    def commit(self):
        self.commitou += 1
    def rollback(self):
        self.desfez += 1
    def close(self):
        pass

if "conexao_teste" not in st.session_state:
    st.session_state.conexao_teste = Conexao()
    st.session_state.usuario_atual = {{"id_usuario": "conta-a"}}
if st.session_state.pop("invalidar_selecao", False):
    st.session_state.planejamento_mensal_selecionado = "id-ausente"
registros = [
{linhas}
]
escolhido, registro = selecionar_planejamento(registros)
st.session_state.escolhido = str(escolhido)
exibir_correcao_texto_planejamento(lambda: st.session_state.conexao_teste, registro)
"""


def _app(registros):
    return AppTest.from_string(_script_correcao(registros)).run()


def test_troca_de_uuid_carrega_os_campos_e_nao_grava_cruzado():
    app = _app([
        (_PRIMEIRO, "Receita", "Aluguel", "Sala A", 400, "20/10/2026", "Aurora", None),
        (_SEGUNDO, "Receita", "Aluguel", "Sala B", 400, "20/10/2026", "Beta", None),
    ])
    assert not app.exception
    assert app.text_input[0].value == "Sala A"
    assert app.text_input[1].value == "Aurora"
    assert any("próxima baixa" in item.value for item in app.info)
    app.selectbox[0].set_value(_SEGUNDO).run()
    assert not app.exception
    assert app.session_state.escolhido == _SEGUNDO
    assert app.text_input[0].value == "Sala B"
    assert app.text_input[1].value == "Beta"
    assert app.session_state.conexao_teste.chamadas == []
    app.text_input[0].set_value("Sala corrigida").run()
    app.button(key="btn_salvar_texto_planejamento").click().run()
    assert not app.exception
    conexao = app.session_state.conexao_teste
    assert conexao.commitou == 1
    sql, args = conexao.chamadas[0]
    assert "UPDATE dbo.planejamentos" in sql
    assert "receitas" not in sql and "gastos" not in sql
    assert args[0] == "Sala corrigida"
    assert args[1] == "Beta"
    assert args[2] == _SEGUNDO
    assert args[3] == "conta-a"


def test_rotulos_iguais_salvam_o_primeiro_uuid_apos_rerun():
    registro = (_PRIMEIRO, "Receita", "Aluguel", "Sala", 400, "20/10/2026", "Aurora", None)
    outro = (_SEGUNDO, "Receita", "Aluguel", "Sala", 400, "20/10/2026", "Aurora", None)
    app = _app([registro, outro])
    assert not app.exception
    assert app.session_state.escolhido == _PRIMEIRO
    app.run()
    assert not app.exception
    assert app.session_state.escolhido == _PRIMEIRO
    app.button(key="btn_salvar_texto_planejamento").click().run()
    assert not app.exception
    _sql, args = app.session_state.conexao_teste.chamadas[0]
    assert args[2] == _PRIMEIRO
    assert app.session_state.conexao_teste.commitou == 1


def test_despesa_na_interface_nao_oferece_cliente():
    app = _app([
        ("dddddddd-dddd-dddd-dddd-ddddddddddd4", "Despesa", "Aluguel", "Sala", 80, "20/10/2026", "NaoMexer", "Pago"),
    ])
    assert not app.exception
    assert len(app.text_input) == 1
    assert any("já realizado" in item.value for item in app.warning)
    app.text_input[0].set_value("Sala paga").run()
    app.button(key="btn_salvar_texto_planejamento").click().run()
    assert not app.exception
    sql, args = app.session_state.conexao_teste.chamadas[0]
    assert "cliente" not in sql.lower()
    assert args == ("Sala paga", "dddddddd-dddd-dddd-dddd-ddddddddddd4", "conta-a")


def test_selecao_invalida_nao_salva_texto():
    app = _app([
        (_PRIMEIRO, "Receita", "Aluguel", "Sala", 400, "20/10/2026", "Aurora", None),
    ])
    app.session_state.invalidar_selecao = True
    app.button(key="btn_salvar_texto_planejamento").click().run()
    assert not app.exception
    assert app.session_state.conexao_teste.chamadas == []
    assert app.session_state.conexao_teste.commitou == 0
