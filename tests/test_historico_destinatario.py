"""Minimizacao de reservas sem conectar a bancos ou SMTP."""
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from trixter.historico import Historico


@pytest.mark.parametrize("registro", [None, ("falha", 1)])
def test_reserva_nao_persiste_endereco(registro):
    conexao = Mock()
    cursor = conexao.cursor.return_value
    cursor.fetchone.return_value = registro
    hist = Historico(conexao)
    hist.bloqueado = True
    periodo = date(2026, 10, 1)
    endereco = "cliente-ficticio@example.com"

    message_id = hist.reservar("usuario-ficticio", periodo, endereco)

    assert message_id
    comandos = cursor.execute.call_args_list
    assert len(comandos) == 2
    sql, *parametros = comandos[-1].args
    assert endereco not in sql
    assert all(endereco not in str(c.args) for c in comandos)
    assert sql.count("?") == len(parametros) == 4
    if registro:
        assert "destinatario=NULL" in sql
        assert "AND status='falha'" in sql
        assert parametros == [message_id, "usuario-ficticio", "relatorio_mensal", periodo]
    else:
        assert "VALUES (?,?,?,NULL,'preparando',?)" in sql
        assert parametros == ["usuario-ficticio", "relatorio_mensal", periodo, message_id]
    conexao.commit.assert_called_once_with()


@pytest.mark.parametrize("estado,tentativas", [
    ("enviado", 1), ("incerto", 1), ("enviando", 1),
    ("preparando", 1), ("falha", 3),
])
def test_minimizacao_nao_libera_reenvios(estado, tentativas):
    conexao = Mock()
    cursor = conexao.cursor.return_value
    cursor.fetchone.return_value = (estado, tentativas)
    hist = Historico(conexao)
    hist.bloqueado = True

    assert hist.reservar("u", date(2026, 10, 1), "ficticio@example.com") is None
    assert cursor.execute.call_count == 1
    assert "SELECT status, tentativas" in cursor.execute.call_args.args[0]
    conexao.commit.assert_not_called()


def test_scripts_separam_esquema_e_limpeza():
    pasta = Path(__file__).resolve().parents[1] / "sql"
    inicial = (pasta / "001_envios_automaticos.sql").read_text(encoding="utf-8")
    migracao = (pasta / "012_destinatario_anulavel.sql").read_text(encoding="utf-8")
    limpeza = (pasta / "013_limpar_destinatarios_historicos.sql").read_text(encoding="utf-8")
    assert "destinatario nvarchar(320) NULL" in inicial
    assert "is_nullable = 0" in migracao
    assert "ALTER COLUMN destinatario nvarchar(320) NULL" in migracao
    assert "UPDATE " not in migracao
    assert "is_nullable = 1" in limpeza
    assert "SET destinatario = NULL" in limpeza
    assert "WHERE destinatario IS NOT NULL" in limpeza
    assert "UPDATE TOP (500)" in limpeza
    assert "@@ROWCOUNT" in limpeza
    for comando in ("DELETE ", "ALTER TABLE", "atualizado_em", "SET status"):
        assert comando not in limpeza
