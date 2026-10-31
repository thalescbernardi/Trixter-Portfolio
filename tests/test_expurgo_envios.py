"""Expurgo sem SQL/SMTP reais; executa o predicado SQL sobre SQLite em memória."""
import calendar
from datetime import date, datetime, timedelta, timezone
import sqlite3
from zoneinfo import ZoneInfo

import pytest

from trixter.historico import Historico

ZONA = ZoneInfo("America/Sao_Paulo")


class Cursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, *args):
        self.conn.comandos.append((sql, args))
        # Adapta somente TOP/CTE/OUTPUT e funções de data; mantém o predicado real.
        predicado = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
        predicado = predicado.replace("DATEADD(day,", "DATEADD('day',")
        lote, utc, local = args
        ids = self.conn.db.execute(
            "SELECT id_envio FROM envios_automaticos WHERE " + predicado
            + " ORDER BY id_envio LIMIT ?",
            (utc.isoformat(' '), local.isoformat(' '), lote),
        ).fetchall()
        self.rows = ids
        self.conn.db.executemany("DELETE FROM envios_automaticos WHERE id_envio=?", ids)

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class Conexao:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.comandos = []
        self.commits = 0
        self.db.execute("CREATE TABLE envios_automaticos (id_envio INTEGER PRIMARY KEY, "
                        "tipo TEXT, periodo TEXT, status TEXT, atualizado_em TEXT)")
        self.db.create_function("DATEADD", 3, lambda unidade, n, valor:
            (datetime.fromisoformat(valor) + timedelta(days=n)).isoformat(' '))

        def eomonth(valor, n):
            d = date.fromisoformat(valor)
            mes = d.year * 12 + d.month - 1 + n
            ano, m = divmod(mes, 12)
            return date(ano, m + 1, calendar.monthrange(ano, m + 1)[1]).isoformat()

        self.db.create_function("EOMONTH", 2, eomonth)

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.db.commit()
        self.commits += 1

    def adicionar(self, tipo, periodo, estado, atualizado):
        self.db.execute("INSERT INTO envios_automaticos VALUES(NULL,?,?,?,?)",
                        (tipo, periodo.isoformat(), estado, atualizado.isoformat(' ')))

    def historico(self):
        hist = Historico(self)
        hist.bloqueado = True
        return hist


@pytest.mark.parametrize("tipo,periodo,fim", [
    ("relatorio_mensal", date(2028, 1, 1), datetime(2028, 3, 1, tzinfo=ZONA)),
    ("relatorio_mensal", date(2026, 12, 1), datetime(2027, 2, 1, tzinfo=ZONA)),
    ("resumo_semanal", date(2026, 9, 28), datetime(2026, 10, 5, tzinfo=ZONA)),
    ("alertas_diarios", date(2026, 9, 30), datetime(2026, 10, 1, tzinfo=ZONA)),
])
@pytest.mark.parametrize("estado", ["enviado", "falha", "incerto"])
def test_limite_da_janela_e_trinta_dias(tipo, periodo, fim, estado):
    conn = Conexao()
    conn.adicionar(tipo, periodo, estado, datetime(2020, 1, 1))
    hist = conn.historico()
    limite = fim + timedelta(days=30)
    assert hist.expurgar(fim - timedelta(microseconds=1)) == 0
    assert hist.expurgar(limite - timedelta(microseconds=1)) == 0
    assert hist.expurgar(limite) == 1
    assert hist.expurgar(limite) == 0


def test_atualizacao_mais_recente_e_estados_ativos():
    conn = Conexao()
    agora = datetime(2026, 10, 23, 12, tzinfo=ZONA)
    atualizado = (agora.astimezone(timezone.utc) - timedelta(days=30)).replace(tzinfo=None)
    for estado in ("enviado", "falha", "incerto", "preparando", "enviando"):
        conn.adicionar("alertas_diarios", date(2026, 1, 1), estado, atualizado)
    conn.adicionar("alertas_diarios", date(2026, 1, 1), "enviado",
                   atualizado + timedelta(microseconds=1))
    conn.adicionar("tipo_futuro", date(2026, 1, 1), "enviado", atualizado)
    assert conn.historico().expurgar(agora, tamanho_lote=2) == 3
    assert conn.commits == 2
    restantes = conn.db.execute("SELECT status FROM envios_automaticos ORDER BY id_envio").fetchall()
    assert restantes == [("preparando",), ("enviando",), ("enviado",), ("enviado",)]
    assert len({args[1:] for _, args in conn.comandos}) == 1


def test_bloqueio_e_referencia_obrigatorios():
    with pytest.raises(RuntimeError, match="bloqueio exclusivo"):
        Historico(None).expurgar(datetime.now(timezone.utc))
    hist = Historico(None)
    hist.bloqueado = True
    with pytest.raises(ValueError, match="fuso"):
        hist.expurgar(datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="lote"):
        hist.expurgar(datetime.now(timezone.utc), 0)


@pytest.mark.parametrize("simular", [False, True])
def test_cli_limpeza_somente_real_sob_bloqueio_apos_recuperacao(monkeypatch, simular):
    import executar_envios as cli
    from contextlib import contextmanager
    eventos = []

    class Hist:
        def __init__(self, conn):
            self.bloqueado = False

        @contextmanager
        def exclusivo(self):
            self.bloqueado = True
            eventos.append("lock")
            try:
                yield
            finally:
                eventos.append("unlock")
                self.bloqueado = False

        def expurgar(self, referencia):
            assert self.bloqueado
            assert referencia.tzinfo is not None
            assert eventos[-1] == "recuperar"
            eventos.append("expurgo")
            return 0

    def executar(conn, hist, config, hoje, simular):
        # Exercita a recuperação real da automação, com lote vazio e sem SMTP.
        from trixter import automacao
        hist.existe = lambda: True
        hist.recuperar_interrompidos = lambda: eventos.append("recuperar")
        monkeypatch.setattr(automacao, "buscar_usuarios", lambda conn: [])
        return automacao.executar(conn, hist, config, hoje, simular=simular)

    monkeypatch.setattr(cli, "Historico", Hist)
    monkeypatch.setattr(cli, "carregar_config", lambda *a: {})
    monkeypatch.setattr(cli, "validar_config", lambda *a, **k: None)
    monkeypatch.setattr(cli, "conectar_banco", lambda *a: sqlite3.connect(":memory:"))
    monkeypatch.setattr(cli, "executar", executar)
    monkeypatch.setattr(cli, "_tentar_expurgo", lambda *a: None)
    monkeypatch.setattr(cli, "_tentar_limpar_limites", lambda *a: None)
    assert cli.main([] if simular else ["--enviar"]) == 0
    assert eventos == ([] if simular else ["lock", "recuperar", "expurgo", "unlock"])
