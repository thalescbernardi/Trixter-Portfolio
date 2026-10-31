"""Exclusão individual de planejamento, com dados fictícios."""
from datetime import date
import sqlite3

from streamlit.testing.v1 import AppTest

from trixter.planejamento import (
    concluir_exclusao_planejamento,
    consultar_planejamento_anual,
    excluir_planejamento,
)
from trixter.sessao import encerrar_sessao_local


def _banco():
    banco = sqlite3.connect(":memory:")
    banco.execute("ATTACH DATABASE ':memory:' AS dbo")
    banco.create_function("MONTH", 1, lambda valor: int(str(valor)[5:7]))
    banco.execute(
        """
        CREATE TABLE dbo.planejamentos (
            id_planejamento TEXT,
            id_usuario TEXT,
            data TEXT,
            valor NUMERIC,
            tipo TEXT,
            descricao TEXT,
            cliente TEXT
        )
        """
    )
    banco.execute(
        "CREATE TABLE dbo.receitas (id_usuario TEXT, data TEXT, valor NUMERIC, tipo TEXT)"
    )
    banco.execute(
        "CREATE TABLE dbo.gastos (id_usuario TEXT, data TEXT, valor NUMERIC, tipo TEXT)"
    )
    return banco


class _Cursor:
    def __init__(self, banco):
        self.banco = banco

    def execute(self, sql, *args):
        parametros = tuple(
            item.isoformat() if isinstance(item, date) else item for item in args
        )
        self.resultado = self.banco.execute(sql, parametros)
        self.rowcount = self.resultado.rowcount

    def fetchall(self):
        return self.resultado.fetchall()

    def fetchone(self):
        return self.resultado.fetchone()


def _cursor(banco):
    return _Cursor(banco)


def test_exclui_somente_o_planejamento_da_conta():
    banco = _banco()
    cursor = _cursor(banco)
    cursor.execute(
        "INSERT INTO dbo.planejamentos VALUES (?, ?, ?, ?, ?, ?, ?)",
        "plano-1", "conta-a", "2026-09-01", 500, "Receita", "Contrato", "Aurora",
    )
    cursor.execute(
        "INSERT INTO dbo.planejamentos VALUES (?, ?, ?, ?, ?, ?, ?)",
        "plano-2", "conta-a", "2026-09-01", 300, "Receita", "Outro", None,
    )
    assert excluir_planejamento(cursor, "plano-1", "conta-a")
    restantes = banco.execute(
        "SELECT id_planejamento FROM dbo.planejamentos ORDER BY id_planejamento"
    ).fetchall()
    assert restantes == [("plano-2",)]


def test_nao_exclui_planejamento_de_outra_conta():
    banco = _banco()
    cursor = _cursor(banco)
    cursor.execute(
        "INSERT INTO dbo.planejamentos VALUES (?, ?, ?, ?, ?, ?, ?)",
        "plano-1", "conta-b", "2026-09-01", 900, "Despesa", "Sala", None,
    )
    assert not excluir_planejamento(cursor, "plano-1", "conta-a")
    assert banco.execute("SELECT COUNT(*) FROM dbo.planejamentos").fetchone()[0] == 1


def test_identificador_inexistente_nao_tem_sucesso():
    banco = _banco()
    cursor = _cursor(banco)
    assert not excluir_planejamento(cursor, "plano-ausente", "conta-a")
    assert not excluir_planejamento(cursor, "", "conta-a")
    assert not excluir_planejamento(cursor, "plano-1", "")


def test_falha_no_banco_desfaz_e_nao_confirma():
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
    assert concluir_exclusao_planejamento(lambda: conexao, "plano-1", "conta-a") == "falha"
    assert conexao.desfez
    assert not conexao.commitou


def test_sucesso_so_quando_uma_linha_sai():
    class Cursor:
        def __init__(self, rowcount):
            self.rowcount = rowcount
            self.sql = ""
            self.args = ()

        def execute(self, sql, *args):
            self.sql = sql
            self.args = args

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

    cursor = Cursor(1)
    conexao = Conexao(cursor)
    assert concluir_exclusao_planejamento(lambda: conexao, "plano-1", "conta-a") == "excluido"
    assert "id_planejamento = ?" in cursor.sql
    assert "id_usuario = ?" in cursor.sql
    assert "receitas" not in cursor.sql
    assert "gastos" not in cursor.sql
    assert cursor.args == ("plano-1", "conta-a")
    assert conexao.commitou
    assert not conexao.desfez

    vazio = Conexao(Cursor(0))
    assert concluir_exclusao_planejamento(lambda: vazio, "plano-1", "conta-a") == "ausente"
    assert vazio.desfez
    assert not vazio.commitou


class _CursorGravacao:
    def __init__(self, banco, falhar_close=False, falhar_execute=False):
        self.banco = banco
        self.falhar_close = falhar_close
        self.falhar_execute = falhar_execute
        self.fechado = False

    def execute(self, sql, *args):
        if self.falhar_execute:
            raise RuntimeError("execute secreto")
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


def _inserir_plano(banco, identificador, usuario, descricao="Contrato"):
    banco.execute(
        "INSERT INTO dbo.planejamentos VALUES (?, ?, ?, ?, ?, ?, ?)",
        (identificador, usuario, "2026-09-01", 500, "Receita", descricao, "Aurora"),
    )


def test_falha_de_close_depois_do_commit_preserva_excluido():
    for falha_cursor, falha_conexao in ((True, False), (False, True), (True, True)):
        banco = _banco()
        _inserir_plano(banco, "plano-1", "conta-a")
        banco.execute(
            "INSERT INTO dbo.receitas VALUES (?, ?, ?, ?)",
            ("conta-a", "2026-09-01", 500, None),
        )
        banco.execute(
            "INSERT INTO dbo.gastos VALUES (?, ?, ?, ?)",
            ("conta-a", "2026-09-01", 80, None),
        )
        banco.commit()
        conexao = _ConexaoGravacao(
            banco,
            falhar_close_cursor=falha_cursor,
            falhar_close_conexao=falha_conexao,
        )
        assert concluir_exclusao_planejamento(
            lambda: conexao, "plano-1", "conta-a"
        ) == "excluido"
        assert conexao.commitou
        assert not conexao.desfez
        assert conexao.cursor_interno.fechado
        assert conexao.fechada
        assert banco.execute("SELECT COUNT(*) FROM dbo.planejamentos").fetchone()[0] == 0
        assert banco.execute("SELECT COUNT(*) FROM dbo.receitas").fetchone()[0] == 1
        assert banco.execute("SELECT COUNT(*) FROM dbo.gastos").fetchone()[0] == 1


def test_nenhuma_linha_com_falha_de_close_permanece_ausente():
    banco = _banco()
    _inserir_plano(banco, "plano-1", "conta-b")
    banco.commit()
    conexao = _ConexaoGravacao(banco, falhar_close_cursor=True, falhar_close_conexao=True)
    assert concluir_exclusao_planejamento(lambda: conexao, "plano-1", "conta-a") == "ausente"
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert banco.execute("SELECT id_usuario FROM dbo.planejamentos").fetchone()[0] == "conta-b"


def test_duas_linhas_com_falha_de_close_desfazem_a_exclusao():
    banco = _banco()
    _inserir_plano(banco, "plano-1", "conta-a", "Primeira")
    _inserir_plano(banco, "plano-1", "conta-a", "Segunda")
    banco.commit()
    conexao = _ConexaoGravacao(banco, falhar_close_cursor=True, falhar_close_conexao=True)
    assert concluir_exclusao_planejamento(lambda: conexao, "plano-1", "conta-a") == "ausente"
    assert conexao.desfez
    assert not conexao.commitou
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert banco.execute(
        "SELECT descricao FROM dbo.planejamentos ORDER BY descricao"
    ).fetchall() == [("Primeira",), ("Segunda",)]


def test_falha_de_execute_seguida_de_close_continua_falha_na_exclusao():
    banco = _banco()
    _inserir_plano(banco, "plano-1", "conta-a")
    banco.commit()
    conexao = _ConexaoGravacao(
        banco,
        falhar_execute=True,
        falhar_close_cursor=True,
        falhar_close_conexao=True,
    )
    assert concluir_exclusao_planejamento(lambda: conexao, "plano-1", "conta-a") == "falha"
    assert not conexao.commitou
    assert conexao.desfez
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert banco.execute("SELECT COUNT(*) FROM dbo.planejamentos").fetchone()[0] == 1


def test_falha_de_commit_seguida_de_close_continua_falha_na_exclusao():
    banco = _banco()
    _inserir_plano(banco, "plano-1", "conta-a")
    banco.commit()
    conexao = _ConexaoGravacao(
        banco,
        falhar_commit=True,
        falhar_close_cursor=True,
        falhar_close_conexao=True,
    )
    assert concluir_exclusao_planejamento(lambda: conexao, "plano-1", "conta-a") == "falha"
    assert not conexao.commitou
    assert conexao.desfez
    assert conexao.cursor_interno.fechado
    assert conexao.fechada
    assert banco.execute("SELECT COUNT(*) FROM dbo.planejamentos").fetchone()[0] == 1


def test_falha_no_rollback_da_exclusao_devolve_falha():
    banco = _banco()
    _inserir_plano(banco, "plano-1", "conta-b")
    banco.commit()
    conexao = _ConexaoGravacao(banco, falhar_rollback=True)
    assert concluir_exclusao_planejamento(lambda: conexao, "plano-1", "conta-a") == "falha"
    assert not conexao.commitou
    assert banco.execute("SELECT id_usuario FROM dbo.planejamentos").fetchone()[0] == "conta-b"


def test_identificador_invalido_nao_executa_a_exclusao():
    class Cursor:
        def execute(self, sql, *args):
            raise AssertionError(sql)

        def close(self):
            self.fechado = True

    class Conexao:
        def __init__(self):
            self.cursor_interno = Cursor()
            self.commitou = False
            self.desfez = False
            self.fechada = False

        def cursor(self):
            return self.cursor_interno

        def commit(self):
            self.commitou = True

        def rollback(self):
            self.desfez = True

        def close(self):
            self.fechada = True

    conexao = Conexao()
    assert concluir_exclusao_planejamento(lambda: conexao, "  ", "conta-a") == "ausente"
    assert not conexao.commitou
    assert conexao.desfez
    assert conexao.fechada


def test_preserva_lancamento_ja_realizado():
    banco = _banco()
    cursor = _cursor(banco)
    cursor.execute(
        "INSERT INTO dbo.planejamentos VALUES (?, ?, ?, ?, ?, ?, ?)",
        "plano-1", "conta-a", "2026-09-01", 500, "Receita", "Contrato", "Aurora",
    )
    cursor.execute(
        "INSERT INTO dbo.receitas VALUES (?, ?, ?, ?)",
        "conta-a", "2026-09-01", 500, None,
    )
    cursor.execute(
        "INSERT INTO dbo.gastos VALUES (?, ?, ?, ?)",
        "conta-a", "2026-09-01", 80, None,
    )
    assert excluir_planejamento(cursor, "plano-1", "conta-a")
    assert banco.execute("SELECT COUNT(*) FROM dbo.receitas").fetchone()[0] == 1
    assert banco.execute("SELECT COUNT(*) FROM dbo.gastos").fetchone()[0] == 1
    assert banco.execute("SELECT COUNT(*) FROM dbo.planejamentos").fetchone()[0] == 0


def test_totais_anuais_deixam_de_somar_o_planejamento_excluido():
    banco = _banco()
    cursor = _cursor(banco)
    cursor.execute(
        "INSERT INTO dbo.planejamentos VALUES (?, ?, ?, ?, ?, ?, ?)",
        "plano-1", "conta-a", "2026-09-01", 500, "Receita", "Contrato", "Aurora",
    )
    cursor.execute(
        "INSERT INTO dbo.planejamentos VALUES (?, ?, ?, ?, ?, ?, ?)",
        "plano-2", "conta-a", "2026-09-01", 300, "Receita", "Outro", None,
    )
    cursor.execute(
        "INSERT INTO dbo.planejamentos VALUES (?, ?, ?, ?, ?, ?, ?)",
        "plano-3", "conta-b", "2026-09-01", 9999, "Receita", "Alheio", None,
    )
    assert excluir_planejamento(cursor, "plano-1", "conta-a")
    dados = consultar_planejamento_anual(cursor, "conta-a", 2026, [], lambda *args: 0)
    assert dados.iloc[8]["receitas_planejadas"] == 300


def test_encerrar_sessao_apaga_a_confirmacao_pendente():
    estado = {
        "usuario_logado": True,
        "usuario_atual": {"id_usuario": "conta-a"},
        "planejamento_exclusao_pendente": {
            "id_usuario": "conta-a",
            "id_planejamento": "plano-1",
            "rotulo": "Aluguel - Sala - Aurora",
        },
        "planejamento_excluido_sucesso": True,
        "planejamento_exclusao_aviso": "Não foi possível excluir esse planejamento.",
        "planejamento_mensal_selecionado": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1",
    }
    encerrar_sessao_local(estado)
    assert "planejamento_exclusao_pendente" not in estado
    assert "planejamento_excluido_sucesso" not in estado
    assert "planejamento_exclusao_aviso" not in estado
    assert "planejamento_mensal_selecionado" not in estado


def _app_confirmacao():
    return AppTest.from_string(
        """
import streamlit as st
from trixter.planejamento_mensal import exibir_confirmacao_exclusao

class Cursor:
    def __init__(self):
        self.rowcount = 1
        self.sql = ""
        self.args = ()
    def execute(self, sql, *args):
        self.sql = sql
        self.args = args
    def close(self):
        pass

class Conexao:
    def __init__(self):
        self.cursor_interno = Cursor()
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

if "conexao_teste" not in st.session_state:
    st.session_state.conexao_teste = Conexao()
    st.session_state.usuario_atual = {"id_usuario": "conta-a"}
    st.session_state.planejamento_exclusao_pendente = {
        "id_usuario": "conta-a",
        "id_planejamento": "plano-1",
        "rotulo": "Aluguel - Sala - R$ 400,00 - 20/10/2026 - Aurora",
    }
exibir_confirmacao_exclusao(lambda: st.session_state.conexao_teste)
"""
    ).run()


def test_cancelar_a_confirmacao_nao_exclui():
    app = _app_confirmacao()
    assert not app.exception
    assert any("Aurora" in item.value for item in app.warning)
    app.button(key="btn_cancelar_exclusao_planejamento").click().run()
    assert not app.exception
    assert "planejamento_exclusao_pendente" not in app.session_state
    assert not app.session_state.conexao_teste.commitou


def test_trocar_a_selecao_invalida_a_confirmacao_anterior():
    from trixter.planejamento_mensal import confirmacao_corresponde

    pendente = {
        "id_usuario": "conta-a",
        "id_planejamento": "11111111-1111-1111-1111-111111111111",
        "rotulo": "Aluguel - Sala - R$ 400,00 - 20/10/2026 - Aurora",
    }
    assert confirmacao_corresponde(
        pendente, "conta-a", "11111111-1111-1111-1111-111111111111"
    )
    assert not confirmacao_corresponde(
        pendente, "conta-a", "22222222-2222-2222-2222-222222222222"
    )
    assert not confirmacao_corresponde(
        pendente, "conta-b", "11111111-1111-1111-1111-111111111111"
    )
    from trixter.planejamento_mensal import (
        _rotulo_planejamento,
        opcoes_planejamento,
        rotulos_para_exibicao,
    )

    primeira = ("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1", "conta-a", "Aluguel", "Sala", 400, "20/10/2026", "Aurora")
    segunda = ("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2", "conta-a", "Aluguel", "Sala", 400, "20/10/2026", "Aurora")
    opcoes = opcoes_planejamento([primeira, segunda])
    assert list(opcoes) == [
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1",
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2",
    ]
    assert _rotulo_planejamento(opcoes[primeira[0]]) == _rotulo_planejamento(opcoes[segunda[0]])
    rotulos = rotulos_para_exibicao([primeira, segunda])
    assert rotulos[primeira[0]] != rotulos[segunda[0]]
    assert primeira[0] in rotulos[primeira[0]]
    assert segunda[0] in rotulos[segunda[0]]
    assert rotulos[primeira[0]].startswith(_rotulo_planejamento(primeira))
    assert "Aluguel" in rotulos[primeira[0]]
    assert "Sala" in rotulos[primeira[0]]
    assert "Aurora" in rotulos[primeira[0]]


_PRIMEIRO = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1"
_SEGUNDO = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2"
_TERCEIRO = "cccccccc-cccc-cccc-cccc-ccccccccccc3"

_SCRIPT_SELECAO = """
import streamlit as st
from trixter.planejamento_mensal import selecionar_planejamento

registros = [
    ("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1", "conta-a", "Aluguel", "Sala", 400, "20/10/2026", "Aurora"),
    ("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2", "conta-a", "Aluguel", "Sala", 400, "20/10/2026", "Aurora"),
]
escolhido, registro = selecionar_planejamento(registros)
st.session_state.escolhido = str(escolhido)
st.session_state.registro_id = str(registro[0])
if st.button("Alterar planejamento", key="btn_alterar_planejamento"):
    st.session_state.alterado = str(escolhido)
if st.button("Excluir planejamento", key="btn_excluir_planejamento"):
    st.session_state.excluido = str(escolhido)
"""


def _app_selecao():
    return AppTest.from_string(_SCRIPT_SELECAO).run()


def test_rerun_mantem_o_primeiro_uuid_com_rotulos_iguais():
    app = _app_selecao()
    assert not app.exception
    assert app.session_state.escolhido == _PRIMEIRO
    assert app.session_state.registro_id == _PRIMEIRO
    opcoes = app.selectbox[0].options
    assert len(opcoes) == 2
    assert len(set(opcoes)) == 2
    assert _PRIMEIRO in opcoes[0]
    assert _SEGUNDO in opcoes[1]
    app.run()
    assert not app.exception
    assert app.session_state.escolhido == _PRIMEIRO
    assert app.session_state.registro_id == _PRIMEIRO
    app.button(key="btn_excluir_planejamento").click().run()
    assert not app.exception
    assert app.session_state.excluido == _PRIMEIRO
    app.button(key="btn_alterar_planejamento").click().run()
    assert not app.exception
    assert app.session_state.alterado == _PRIMEIRO
    assert app.session_state.escolhido == _PRIMEIRO


def test_rerun_mantem_o_segundo_uuid_com_rotulos_iguais():
    app = _app_selecao()
    app.selectbox[0].set_value(_SEGUNDO).run()
    assert not app.exception
    assert app.session_state.escolhido == _SEGUNDO
    app.run()
    assert not app.exception
    assert app.session_state.escolhido == _SEGUNDO
    assert app.session_state.registro_id == _SEGUNDO
    app.button(key="btn_excluir_planejamento").click().run()
    assert not app.exception
    assert app.session_state.excluido == _SEGUNDO
    app.button(key="btn_alterar_planejamento").click().run()
    assert not app.exception
    assert app.session_state.alterado == _SEGUNDO
    assert app.session_state.escolhido == _SEGUNDO


def test_troca_de_conta_nao_reutiliza_a_selecao():
    app = AppTest.from_string(
        """
import streamlit as st
from trixter.planejamento_mensal import selecionar_planejamento

if st.session_state.get("conta") == "b":
    registros = [
        ("cccccccc-cccc-cccc-cccc-ccccccccccc3", "conta-b", "Honorário", "Visita", 80, "02/02/2026", "Beta"),
    ]
else:
    registros = [
        ("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1", "conta-a", "Aluguel", "Sala", 400, "20/10/2026", "Aurora"),
        ("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2", "conta-a", "Aluguel", "Sala", 400, "20/10/2026", "Aurora"),
    ]
escolhido, registro = selecionar_planejamento(registros)
st.session_state.escolhido = str(escolhido)
st.session_state.registro_id = str(registro[0])
if st.button("trocar", key="btn_trocar_conta"):
    st.session_state.conta = "b"
    st.rerun()
"""
    ).run()
    assert not app.exception
    assert app.session_state.escolhido == _PRIMEIRO
    app.button(key="btn_trocar_conta").click().run()
    assert not app.exception
    assert app.session_state.escolhido == _TERCEIRO
    assert app.session_state.registro_id == _TERCEIRO


_SCRIPT_ESCRITA = """
import streamlit as st
from trixter.planejamento_mensal import (
    confirmacao_corresponde,
    exibir_confirmacao_exclusao,
    selecionar_planejamento,
)

class Cursor:
    def __init__(self, dono):
        self.dono = dono
        self.rowcount = 0
        self.sql = ""
        self.args = ()
    def execute(self, sql, *args):
        self.sql = sql
        self.args = args
        self.rowcount = 1
        self.dono.chamadas.append((" ".join(sql.split()), args))
    def close(self):
        pass

class Conexao:
    def __init__(self):
        self.chamadas = []
        self.commitou = 0
        self.cursor_interno = Cursor(self)
    def cursor(self):
        return self.cursor_interno
    def commit(self):
        self.commitou += 1
    def rollback(self):
        pass
    def close(self):
        pass

if "conexao_teste" not in st.session_state:
    st.session_state.conexao_teste = Conexao()
    st.session_state.usuario_atual = {"id_usuario": "conta-a"}

if st.session_state.pop("invalidar_selecao", False):
    st.session_state.planejamento_mensal_selecionado = "id-ausente"
if st.session_state.pop("usar_conta_b", False):
    st.session_state.conta = "b"

if st.session_state.get("conta") == "b":
    registros = [
        ("cccccccc-cccc-cccc-cccc-ccccccccccc3", "conta-b", "Honorário", "Visita", 80, "02/02/2026", "Beta"),
    ]
else:
    registros = [
        ("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1", "conta-a", "Aluguel", "Sala", 400, "20/10/2026", "Aurora"),
        ("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2", "conta-a", "Aluguel", "Sala", 400, "20/10/2026", "Aurora"),
    ]

escolhido, registro = selecionar_planejamento(registros)
st.session_state.escolhido = str(escolhido)
st.session_state.registro_id = str(registro[0])
usuario = str(st.session_state.usuario_atual["id_usuario"])
conexao = st.session_state.conexao_teste
if st.button("Alterar planejamento", key="btn_alterar_planejamento"):
    conexao.cursor().execute(
        "UPDATE dbo.planejamentos set valor = ? WHERE id_planejamento = ? AND id_usuario = ?",
        10,
        escolhido,
        usuario,
    )
    conexao.commit()
    st.session_state.alterado = str(escolhido)
pendente = st.session_state.get("planejamento_exclusao_pendente")
if not confirmacao_corresponde(pendente, usuario, escolhido):
    st.session_state.pop("planejamento_exclusao_pendente", None)
    if st.button("Excluir planejamento", key="btn_excluir_planejamento"):
        st.session_state.planejamento_exclusao_pendente = {
            "id_usuario": usuario,
            "id_planejamento": str(escolhido),
            "rotulo": "pendente",
        }
        st.rerun()
else:
    exibir_confirmacao_exclusao(lambda: st.session_state.conexao_teste)
"""


def _app_escrita():
    return AppTest.from_string(_SCRIPT_ESCRITA).run()


def _sqls(app):
    return [sql for sql, _args in app.session_state.conexao_teste.chamadas]


def test_selecao_invalida_com_alterar_nao_grava():
    app = _app_escrita()
    app.session_state.invalidar_selecao = True
    app.button(key="btn_alterar_planejamento").click().run()
    assert not app.exception
    assert app.session_state.conexao_teste.commitou == 0
    assert _sqls(app) == []
    assert "planejamento_exclusao_pendente" not in app.session_state
    assert app.session_state.escolhido in (_PRIMEIRO, _SEGUNDO)
    assert len(app.selectbox) >= 1


def test_selecao_invalida_com_excluir_nao_cria_pendencia_nem_apaga():
    app = _app_escrita()
    app.session_state.invalidar_selecao = True
    app.button(key="btn_excluir_planejamento").click().run()
    assert not app.exception
    assert app.session_state.conexao_teste.commitou == 0
    assert _sqls(app) == []
    assert "planejamento_exclusao_pendente" not in app.session_state
    assert app.session_state.escolhido in (_PRIMEIRO, _SEGUNDO)


def test_selecao_invalida_descarta_confirmacao_anterior():
    app = _app_escrita()
    app.button(key="btn_excluir_planejamento").click().run()
    assert not app.exception
    assert app.session_state.planejamento_exclusao_pendente["id_planejamento"] == _PRIMEIRO
    assert _sqls(app) == []
    app.session_state.invalidar_selecao = True
    app.button(key="btn_confirmar_exclusao_planejamento").click().run()
    assert not app.exception
    assert app.session_state.conexao_teste.commitou == 0
    assert _sqls(app) == []
    assert "planejamento_exclusao_pendente" not in app.session_state
    assert app.session_state.escolhido in (_PRIMEIRO, _SEGUNDO)


def test_troca_de_conta_com_id_anterior_nao_grava():
    app = _app_escrita()
    app.session_state.usar_conta_b = True
    app.button(key="btn_alterar_planejamento").click().run()
    assert not app.exception
    assert app.session_state.conexao_teste.commitou == 0
    assert _sqls(app) == []
    assert app.session_state.escolhido == _TERCEIRO
    assert app.session_state.registro_id == _TERCEIRO
    assert "planejamento_exclusao_pendente" not in app.session_state


def test_selecao_valida_depois_da_reconstrucao_altera_e_exclui():
    app = _app_escrita()
    app.session_state.invalidar_selecao = True
    app.button(key="btn_alterar_planejamento").click().run()
    assert not app.exception
    assert _sqls(app) == []
    app.selectbox[0].set_value(_SEGUNDO).run()
    assert not app.exception
    assert app.session_state.escolhido == _SEGUNDO
    app.run()
    assert app.session_state.escolhido == _SEGUNDO
    app.button(key="btn_alterar_planejamento").click().run()
    assert not app.exception
    assert app.session_state.alterado == _SEGUNDO
    assert app.session_state.conexao_teste.commitou == 1
    sql, args = app.session_state.conexao_teste.chamadas[0]
    assert "UPDATE" in sql
    assert args == (10, _SEGUNDO, "conta-a")
    app.button(key="btn_excluir_planejamento").click().run()
    assert not app.exception
    assert app.session_state.planejamento_exclusao_pendente["id_planejamento"] == _SEGUNDO
    assert len(app.session_state.conexao_teste.chamadas) == 1
    app.button(key="btn_confirmar_exclusao_planejamento").click().run()
    assert not app.exception
    assert app.session_state.conexao_teste.commitou == 2
    delete_sql, delete_args = app.session_state.conexao_teste.chamadas[1]
    assert "DELETE" in delete_sql
    assert delete_args == (_SEGUNDO, "conta-a")
    assert "id_usuario = ?" in delete_sql


def test_rotulo_unico_nao_recebe_o_identificador():
    from trixter.planejamento_mensal import rotulos_para_exibicao

    registro = (_PRIMEIRO, "conta-a", "Aluguel", "Sala", 400, "20/10/2026", "Aurora")
    rotulo = rotulos_para_exibicao([registro])[_PRIMEIRO]
    assert _PRIMEIRO not in rotulo
    assert "Aluguel" in rotulo
    assert "Aurora" in rotulo


def test_confirmar_a_exclusao_grava_o_sucesso():
    app = _app_confirmacao()
    app.button(key="btn_confirmar_exclusao_planejamento").click().run()
    assert not app.exception
    assert app.session_state.planejamento_excluido_sucesso is True
    assert "planejamento_exclusao_pendente" not in app.session_state
    conexao = app.session_state.conexao_teste
    assert conexao.commitou
    assert conexao.cursor_interno.args == ("plano-1", "conta-a")
    assert "id_usuario = ?" in conexao.cursor_interno.sql
