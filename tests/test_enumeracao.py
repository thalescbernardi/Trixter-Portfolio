import re
from datetime import datetime, timedelta

import pytest
from streamlit.testing.v1 import AppTest

from trixter.acesso import abrir_sessao, descartar_credenciais_digitadas


def app_cadastro():
    return AppTest.from_string(
        '''
from trixter.acesso import exibir_cadastro, exibir_login, exibir_recuperacao
import streamlit as st
from datetime import datetime, timedelta
st.session_state.setdefault("envios", [])
st.session_state.setdefault("inserts", 0)
st.session_state.setdefault("updates", 0)
st.session_state.setdefault("criar_conta", True)
st.session_state.setdefault("entrar", False)
st.session_state.setdefault("recuperar_senha", False)
area = st.empty()
class Cursor:
    rowcount = 1
    def __init__(self):
        self.sql = ""
        self.description = None
    def execute(self, sql, *args):
        self.sql = " ".join(sql.split())
        st.session_state.consultas = st.session_state.get("consultas", 0) + 1
        self.description = None
        if "INSERT INTO dbo.usuarios" in self.sql:
            st.session_state.inserts += 1
            st.session_state.ultimo_insert = args
            st.session_state.ultimo_insert_sql = self.sql
        if self.sql.startswith("UPDATE") and "limites_acesso" not in self.sql:
            st.session_state.updates += 1
        if self.sql.startswith("SELECT *"):
            self.description = [
                ("id_usuario",), ("email",), ("nome",), ("tipo_pessoa",),
                ("onboarding_concluido",),
            ]
    def fetchone(self):
        if "sp_getapplock" in self.sql:
            return (0,)
        if "limites_acesso" in self.sql:
            if st.session_state.get("limite_bloqueado"):
                return (99, datetime.now(), datetime.now() + timedelta(minutes=15))
            return None
        if self.sql.startswith("SELECT id_usuario"):
            if st.session_state.get("email_existe"):
                return ("id-existente",)
            return None
        if self.sql.startswith("SELECT *"):
            return ("id-existente", "pessoa@example.com", "Ana", "Pessoa Física", 1)
        if "credencial_versao" in self.sql:
            if st.session_state.get("falha_versao"):
                import pyodbc
                raise pyodbc.OperationalError("08S01", "falha")
            if st.session_state.get("versao_ausente"):
                return None
            return (int(st.session_state.get("versao_gravada", 4)),)
        return None
    def close(self):
        pass
class Conexao:
    def cursor(self): return Cursor()
    def commit(self): pass
    def rollback(self):
        st.session_state.rollbacks = st.session_state.get("rollbacks", 0) + 1
    def close(self): pass
def conectar_banco(): return Conexao()
def gerar_hash_senha(senha): return "hash-teste"
def enviar_email(**kwargs):
    st.session_state.envios.append(kwargs)
def voltar(area=None): pass
def confirmar_entrada(area): pass
if (
    st.session_state.criar_conta
    or st.session_state.get("codigo_cadastro_enviado")
    or st.session_state.get("aviso_conta_existente")
):
    exibir_cadastro(area, conectar_banco, gerar_hash_senha, enviar_email, voltar)
elif st.session_state.entrar:
    exibir_login(area, confirmar_entrada, voltar)
elif st.session_state.recuperar_senha:
    exibir_recuperacao(area, conectar_banco, gerar_hash_senha, enviar_email, voltar)
''',
        default_timeout=20,
    ).run()


def _criar(app):
    app.text_input(key="novo_nome").set_value("Ana")
    app.text_input(key="novo_email").set_value("pessoa@example.com")
    app.text_input(key="nova_senha").set_value("Teste123!")
    app.text_input(key="confirmar_senha").set_value("Teste123!")
    app.checkbox(key="declaracao_maioridade").set_value(True)
    next(botao for botao in app.button if botao.label == "Criar Conta").click().run()
    return app


def _assinatura(app):
    return (
        tuple(botao.label for botao in app.button),
        tuple(item.value for item in app.info),
        tuple(erro.value for erro in app.error),
        tuple(aviso.value for aviso in app.warning),
    )


@pytest.mark.parametrize("cenario", ["novo", "existente", "bloqueado"])
def test_cadastro_nao_revela_se_o_email_existe(cenario):
    app = app_cadastro()
    if cenario == "existente":
        app.session_state.email_existe = True
    if cenario == "bloqueado":
        app.session_state.limite_bloqueado = True
    _criar(app)
    assert not app.exception
    referencia = _criar(app_cadastro())
    assert _assinatura(app) == _assinatura(referencia)
    assert not any("já está cadastrado" in erro.value for erro in app.error)
    assert any("Enviamos um código" in item.value for item in app.info)
    assert any(botao.label == "Validar código de confirmação" for botao in app.button)
    assert (len(app.session_state.envios) == 1) is (cenario != "bloqueado")
    assert app.session_state.inserts == 0


def _logado(app):
    return "usuario_logado" in app.session_state and bool(app.session_state["usuario_logado"])


def _validar_cadastro(app, codigo):
    app.text_input(key="codigo_digitado_cadastro").set_value(codigo)
    next(botao for botao in app.button if botao.label == "Validar código de confirmação").click().run()
    return app


def _codigo_do_email(app):
    corpo = app.session_state.envios[-1]["corpo"]
    encontrado = re.search(r"\b(\d{6})\b", corpo)
    assert encontrado
    return encontrado.group(1)


def _fixar_codigo_opaco(monkeypatch):
    def randbelow(limite):
        if limite != 1_000_000:
            raise AssertionError(limite)
        return 123456

    monkeypatch.setattr("trixter.acesso.secrets.randbelow", randbelow)


def test_cadastro_novo_abre_sessao_sem_hash_e_sem_reuso_do_codigo():
    app = app_cadastro()
    _criar(app)
    codigo = _codigo_do_email(app)
    app.session_state.autorizacao_recuperacao = {"usuario_id": "antigo"}
    _validar_cadastro(app, codigo)
    assert not app.exception
    assert app.session_state.inserts == 1
    assert app.session_state.usuario_logado
    assert app.session_state.tela_atual == "onboarding"
    assert "senha" not in app.session_state.usuario_atual
    assert "novo_usuario_pendente" not in app.session_state
    assert "verificacao_cadastro" not in app.session_state
    assert "autorizacao_cadastro" not in app.session_state
    assert "autorizacao_recuperacao" not in app.session_state


def _codigo_errado(app):
    codigo = _codigo_do_email(app)
    return "000001" if codigo == "000000" else "000000"


def test_codigo_errado_nao_revela_conta_existente():
    from trixter.acesso import MENSAGEM_CONTA_EXISTENTE
    app = app_cadastro()
    app.session_state.email_existe = True
    _criar(app)
    _validar_cadastro(app, _codigo_errado(app))
    assert not app.exception
    assert any("Código inválido" in erro.value for erro in app.error)
    assert not any(MENSAGEM_CONTA_EXISTENTE in item.value for item in app.info)
    assert not any(botao.label == "Entrar com senha" for botao in app.button)
    assert app.session_state.inserts == 0
    assert app.session_state.updates == 0
    assert not _logado(app)


def test_cadastro_existente_informa_a_conta_e_oferece_as_telas():
    from trixter.acesso import MENSAGEM_CONTA_EXISTENTE
    app = app_cadastro()
    app.session_state.email_existe = True
    _criar(app)
    codigo = _codigo_do_email(app)
    _validar_cadastro(app, codigo)
    assert not app.exception
    assert app.session_state.inserts == 0
    assert app.session_state.updates == 0
    assert not _logado(app)
    assert "verificacao_cadastro" not in app.session_state
    assert "autorizacao_cadastro" not in app.session_state
    assert "novo_usuario_pendente" not in app.session_state
    assert any(MENSAGEM_CONTA_EXISTENTE in item.value for item in app.info)
    assert any(botao.label == "Entrar com senha" for botao in app.button)
    assert any(botao.label == "Recuperar senha" for botao in app.button)
    assert not any(botao.label == "Validar código de confirmação" for botao in app.button)

    app.session_state.codigo_cadastro_enviado = True
    app.session_state.aviso_conta_existente = None
    app.run()
    app.text_input(key="codigo_digitado_cadastro").set_value(codigo)
    next(botao for botao in app.button if botao.label == "Validar código de confirmação").click().run()
    assert app.session_state.inserts == 0
    assert app.session_state.updates == 0
    assert not _logado(app)


def test_conta_existente_abre_login_e_recuperacao():
    app = app_cadastro()
    app.session_state.email_existe = True
    _criar(app)
    codigo = _codigo_do_email(app)
    _validar_cadastro(app, codigo)
    next(botao for botao in app.button if botao.label == "Entrar com senha").click().run()
    assert not app.exception
    assert app.session_state.entrar
    assert not app.session_state.criar_conta
    assert not app.session_state.recuperar_senha
    assert not _logado(app)
    assert app.session_state.inserts == 0
    assert app.session_state.updates == 0
    assert app.text_input(key="email_entrada").value == "pessoa@example.com"
    assert any(botao.label == "Entrar" for botao in app.button)
    assert "autorizacao_recuperacao" not in app.session_state

    app = app_cadastro()
    app.session_state.email_existe = True
    _criar(app)
    codigo = _codigo_do_email(app)
    _validar_cadastro(app, codigo)
    next(botao for botao in app.button if botao.label == "Recuperar senha").click().run()
    assert not app.exception
    assert app.session_state.recuperar_senha
    assert not app.session_state.criar_conta
    assert not app.session_state.entrar
    assert not _logado(app)
    assert app.session_state.inserts == 0
    assert app.session_state.updates == 0
    assert app.text_input(key="email_recuperacao").value == "pessoa@example.com"
    assert any(botao.label == "Enviar código de recuperação" for botao in app.button)
    assert "autorizacao_recuperacao" not in app.session_state
    assert "autorizacao_cadastro" not in app.session_state


def test_cadastro_existente_expirado_ou_esgotado_nao_autentica():
    app = app_cadastro()
    app.session_state.email_existe = True
    _criar(app)
    app.session_state.verificacao_cadastro["expira"] = datetime.now() - timedelta(seconds=1)
    codigo = _codigo_do_email(app)
    _validar_cadastro(app, codigo)
    assert not app.exception
    assert app.session_state.inserts == 0
    assert not _logado(app)
    assert "verificacao_cadastro" not in app.session_state
    assert not any("já possui cadastro" in item.value for item in app.info)

    app = app_cadastro()
    app.session_state.email_existe = True
    _criar(app)
    codigo = _codigo_do_email(app)
    app.session_state.verificacao_cadastro["tentativas"] = 5
    _validar_cadastro(app, codigo)
    assert app.session_state.inserts == 0
    assert not _logado(app)
    assert "verificacao_cadastro" not in app.session_state


def test_abrir_sessao_descarta_o_estado_anterior():
    estado = {
        "usuario_atual": {"id_usuario": "antigo", "senha": "hash-antigo"},
        "usuario_logado": False,
        "novo_usuario_pendente": {"senha": "hash"},
        "verificacao_cadastro": {"codigo": "123456"},
        "autorizacao_recuperacao": {"usuario_id": "x"},
        "senha": "plain",
        "criar_conta": True,
    }
    abrir_sessao(
        {
            "id_usuario": "novo",
            "email": "a@example.com",
            "senha": "hash",
            "conta_existente": "id-antigo",
            "pedido_opaco": True,
        },
        "menu",
        estado,
    )
    assert estado["usuario_logado"] is True
    assert estado["tela_atual"] == "menu"
    assert estado["criar_conta"] is False
    assert estado["usuario_atual"] == {"id_usuario": "novo", "email": "a@example.com"}
    assert "novo_usuario_pendente" not in estado
    assert "verificacao_cadastro" not in estado
    assert "autorizacao_recuperacao" not in estado
    assert estado["senha"] == "plain"
    descartar_credenciais_digitadas(estado)
    assert "senha" not in estado


def test_cadastro_grava_se_a_conta_deixou_de_existir():
    app = app_cadastro()
    app.session_state.email_existe = True
    _criar(app)
    codigo = _codigo_do_email(app)
    app.session_state.email_existe = False
    _validar_cadastro(app, codigo)
    assert not app.exception
    assert app.session_state.inserts == 1
    assert app.session_state.usuario_logado
    assert "senha" not in app.session_state.usuario_atual
    assert "conta_existente" not in app.session_state.usuario_atual


def test_cadastro_bloqueado_nao_cria_conta_nem_com_o_codigo_da_sessao(monkeypatch):
    _fixar_codigo_opaco(monkeypatch)
    app = app_cadastro()
    app.session_state.limite_bloqueado = True
    _criar(app)
    desafio = app.session_state.verificacao_cadastro
    assert "codigo" not in desafio
    assert "123456" not in desafio.values()
    assert app.session_state.envios == []
    app.text_input(key="codigo_digitado_cadastro").set_value("123456")
    next(botao for botao in app.button if botao.label == "Validar código de confirmação").click().run()
    assert not app.exception
    assert app.session_state.inserts == 0
    assert app.session_state["tela_atual"] != "menu" if "tela_atual" in app.session_state else True
    assert any("Código inválido" in erro.value for erro in app.error)
    assert not any("já possui cadastro" in item.value for item in app.info)


def test_cadastro_real_guarda_hash_e_valida_o_codigo_do_email():
    app = app_cadastro()
    _criar(app)
    desafio = app.session_state.verificacao_cadastro
    codigo = _codigo_do_email(app)
    assert "codigo" not in desafio
    assert desafio["sal"]
    assert desafio["codigo_hash"] != codigo
    assert codigo not in desafio.values()
    _validar_cadastro(app, codigo)
    assert not app.exception
    assert app.session_state.usuario_logado
    assert app.session_state.inserts == 1
    assert "verificacao_cadastro" not in app.session_state
    assert "autorizacao_cadastro" not in app.session_state


def test_teste_local_preserva_o_codigo_exibido(monkeypatch):
    monkeypatch.setattr(
        "trixter.acesso.cadastro_local_permitido", lambda *args, **kwargs: True,
    )
    app = app_cadastro()
    app.text_input(key="novo_nome").set_value("Ana")
    app.text_input(key="novo_email").set_value("pessoa@example.test")
    app.text_input(key="nova_senha").set_value("Teste123!")
    app.text_input(key="confirmar_senha").set_value("Teste123!")
    app.checkbox(key="declaracao_maioridade").set_value(True)
    next(botao for botao in app.button if botao.label == "Criar Conta").click().run()
    assert not app.exception
    desafio = app.session_state.verificacao_cadastro
    assert desafio["teste_local"] is True
    assert desafio["codigo"]
    assert "codigo_hash" not in desafio
    assert app.session_state.envios == []
    assert any("Teste local" in aviso.value for aviso in app.warning)
    _validar_cadastro(app, desafio["codigo"])
    assert not app.exception
    assert app.session_state.usuario_logado
    assert app.session_state.inserts == 1
