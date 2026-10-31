"""Ciclo da conta demonstrativa, com dados fictícios e sem banco real."""
import ast
import pytest
from datetime import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

from trixter.demo import criar_demo_pj, hash_senha_demo
from trixter.demo_expurgo import excluir_demonstracao
from trixter.seguranca import (
    AVISO_DEMO,
    concluir_alteracao_email,
    em_demonstracao,
    pedir_confirmacao_email,
)
from trixter.senha import senha_confere
from trixter.sessao import descartar_exportacao, encerrar_sessao_local, limpar_pdf_da_conta


def _funcoes(*nomes):
    arvore = ast.parse(Path("Gerenciador de Gastos V2.py").read_text(encoding="utf-8"))
    corpo = [
        no for no in arvore.body
        if isinstance(no, ast.FunctionDef) and no.name in nomes
    ]
    escopo = {"descartar_exportacao": descartar_exportacao}
    exec(compile(ast.Module(body=corpo, type_ignores=[]), "demo", "exec"), escopo)
    return escopo


def _senha_gravada(comandos):
    sql, args = next(
        item for item in comandos if "INSERT INTO dbo.usuarios" in item[0]
    )
    colunas = sql.split("(", 1)[1].split(")", 1)[0]
    nomes = [coluna.strip() for coluna in colunas.split(",")]
    if len(args) == 1 and isinstance(args[0], tuple):
        args = args[0]
    return dict(zip(nomes, args))["senha"]


class _Estado(dict):
    def __getattr__(self, chave):
        return self[chave]

    def __setattr__(self, chave, valor):
        self[chave] = valor


class _Sessao:
    def __init__(self, estado):
        self.session_state = estado


def test_demo_pj_grava_hash_e_nao_devolve_senha():
    from tests.test_demo import Conexao

    conexao = Conexao()
    usuario = criar_demo_pj(lambda: conexao, datetime(2026, 12, 28).date())
    gravada = _senha_gravada(conexao.comandos)
    assert gravada.startswith("$2")
    assert senha_confere("senha-ficticia", gravada) is False
    assert "senha" not in usuario
    assert usuario["email"].endswith("@demo.trixter.local")
    assert usuario["conta_demo"] is True


def test_hash_da_demo_nao_repete_a_senha_aleatoria():
    primeiro = hash_senha_demo()
    segundo = hash_senha_demo()
    assert primeiro.startswith("$2") and segundo.startswith("$2")
    assert primeiro != segundo


def test_demo_pf_nao_copia_a_senha_do_modelo():
    from trixter.demo import hash_senha_demo as hash_real

    colunas = [
        "id_usuario", "senha", "tipo_pessoa", "email", "nome", "cpf",
        "renda_mensal", "nome_empresa", "cnpj", "faturamento_mensal",
        "objetivo_financeiro", "valor_objetivo", "data_objetivo",
        "valor_acumulado_meta",
    ]
    linha = (
        "00000000-0000-0000-0000-000000000001", "segredo-em-claro",
        "Pessoa Física", "modelo@example.com", "Modelo", "00000000000",
        1000, None, None, None, None, 0, None, 0,
    )

    class Cursor:
        def __init__(self):
            self.comandos = []
            self.description = [(coluna,) for coluna in colunas]

        def execute(self, sql, *args):
            self.comandos.append((" ".join(sql.split()), args))

        def fetchone(self):
            return linha

    class Conexao:
        def __init__(self):
            self.cursor_memoria = Cursor()
            self.commits = 0
            self.rollbacks = 0

        def cursor(self):
            return self.cursor_memoria

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

    conexao = Conexao()
    escopo = _funcoes("_preencher_demo_temporaria")
    escopo.update(
        reservar_email=lambda *args: True,
        hash_senha_demo=hash_real,
        datetime=datetime,
        uuid=__import__("uuid"),
        ID_CONTA_DEMO="00000000-0000-0000-0000-000000000001",
    )
    usuario = escopo["_preencher_demo_temporaria"](conexao, conexao.cursor())
    gravada = _senha_gravada(conexao.cursor_memoria.comandos)
    assert gravada.startswith("$2")
    assert gravada != "segredo-em-claro"
    assert "senha" not in usuario
    assert usuario["conta_demo"] is True
    assert conexao.commits == 1 and conexao.rollbacks == 0
    assert all(
        "u-real" not in args
        for _sql, args in conexao.cursor_memoria.comandos
    )


def test_demo_pf_sem_modelo_interrompe_antes_de_gravar_e_faz_rollback():
    from unittest.mock import Mock
    conexao = Mock()
    cursor = conexao.cursor.return_value
    cursor.fetchone.return_value = None
    escopo = _funcoes("criar_demo_temporaria", "_preencher_demo_temporaria")
    escopo.update(conectar_banco=lambda: conexao, ID_CONTA_DEMO="modelo-ficticio")
    with pytest.raises(ValueError, match="conta modelo"):
        escopo["criar_demo_temporaria"]("usuario-ficticio")
    assert cursor.execute.call_count == 1
    assert "SELECT *" in cursor.execute.call_args.args[0]
    conexao.rollback.assert_called_once_with()
    conexao.commit.assert_not_called()
    cursor.close.assert_called_once_with()
    conexao.close.assert_called_once_with()


def test_clique_demo_sem_modelo_mostra_aviso_sem_rerun():
    from unittest.mock import Mock
    arvore = ast.parse(Path("Gerenciador de Gastos V2.py").read_text(encoding="utf-8"))
    bloco = next(n for n in ast.walk(arvore) if isinstance(n, ast.Try)
                 and any(isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
                         and isinstance(item.value.func, ast.Name)
                         and item.value.func.id == "entrar_conta_demo" for item in n.body))
    st = Mock()
    escopo = {"st": st, "entrar_conta_demo": Mock(side_effect=ValueError("modelo ausente"))}
    exec(compile(ast.Module(body=[bloco], type_ignores=[]), "demo", "exec"), escopo)
    st.warning.assert_called_once()
    st.rerun.assert_not_called()


def test_falha_na_criacao_preserva_usuario_original():
    estado = _Estado(
        usuario_atual={
            "id_usuario": "u-real",
            "tipo_pessoa": "Pessoa Física",
            "email": "pessoa@example.com",
        },
        usuario_original={"id_usuario": "anterior"},
    )
    escopo = _funcoes("entrar_conta_demo")
    escopo["st"] = _Sessao(estado)

    def criar(*_args):
        raise RuntimeError("falha ficticia")

    escopo["criar_demo_temporaria"] = criar
    try:
        escopo["entrar_conta_demo"]()
    except RuntimeError as erro:
        assert str(erro) == "falha ficticia"
    else:
        raise AssertionError("a falha foi ignorada")
    assert estado["usuario_original"]["id_usuario"] == "anterior"
    assert estado["usuario_atual"]["id_usuario"] == "u-real"


def test_entrada_na_demo_so_troca_a_sessao_depois_do_sucesso():
    estado = _Estado(
        usuario_atual={
            "id_usuario": "u-real",
            "tipo_pessoa": "Pessoa Jurídica",
            "email": "pessoa@example.com",
            "nome_empresa": "Empresa Real",
        },
    )
    escopo = _funcoes("entrar_conta_demo")
    escopo["st"] = _Sessao(estado)

    def criar(identificador, tipo):
        assert identificador == "u-real"
        return {
            "id_usuario": "u-demo",
            "conta_demo": True,
            "senha": "nao-deve-passar",
            "tipo_pessoa": tipo,
            "email": "u-demo@demo.trixter.local",
            "nome_empresa": "Aurora Serviços — Demo",
        }

    escopo["criar_demo_temporaria"] = criar
    escopo["entrar_conta_demo"]()
    assert estado["usuario_original"]["id_usuario"] == "u-real"
    assert estado["usuario_atual"]["id_usuario"] == "u-demo"
    assert "senha" not in estado["usuario_atual"]
    assert estado["tela_atual"] == "menu"


def test_operacoes_sensiveis_recusam_a_demonstracao():
    estado = {
        "usuario_atual": {"id_usuario": "u-demo", "conta_demo": True},
        "verificacao_email": {"codigo": "123456", "email": "pessoa@example.com"},
    }

    def conectar():
        raise AssertionError("banco indevido")

    assert em_demonstracao(estado) is True
    assert em_demonstracao({"usuario_atual": {"id_usuario": "u-real"}}) is False
    assert pedir_confirmacao_email(
        estado, conectar, "u-demo", "novo@example.com", "novo@example.com",
        "Senha123!", None, "203.0.113.10",
    ) == "demo"
    assert concluir_alteracao_email(
        estado, conectar, "u-demo", "123456", None, "203.0.113.10",
    )[0] == "demo"
    assert estado["verificacao_email"]["codigo"] == "123456"


def test_tela_de_seguranca_nao_abre_operacoes_na_demo():
    app = AppTest.from_string(
        """
import streamlit as st
from trixter.seguranca import exibir_seguranca
st.session_state.usuario_logado = True
st.session_state.usuario_atual = {
    "id_usuario": "u-demo",
    "email": "u-demo@demo.trixter.local",
    "credencial_versao": 1,
    "conta_demo": True,
}
st.session_state.sqls = []
class Cursor:
    def execute(self, sql, *args):
        self.sql = " ".join(sql.split())
        st.session_state.sqls.append(self.sql)
    def fetchone(self):
        if "credencial_versao" in getattr(self, "sql", ""):
            return (1,)
        return None
    def close(self):
        pass
class Conexao:
    def cursor(self):
        return Cursor()
    def commit(self):
        pass
    def rollback(self):
        pass
    def close(self):
        pass
exibir_seguranca(lambda: Conexao())
""",
        default_timeout=30,
    ).run()
    assert not app.exception
    assert any("demonstração" in item.value for item in app.info)
    assert AVISO_DEMO in [item.value for item in app.info]
    assert all(botao.key != "btn_excluir_conta" for botao in app.button)
    assert all(botao.key != "btn_alterar_senha" for botao in app.button)
    assert all(botao.key != "btn_alterar_email" for botao in app.button)
    assert not any("DELETE" in sql for sql in app.session_state.sqls)


class _ConexaoExclusao:
    def __init__(self, falhar=False):
        self.comandos = []
        self.commits = 0
        self.rollbacks = 0
        self.fechada = False
        self.falhar = falhar

    def cursor(self):
        return self

    def execute(self, sql, *args):
        texto = " ".join(sql.split())
        if self.falhar and "envios_automaticos" in texto:
            raise RuntimeError("falha ficticia")
        self.comandos.append((texto, args))

    def fetchone(self):
        texto, args = self.comandos[-1]
        if "sp_getapplock" in texto:
            return (0,)
        if "UPDLOCK" in texto:
            return (args[0],)
        return None

    def close(self):
        self.fechada = True

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_exclusao_da_demo_apaga_envios_e_preserva_a_conta_real():
    conexao = _ConexaoExclusao()
    escopo = _funcoes("excluir_demo_temporaria")
    escopo["conectar_banco"] = lambda: conexao
    escopo["excluir_demonstracao"] = excluir_demonstracao
    escopo["excluir_demo_temporaria"]("u-demo")
    apagamentos = [(sql, args) for sql, args in conexao.comandos if sql.startswith("DELETE")]
    textos = [sql for sql, _args in apagamentos]
    assert "DELETE FROM dbo.envios_automaticos WHERE id_usuario = ?" in textos
    assert textos[-1] == "DELETE FROM dbo.usuarios WHERE id_usuario = ?"
    assert all(args == ("u-demo",) for _sql, args in apagamentos)
    assert any("sp_getapplock" in sql for sql, _args in conexao.comandos)
    assert not any("data_entrada" in sql for sql, _args in conexao.comandos)
    assert conexao.commits == 1 and conexao.rollbacks == 0
    assert conexao.fechada is True


def test_falha_na_exclusao_da_demo_desfaz_a_transacao():
    conexao = _ConexaoExclusao(falhar=True)
    escopo = _funcoes("excluir_demo_temporaria")
    escopo["conectar_banco"] = lambda: conexao
    escopo["excluir_demonstracao"] = excluir_demonstracao
    try:
        escopo["excluir_demo_temporaria"]("u-demo")
    except RuntimeError as erro:
        assert str(erro) == "falha ficticia"
    else:
        raise AssertionError("a falha foi ignorada")
    assert conexao.commits == 0 and conexao.rollbacks == 1
    assert conexao.fechada is True
    assert not any("u-real" in args for _sql, args in conexao.comandos)


class _Area:
    def empty(self):
        return None

    def markdown(self, *_args, **_kwargs):
        return None


class _Estilo:
    ESTILO_OCULTAR_NAVEGACAO = "ocultar"

    @staticmethod
    def folha(valor):
        return valor


def _sair(estado, excluir):
    escopo = _funcoes("sair_conta")
    escopo.update(
        st=_Sessao(estado),
        excluir_demo_temporaria=excluir,
        encerrar_sessao_local=encerrar_sessao_local,
        estilo=_Estilo,
    )
    escopo["sair_conta"](_Area(), _Area())
    return escopo


def test_logout_com_demo_ativa_apaga_so_a_copia():
    estado = _Estado(
        usuario_logado=True,
        usuario_atual={
            "id_usuario": "u-demo",
            "conta_demo": True,
            "email": "u-demo@demo.trixter.local",
        },
        usuario_original={"id_usuario": "u-real", "email": "pessoa@example.com"},
        pdf_texto_sessao={"usuario": "u-demo", "texto": "extrato ficticio", "conteudo": "abc"},
    )
    apagados = []
    _sair(estado, lambda identificador: apagados.append(identificador))
    assert apagados == ["u-demo"]
    assert estado["usuario_logado"] is False
    assert estado["usuario_atual"] is None
    assert "usuario_original" not in estado
    assert "pdf_texto_sessao" not in estado


def test_falha_no_logout_da_demo_preserva_o_contexto():
    estado = _Estado(
        usuario_logado=True,
        usuario_atual={"id_usuario": "u-demo", "conta_demo": True},
        usuario_original={"id_usuario": "u-real", "email": "pessoa@example.com"},
        pdf_texto_sessao={"usuario": "u-demo", "texto": "extrato ficticio", "conteudo": "abc"},
    )

    def excluir(_identificador):
        raise RuntimeError("detalhe interno")

    _sair(estado, excluir)
    assert estado["usuario_logado"] is True
    assert estado["usuario_atual"]["id_usuario"] == "u-demo"
    assert estado["usuario_original"]["id_usuario"] == "u-real"
    assert estado["pdf_texto_sessao"]["texto"] == "extrato ficticio"
    assert estado["aviso_saida_demo"] == "Não foi possível encerrar a demonstração. Tente novamente."
    assert "detalhe interno" not in estado["aviso_saida_demo"]


def test_logout_sem_demo_nao_apaga_a_conta_real():
    estado = _Estado(
        usuario_logado=True,
        usuario_atual={"id_usuario": "u-real", "email": "pessoa@example.com"},
    )
    apagados = []
    _sair(estado, lambda identificador: apagados.append(identificador))
    assert apagados == []
    assert estado["usuario_logado"] is False
    assert estado["usuario_atual"] is None


def test_retorno_normal_restaura_a_conta_real_e_limpa_o_pdf_da_demo():
    estado = _Estado(
        usuario_atual={"id_usuario": "u-demo", "conta_demo": True},
        usuario_original={"id_usuario": "u-real", "email": "pessoa@example.com"},
        pdf_texto_sessao={"usuario": "u-demo", "texto": "comprovante ficticio", "conteudo": "def"},
        arquivo_pdf=b"%PDF-demo",
        tela_atual="importar_pdf",
    )
    apagados = []
    escopo = _funcoes("voltar_conta_original")
    escopo.update(
        st=_Sessao(estado),
        excluir_demo_temporaria=lambda identificador: apagados.append(identificador),
        limpar_pdf_da_conta=limpar_pdf_da_conta,
    )
    escopo["voltar_conta_original"]()
    assert apagados == ["u-demo"]
    assert estado["usuario_atual"]["id_usuario"] == "u-real"
    assert estado["usuario_original"] is None
    assert estado["tela_atual"] == "menu"
    assert "pdf_texto_sessao" not in estado
    assert "arquivo_pdf" not in estado
