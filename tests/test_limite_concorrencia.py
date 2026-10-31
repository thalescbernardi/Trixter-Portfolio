"""Concorrência do limite com trava de aplicação até o commit.

A leitura de uma chave ausente não é exclusiva. Sem sp_getapplock, as
sessões passam juntas da checagem e a gravação perde atualização. A trava
de aplicação serializa a chave antes dessa leitura. Não substitui o
SQL Server.
"""
import threading
from datetime import datetime, timedelta

import pytest

from tests.test_limite_acesso import CursorMemoria
from trixter import limite_acesso as limite

AGORA = datetime(2026, 10, 9, 12, 0, 0)
IP = "203.0.113.9"
EMAIL = "a@example.com"


class ConexaoTrava:
    def __init__(self, armazem):
        self.armazem = armazem
        self.pendente = {}
        self.travadas = []
        self.applocks = {}
        self._cursor = CursorTrava(self)

    def cursor(self):
        return self._cursor

    def _segurar(self, fluxo, chave):
        if any(item[0] == fluxo and item[1] == chave for item in self.travadas):
            return
        trava = self.armazem.trava((fluxo, chave))
        trava.acquire()
        self.travadas.append((fluxo, chave, trava))

    def _tem_applock(self, fluxo, chave):
        sufixo = f"|{fluxo}|{chave}"
        return any(recurso.endswith(sufixo) for recurso in self.applocks)

    def adquirir(self, recurso, espera_ms):
        if recurso in self.applocks:
            self.applocks[recurso] += 1
            return 0
        trava = self.armazem.trava_app(recurso)
        if not trava.acquire(timeout=max(int(espera_ms), 0) / 1000):
            return -1
        self.applocks[recurso] = 1
        return 0

    def ler(self, fluxo, chave):
        if self._tem_applock(fluxo, chave):
            self._segurar(fluxo, chave)
            return self._valor(fluxo, chave)
        if self._existe(fluxo, chave):
            self._segurar(fluxo, chave)
            return self._valor(fluxo, chave)
        if self.armazem.ao_ler_ausente is not None:
            self.armazem.ao_ler_ausente(fluxo, chave)
        return self._valor(fluxo, chave)

    def _existe(self, fluxo, chave):
        if (fluxo, chave) in self.pendente:
            return self.pendente[(fluxo, chave)] is not None
        with self.armazem.mestre:
            return (fluxo, chave) in self.armazem.linhas

    def _valor(self, fluxo, chave):
        if (fluxo, chave) in self.pendente:
            return self.pendente[(fluxo, chave)]
        with self.armazem.mestre:
            return self.armazem.linhas.get((fluxo, chave))

    def gravar(self, fluxo, chave, valor):
        self._segurar(fluxo, chave)
        self.pendente[(fluxo, chave)] = valor

    def commit(self):
        with self.armazem.mestre:
            for chave, valor in self.pendente.items():
                if valor is None:
                    self.armazem.linhas.pop(chave, None)
                else:
                    self.armazem.linhas[chave] = valor
        self.pendente.clear()
        self._soltar()

    def rollback(self):
        self.pendente.clear()
        self._soltar()

    def _soltar(self):
        for _fluxo, _chave, trava in self.travadas:
            trava.release()
        self.travadas.clear()
        for recurso in list(self.applocks):
            self.armazem.trava_app(recurso).release()
        self.applocks.clear()


class CursorTrava:
    def __init__(self, conexao):
        self.connection = conexao
        self._linha = None
        self.rowcount = -1

    def execute(self, sql, *params):
        texto = " ".join(sql.split())
        if "sp_getapplock" in texto:
            self._linha = (self.connection.adquirir(params[0], params[1]),)
            return
        if texto.startswith("DELETE") and "READPAST" in texto:
            return
        if texto.startswith("SELECT"):
            self._linha = self.connection.ler(params[0], params[1])
            return
        if texto.startswith("UPDATE"):
            tentativas, inicio, ate, fluxo, chave = params
            atual = self.connection.ler(fluxo, chave)
            if atual is None:
                raise RuntimeError("duplicate key 2627")
            self.connection.gravar(fluxo, chave, (tentativas, inicio, ate))
            self.rowcount = 1
            return
        if texto.startswith("INSERT"):
            fluxo, chave, tentativas, inicio, ate = params
            if self.connection.ler(fluxo, chave) is not None:
                raise RuntimeError("duplicate key 2627")
            self.connection.gravar(fluxo, chave, (tentativas, inicio, ate))
            self.rowcount = 1
            return
        if texto.startswith("DELETE"):
            self.connection.gravar(params[0], params[1], None)
            return
        raise AssertionError(texto)

    def fetchone(self):
        return self._linha


class Armazem:
    def __init__(self):
        self.linhas = {}
        self.mestre = threading.Lock()
        self._travas = {}
        self._applocks = {}
        self.ao_ler_ausente = None

    def trava(self, chave):
        with self.mestre:
            if chave not in self._travas:
                self._travas[chave] = threading.Lock()
            return self._travas[chave]

    def trava_app(self, recurso):
        with self.mestre:
            if recurso not in self._applocks:
                self._applocks[recurso] = threading.Lock()
            return self._applocks[recurso]

    def conectar(self):
        return ConexaoTrava(self)


def _tentativas(armazem, fluxo, prefixo):
    return [
        valor[0]
        for (nome_fluxo, chave), valor in armazem.linhas.items()
        if nome_fluxo == fluxo and chave.startswith(prefixo)
    ]


def _disparar(quantidade, funcao):
    barreira = threading.Barrier(quantidade)
    erros = []
    saida = []

    def alvo():
        try:
            barreira.wait(5)
            saida.append(funcao())
        except Exception as erro:
            erros.append(erro)

    threads = [threading.Thread(target=alvo) for _ in range(quantidade)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive()
    assert erros == []
    return saida


def test_limpeza_usa_lote_e_nao_espera_linha_travada():
    cursor = CursorMemoria()
    limite.consumir(cursor, "login", EMAIL, IP, AGORA)
    limpezas = [sql for sql, _params in cursor.chamadas if sql.startswith("DELETE") and "janela_inicio" in sql]
    assert limpezas
    assert all("READPAST" in sql and "TOP (32)" in sql for sql in limpezas)
    assert all("UPDLOCK" not in sql for sql in limpezas)


def test_deadlock_desfaz_e_nao_autoriza():
    class Conexao:
        def __init__(self):
            self.desfez = 0
            self._cursor = Cursor(self)

        def cursor(self):
            return self._cursor

        def rollback(self):
            self.desfez += 1

        def commit(self):
            raise AssertionError("commit")

    class Cursor:
        def __init__(self, conexao):
            self.connection = conexao

        def execute(self, sql, *params):
            raise RuntimeError("Transaction was deadlocked on lock resources 1205")

    conexao = Conexao()
    with pytest.raises(limite.ErroLimite):
        limite.confirmar_reserva(
            conexao, conexao.cursor(), "login", EMAIL, IP, registrar=True, agora=AGORA,
        )
    assert conexao.desfez >= 1


def test_tabela_ausente_nao_autoriza_a_reserva():
    class Cursor:
        def execute(self, sql, *params):
            raise RuntimeError("Invalid object name 'dbo.limites_acesso' (208)")

        def rollback(self):
            pass

        connection = None

    with pytest.raises(limite.ErroLimite):
        limite.reservar(Cursor(), "cadastro_codigo", EMAIL, IP, AGORA)


def test_24_falhas_na_mesma_chave_param_em_8():
    armazem = Armazem()

    def tentativa():
        conexao = armazem.conectar()
        return limite.confirmar_reserva(
            conexao, conexao.cursor(), "login", EMAIL, IP, registrar=True, agora=AGORA,
        )

    saida = _disparar(24, tentativa)
    assert saida.count(True) == 8
    assert saida.count(False) == 16
    assert _tentativas(armazem, "login", "par:") == [8]
    assert _tentativas(armazem, "login", "ip:") == [8]


def test_24_chaves_novas_gravam_uma_vez_cada():
    armazem = Armazem()
    nomes = [f"u{indice}@example.com" for indice in range(24)]
    barreira = threading.Barrier(24)
    erros = []
    saida = []

    def alvo(indice):
        try:
            barreira.wait(5)
            conexao = armazem.conectar()
            saida.append(limite.confirmar_reserva(
                conexao, conexao.cursor(), "login", nomes[indice], f"198.51.100.{indice}",
                registrar=True, agora=AGORA,
            ))
        except Exception as erro:
            erros.append(erro)

    threads = [threading.Thread(target=alvo, args=(indice,)) for indice in range(24)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert erros == []
    assert saida.count(True) == 24
    assert _tentativas(armazem, "login", "par:") == [1] * 24
    assert sorted(_tentativas(armazem, "login", "ip:")) == [1] * 24


def test_mesmo_ip_com_emails_diferentes_isola_o_par():
    armazem = Armazem()
    barreira = threading.Barrier(24)
    erros = []

    def alvo(indice):
        try:
            barreira.wait(5)
            conexao = armazem.conectar()
            limite.confirmar_reserva(
                conexao, conexao.cursor(), "login", f"u{indice}@example.com", IP,
                registrar=True, agora=AGORA,
            )
        except Exception as erro:
            erros.append(erro)

    threads = [threading.Thread(target=alvo, args=(indice,)) for indice in range(24)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert erros == []
    assert sorted(_tentativas(armazem, "login", "par:")) == [1] * 24
    assert _tentativas(armazem, "login", "ip:") == [24]


def test_codigo_simultaneo_para_em_5():
    armazem = Armazem()

    def tentativa():
        conexao = armazem.conectar()
        return limite.confirmar_reserva(
            conexao, conexao.cursor(), "cadastro_codigo", EMAIL, IP,
            registrar=True, agora=AGORA,
        )

    saida = _disparar(24, tentativa)
    assert saida.count(True) == 5
    assert _tentativas(armazem, "cadastro_codigo", "par:") == [5]


def test_trava_e_solta_antes_do_trabalho_lento():
    armazem = Armazem()
    liberou = threading.Event()

    def primeira():
        conexao = armazem.conectar()
        assert limite.confirmar_reserva(
            conexao, conexao.cursor(), "recuperacao_envio", EMAIL, IP,
            registrar=True, agora=AGORA,
        )
        liberou.set()
        if not liberou.wait(1):
            raise AssertionError("espera")
        threading.Event().wait(0.5)

    def segunda():
        assert liberou.wait(1)
        inicio = datetime.now()
        conexao = armazem.conectar()
        assert limite.confirmar_reserva(
            conexao, conexao.cursor(), "recuperacao_envio", EMAIL, IP,
            registrar=True, agora=AGORA,
        )
        assert datetime.now() - inicio < timedelta(milliseconds=300)

    threads = [threading.Thread(target=primeira), threading.Thread(target=segunda)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(2)
        assert not thread.is_alive()
    assert _tentativas(armazem, "recuperacao_envio", "par:") == [2]


def test_travas_saem_em_ordem_antes_da_leitura():
    cursor = CursorMemoria()
    assert limite.reservar(cursor, "login", EMAIL, IP, AGORA) is True
    travas = [params[0] for sql, params in cursor.chamadas if "sp_getapplock" in sql]
    assert travas == sorted(travas)
    assert len(travas) == 2
    assert "|ip:" in travas[0]
    assert "|par:" in travas[1]
    textos = [sql for sql, _params in cursor.chamadas]
    ultima_trava = max(indice for indice, sql in enumerate(textos) if "sp_getapplock" in sql)
    primeira_leitura = next(indice for indice, sql in enumerate(textos) if "UPDLOCK" in sql)
    assert ultima_trava < primeira_leitura

    envio = CursorMemoria()
    assert limite.reservar(envio, "recuperacao_envio", EMAIL, IP, AGORA) is True
    recursos = [params[0] for sql, params in envio.chamadas if "sp_getapplock" in sql]
    assert recursos == sorted(recursos)
    assert len(recursos) == 3
    assert [item.split("|")[2].split(":")[0] for item in recursos] == ["email", "ip", "par"]


def test_32_na_chave_ausente_nao_diverge_nem_passa_de_8():
    armazem = Armazem()
    barreira = threading.Barrier(32)

    def gancho(fluxo, chave):
        if fluxo == "login" and chave.startswith("par:"):
            barreira.wait(2)

    armazem.ao_ler_ausente = gancho

    def tentativa():
        conexao = armazem.conectar()
        return limite.confirmar_reserva(
            conexao, conexao.cursor(), "login", EMAIL, IP, registrar=True, agora=AGORA,
        )

    saida = _disparar(32, tentativa)
    assert saida.count(True) == 8
    assert saida.count(False) == 24
    assert _tentativas(armazem, "login", "par:") == [8]
    assert _tentativas(armazem, "login", "ip:") == [8]


def test_36_emails_no_mesmo_ip_param_em_30():
    armazem = Armazem()
    barreira = threading.Barrier(36)
    erros = []
    saida = []

    def alvo(indice):
        try:
            barreira.wait(5)
            conexao = armazem.conectar()
            saida.append(limite.confirmar_reserva(
                conexao, conexao.cursor(), "login", f"u{indice}@example.com", IP,
                registrar=True, agora=AGORA,
            ))
        except Exception as erro:
            erros.append(erro)

    threads = [threading.Thread(target=alvo, args=(indice,)) for indice in range(36)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive()
    assert erros == []
    assert saida.count(True) == 30
    assert saida.count(False) == 6
    assert sorted(_tentativas(armazem, "login", "par:")) == [1] * 30
    assert _tentativas(armazem, "login", "ip:") == [30]


@pytest.mark.parametrize("codigo", [-1, -3, -999])
def test_applock_negativo_nao_autoriza(codigo):
    class Conexao:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0
            self.cursor_obj = Cursor(self)

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

    class Cursor:
        def __init__(self, conexao):
            self.connection = conexao
            self._linha = None
            self.tocou_tabela = False

        def execute(self, sql, *params):
            texto = " ".join(sql.split())
            if "sp_getapplock" in texto:
                self._linha = (codigo,)
                return
            self.tocou_tabela = True
            raise AssertionError(texto)

        def fetchone(self):
            return self._linha

    conexao = Conexao()
    with pytest.raises(limite.ErroLimite):
        limite.confirmar_reserva(
            conexao, conexao.cursor(), "login", EMAIL, IP, registrar=True, agora=AGORA,
        )
    assert conexao.commits == 0
    assert conexao.rollbacks >= 1
    assert conexao.cursor_obj.tocou_tabela is False


def test_gravacao_parcial_desfaz_e_nao_autoriza():
    class Conexao:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0
            self.ip = 0
            self.cursor_obj = Cursor(self)

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

    class Cursor:
        def __init__(self, conexao):
            self.connection = conexao
            self.rowcount = 1
            self._linha = (3, AGORA, None)

        def execute(self, sql, *params):
            texto = " ".join(sql.split())
            if "sp_getapplock" in texto:
                self._linha = (0,)
                return
            if texto.startswith("DELETE"):
                return
            if texto.startswith("SELECT"):
                self._linha = (3, AGORA, None)
                return
            if texto.startswith("UPDATE"):
                if params[4].startswith("par:"):
                    self.rowcount = 0
                    return
                self.connection.ip += 1
                self.rowcount = 1
                return
            raise AssertionError(texto)

        def fetchone(self):
            return self._linha

    conexao = Conexao()
    with pytest.raises(limite.ErroLimite):
        limite.confirmar_reserva(
            conexao, conexao.cursor(), "login", EMAIL, IP, registrar=True, agora=AGORA,
        )
    assert conexao.commits == 0
    assert conexao.rollbacks >= 1
    assert conexao.ip == 0


def test_deadlock_na_limpeza_pede_a_trava_de_novo():
    class Conexao:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0
            self.cursor_obj = Cursor(self)

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

    class Cursor:
        def __init__(self, conexao):
            self.connection = conexao
            self.rowcount = 1
            self._linha = None
            self.limpezas = 0
            self.travas = 0
            self.gravou = []

        def execute(self, sql, *params):
            texto = " ".join(sql.split())
            if "sp_getapplock" in texto:
                self.travas += 1
                self._linha = (0,)
                return
            if texto.startswith("DELETE") and "janela_inicio" in texto:
                self.limpezas += 1
                if self.limpezas == 1:
                    raise RuntimeError("deadlock 1205")
                return
            if texto.startswith("SELECT"):
                self._linha = None
                return
            if texto.startswith("INSERT"):
                self.rowcount = 1
                self.gravou.append(params[1])
                return
            raise AssertionError(texto)

        def fetchone(self):
            return self._linha

    conexao = Conexao()
    assert limite.confirmar_reserva(
        conexao, conexao.cursor(), "login", EMAIL, IP, registrar=True, agora=AGORA,
    ) is True
    assert conexao.commits == 1
    assert conexao.rollbacks >= 1
    assert conexao.cursor_obj.limpezas == 1
    assert conexao.cursor_obj.travas == 4
    assert sum(chave.startswith("par:") for chave in conexao.cursor_obj.gravou) == 1
    assert sum(chave.startswith("ip:") for chave in conexao.cursor_obj.gravou) == 1
