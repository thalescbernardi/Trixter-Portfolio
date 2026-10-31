"""Manutencao exclusiva: limpa dados elegiveis, sem processar ou enviar e-mails."""
import argparse
from contextlib import closing
from datetime import datetime
import logging
from zoneinfo import ZoneInfo

import pyodbc

from trixter.demo_expurgo import expurgar_demonstracoes
from trixter.historico import Historico
from trixter.infra import (
    carregar_config, conectar_banco, descrever_erro_sql, limpar_falha_sql,
    operacao_sql, validar_config,
)
from trixter.limite_acesso import limpar_expirados


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="TOML exclusivo de banco e fuso, sem secao email.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    limpar_falha_sql()
    etapa = "configuracao"
    try:
        config = carregar_config(args.config)
        if set(config) - {"database", "automacao"}:
            raise ValueError("Configuracao de manutencao deve conter somente banco e automacao.")
        validar_config(config, smtp=False)
        zona = ZoneInfo(config.get("automacao", {}).get("fuso_horario", "America/Sao_Paulo"))
        referencia = datetime.now(zona)
        agora_local = referencia.replace(tzinfo=None)
        etapa = "conectar"
        with operacao_sql("conectar"):
            conexao_banco = conectar_banco(config)
        with closing(conexao_banco) as conexao:
            historico = Historico(conexao)
            etapa = "bloqueio"
            with historico.exclusivo():
                etapa = "verificar_historico"
                if not historico.existe():
                    raise RuntimeError("Historico ausente; manutencao nao cria tabelas.")
                etapa = "recuperar_interrompidos"
                historico.recuperar_interrompidos()
                etapa = "expurgar_historico"
                removidos = historico.expurgar(referencia)
                logging.info("Historico: removidos=%s", removidos)
                etapa = "expurgar_demonstracoes"
                demos = expurgar_demonstracoes(conexao, agora_local)
                logging.info("Demonstracoes: excluidas=%s adiadas=%s falhas=%s",
                             demos["excluidas"], demos["adiadas"], demos["falhas"])
                if demos["falhas"] or demos["adiadas"]:
                    raise RuntimeError("Expurgo de demonstracoes incompleto.")
                etapa = "limpar_limites"
                limites = limpar_expirados(conexao, agora_local)
                logging.info("Limites: apagadas=%s incompleta=%s",
                             limites["apagadas"], limites["incompleta"])
                if limites["incompleta"]:
                    raise RuntimeError("Limpeza de limites incompleta.")
                etapa = "liberar_bloqueio"
        logging.info("Manutencao concluida; nenhum envio executado.")
        return 0
    except pyodbc.Error as erro:
        logging.error("etapa=%s classe=%s %s", etapa, type(erro).__name__, descrever_erro_sql(erro))
    except Exception as erro:
        logging.error("etapa=%s classe=%s categoria=manutencao_interrompida", etapa, type(erro).__name__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
