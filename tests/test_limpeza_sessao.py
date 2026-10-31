"""Limpeza de dados pessoais na sessão, com valores fictícios."""
import ast
import hashlib
import inspect
from pathlib import Path

from streamlit.testing.v1 import AppTest

from trixter import limite_acesso
from trixter.senha import gerar_hash_senha
from trixter.sessao import encerrar_sessao_local, limpar_pdf_da_conta


_RESIDUAIS = (
    "pdf_texto_sessao",
    "arquivo_pdf",
    "novo_nome",
    "novo_cpf",
    "novo_cnpj",
    "novo_nome_empresa",
    "novo_email",
    "renda_mensal",
    "faturamento_mensal",
    "email_entrada",
    "email_recuperacao",
    "novo_email_seguranca",
    "confirmar_email_seguranca",
    "editando_movimentacao",
    "editar_data",
    "editar_categoria",
    "editar_valor",
    "editar_descricao",
    "editar_classificacao",
    "senha",
    "verificacao_cadastro",
    "autorizacao_recuperacao",
)


def _estado_com_residuos():
    estado = {
        "usuario_logado": True,
        "usuario_atual": {
            "id_usuario": "u-real",
            "email": "pessoa@example.com",
            "nome": "Pessoa Ficticia",
            "cpf": "00000000000",
            "credencial_versao": 1,
        },
        "mensagem_conta_excluida": True,
        "pdf_texto_sessao": {
            "usuario": "u-real",
            "conteudo": "abc",
            "texto": "extrato ficticio",
        },
        "arquivo_pdf": b"%PDF-ficticio",
        "novo_nome": "Pessoa Ficticia",
        "novo_cpf": "000.000.000-00",
        "novo_cnpj": "00.000.000/0000-00",
        "novo_nome_empresa": "Empresa Ficticia",
        "novo_email": "pessoa@example.com",
        "renda_mensal": 1000.0,
        "faturamento_mensal": 2000.0,
        "email_entrada": "pessoa@example.com",
        "email_recuperacao": "pessoa@example.com",
        "novo_email_seguranca": "outro@example.com",
        "confirmar_email_seguranca": "outro@example.com",
        "editando_movimentacao": ("u-real", "mov-1"),
        "editar_data": "2026-01-01",
        "editar_categoria": "Mercado",
        "editar_valor": 10.0,
        "editar_descricao": "mercado ficticio",
        "editar_classificacao": "Variavel",
        "senha": "Senha123!",
        "verificacao_cadastro": {"codigo": "123456", "email": "pessoa@example.com"},
        "autorizacao_recuperacao": {"email": "pessoa@example.com"},
    }
    return estado


class _EstadoQueFalha(dict):
    def pop(self, chave, default=None):
        raise RuntimeError("falha ficticia")


def test_falha_ao_remover_chave_nao_e_ignorada():
    estado = _EstadoQueFalha(_estado_com_residuos())
    try:
        encerrar_sessao_local(estado)
    except RuntimeError as erro:
        assert str(erro) == "falha ficticia"
    else:
        raise AssertionError("a falha foi ignorada")
    assert estado["usuario_logado"] is True
    assert estado["pdf_texto_sessao"]["texto"] == "extrato ficticio"
    assert estado["mensagem_conta_excluida"] is True


def test_encerrar_remove_residuos_e_preserva_o_aviso():
    estado = _estado_com_residuos()
    encerrar_sessao_local(estado)
    assert estado["mensagem_conta_excluida"] is True
    assert estado["usuario_logado"] is False
    assert estado["usuario_atual"] is None
    for chave in _RESIDUAIS:
        assert chave not in estado


def test_limpar_pdf_da_demo_nao_apaga_o_texto_da_conta_real():
    estado = {
        "usuario_atual": {"id_usuario": "u-real", "email": "pessoa@example.com"},
        "pdf_texto_sessao": {
            "usuario": "u-real",
            "conteudo": "abc",
            "texto": "extrato ficticio",
        },
        "arquivo_pdf": b"%PDF-ficticio",
    }
    limpar_pdf_da_conta(estado, "u-demo")
    assert estado["pdf_texto_sessao"]["texto"] == "extrato ficticio"
    assert estado["arquivo_pdf"] == b"%PDF-ficticio"
    assert estado["usuario_atual"]["id_usuario"] == "u-real"


def test_limpar_pdf_remove_o_cache_da_demonstracao():
    estado = {
        "usuario_atual": {"id_usuario": "u-real"},
        "pdf_texto_sessao": {
            "usuario": "u-demo",
            "conteudo": "def",
            "texto": "comprovante ficticio",
        },
        "arquivo_pdf": b"%PDF-demo",
    }
    limpar_pdf_da_conta(estado, "u-demo")
    assert "pdf_texto_sessao" not in estado
    assert "arquivo_pdf" not in estado
    assert estado["usuario_atual"]["id_usuario"] == "u-real"


def test_voltar_da_demo_chama_a_limpeza_depois_de_apagar_a_copia():
    arvore = ast.parse(Path("Gerenciador de Gastos V2.py").read_text(encoding="utf-8"))
    funcao = next(
        no for no in arvore.body
        if isinstance(no, ast.FunctionDef) and no.name == "voltar_conta_original"
    )
    texto = ast.unparse(funcao)
    assert "excluir_demo_temporaria" in texto
    assert "limpar_pdf_da_conta" in texto
    assert texto.index("excluir_demo_temporaria") < texto.index("limpar_pdf_da_conta")
    assert "limites_acesso" not in texto


def test_contadores_de_acesso_permanecem_como_estavam():
    assert limite_acesso._POLITICA == {
        "login": {"par": (8, 15), "ip": (30, 15)},
        "recuperacao_envio": {"par": (3, 30), "ip": (10, 30), "email": (5, 60)},
        "cadastro_envio": {"par": (3, 30), "ip": (10, 30), "email": (5, 60)},
        "recuperacao_codigo": {"par": (5, 15), "ip": (20, 15)},
        "cadastro_codigo": {"par": (5, 15), "ip": (20, 15)},
        "alteracao_email_envio": {"par": (3, 30), "ip": (10, 30), "email": (5, 60)},
        "alteracao_email_codigo": {"par": (5, 15), "ip": (20, 15)},
    }
    fonte = inspect.getsource(limite_acesso._limpar_antigos)
    assert "DELETE TOP (32)" in fonte
    assert "hours=24" in fonte
    chaves = [
        chave for chave, _limite, _minutos in limite_acesso._chaves(
            "login", "pessoa@example.com", "203.0.113.10",
        )
    ]
    assert all("pessoa@example.com" not in chave for chave in chaves)
    assert any(chave.startswith("ip:203.0.113.10") for chave in chaves)


def _app_exclusao():
    return AppTest.from_string(
        """
import streamlit as st
from trixter.seguranca import exibir_seguranca
if "pronto" not in st.session_state:
    st.session_state.pronto = True
    st.session_state.usuario_logado = True
    st.session_state.usuario_atual = {
        "id_usuario": "u-real",
        "email": "pessoa@example.com",
        "nome": "Pessoa Ficticia",
        "cpf": "00000000000",
        "credencial_versao": 1,
    }
    st.session_state.sqls = []
    st.session_state.parametros = []
    st.session_state.commits = 0
    st.session_state.rollbacks = 0
    st.session_state.pdf_texto_sessao = {
        "usuario": "u-real", "conteudo": "abc", "texto": "extrato ficticio",
    }
    st.session_state.novo_cpf = "000.000.000-00"
    st.session_state.email_recuperacao = "pessoa@example.com"
    st.session_state.editar_descricao = "mercado ficticio"
class Cursor:
    def execute(self, sql, *args):
        self.sql = " ".join(sql.split())
        st.session_state.sqls.append(self.sql)
        st.session_state.parametros.append(args)
        if st.session_state.get("falha_exclusao") and self.sql.startswith("DELETE"):
            raise RuntimeError("falha ficticia")
    def fetchone(self):
        sql = getattr(self, "sql", "")
        if "SELECT senha" in sql:
            return (st.session_state.hash_senha,)
        if sql.startswith("SELECT credencial_versao"):
            return (1,)
        if sql.startswith("SELECT email"):
            return ("  Outra.Pessoa@Example.com ",)
        if "OBJECT_ID" in sql and "limites_acesso" in sql:
            return (1,)
        return None
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
def conectar():
    return Conexao()
exibir_seguranca(conectar)
""",
        default_timeout=30,
    ).run()


def _confirmar_exclusao(app):
    app.session_state.hash_senha = gerar_hash_senha("Senha123!")
    app.text_input(key="senha_exclusao").set_value("Senha123!")
    app.checkbox[0].set_value(True)
    app.button(key="btn_excluir_conta").click().run()


def test_exclusao_confirmada_encerra_na_hora_e_nao_mexe_nos_contadores():
    app = _app_exclusao()
    _confirmar_exclusao(app)
    assert not app.exception
    assert app.session_state.commits == 1
    assert app.session_state.usuario_logado is False
    assert app.session_state.usuario_atual is None
    assert app.session_state.mensagem_conta_excluida is True
    for chave in ("pdf_texto_sessao", "novo_cpf", "email_recuperacao", "editar_descricao", "senha_exclusao"):
        assert chave not in app.session_state
    textos = " ".join(app.session_state.sqls)
    for tabela in (
        "DELETE FROM gastos",
        "DELETE FROM receitas",
        "DELETE FROM orcamentos",
        "DELETE FROM planejamentos",
        "DELETE FROM recorrencias",
        "DELETE FROM categorias",
        "DELETE FROM dbo.envios_automaticos",
        "DELETE FROM usuarios",
    ):
        assert tabela in textos
    resumo = hashlib.sha256(b"outra.pessoa@example.com").hexdigest()
    apagamentos = [
        (sql, params)
        for sql, params in zip(app.session_state.sqls, app.session_state.parametros)
        if "limites_acesso" in sql and sql.startswith("DELETE")
    ]
    assert len(apagamentos) == 1
    sql_limites, params_limites = apagamentos[0]
    assert "LIKE" in sql_limites and "ESCAPE" in sql_limites
    assert f"email:{resumo}" in params_limites
    assert f"par:{resumo}|%" in params_limites
    assert all("pessoa@example.com" not in str(valor) for valor in params_limites)
    assert all("Outra.Pessoa" not in str(valor) for valor in params_limites)
    assert all(not str(valor).startswith("ip:") for valor in params_limites)
    assert sum(1 for sql in app.session_state.sqls if sql.startswith("SELECT credencial_versao")) == 2


def test_falha_da_exclusao_preserva_a_sessao():
    app = _app_exclusao()
    app.session_state.falha_exclusao = True
    _confirmar_exclusao(app)
    assert not app.exception
    assert app.session_state.commits == 0
    assert app.session_state.rollbacks == 1
    assert app.session_state.usuario_logado is True
    assert app.session_state.usuario_atual["id_usuario"] == "u-real"
    assert app.session_state.usuario_atual["cpf"] == "00000000000"
    assert app.session_state.pdf_texto_sessao["texto"] == "extrato ficticio"
    assert app.session_state.novo_cpf == "000.000.000-00"
    assert "mensagem_conta_excluida" not in app.session_state
    assert any("Não foi possível excluir a conta." in erro.value for erro in app.error)


def test_encerrar_depois_do_widget_nao_dispara_erro():
    app = AppTest.from_string(
        """
import streamlit as st
from trixter.sessao import encerrar_sessao_local
if "pronto" not in st.session_state:
    st.session_state.pronto = True
    st.session_state.usuario_logado = True
    st.session_state.usuario_atual = {
        "id_usuario": "u-real", "email": "pessoa@example.com", "cpf": "00000000000",
    }
    st.session_state.pdf_texto_sessao = {
        "usuario": "u-real", "conteudo": "abc", "texto": "extrato ficticio",
    }
    st.session_state.arquivo_pdf = b"%PDF-ficticio"
    st.session_state.mensagem_conta_excluida = True
st.text_input("CPF", key="novo_cpf")
st.text_input("E-mail", key="email_entrada")
st.text_input("Descricao", key="editar_descricao")
if st.button("Encerrar", key="btn_encerrar"):
    encerrar_sessao_local(st.session_state)
""",
        default_timeout=30,
    ).run()
    app.text_input(key="novo_cpf").set_value("000.000.000-00")
    app.text_input(key="email_entrada").set_value("pessoa@example.com")
    app.text_input(key="editar_descricao").set_value("mercado ficticio")
    app.button(key="btn_encerrar").click().run()
    assert not app.exception
    assert app.session_state.usuario_logado is False
    assert app.session_state.usuario_atual is None
    assert app.session_state.mensagem_conta_excluida is True
    for chave in ("pdf_texto_sessao", "arquivo_pdf", "novo_cpf", "email_entrada", "editar_descricao"):
        assert chave not in app.session_state
