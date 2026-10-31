from datetime import datetime, timedelta

import pytest
from streamlit.testing.v1 import AppTest

from trixter import limite_acesso as limite
from trixter.limite_acesso import MENSAGEM_LOGIN

AGORA = datetime(2026, 10, 9, 12, 0, 0)
IP = "203.0.113.9"
OUTRO_IP = "203.0.113.10"
EMAIL = "a@example.com"


class CursorMemoria:
    def __init__(self):
        self.linhas = {}
        self.chamadas = []
        self._linha = None
        self.rowcount = -1

    def execute(self, sql, *params):
        texto = " ".join(sql.split())
        self.chamadas.append((texto, params))
        if "sp_getapplock" in texto:
            self._linha = (0,)
            return
        if texto.startswith("DELETE") and "janela_inicio" in texto:
            limite_data = params[0]
            self.linhas = {chave: valor for chave, valor in self.linhas.items() if valor[1] >= limite_data}
        elif texto.startswith("DELETE"):
            self.linhas.pop((params[0], params[1]), None)
        elif texto.startswith("SELECT"):
            self._linha = self.linhas.get((params[0], params[1]))
        elif texto.startswith("UPDATE"):
            tentativas, inicio, ate, fluxo, chave = params
            self.linhas[(fluxo, chave)] = (tentativas, inicio, ate)
            self.rowcount = 1
        elif texto.startswith("INSERT"):
            fluxo, chave, tentativas, inicio, ate = params
            self.linhas[(fluxo, chave)] = (tentativas, inicio, ate)
            self.rowcount = 1
        else:
            raise AssertionError(texto)

    def fetchone(self):
        return self._linha


class CursorAusente:
    def execute(self, sql, *params):
        raise RuntimeError("Invalid object name 'dbo.limites_acesso' (208)")


class CursorTimeout:
    def execute(self, sql, *params):
        raise RuntimeError("timeout de conexao")


def _email_no_sql(cursor, email):
    for sql, params in cursor.chamadas:
        if email in sql or any(email in str(valor) for valor in params):
            return True
    return False


def test_oito_falhas_de_login_bloqueiam_o_par_e_outro_ip_passa():
    cursor = CursorMemoria()
    for _ in range(7):
        assert limite.bloqueado(cursor, "login", EMAIL, IP, AGORA) is False
        limite.consumir(cursor, "login", EMAIL, IP, AGORA)
    assert limite.bloqueado(cursor, "login", EMAIL, IP, AGORA) is False
    limite.consumir(cursor, "login", EMAIL, IP, AGORA)
    assert limite.bloqueado(cursor, "login", EMAIL, IP, AGORA) is True
    assert limite.bloqueado(cursor, "login", EMAIL, OUTRO_IP, AGORA) is False
    assert not _email_no_sql(cursor, EMAIL)


def test_senha_certa_zera_o_par_e_preserva_o_ip():
    cursor = CursorMemoria()
    for _ in range(8):
        limite.consumir(cursor, "login", EMAIL, IP, AGORA)
    limite.liberar_par(cursor, "login", EMAIL, IP)
    assert limite.bloqueado(cursor, "login", EMAIL, IP, AGORA) is False
    assert any(chave.startswith("ip:") for _fluxo, chave in cursor.linhas)
    assert not any(chave.startswith("par:") for _fluxo, chave in cursor.linhas)


def test_trinta_falhas_no_ip_bloqueiam_outro_email():
    cursor = CursorMemoria()
    for indice in range(29):
        limite.consumir(cursor, "login", f"u{indice}@example.com", IP, AGORA)
    assert limite.bloqueado(cursor, "login", "outro@example.com", IP, AGORA) is False
    limite.consumir(cursor, "login", "u29@example.com", IP, AGORA)
    assert limite.bloqueado(cursor, "login", "outro@example.com", IP, AGORA) is True
    assert limite.bloqueado(cursor, "login", "outro@example.com", OUTRO_IP, AGORA) is False


def test_envio_nao_zera_os_erros_do_codigo():
    cursor = CursorMemoria()
    for _ in range(5):
        assert limite.bloqueado(cursor, "recuperacao_codigo", EMAIL, IP, AGORA) is False
        limite.consumir(cursor, "recuperacao_codigo", EMAIL, IP, AGORA)
    limite.consumir(cursor, "recuperacao_envio", EMAIL, IP, AGORA)
    assert limite.bloqueado(cursor, "recuperacao_codigo", EMAIL, IP, AGORA) is True
    assert limite.bloqueado(cursor, "recuperacao_envio", EMAIL, IP, AGORA) is False


def test_quarto_envio_e_janela_do_login():
    cursor = CursorMemoria()
    for _ in range(3):
        assert limite.bloqueado(cursor, "recuperacao_envio", EMAIL, IP, AGORA) is False
        limite.consumir(cursor, "recuperacao_envio", EMAIL, IP, AGORA)
    assert limite.bloqueado(cursor, "recuperacao_envio", EMAIL, IP, AGORA) is True
    for _ in range(8):
        limite.consumir(cursor, "login", EMAIL, IP, AGORA)
    assert limite.bloqueado(cursor, "login", EMAIL, IP, AGORA + timedelta(minutes=14)) is True
    assert limite.bloqueado(cursor, "login", EMAIL, IP, AGORA + timedelta(minutes=15)) is False


def test_tabela_ausente_libera_e_outro_erro_sobe():
    assert limite.bloqueado(CursorAusente(), "login", EMAIL, IP, AGORA) is False
    limite.consumir(CursorAusente(), "login", EMAIL, IP, AGORA)
    limite.liberar_par(CursorAusente(), "login", EMAIL, IP)
    with pytest.raises(RuntimeError):
        limite.bloqueado(CursorTimeout(), "login", EMAIL, IP, AGORA)


def test_ip_vazio_cai_no_balde_local():
    assert limite.normalizar_ip(None) == "local"
    assert limite.normalizar_ip("  ") == "local"
    assert len(limite.normalizar_ip("x" * 80)) == 45


def test_login_mostra_a_mesma_mensagem():
    app = AppTest.from_string(
        """
from trixter.acesso import exibir_login
import streamlit as st
st.session_state.erro_login = True
exibir_login(st.empty(), lambda area: None, lambda area=None: None)
"""
    ).run()
    assert not app.exception
    assert any(MENSAGEM_LOGIN in erro.value for erro in app.error)


class CursorRetencao:
    def __init__(self, linhas, tabela=True, falha=None):
        self.linhas = linhas
        self.tabela = tabela
        self.falha = falha
        self.rowcount = -1
        self._linha = None
        self.chamadas = []

    def execute(self, sql, *params):
        if len(params) == 1 and isinstance(params[0], (tuple, list)):
            params = tuple(params[0])
        texto = " ".join(sql.split())
        self.chamadas.append((texto, params))
        if "OBJECT_ID" in texto:
            self._linha = (1 if self.tabela else None,)
            return
        if self.falha:
            raise self.falha
        if texto.startswith("DELETE TOP"):
            corte, agora = params
            vencidas = sorted(
                (
                    chave for chave, valor in self.linhas.items()
                    if valor[1] is not None
                    and valor[1] < corte
                    and (valor[2] is None or valor[2] <= agora)
                ),
                key=lambda chave: (str(chave[0]), str(chave[1])),
            )
            for chave in vencidas[:32]:
                del self.linhas[chave]
            self.rowcount = min(32, len(vencidas))
            return
        if texto.startswith("DELETE") and "LIKE" in texto:
            exata, padrao = params
            prefixo = padrao[:-1].replace("\\%", "%").replace("\\_", "_").replace("\\\\", "\\")
            for chave in list(self.linhas):
                if chave[1] == exata or str(chave[1]).startswith(prefixo):
                    del self.linhas[chave]
            return
        if texto.startswith("SELECT") and len(params) >= 2:
            self._linha = self.linhas.get((params[0], params[1]))
            return
        raise AssertionError(texto)

    def fetchone(self):
        return self._linha

    def close(self):
        return None


class ConexaoRetencao:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _guardar(linhas, fluxo, email, ip, inicio, tentativas, ate):
    for chave, _limite, _minutos in limite._chaves(fluxo, email, ip):
        linhas[(fluxo, chave)] = (tentativas, inicio, ate)


def test_limpeza_remove_mais_de_32_e_preserva_janela_recente():
    linhas = {}
    antigo = AGORA - timedelta(hours=25)
    for indice in range(40):
        linhas[("login", f"par:expirado-{indice}|203.0.113.50")] = (1, antigo, None)
    _guardar(linhas, "login", EMAIL, IP, AGORA - timedelta(minutes=10), 8, AGORA + timedelta(minutes=5))
    cursor = CursorRetencao(linhas)
    conexao = ConexaoRetencao(cursor)
    resultado = limite.limpar_expirados(conexao, AGORA)
    assert resultado == {"apagadas": 40, "incompleta": False}
    assert conexao.commits == 2
    assert len(linhas) == 2
    assert limite.bloqueado(cursor, "login", EMAIL, IP, AGORA) is True
    sql = next(texto for texto, _params in cursor.chamadas if texto.startswith("DELETE TOP"))
    assert "ROWLOCK" in sql and "READPAST" in sql and "bloqueado_ate" in sql


def test_bloqueio_futuro_permanece_e_nao_segura_o_acesso(caplog):
    linhas = {}
    _guardar(
        linhas, "login", EMAIL, IP,
        AGORA - timedelta(hours=25), 8, AGORA + timedelta(hours=1),
    )
    linhas[("login", "par:velho|203.0.113.9")] = (1, AGORA - timedelta(hours=25), AGORA - timedelta(hours=1))
    cursor = CursorRetencao(linhas)
    with caplog.at_level("INFO"):
        resultado = limite.limpar_expirados(ConexaoRetencao(cursor), AGORA)
    assert resultado["apagadas"] == 1
    assert resultado["incompleta"] is False
    assert any(chave[1].startswith("par:") and "expirado" not in chave[1] for chave in linhas)
    assert limite.bloqueado(cursor, "login", EMAIL, IP, AGORA) is False
    assert EMAIL not in caplog.text


def test_teto_de_32_lotes_deixa_expirados(caplog):
    linhas = {
        ("login", f"par:expirado-{indice}|203.0.113.50"): (1, AGORA - timedelta(hours=30), None)
        for indice in range(32 * 32 + 5)
    }
    cursor = CursorRetencao(linhas)
    with caplog.at_level("INFO"):
        resultado = limite.limpar_expirados(ConexaoRetencao(cursor), AGORA)
    assert resultado == {"apagadas": 32 * 32, "incompleta": True}
    assert len(linhas) == 5
    assert sum(1 for texto, _params in cursor.chamadas if texto.startswith("DELETE TOP")) == 32
    assert "registros expirados podem permanecer" in caplog.text
    assert "example.com" not in caplog.text


def test_chaves_de_um_email_saem_e_o_ip_compartilhado_fica():
    linhas = {}
    outro = "outro@example.com"
    _guardar(linhas, "login", EMAIL, IP, AGORA, 4, None)
    _guardar(linhas, "recuperacao_envio", EMAIL, IP, AGORA, 2, None)
    _guardar(linhas, "login", outro, IP, AGORA, 3, None)
    resumo = limite._resumo_email(EMAIL)
    linhas[("login", f"email:{resumo}extra")] = (1, AGORA, None)
    linhas[("login", f"par:{resumo}sem-barra")] = (1, AGORA, None)
    cursor = CursorRetencao(linhas)
    limite.apagar_chaves_do_email(cursor, "  A@Example.com ")
    chaves = {chave for _fluxo, chave in linhas}
    assert not any(chave == f"email:{resumo}" or chave.startswith(f"par:{resumo}|") for chave in chaves)
    assert any(chave.startswith("ip:") for chave in chaves)
    assert any(chave.startswith("par:") and resumo not in chave for chave in chaves)
    assert f"email:{resumo}extra" in chaves
    assert f"par:{resumo}sem-barra" in chaves
    sql, params = next(item for item in cursor.chamadas if item[0].startswith("DELETE"))
    assert "LIKE" in sql and "ESCAPE" in sql
    assert EMAIL not in sql
    assert all(EMAIL not in str(valor) and "A@Example.com" not in str(valor) for valor in params)


def test_curinga_escapa_percente_e_sublinhado():
    assert limite._curinga_par("a%b_c\\d") == "par:a\\%b\\_c\\\\d|%"


def test_tabela_ausente_nao_apaga_e_outro_erro_sobe():
    vazia = CursorRetencao({}, tabela=False)
    assert limite.limpar_expirados(ConexaoRetencao(vazia), AGORA) == {
        "apagadas": 0, "incompleta": False,
    }
    assert not any(texto.startswith("DELETE") for texto, _params in vazia.chamadas)
    limite.apagar_chaves_do_email(vazia, EMAIL)
    assert not any(texto.startswith("DELETE") for texto, _params in vazia.chamadas)

    ausente = CursorRetencao({}, falha=RuntimeError("Invalid object name 'dbo.limites_acesso' (208)"))
    assert limite.limpar_expirados(ConexaoRetencao(ausente), AGORA)["apagadas"] == 0
    with pytest.raises(RuntimeError, match="timeout"):
        limite.apagar_chaves_do_email(
            CursorRetencao({}, falha=RuntimeError("timeout de conexao")),
            EMAIL,
        )
    with pytest.raises(RuntimeError, match="timeout"):
        limite.limpar_expirados(
            ConexaoRetencao(CursorRetencao({}, falha=RuntimeError("timeout de conexao"))),
            AGORA,
        )
