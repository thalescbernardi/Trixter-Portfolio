import ast
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from trixter import verificacao as v

AGORA = datetime(2026, 9, 25, 12)


@pytest.mark.parametrize("fluxo", ["cadastro", "recuperacao"])
def test_expiracao_limite_exato(fluxo):
    estado = {}
    v.registrar(estado, fluxo, "000123", "a@example.com", agora=AGORA)
    assert v.validar(estado, fluxo, "000123", AGORA + timedelta(minutes=10)) == "expirado"
    assert not v.autorizacao(estado, fluxo, AGORA)
    assert v.validar(estado, fluxo, "000123", AGORA) == "ausente"


@pytest.mark.parametrize("fluxo", ["cadastro", "recuperacao"])
def test_cinco_tentativas_e_reenvio(fluxo):
    estado = {}
    v.iniciar_solicitacao(estado, fluxo, AGORA)
    v.registrar(estado, fluxo, "000123", "a@example.com", agora=AGORA)
    for i in range(4):
        assert v.validar(estado, fluxo, "errado", AGORA) == "invalido"
        assert str(4-i) in v.mensagem(estado, fluxo, "invalido")
    assert v.validar(estado, fluxo, "errado", AGORA) == "limite"
    assert v.iniciar_solicitacao(estado, fluxo, AGORA + timedelta(seconds=59)) > 0
    assert v.iniciar_solicitacao(estado, fluxo, AGORA + timedelta(seconds=60)) == 0
    v.registrar(estado, fluxo, "111111", "a@example.com", agora=AGORA)
    assert estado[f"verificacao_{fluxo}"]["tentativas"] == 0
    assert v.validar(estado, fluxo, "111111", AGORA) == "sucesso"


def test_autorizacao_vinculada_consumo_prazo_e_revogacao():
    estado = {}
    v.registrar(estado, "recuperacao", "000123", " A@example.com ", "id-a", AGORA)
    assert v.validar(estado, "recuperacao", "000123", AGORA) == "sucesso"
    assert v.validar(estado, "recuperacao", "000123", AGORA) == "ausente"
    auth = v.autorizacao(estado, "recuperacao", AGORA)
    assert auth["email"] == "a@example.com" and auth["usuario_id"] == "id-a"
    assert v.autorizacao(estado, "recuperacao", AGORA + timedelta(minutes=10)) is None
    v.registrar(estado, "recuperacao", "123456", "a@example.com", "id-a", AGORA)
    v.validar(estado, "recuperacao", "123456", AGORA)
    v.iniciar_solicitacao(estado, "recuperacao", AGORA)
    assert not v.autorizacao(estado, "recuperacao", AGORA)


def app_recuperacao():
    fonte = (Path(__file__).resolve().parents[1] / "Gerenciador de Gastos V2.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    voltar = next(n for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef)
                  and n.name == "voltar_para_inicio")
    bloco = next(n for n in ast.walk(arvore) if isinstance(n, ast.If)
                 and ast.unparse(n.test) == "st.session_state.recuperar_senha")
    setup = '''
from trixter.acesso import exibir_recuperacao
import streamlit as st
from contextlib import closing
from datetime import datetime, timedelta
from trixter import verificacao
import secrets
st.session_state.setdefault("limites", [])
st.session_state.setdefault("recuperar_senha", True)
st.session_state.setdefault("envios", [])
st.session_state.setdefault("updates", [])
st.session_state.setdefault("commits", 0)
st.session_state.setdefault("rollbacks", 0)
area_recuperar_senha = st.empty()
area_recuperacao = st.empty()
class Cursor:
    rowcount = 1
    def execute(self, sql, *args):
        self.sql = " ".join(sql.split())
        self.args = args
        if "limites_acesso" in self.sql:
            st.session_state.limites.append((self.sql, self.args))
        elif self.sql.startswith("UPDATE"):
            st.session_state.updates.append(args)
    def fetchone(self):
        if "sp_getapplock" in getattr(self, "sql", ""):
            return (0,)
        if "limites_acesso" in getattr(self, "sql", ""):
            if st.session_state.get("limite_bloqueado"):
                return (99, datetime.now(), datetime.now() + timedelta(minutes=15))
            return None
        if getattr(self, "sql", "").startswith("UPDATE") and st.session_state.get("atualizacao_vazia"):
            return None
        if "credencial_versao" in getattr(self, "sql", ""):
            return (2,)
        if st.session_state.get("conta_inexistente"):
            return None
        return ("id-a",)
    def close(self): pass
class Conexao:
    def cursor(self): return Cursor()
    def close(self): pass
    def commit(self):
        st.session_state.commits += 1
    def rollback(self):
        st.session_state.rollbacks += 1
def conectar_banco(): return Conexao()
def gerar_hash_senha(senha): return "hash-teste"
def enviar_email(**kwargs):
    if st.session_state.get("falha_smtp"): raise RuntimeError("SMTP teste")
    st.session_state.envios.append(kwargs)
'''
    return AppTest.from_string(setup + ast.unparse(voltar) + "\n" + ast.unparse(bloco)).run()


def _codigo_do_email(app):
    import re
    corpo = app.session_state.envios[-1]["corpo"]
    return re.search(r"\b(\d{6})\b", corpo).group(1)


def enviar_e_validar(app):
    app.text_input(key="email_recuperacao").set_value("a@example.com")
    next(b for b in app.button if b.label == "Enviar código de recuperação").click().run()
    assert not app.exception
    desafio = app.session_state.verificacao_recuperacao
    codigo = _codigo_do_email(app)
    assert "codigo" not in desafio
    assert desafio["sal"]
    assert desafio["codigo_hash"] != codigo
    assert codigo not in desafio.values()
    app.text_input(key="codigo_digitado_recuperacao").set_value(codigo)
    next(b for b in app.button if b.label == "Validar código").click().run()
    assert not app.exception
    assert "verificacao_recuperacao" not in app.session_state


def test_interface_nao_valida_sem_envio_e_grava_conta_validada():
    app = app_recuperacao()
    assert not app.exception
    assert not any(b.label == "Validar código" for b in app.button)
    enviar_e_validar(app)
    app.text_input(key="email_recuperacao").set_value("b@example.com").run()
    app.text_input(key="nova_senha_recuperacao").set_value("Teste123!")
    app.text_input(key="confirmar_nova_senha_recuperacao").set_value("Teste123!")
    next(b for b in app.button if b.label == "Redefinir Senha").click().run()
    assert not app.exception
    assert app.session_state.updates == [("hash-teste", "id-a", "a@example.com")]
    assert "autorizacao_recuperacao" not in app.session_state
    from trixter.acesso import MENSAGEM_REDEFINICAO
    assert app.session_state.mensagem_sucesso == MENSAGEM_REDEFINICAO
    assert app.session_state.mensagem_sucesso != "Senha redefinida com sucesso!"


def test_novo_pedido_revoga_validacao_mesmo_no_cooldown():
    app = app_recuperacao()
    enviar_e_validar(app)
    app.text_input(key="email_recuperacao").set_value("b@example.com")
    next(b for b in app.button if b.label == "Enviar código de recuperação").click().run()
    assert not app.exception
    assert not any(b.label == "Redefinir Senha" for b in app.button)
    assert len(app.session_state.envios) == 1
    assert not app.session_state.updates


def test_expiracao_e_falha_smtp_na_interface():
    app = app_recuperacao()
    enviar_e_validar(app)
    app.session_state.autorizacao_recuperacao["expira"] = datetime.now() - timedelta(seconds=1)
    app.run()
    assert not any(b.label == "Redefinir Senha" for b in app.button)
    assert any("expirou" in e.value for e in app.error)
    app.session_state.reenvio_recuperacao = datetime.now() - timedelta(seconds=1)
    app.session_state.falha_smtp = True
    next(b for b in app.button if b.label == "Enviar código de recuperação").click().run()
    assert not app.exception
    assert not any("Não foi possível enviar" in erro.value for erro in app.error)
    assert any(botao.label == "Validar código" for botao in app.button)
    assert len(app.session_state.envios) == 1
    assert "autorizacao_recuperacao" not in app.session_state


def _pedir_recuperacao(app, email="pessoa@example.com"):
    app.text_input(key="email_recuperacao").set_value(email)
    next(botao for botao in app.button if botao.label == "Enviar código de recuperação").click().run()
    return app


def _assinatura_recuperacao(app):
    return (
        tuple(botao.label for botao in app.button),
        tuple(item.value for item in app.info),
        tuple(erro.value for erro in app.error),
        tuple(aviso.value for aviso in app.warning),
        tuple(campo.key for campo in app.text_input),
    )


@pytest.mark.parametrize("cenario", ["existente", "inexistente", "bloqueado"])
def test_recuperacao_nao_revela_conta_envio_nem_bloqueio(cenario, monkeypatch):
    from tests.test_enumeracao import _fixar_codigo_opaco
    _fixar_codigo_opaco(monkeypatch)
    app = app_recuperacao()
    if cenario == "inexistente":
        app.session_state.conta_inexistente = True
    if cenario == "bloqueado":
        app.session_state.limite_bloqueado = True
    _pedir_recuperacao(app)
    assert not app.exception
    referencia = app_recuperacao()
    _fixar_codigo_opaco(monkeypatch)
    assert _assinatura_recuperacao(app) == _assinatura_recuperacao(_pedir_recuperacao(
        referencia
    ))
    assert any(botao.label == "Validar código" for botao in app.button)
    assert any("Se o e-mail estiver cadastrado" in item.value for item in app.info)
    assert not any("Não foi possível enviar" in erro.value for erro in app.error)
    assert (len(app.session_state.envios) == 1) is (cenario == "existente")
    desafio = app.session_state.verificacao_recuperacao
    assert "codigo" not in desafio
    assert desafio["sal"] and desafio["codigo_hash"]
    assert "123456" not in desafio.values()
    app.text_input(key="codigo_digitado_recuperacao").set_value("000000")
    next(botao for botao in app.button if botao.label == "Validar código").click().run()
    assert not app.exception
    assert any("Código inválido" in erro.value for erro in app.error)
    assert not any(botao.label == "Redefinir Senha" for botao in app.button)


def _redefinir(app):
    app.text_input(key="nova_senha_recuperacao").set_value("Teste123!")
    app.text_input(key="confirmar_nova_senha_recuperacao").set_value("Teste123!")
    next(botao for botao in app.button if botao.label == "Redefinir Senha").click().run()
    return app


def _preparar_redefinicao(cenario, monkeypatch):
    from tests.test_enumeracao import _fixar_codigo_opaco
    _fixar_codigo_opaco(monkeypatch)
    app = app_recuperacao()
    if cenario == "inexistente":
        app.session_state.conta_inexistente = True
    _pedir_recuperacao(app)
    desafio = app.session_state.verificacao_recuperacao
    assert "codigo" not in desafio
    assert "123456" not in desafio.values()
    app.text_input(key="codigo_digitado_recuperacao").set_value("123456")
    next(botao for botao in app.button if botao.label == "Validar código").click().run()
    return app


def test_redefinicao_nao_confirma_alteracao_sem_gravacao(monkeypatch):
    from trixter.acesso import MENSAGEM_REDEFINICAO
    respostas = {}
    for cenario in ("existente", "inexistente", "sem_linha"):
        app = _preparar_redefinicao(
            "inexistente" if cenario == "inexistente" else "existente", monkeypatch,
        )
        assert any(botao.label == "Redefinir Senha" for botao in app.button)
        if cenario == "sem_linha":
            app.session_state.atualizacao_vazia = True
        commits = app.session_state.commits
        rollbacks = app.session_state.rollbacks
        _redefinir(app)
        assert not app.exception
        assert app.session_state.mensagem_sucesso == MENSAGEM_REDEFINICAO
        assert "autorizacao_recuperacao" not in app.session_state
        assert "verificacao_recuperacao" not in app.session_state
        respostas[cenario] = (
            app.session_state.mensagem_sucesso,
            app.session_state.entrar,
            app.session_state.recuperar_senha,
        )
        if cenario == "existente":
            assert app.session_state.updates == [("hash-teste", "id-a", "pessoa@example.com")]
            assert app.session_state.commits == commits + 1
        elif cenario == "inexistente":
            assert app.session_state.updates == []
            assert app.session_state.commits == commits
        else:
            assert app.session_state.rollbacks == rollbacks + 1
            assert app.session_state.commits == commits
    assert respostas["existente"] == respostas["inexistente"] == respostas["sem_linha"]


def test_autorizacao_de_outro_fluxo_nao_redefine_senha():
    app = app_recuperacao()
    app.session_state.autorizacao_recuperacao = {
        "email": "pessoa@example.com",
        "usuario_id": "id-a",
        "finalidade": "cadastro",
        "expira": datetime.now() + timedelta(minutes=5),
    }
    app.run()
    _redefinir(app)
    assert not app.exception
    assert app.session_state.updates == []
    assert "autorizacao_recuperacao" not in app.session_state


@pytest.mark.parametrize("fluxo", ["cadastro", "recuperacao"])
def test_codigo_protegido_valida_uma_vez_e_nao_fica_em_texto(fluxo):
    estado = {}
    v.registrar(estado, fluxo, "000123", "a@example.com", "id-a", AGORA, proteger=True)
    desafio = estado[f"verificacao_{fluxo}"]
    assert "codigo" not in desafio
    assert desafio["sal"]
    assert desafio["codigo_hash"] != "000123"
    assert "000123" not in desafio.values()
    assert v.validar(estado, fluxo, "000123", AGORA) == "sucesso"
    assert "verificacao_" + fluxo not in estado
    assert v.validar(estado, fluxo, "000123", AGORA) == "ausente"
    assert v.autorizacao(estado, fluxo, AGORA)["usuario_id"] == "id-a"


def test_recusa_da_cota_substitui_recuperacao_por_hash(monkeypatch):
    from tests.test_enumeracao import _fixar_codigo_opaco
    _fixar_codigo_opaco(monkeypatch)
    app = app_recuperacao()
    app.text_input(key="email_recuperacao").set_value("pessoa@example.com")
    next(botao for botao in app.button if botao.label == "Enviar código de recuperação").click().run()
    assert not app.exception
    assert _codigo_do_email(app) == "123456"
    app.session_state.limite_bloqueado = True
    app.text_input(key="codigo_digitado_recuperacao").set_value("123456")
    next(botao for botao in app.button if botao.label == "Validar código").click().run()
    assert not app.exception
    desafio = app.session_state.verificacao_recuperacao
    assert "codigo" not in desafio
    assert desafio["sal"]
    assert desafio["codigo_hash"]
    assert "123456" not in desafio.values()
    assert desafio["tentativas"] == 1
    assert any("Código inválido. Tentativas restantes: 4" in erro.value for erro in app.error)
    assert not any(botao.label == "Redefinir Senha" for botao in app.button)


def test_codigo_nao_vale_em_outro_fluxo():
    estado = {}
    v.registrar(estado, "cadastro", "000123", "a@example.com", agora=AGORA)
    estado["verificacao_recuperacao"] = dict(estado["verificacao_cadastro"])
    assert v.validar(estado, "recuperacao", "000123", AGORA) == "ausente"
    assert v.autorizacao(estado, "recuperacao", AGORA) is None
    assert v.validar(estado, "cadastro", "000123", AGORA) == "sucesso"
    assert v.validar(estado, "cadastro", "000123", AGORA) == "ausente"


@pytest.mark.parametrize("situacao", ["expirado", "limite", "sucesso", "sem_declaracao"])
def test_cadastro_sem_avisos_duplicados(situacao):
    fonte = (Path(__file__).resolve().parents[1] / "trixter" / "acesso.py").read_text(encoding="utf-8")
    bloco = next(n for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.If)
                 and ast.unparse(n.test) == "st.session_state.get('codigo_cadastro_enviado', False)")
    setup = '''
import streamlit as st
from contextlib import closing
from datetime import datetime, timedelta
import pyodbc
from trixter import verificacao
from trixter.acesso import MENSAGEM_MAIORIDADE, _aplicar_limite_codigo, abrir_sessao
from trixter.credencial import reservar_email
st.session_state.setdefault("codigo_cadastro_enviado", True)
st.session_state.setdefault("inserts", 0)
st.session_state.setdefault("novo_usuario_pendente", dict(id_usuario="id-a", senha="hash",
    tipo_pessoa="Pessoa Física", email="a@example.com", declaracao_maioridade=True))
if "iniciado" not in st.session_state:
    verificacao.registrar(st.session_state, "cadastro", "123456", "a@example.com")
    st.session_state.iniciado = True
area_cadastro = st.empty()
def voltar_para_inicio(): pass
class Cursor:
    rowcount = 1
    def execute(self, sql, *args):
        self.sql = " ".join(sql.split())
        if "INSERT INTO dbo.usuarios" in self.sql:
            st.session_state.inserts += 1
    def fetchone(self):
        if "sp_getapplock" in getattr(self, "sql", ""):
            return (0,)
        if "credencial_versao" in getattr(self, "sql", ""):
            return (int(st.session_state.get("versao_gravada", 4)),)
        return None
    def close(self): pass
class Conexao:
    def cursor(self): return Cursor()
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass
def conectar_banco(): return Conexao()
if aviso := st.session_state.pop("aviso_codigo_cadastro", None): st.error(aviso)
'''
    app = AppTest.from_string(setup + ast.unparse(bloco)).run()
    assert not app.exception
    desafio = app.session_state.verificacao_cadastro
    if situacao == "expirado":
        desafio["expira"] = datetime.now() - timedelta(seconds=1)
    elif situacao == "limite":
        desafio["tentativas"] = 4
    if situacao == "sem_declaracao":
        app.session_state.novo_usuario_pendente.pop("declaracao_maioridade")
    app.text_input(key="codigo_digitado_cadastro").set_value("errado" if situacao == "limite" else "123456")
    next(b for b in app.button if b.label == "Validar código de confirmação").click().run()
    assert not app.exception
    if situacao == "sucesso":
        assert app.session_state.inserts == 1 and not app.error
        assert app.session_state.usuario_logado
        assert "senha" not in app.session_state.usuario_atual
        assert "declaracao_maioridade" not in app.session_state.usuario_atual
    elif situacao == "sem_declaracao":
        assert app.session_state.inserts == 0
        assert "usuario_logado" not in app.session_state or not app.session_state.usuario_logado
        assert any("18 anos" in erro.value for erro in app.error)
    else:
        assert app.session_state.inserts == 0 and len(app.error) == 1
        assert "expirou" in app.error[0].value if situacao == "expirado" else "Limite" in app.error[0].value
    assert "verificacao_cadastro" not in app.session_state
    assert "autorizacao_cadastro" not in app.session_state
