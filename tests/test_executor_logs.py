"""Diagnostico do CLI com configuracao, SQL e envios simulados."""
from contextlib import nullcontext
import logging
from unittest.mock import Mock

import pytest

import executar_envios as cli


@pytest.mark.parametrize("etapa", ["principal", "execucao"])
@pytest.mark.parametrize("tipo,categoria", [
    (ValueError, "valor_invalido"),
    (FileNotFoundError, "arquivo_nao_encontrado"),
])
def test_excecoes_nao_registram_conteudo(monkeypatch, caplog, etapa, tipo, categoria):
    segredo = r"C:\Users\Pessoa\privado.toml PWD=senha_ficticia token=abc pessoa@example.com saldo=12345"
    erro = tipo(segredo)
    conexao = Mock()
    historico = Mock()
    historico.exclusivo.return_value = nullcontext()
    carregar = Mock(return_value={})
    executar = Mock(return_value={"falhas": 0, "incertos": 0})
    if etapa == "principal":
        carregar.side_effect = erro
    else:
        executar.side_effect = erro
    conectar = Mock(return_value=conexao)
    expurgo = Mock()
    limites = Mock()
    monkeypatch.setattr(cli, "carregar_config", carregar)
    monkeypatch.setattr(cli, "validar_config", Mock())
    monkeypatch.setattr(cli, "conectar_banco", conectar)
    monkeypatch.setattr(cli, "Historico", Mock(return_value=historico))
    monkeypatch.setattr(cli, "executar", executar)
    monkeypatch.setattr(cli, "_tentar_expurgo", expurgo)
    monkeypatch.setattr(cli, "_tentar_limpar_limites", limites)

    with caplog.at_level(logging.ERROR):
        assert cli.main(["--enviar"]) == 1

    assert [r.getMessage() for r in caplog.records] == [
        f"etapa={etapa} classe={tipo.__name__} categoria={categoria}"
    ]
    assert all(r.exc_info is None for r in caplog.records)
    for sensivel in (segredo, "Pessoa", "privado.toml", "senha_ficticia", "abc", "pessoa@example.com", "12345"):
        assert sensivel not in caplog.text
    if etapa == "principal":
        conectar.assert_not_called()
        executar.assert_not_called()
        expurgo.assert_not_called()
        limites.assert_not_called()
    else:
        conexao.close.assert_called_once_with()
        expurgo.assert_called_once()
        limites.assert_called_once()
