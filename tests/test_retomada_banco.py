import pyodbc
import pytest

from trixter import infra
from trixter.infra import abrir_com_retomada, erro_de_retomada


def test_erro_40613_e_de_retomada_e_senha_errada_nao():
    pausado = Exception(
        "42000",
        "Database 'trixter' on server 'x' is not currently available (40613)",
    )
    assert erro_de_retomada(pausado)
    assert erro_de_retomada(Exception("HYT00", "Login timeout expired (0)"))
    assert erro_de_retomada(Exception("HYT01", "Connection timeout expired"))
    assert not erro_de_retomada(Exception("18456", "Login failed for user"))
    assert not erro_de_retomada(Exception(
        "42000",
        "Client with IP address is not allowed to access the server (40615)",
    ))


def test_retomada_espera_e_devolve_a_conexao():
    relogio = {"t": 0.0}
    esperas = []

    def agora():
        return relogio["t"]

    def dormir(segundos):
        esperas.append(segundos)
        relogio["t"] += segundos

    tentativas = {"n": 0}

    def abrir():
        tentativas["n"] += 1
        if tentativas["n"] < 3:
            raise Exception("not currently available (40613)")
        return "conexao"

    assert abrir_com_retomada(abrir, dormir=dormir, relogio=agora, limite=90) == "conexao"
    assert esperas == [5.0, 10.0]


def test_hyt01_repete_e_18456_e_40615_nao_esperam():
    relogio = {"t": 0.0}
    esperas = []

    def dormir(segundos):
        esperas.append(segundos)
        relogio["t"] += segundos

    tentativas = {"n": 0}

    def abrir():
        tentativas["n"] += 1
        if tentativas["n"] == 1:
            raise Exception("HYT01", "Connection timeout expired")
        return "conexao"

    assert abrir_com_retomada(
        abrir, dormir=dormir, relogio=lambda: relogio["t"], limite=90,
    ) == "conexao"
    assert esperas == [5.0]

    def recusar(mensagem):
        def abrir_recusa():
            raise Exception(mensagem)

        def dormir_recusa(_segundos):
            raise AssertionError("nao deveria esperar")

        with pytest.raises(Exception, match="18456|40615"):
            abrir_com_retomada(
                abrir_recusa, dormir=dormir_recusa, relogio=lambda: 0.0, limite=90,
            )

    recusar("Login failed (18456)")
    recusar("not allowed (40615)")


def test_erro_permanente_nao_espera():
    def abrir():
        raise Exception("Login failed (18456)")

    def dormir(_segundos):
        raise AssertionError("nao deveria esperar")

    with pytest.raises(Exception, match="18456"):
        abrir_com_retomada(abrir, dormir=dormir, relogio=lambda: 0.0, limite=90)


def test_estoura_o_prazo_da_retomada():
    relogio = {"t": 0.0}

    def agora():
        return relogio["t"]

    def dormir(segundos):
        relogio["t"] += segundos

    def abrir():
        raise Exception("(40613)")

    with pytest.raises(Exception, match="40613"):
        abrir_com_retomada(abrir, dormir=dormir, relogio=agora, limite=12)
    assert relogio["t"] == 12


def test_conectar_banco_repete_enquanto_o_azure_retoma(monkeypatch):
    chamadas = {"n": 0}

    class Conexao:
        timeout = None

    def connect(cadeia, timeout=0):
        chamadas["n"] += 1
        assert "ODBC Driver 18 for SQL Server" in cadeia
        assert "Trusted_Connection" not in cadeia
        assert timeout == 15
        if chamadas["n"] == 1:
            raise pyodbc.Error("HYT00", "Database is not currently available (40613)")
        return Conexao()

    monkeypatch.setattr(pyodbc, "connect", connect)
    real = infra.abrir_com_retomada
    relogio = {"t": 0.0}

    def retomada(abrir):
        return real(
            abrir,
            dormir=lambda segundos: relogio.__setitem__("t", relogio["t"] + segundos),
            relogio=lambda: relogio["t"],
            limite=90,
        )

    monkeypatch.setattr(infra, "abrir_com_retomada", retomada)
    conexao = infra.conectar_banco({
        "database": {
            "driver": "ODBC Driver 18 for SQL Server",
            "server": "srv",
            "database": "db",
            "trusted_connection": "no",
            "usuario": "usuario",
            "senha": "senha",
            "encrypt": "yes",
            "trust_server_certificate": "no",
        }
    })
    assert chamadas["n"] == 2
    assert conexao.timeout == 60
    assert relogio["t"] == 5.0
