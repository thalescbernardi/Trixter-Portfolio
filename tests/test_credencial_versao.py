"""Revogação da sessão quando a senha muda, a conta some ou o banco falha."""
import ast
from pathlib import Path

import pyodbc
import pytest
from streamlit.testing.v1 import AppTest

from trixter.acesso import abrir_sessao
from trixter.credencial import (
    MENSAGEM_SESSAO_INDISPONIVEL,
    SessaoIndisponivel,
    adotar_versao,
    gravar_senha,
    preparar_operacao,
)
from trixter.senha import gerar_hash_senha
from trixter.sessao import encerrar_sessao_local


def _sessao(versao=1, **extras):
    estado = {
        "usuario_logado": True,
        "usuario_atual": {
            "id_usuario": "u1",
            "email": "a@example.com",
            "credencial_versao": versao,
        },
        "verificacao_recuperacao": {"codigo": "123456"},
        "autorizacao_cadastro": {"email": "a@example.com"},
        "novo_usuario_pendente": {"senha": "hash-pendente"},
        "seguranca_senha_atual": "digitada",
        "senha_email_seguranca": "digitada",
        "senha_exclusao": "digitada",
        "usuario_original": {"id_usuario": "u1", "email": "a@example.com"},
    }
    estado.update(extras)
    return estado


class _Banco:
    def __init__(self):
        self.usuarios = {
            "u1": {"email": "a@example.com", "senha": "hash-0", "credencial_versao": 1},
        }
        self.commits = 0
        self.rollbacks = 0
        self.comandos = []

    def conectar(self):
        return self

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class _Cursor:
    def __init__(self, banco):
        self.banco = banco
        self.linha = None
        self.sql = ""

    def execute(self, sql, *args):
        self.sql = " ".join(sql.split())
        self.banco.comandos.append(self.sql)
        if self.sql.startswith("SELECT credencial_versao"):
            usuario = self.banco.usuarios.get(args[0])
            self.linha = None if usuario is None else (usuario["credencial_versao"],)
            return
        if not self.sql.startswith("UPDATE"):
            raise AssertionError(self.sql)
        assert "credencial_versao = credencial_versao + 1" in self.sql
        assert self.sql.count("UPDATE") == 1
        if len(args) == 3:
            senha, identificador, email = args
            usuario = self.banco.usuarios.get(identificador)
            if usuario is None or usuario["email"] != email:
                self.linha = None
                return
        else:
            senha, identificador = args
            usuario = self.banco.usuarios.get(identificador)
            if usuario is None:
                self.linha = None
                return
        usuario["senha"] = senha
        usuario["credencial_versao"] += 1
        self.linha = (usuario["credencial_versao"],)

    def fetchone(self):
        return self.linha

    def close(self):
        pass


def _operar_se_autorizado(banco, estado, gravador):
    situacao = preparar_operacao(banco.conectar, estado)
    if situacao == "ok":
        gravador.append("gravou")
    return situacao


def test_abrir_sessao_guarda_a_versao_e_remove_o_hash():
    estado = {}
    abrir_sessao(
        {"id_usuario": "u1", "email": "a@example.com", "senha": "hash", "credencial_versao": "3"},
        "menu",
        estado,
    )
    assert estado["usuario_logado"] is True
    assert estado["usuario_atual"]["credencial_versao"] == 3
    assert "senha" not in estado["usuario_atual"]


def test_troca_de_senha_revoga_a_outra_sessao_e_preserva_a_atual():
    banco = _Banco()
    atual = _sessao()
    outra = _sessao()
    cursor = banco.cursor()
    nova = gravar_senha(cursor, "u1", "hash-1")
    banco.commit()
    adotar_versao(atual, nova)
    gravador = []
    assert _operar_se_autorizado(banco, atual, gravador) == "ok"
    assert gravador == ["gravou"]
    assert atual["usuario_atual"]["credencial_versao"] == 2
    gravador.clear()
    assert _operar_se_autorizado(banco, outra, gravador) == "revogada"
    assert gravador == []
    assert outra["usuario_logado"] is False
    assert outra["usuario_atual"] is None
    assert "verificacao_recuperacao" not in outra
    assert "autorizacao_cadastro" not in outra
    assert "novo_usuario_pendente" not in outra
    assert "seguranca_senha_atual" not in outra
    assert "usuario_original" not in outra


def test_recuperacao_incrementa_e_revoga_sessao_autenticada():
    banco = _Banco()
    autenticada = _sessao()
    cursor = banco.cursor()
    assert gravar_senha(cursor, "u1", "hash-2", "outra@example.com") is None
    assert banco.usuarios["u1"]["credencial_versao"] == 1
    assert banco.usuarios["u1"]["senha"] == "hash-0"
    nova = gravar_senha(cursor, "u1", "hash-2", "a@example.com")
    assert nova == 2
    assert banco.usuarios["u1"]["senha"] == "hash-2"
    assert preparar_operacao(banco.conectar, autenticada) == "revogada"
    assert autenticada["usuario_logado"] is False


def test_conta_excluida_revoga_a_sessao_restante():
    banco = _Banco()
    restante = _sessao()
    del banco.usuarios["u1"]
    gravador = []
    assert _operar_se_autorizado(banco, restante, gravador) == "revogada"
    assert gravador == []
    assert "senha_exclusao" not in restante
    assert restante["usuario_atual"] is None


def test_sessao_sem_versao_nao_consulta_o_banco():
    def conectar():
        raise AssertionError("consulta indevida")

    estado = _sessao()
    del estado["usuario_atual"]["credencial_versao"]
    assert preparar_operacao(conectar, estado) == "revogada"
    assert estado["usuario_logado"] is False


def test_falha_de_banco_nao_autoriza_e_nao_apaga_a_sessao():
    estado = _sessao()

    def conectar():
        raise pyodbc.OperationalError("08S01", "falha de rede")

    gravador = []
    with pytest.raises(SessaoIndisponivel):
        situacao = preparar_operacao(conectar, estado)
        if situacao == "ok":
            gravador.append("gravou")
    assert gravador == []
    assert estado["usuario_logado"] is True
    assert estado["usuario_atual"]["credencial_versao"] == 1
    assert estado["seguranca_senha_atual"] == "digitada"

    class Conexao:
        def __init__(self):
            self.rolled = False

        def cursor(self):
            return self

        def execute(self, sql, *args):
            raise pyodbc.ProgrammingError("42S22", "coluna ausente")

        def rollback(self):
            self.rolled = True

        def close(self):
            pass

    conexao = Conexao()
    with pytest.raises(SessaoIndisponivel):
        preparar_operacao(lambda: conexao, estado)
    assert conexao.rolled is True
    assert estado["usuario_logado"] is True


def test_logout_remove_codigos_hashes_senhas_e_conta():
    arvore = ast.parse(Path("Gerenciador de Gastos V2.py").read_text(encoding="utf-8"))
    callback = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == "sair_conta")
    fonte = '''
import streamlit as st
from trixter import estilo
from trixter.sessao import encerrar_sessao_local
if "pronto" not in st.session_state:
    st.session_state.pronto = True
    st.session_state.usuario_logado = True
    st.session_state.usuario_atual = {"id_usuario": "u1", "email": "a@example.com"}
    st.session_state.verificacao_cadastro = {"codigo": "123456"}
    st.session_state.autorizacao_recuperacao = {"email": "a@example.com"}
    st.session_state.novo_usuario_pendente = {"senha": "hash"}
    st.session_state.seguranca_senha_atual = "atual"
    st.session_state.seguranca_nova_senha = "nova"
    st.session_state.senha_email_seguranca = "email"
    st.session_state.senha_exclusao = "exclusao"
    st.session_state.usuario_original = {"email": "a@example.com"}
    st.session_state.mensagem_conta_excluida = True
    st.session_state.pdf_texto_sessao = {"usuario": "u1", "texto": "extrato ficticio", "conteudo": "abc"}
    st.session_state.arquivo_pdf = b"%PDF-ficticio"
    st.session_state.novo_cpf = "000.000.000-00"
    st.session_state.email_entrada = "pessoa@example.com"
    st.session_state.editar_descricao = "mercado ficticio"
'''
    fonte += ast.unparse(callback) + "\n"
    fonte += '''
area = st.empty()
if st.session_state.usuario_logado:
    st.button("Sair", key="sair", on_click=sair_conta, args=(area, area))
else:
    st.title("Landing")
'''
    app = AppTest.from_string(fonte).run()
    app.button(key="sair").click().run()
    assert not app.exception
    assert app.title[0].value == "Landing"
    assert app.session_state.usuario_logado is False
    assert app.session_state.usuario_atual is None
    for chave in (
        "verificacao_cadastro",
        "autorizacao_recuperacao",
        "novo_usuario_pendente",
        "seguranca_senha_atual",
        "seguranca_nova_senha",
        "senha_email_seguranca",
        "senha_exclusao",
        "usuario_original",
        "pdf_texto_sessao",
        "arquivo_pdf",
        "novo_cpf",
        "email_entrada",
        "editar_descricao",
    ):
        assert chave not in app.session_state
    assert app.session_state.mensagem_conta_excluida is True


def _app_seguranca():
    return AppTest.from_string(
        '''
import streamlit as st
from trixter.seguranca import exibir_seguranca
st.session_state.setdefault("versao_banco", 1)
st.session_state.setdefault("gravacoes", [])
st.session_state.setdefault("exclusoes", [])
st.session_state.setdefault("usuario_logado", True)
st.session_state.setdefault("usuario_atual", {
    "id_usuario": "u1", "email": "a@example.com", "credencial_versao": 1,
})
class Cursor:
    def execute(self, sql, *args):
        self.sql = " ".join(sql.split())
        self.args = args
        if self.sql.startswith("UPDATE") and "senha" in self.sql:
            st.session_state.gravacoes.append(args)
        if self.sql.startswith("DELETE FROM usuarios"):
            st.session_state.exclusoes.append(args)
            st.session_state.usuario_apagado = True
    def fetchone(self):
        sql = getattr(self, "sql", "")
        if sql.startswith("SELECT credencial_versao"):
            if st.session_state.get("usuario_apagado"):
                return None
            return (int(st.session_state.versao_banco),)
        if "SELECT senha" in sql:
            return (st.session_state.hash_senha,)
        if sql.startswith("UPDATE") and "credencial_versao" in sql:
            st.session_state.versao_banco = int(st.session_state.versao_banco) + 1
            return (int(st.session_state.versao_banco),)
        if sql.startswith("DELETE"):
            return None
        return None
    def close(self):
        pass
class Conexao:
    def cursor(self):
        return Cursor()
    def commit(self):
        pass
    def rollback(self):
        st.session_state.rollbacks = st.session_state.get("rollbacks", 0) + 1
    def close(self):
        pass
def conectar():
    if st.session_state.get("falha_banco"):
        import pyodbc
        raise pyodbc.OperationalError("08S01", "falha")
    return Conexao()
exibir_seguranca(conectar)
''',
        default_timeout=30,
    ).run()


def test_botao_de_senha_nao_grava_depois_da_revogacao():
    app = _app_seguranca()
    assert not app.exception
    app.session_state.verificacao_recuperacao = {"codigo": "123456"}
    app.session_state.seguranca_senha_atual = "digitada"
    app.session_state.versao_banco = 2
    app.button(key="btn_alterar_senha").click().run()
    assert not app.exception
    assert app.session_state.gravacoes == []
    assert app.session_state.usuario_logado is False
    assert "verificacao_recuperacao" not in app.session_state
    assert "seguranca_senha_atual" not in app.session_state


def test_botao_de_senha_atualiza_so_a_sessao_que_alterou():
    app = _app_seguranca()
    app.session_state.hash_senha = gerar_hash_senha("Senha123!")
    app.text_input(key="seguranca_senha_atual").set_value("Senha123!")
    app.text_input(key="seguranca_nova_senha").set_value("Nova123!")
    app.text_input(key="seguranca_confirmar_senha").set_value("Nova123!")
    app.button(key="btn_alterar_senha").click().run()
    assert not app.exception
    assert len(app.session_state.gravacoes) == 1
    assert app.session_state.gravacoes[0][1] == "u1"
    assert str(app.session_state.gravacoes[0][0]).startswith("$2")
    assert app.session_state.usuario_atual["credencial_versao"] == 2
    assert app.session_state.versao_banco == 2
    assert app.session_state.usuario_logado is True
    outra = _sessao(versao=1)
    banco = _Banco()
    banco.usuarios["u1"]["credencial_versao"] = 2
    assert preparar_operacao(banco.conectar, outra) == "revogada"


def test_excluir_conta_encerra_e_a_outra_sessao_nao_opera():
    app = _app_seguranca()
    app.session_state.verificacao_recuperacao = {"codigo": "123456"}
    app.session_state.hash_senha = gerar_hash_senha("Senha123!")
    app.text_input(key="senha_exclusao").set_value("Senha123!")
    app.checkbox[0].set_value(True)
    app.button(key="btn_excluir_conta").click().run()
    assert not app.exception
    assert app.session_state.exclusoes == [("u1",)]
    assert app.session_state.mensagem_conta_excluida is True
    assert app.session_state.usuario_logado is False
    assert "senha_exclusao" not in app.session_state
    assert "verificacao_recuperacao" not in app.session_state


def test_falha_de_banco_no_formulario_nao_grava_nem_desloga():
    app = _app_seguranca()
    app.session_state.falha_banco = True
    app.button(key="btn_alterar_senha").click().run()
    assert not app.exception
    assert app.session_state.gravacoes == []
    assert app.session_state.usuario_logado is True
    assert any(MENSAGEM_SESSAO_INDISPONIVEL in erro.value for erro in app.error)


def test_cadastro_novo_permanece_com_a_versao_lida_do_banco():
    from tests.test_enumeracao import _codigo_do_email, _criar, _validar_cadastro, app_cadastro

    app = app_cadastro()
    app.session_state.versao_gravada = 4
    _criar(app)
    codigo = _codigo_do_email(app)
    _validar_cadastro(app, codigo)
    assert not app.exception
    assert app.session_state.usuario_logado is True
    assert app.session_state.usuario_atual["credencial_versao"] == 4
    assert "senha" not in app.session_state.usuario_atual

    usuario = dict(app.session_state.usuario_atual)
    banco = _Banco()
    banco.usuarios[usuario["id_usuario"]] = {
        "email": usuario["email"],
        "senha": "hash",
        "credencial_versao": usuario["credencial_versao"],
    }
    estado = {"usuario_logado": True, "usuario_atual": usuario}
    assert preparar_operacao(banco.conectar, estado) == "ok"
    assert estado["usuario_logado"] is True
    banco.usuarios[usuario["id_usuario"]]["credencial_versao"] = 5
    assert preparar_operacao(banco.conectar, estado) == "revogada"
    assert estado["usuario_logado"] is False
    assert estado["usuario_atual"] is None


@pytest.mark.parametrize("marca", ["versao_ausente", "falha_versao"])
def test_cadastro_sem_versao_lida_nao_autentica(marca):
    from tests.test_enumeracao import _codigo_do_email, _criar, _logado, _validar_cadastro, app_cadastro

    app = app_cadastro()
    app.session_state[marca] = True
    _criar(app)
    codigo = _codigo_do_email(app)
    rollbacks = app.session_state["rollbacks"] if "rollbacks" in app.session_state else 0
    _validar_cadastro(app, codigo)
    assert not app.exception
    assert not _logado(app)
    assert app.session_state.rollbacks == rollbacks + 1
    assert any("Não foi possível concluir agora" in erro.value for erro in app.error)


def test_encerrar_sessao_local_preserva_aviso_de_exclusao():
    estado = _sessao()
    estado["mensagem_conta_excluida"] = True
    estado["pdf_texto_sessao"] = {"usuario": "u1", "texto": "extrato ficticio", "conteudo": "abc"}
    estado["novo_cpf"] = "000.000.000-00"
    encerrar_sessao_local(estado)
    assert estado["mensagem_conta_excluida"] is True
    assert estado["tela_atual"] == "menu"
    assert "pdf_texto_sessao" not in estado
    assert "novo_cpf" not in estado
