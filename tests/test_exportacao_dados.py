"""Exportação da conta, com banco fictício."""
import ast
import inspect
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from trixter.exportacao import (
    CATEGORIAS,
    CONTA,
    ENVIOS,
    GASTOS,
    ORCAMENTOS,
    PLANEJAMENTOS,
    RECEITAS,
    RECORRENCIAS,
    ExportacaoIndisponivel,
    concluir_exportacao,
    exportar_conta,
    serializar,
    sessao_autorizada,
)
from trixter.acesso import abrir_sessao
from trixter.senha import gerar_hash_senha
from trixter.sessao import (
    arquivo_autorizado,
    descartar_exportacao,
    encerrar_sessao_local,
    guardar_exportacao,
)
from trixter.seguranca import _exibir_exportacao, exibir_seguranca

SENHA = "Atual123!"
HASH = gerar_hash_senha(SENHA)
ENTRADA = datetime(2026, 10, 16, 12, 0, 0)
DIA = date(2026, 10, 1)


def _perfil(identificador, email, demo=0):
    dados = {coluna: None for coluna in CONTA}
    dados.update(
        id_usuario=identificador,
        tipo_pessoa="Pessoa Física",
        data_entrada=ENTRADA,
        email=email,
        nome="José",
        renda_mensal=Decimal("19.90"),
        objetivo_financeiro="Reserva",
        data_objetivo=DIA,
        conta_demo=demo,
        onboarding_concluido=1,
        receber_relatorio_mensal=0,
        receber_alertas=0,
        receber_resumo_semanal=0,
    )
    return dados


class _Banco:
    def __init__(self):
        self.auth = {}
        self.contas = {}
        self.filhas = {
            "dbo.categorias": {},
            "dbo.receitas": {},
            "dbo.gastos": {},
            "dbo.orcamentos": {},
            "dbo.recorrencias": {},
            "dbo.planejamentos": {},
            "dbo.envios_automaticos": {},
        }
        self.comandos = []
        self.falhar = None

    def adicionar(self, perfil, senha=HASH, **filhas):
        identificador = perfil["id_usuario"]
        self.auth[identificador] = {
            "senha": senha,
            "conta_demo": perfil["conta_demo"],
        }
        self.contas[identificador] = dict(perfil)
        for tabela, linhas in filhas.items():
            self.filhas[tabela][identificador] = list(linhas)


class _Cursor:
    def __init__(self, banco):
        self.banco = banco
        self.sql = ""
        self.params = ()
        self._uma = None
        self._varias = []

    def execute(self, sql, *params):
        if len(params) == 1 and isinstance(params[0], (tuple, list)):
            params = tuple(params[0])
        self.sql = " ".join(sql.split())
        self.params = params
        self.banco.comandos.append((self.sql, self.params))
        self._uma = None
        self._varias = []
        if self.banco.falhar and self.banco.falhar in self.sql:
            raise RuntimeError("falha ficticia")
        identificador = self.params[0] if self.params else None
        if self.sql.startswith("SELECT senha"):
            auth = self.banco.auth.get(identificador)
            self._uma = None if auth is None else (auth["senha"], auth["conta_demo"])
            return
        if "FROM dbo.usuarios" in self.sql:
            conta = self.banco.contas.get(identificador)
            self._uma = None if conta is None else tuple(conta[coluna] for coluna in CONTA)
            return
        for tabela, linhas in self.banco.filhas.items():
            if f"FROM {tabela}" in self.sql:
                self._varias = [
                    tuple(linha[coluna] for coluna in _colunas(tabela))
                    for linha in linhas.get(identificador, [])
                ]
                return
        raise AssertionError(self.sql)

    def fetchone(self):
        return self._uma

    def fetchall(self):
        return list(self._varias)

    def close(self):
        return None


def _colunas(tabela):
    return {
        "dbo.categorias": CATEGORIAS,
        "dbo.receitas": RECEITAS,
        "dbo.gastos": GASTOS,
        "dbo.orcamentos": ORCAMENTOS,
        "dbo.recorrencias": RECORRENCIAS,
        "dbo.planejamentos": PLANEJAMENTOS,
        "dbo.envios_automaticos": ENVIOS,
    }[tabela]


def test_exportacao_isola_a_conta_e_omite_credenciais():
    banco = _Banco()
    banco.adicionar(
        _perfil("conta-a", "conta-a@example.com"),
        **{
            "dbo.receitas": [{
                "id_transacao": "t-a",
                "id_usuario": "conta-a",
                "id_recorrencia": None,
                "data": DIA,
                "categoria": "Salário",
                "descricao": "Fictício",
                "valor": Decimal("19.90"),
                "classificacao": None,
                "cliente": None,
            }],
            "dbo.envios_automaticos": [{
                "tipo": "relatorio_mensal",
                "periodo": DIA,
                "status": "enviado",
                "tentativas": 1,
                "criado_em": ENTRADA,
                "enviado_em": ENTRADA,
            }],
        },
    )
    banco.adicionar(_perfil("conta-b", "vizinha@example.com"))
    documento = exportar_conta(_Cursor(banco), "conta-a")
    texto = serializar(documento).decode("utf-8")
    assert documento["conta"]["email"] == "conta-a@example.com"
    assert "vizinha@example.com" not in texto
    assert "$2b$" not in texto
    assert "senha" not in texto.casefold()
    assert "message_id" not in texto
    assert "ultimo_erro" not in texto
    assert "limites_acesso" not in texto
    for sql, params in banco.comandos:
        assert "WHERE id_usuario = ?" in sql
        assert params == ("conta-a",)
        assert "senha" not in sql
        assert "message_id" not in sql
        assert "ultimo_erro" not in sql
        assert "limites_acesso" not in sql
    assert set(documento["envios_automaticos"][0]) == set(ENVIOS)


def test_senha_incorreta_nao_consulta_o_restante():
    banco = _Banco()
    banco.adicionar(_perfil("conta-a", "conta-a@example.com"))
    situacao, arquivo = concluir_exportacao(
        _Cursor(banco), "conta-a", "Errada123!", False, True,
    )
    assert situacao == "senha"
    assert arquivo is None
    assert len(banco.comandos) == 1
    assert banco.comandos[0][0].startswith("SELECT senha")


def test_sessao_expirada_nao_gera_arquivo_e_encerra_a_aba():
    estado = {
        "usuario_logado": True,
        "usuario_atual": {"id_usuario": "conta-a", "credencial_versao": 1},
        "exportacao_conta_json": b'{"conta":"antiga"}',
        "senha_exportacao": "Atual123!",
    }

    class _CursorSessao:
        def execute(self, sql, *args):
            self.sql = sql

        def fetchone(self):
            return (2,)

        def close(self):
            return None

    class _Conexao:
        def cursor(self):
            return _CursorSessao()

        def rollback(self):
            return None

        def close(self):
            return None

    assert sessao_autorizada(lambda: _Conexao(), estado) is False
    assert estado["usuario_logado"] is False
    assert estado["usuario_atual"] is None
    assert "exportacao_conta_json" not in estado
    assert "senha_exportacao" not in estado
    situacao, arquivo = concluir_exportacao(
        _Cursor(_Banco()), "conta-a", SENHA, False, False,
    )
    assert situacao == "sessao"
    assert arquivo is None


def test_demonstracao_exporta_sem_senha_e_conta_real_nao_herda_esse_atalho():
    banco = _Banco()
    banco.adicionar(_perfil("demo", "demo@demo.trixter.local", demo=1))
    banco.adicionar(_perfil("real", "real@example.com"))
    situacao, arquivo = concluir_exportacao(
        _Cursor(banco), "demo", "senha-que-nao-existe", True, True,
    )
    assert situacao == "ok"
    texto = arquivo.decode("utf-8")
    assert "demo@demo.trixter.local" in texto
    assert "$2b$" not in texto
    recusada, vazio = concluir_exportacao(_Cursor(banco), "real", "", True, True)
    assert recusada == "senha"
    assert vazio is None
    misturada, nada = concluir_exportacao(_Cursor(banco), "demo", "", False, True)
    assert misturada == "recusada"
    assert nada is None


def test_conta_sem_movimentacao_gera_listas_vazias():
    banco = _Banco()
    banco.adicionar(_perfil("conta-a", "conta-a@example.com"))
    documento = exportar_conta(_Cursor(banco), "conta-a")
    for nome in (
        "categorias", "receitas", "gastos", "orcamentos",
        "recorrencias", "planejamentos", "envios_automaticos",
    ):
        assert documento[nome] == []
    assert documento["conta"]["id_usuario"] == "conta-a"


def test_serializa_data_e_decimal_sem_perder_o_texto():
    banco = _Banco()
    banco.adicionar(_perfil("conta-a", "conta-a@example.com"))
    texto = serializar(exportar_conta(_Cursor(banco), "conta-a")).decode("utf-8")
    carregado = json.loads(texto)
    assert carregado["conta"]["renda_mensal"] == "19.90"
    assert carregado["conta"]["data_entrada"] == "2026-10-16T12:00:00"
    assert carregado["conta"]["data_objetivo"] == "2026-10-01"
    assert "José" in texto
    assert "\\u00e9" not in texto


def test_falha_de_consulta_nao_devolve_arquivo_parcial():
    banco = _Banco()
    banco.adicionar(
        _perfil("conta-a", "conta-a@example.com"),
        **{"dbo.categorias": [{"id_usuario": "conta-a", "nome": "Casa", "tipo": "gasto"}]},
    )
    banco.falhar = "dbo.receitas"
    with pytest.raises(ExportacaoIndisponivel):
        exportar_conta(_Cursor(banco), "conta-a")
    situacao, arquivo = concluir_exportacao(
        _Cursor(banco), "conta-a", SENHA, False, True,
    )
    assert situacao == "falha"
    assert arquivo is None
    assert any("dbo.categorias" in sql for sql, _params in banco.comandos)
    assert not any("dbo.gastos" in sql for sql, _params in banco.comandos)


def test_logout_apaga_o_arquivo_e_a_senha_digitada():
    estado = {
        "usuario_logado": True,
        "usuario_atual": {"id_usuario": "conta-a"},
        "exportacao_conta_json": b"{}",
        "senha_exportacao": SENHA,
        "exportacao_conta_aviso": "senha",
        "_limpar_senha_exportacao": True,
    }
    encerrar_sessao_local(estado)
    assert estado["usuario_logado"] is False
    for chave in (
        "exportacao_conta_json",
        "senha_exportacao",
        "exportacao_conta_aviso",
        "_limpar_senha_exportacao",
    ):
        assert chave not in estado


def test_exportacao_fica_entre_acesso_e_exclusao():
    fonte = inspect.getsource(exibir_seguranca)
    primeira = fonte.index("_exibir_exportacao")
    segunda = fonte.index("_exibir_exportacao", primeira + 1)
    assert "em_demonstracao" in fonte[:primeira]
    assert fonte.index("Informações de acesso") < segunda < fonte.index("Excluir conta")
    entrega = inspect.getsource(_exibir_exportacao)
    assert "st.download_button" in entrega
    assert 'file_name="trixter-dados-conta.json"' in entrega
    assert "if arquivo:" in entrega
    assert "on_click=descartar_exportacao" in entrega
    assert entrega.index("guardar_exportacao") < entrega.index("st.download_button")


def _app_exportacao(demo=False):
    marca = "True" if demo else "False"
    demo_bit = "1" if demo else "0"
    return AppTest.from_string(
        """
import streamlit as st
from trixter.exportacao import CONTA
from trixter.seguranca import exibir_seguranca
from trixter.senha import gerar_hash_senha
st.session_state.usuario_logado = True
st.session_state.usuario_atual = {
    "id_usuario": "conta-a",
    "email": "conta-a@example.com",
    "credencial_versao": 1,
    "conta_demo": """ + marca + """,
}
if "sqls" not in st.session_state:
    st.session_state.sqls = []
HASH = gerar_hash_senha("Atual123!")
PERFIL = {coluna: None for coluna in CONTA}
PERFIL.update(
    id_usuario="conta-a",
    email="conta-a@example.com",
    nome="José",
    conta_demo=""" + demo_bit + """,
)
class Cursor:
    def execute(self, sql, *args):
        self.sql = " ".join(sql.split())
        st.session_state.sqls.append(self.sql)
    def fetchone(self):
        sql = getattr(self, "sql", "")
        if "credencial_versao" in sql:
            return (1,)
        if sql.startswith("SELECT senha"):
            return (HASH, """ + demo_bit + """)
        if "FROM dbo.usuarios" in sql:
            return tuple(PERFIL[coluna] for coluna in CONTA)
        return None
    def fetchall(self):
        return []
    def close(self):
        return None
class Conexao:
    def cursor(self):
        return Cursor()
    def commit(self):
        return None
    def rollback(self):
        return None
    def close(self):
        return None
exibir_seguranca(lambda: Conexao())
""",
        default_timeout=30,
    ).run()


def test_tela_recusa_senha_incorreta_sem_arquivo():
    app = _app_exportacao()
    app.text_input(key="senha_exportacao").set_value("Errada123!")
    app.button(key="btn_exportar_dados").click().run()
    assert not app.exception
    assert any("Senha atual incorreta." in item.value for item in app.error)
    assert any(item.value == "Exportar meus dados" for item in app.subheader)
    senha_restante = (
        app.session_state["senha_exportacao"]
        if "senha_exportacao" in app.session_state
        else None
    )
    assert senha_restante in (None, "")
    assert "Errada123!" not in " ".join(app.session_state.sqls)
    assert "exportacao_conta_json" not in app.session_state


def test_tela_da_demonstracao_exporta_sem_campo_de_senha():
    app = _app_exportacao(demo=True)
    assert all(campo.key != "senha_exportacao" for campo in app.text_input)
    app.button(key="btn_exportar_dados").click().run()
    assert not app.exception
    assert any(item.value == "Exportar meus dados" for item in app.subheader)
    guardado = app.session_state.exportacao_conta_json
    assert set(guardado) == {"id_usuario", "arquivo"}
    assert guardado["id_usuario"] == "conta-a"
    texto = guardado["arquivo"].decode("utf-8")
    assert "conta-a@example.com" in texto
    assert "$2b$" not in texto
    assert "senha" not in texto.casefold()


class _Estado(dict):
    def __getattr__(self, chave):
        return self[chave]

    def __setattr__(self, chave, valor):
        self[chave] = valor


class _Sessao:
    def __init__(self, estado):
        self.session_state = estado


def _funcoes_gerenciador(*nomes):
    arvore = ast.parse(Path("Gerenciador de Gastos V2.py").read_text(encoding="utf-8"))
    corpo = [
        no for no in arvore.body
        if isinstance(no, ast.FunctionDef) and no.name in nomes
    ]
    escopo = {"descartar_exportacao": descartar_exportacao}
    exec(compile(ast.Module(body=corpo, type_ignores=[]), "demo", "exec"), escopo)
    return escopo


def test_entrada_na_demo_descarta_a_exportacao_da_conta_real():
    estado = _Estado(
        usuario_atual={
            "id_usuario": "u-real",
            "tipo_pessoa": "Pessoa Física",
            "email": "pessoa@example.com",
        },
        exportacao_conta_json={"id_usuario": "u-real", "arquivo": b'{"conta":"real"}'},
        exportacao_conta_aviso=None,
    )
    escopo = _funcoes_gerenciador("entrar_conta_demo")
    escopo["st"] = _Sessao(estado)
    escopo["criar_demo_temporaria"] = lambda identificador, tipo: {
        "id_usuario": "u-demo",
        "conta_demo": True,
        "senha": "nao-deve-passar",
        "tipo_pessoa": tipo,
    }
    escopo["entrar_conta_demo"]()
    assert estado["usuario_atual"]["id_usuario"] == "u-demo"
    assert "exportacao_conta_json" not in estado
    assert "exportacao_conta_aviso" not in estado


def test_falha_ao_entrar_na_demo_preserva_a_exportacao_real():
    estado = _Estado(
        usuario_atual={"id_usuario": "u-real", "tipo_pessoa": "Pessoa Física"},
        exportacao_conta_json={"id_usuario": "u-real", "arquivo": b'{"conta":"real"}'},
    )
    escopo = _funcoes_gerenciador("entrar_conta_demo")
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
    assert estado["usuario_atual"]["id_usuario"] == "u-real"
    assert estado["exportacao_conta_json"]["arquivo"] == b'{"conta":"real"}'


def test_retorno_da_demo_descarta_a_exportacao_da_demonstracao():
    estado = _Estado(
        usuario_atual={"id_usuario": "u-demo", "conta_demo": True},
        usuario_original={"id_usuario": "u-real", "email": "pessoa@example.com"},
        exportacao_conta_json={"id_usuario": "u-demo", "arquivo": b'{"conta":"demo"}'},
        exportacao_conta_aviso="falha",
    )
    escopo = _funcoes_gerenciador("voltar_conta_original")
    escopo.update(
        st=_Sessao(estado),
        excluir_demo_temporaria=lambda identificador: None,
        limpar_pdf_da_conta=lambda estado, identificador: None,
    )
    escopo["voltar_conta_original"]()
    assert estado["usuario_atual"]["id_usuario"] == "u-real"
    assert "exportacao_conta_json" not in estado
    assert "exportacao_conta_aviso" not in estado


def test_nova_sessao_descarta_a_exportacao_do_usuario_anterior():
    estado = {
        "usuario_atual": {"id_usuario": "antigo"},
        "usuario_logado": False,
        "exportacao_conta_json": {"id_usuario": "antigo", "arquivo": b"{}"},
        "exportacao_conta_aviso": "senha",
    }
    abrir_sessao({"id_usuario": "novo", "email": "novo@example.com"}, "menu", estado)
    assert estado["usuario_atual"]["id_usuario"] == "novo"
    assert "exportacao_conta_json" not in estado
    assert "exportacao_conta_aviso" not in estado


def test_proprietario_divergente_nao_entrega_o_arquivo():
    estado = {
        "exportacao_conta_json": {
            "id_usuario": "outra-conta",
            "arquivo": b'{"conta":"alheia"}',
        },
        "exportacao_conta_aviso": None,
    }
    assert arquivo_autorizado(estado, "conta-a") is None
    assert "exportacao_conta_json" not in estado
    assert "exportacao_conta_aviso" not in estado


def test_tela_descarta_json_de_outro_proprietario():
    app = _app_exportacao()
    app.session_state.exportacao_conta_json = {
        "id_usuario": "outra-conta",
        "arquivo": b'{"conta":"alheia"}',
    }
    app.run()
    assert not app.exception
    assert "exportacao_conta_json" not in app.session_state


def test_download_descarta_os_bytes_depois_de_entregar():
    estado = {}
    guardar_exportacao(estado, "conta-a", b'{"conta":"autorizada"}')
    entregue = arquivo_autorizado(estado, "conta-a")
    assert entregue == b'{"conta":"autorizada"}'
    descartar_exportacao(estado)
    assert "exportacao_conta_json" not in estado
    assert arquivo_autorizado(estado, "conta-a") is None
    entrega = inspect.getsource(_exibir_exportacao)
    botao = entrega.index("st.download_button")
    assert entrega.index("data=arquivo") < botao or "data=arquivo" in entrega[botao:]
    assert "on_click=descartar_exportacao" in entrega[botao:]


def test_json_traz_gerado_em_em_utc():
    banco = _Banco()
    banco.adicionar(_perfil("conta-a", "conta-a@example.com"))
    fixo = datetime(2026, 10, 16, 17, 51, 30, tzinfo=timezone(timedelta(hours=-3)))
    documento = exportar_conta(_Cursor(banco), "conta-a", agora=lambda: fixo)
    assert documento["gerado_em"] == "2026-10-16T20:51:30+00:00"
    assert '"gerado_em": "2026-10-16T20:51:30+00:00"' in serializar(documento).decode("utf-8")
    assert all("gerado_em" not in sql for sql, _params in banco.comandos)
    banco_agora = _Banco()
    banco_agora.adicionar(_perfil("conta-a", "conta-a@example.com"))
    outro = exportar_conta(_Cursor(banco_agora), "conta-a")
    lido = datetime.fromisoformat(outro["gerado_em"])
    assert lido.utcoffset() == timedelta(0)


def test_exportacao_autorizada_continua_disponivel_para_o_mesmo_usuario():
    banco = _Banco()
    banco.adicionar(_perfil("conta-a", "conta-a@example.com"))
    situacao, arquivo = concluir_exportacao(
        _Cursor(banco), "conta-a", SENHA, False, True,
    )
    assert situacao == "ok"
    assert b"conta-a@example.com" in arquivo
    assert b"gerado_em" in arquivo
    estado = {}
    guardar_exportacao(estado, "conta-a", arquivo)
    assert set(estado["exportacao_conta_json"]) == {"id_usuario", "arquivo"}
    assert arquivo_autorizado(estado, "conta-a") == arquivo
