"""CLI para o Agendador de Tarefas. Sem argumentos de ação, apenas simula."""
import argparse
from contextlib import closing, nullcontext
from datetime import date, datetime
import logging
from zoneinfo import ZoneInfo

import pyodbc

from trixter.automacao import executar
from trixter.demo_expurgo import conexao_utilizavel, expurgar_demonstracoes
from trixter.limite_acesso import limpar_expirados
from trixter.historico import Historico
from trixter.infra import (
    carregar_config, conectar_banco, descrever_erro_sql, limpar_falha_sql,
    operacao_sql, validar_config,
)


def _tentar_expurgo(conexao, agora):
    """Não altera o resultado dos envios e não repete e-mails já processados."""
    if not conexao_utilizavel(conexao):
        logging.error("Expurgo de demonstrações não executado (conexão indisponível).")
        return
    try:
        expurgar_demonstracoes(conexao, agora)
    except Exception as erro:
        logging.error("Expurgo de demonstrações interrompido (%s).", type(erro).__name__)


def _tentar_limpar_limites(conexao, agora):
    """Não altera o resultado dos envios nem impede o expurgo."""
    try:
        limpar_expirados(conexao, agora)
    except Exception as erro:
        logging.error(
            "Limpeza de limites de acesso interrompida (%s).",
            type(erro).__name__,
        )
        try:
            conexao.rollback()
        except Exception:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Arquivo TOML de configuração; também aceita TRIXTER_CONFIG.")
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--simular", action="store_true", help="Prepara relatórios e alertas em memória; não envia nem grava histórico (padrão).")
    modo.add_argument("--enviar", action="store_true", help="Executa envios reais respeitando preferências e histórico.")
    modo.add_argument("--inicializar-historico", action="store_true", help="Cria apenas a tabela de histórico, se ausente.")
    parser.add_argument("--data", type=date.fromisoformat, help="Data YYYY-MM-DD, somente para simulação.")
    args = parser.parse_args(argv)
    if args.data and (args.enviar or args.inicializar_historico):
        parser.error("--data é permitido somente em simulações.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    limpar_falha_sql()
    try:
        config = carregar_config(args.config)
        validar_config(config, smtp=args.enviar)
        zona = ZoneInfo(config.get("automacao", {}).get("fuso_horario", "America/Sao_Paulo"))
        referencia = datetime.now(zona)
        hoje = args.data or referencia.date()
        with operacao_sql("conectar"):
            conexao_banco = conectar_banco(config)
        with closing(conexao_banco) as conexao:
            try:
                historico = Historico(conexao)
                # A simulação não adquire bloqueios de aplicação nem altera o banco.
                contexto = historico.exclusivo() if args.enviar or args.inicializar_historico else nullcontext()
                with contexto:
                    if args.inicializar_historico:
                        historico.inicializar()
                        logging.info("Histórico inicializado; nenhum e-mail enviado.")
                        return 0
                    resumo = executar(conexao, historico, config, hoje, simular=not args.enviar)
                    if args.enviar:
                        removidos = historico.expurgar(referencia)
                        logging.info("Histórico de envios: %s registros expurgados.", removidos)
                    logging.info("Resultado: %s", resumo)
                    codigo = 1 if resumo["falhas"] or resumo["incertos"] else 0
            except (ValueError, FileNotFoundError) as erro:
                logging.error(
                    "etapa=execucao classe=%s categoria=%s",
                    type(erro).__name__,
                    "arquivo_nao_encontrado" if isinstance(erro, FileNotFoundError) else "valor_invalido",
                )
                codigo = 1
            except pyodbc.Error as erro:
                logging.error(
                    "Executor interrompido (%s %s). Verifique configuração, banco e histórico; nenhum reenvio foi liberado.",
                    type(erro).__name__, descrever_erro_sql(erro),
                )
                codigo = 1
            except Exception as erro:
                logging.error(
                    "Executor interrompido (%s). Verifique configuração, banco e histórico; nenhum reenvio foi liberado.",
                    type(erro).__name__,
                )
                codigo = 1
            if args.enviar:
                agora_local = datetime.now(zona).replace(tzinfo=None)
                _tentar_expurgo(conexao, agora_local)
                _tentar_limpar_limites(conexao, agora_local)
            return codigo
    except (ValueError, FileNotFoundError) as erro:
        logging.error(
            "etapa=principal classe=%s categoria=%s",
            type(erro).__name__,
            "arquivo_nao_encontrado" if isinstance(erro, FileNotFoundError) else "valor_invalido",
        )
        return 1
    except pyodbc.Error as erro:
        logging.error(
            "Executor interrompido (%s %s). Verifique configuração, banco e histórico; nenhum reenvio foi liberado.",
            type(erro).__name__, descrever_erro_sql(erro),
        )
        return 1
    except Exception as erro:
        logging.error(
            "Executor interrompido (%s). Verifique configuração, banco e histórico; nenhum reenvio foi liberado.",
            type(erro).__name__,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
