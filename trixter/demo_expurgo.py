"""Exclusão de demonstrações, sem Streamlit.

O logout e o expurgo usam a mesma lista e o mesmo bloqueio por conta.
"""
from datetime import datetime, timedelta
import logging

import pyodbc

from .infra import descrever_erro_sql

log = logging.getLogger(__name__)

ID_CONTA_DEMO = "00000000-0000-0000-0000-000000000001"
DOMINIO_DEMO = "@demo.trixter.local"
RETENCAO = timedelta(hours=24)
LIMITE_POR_EXECUCAO = 32
ESPERA_BLOQUEIO_MS = 5000

TABELAS = (
    "dbo.planejamentos",
    "dbo.gastos",
    "dbo.receitas",
    "dbo.recorrencias",
    "dbo.orcamentos",
    "dbo.categorias",
    "dbo.envios_automaticos",
    "dbo.usuarios",
)

_EMAIL = """
    LEN(LOWER(LTRIM(RTRIM(email)))) - LEN(REPLACE(LOWER(LTRIM(RTRIM(email))), '@', '')) = 1
    AND LOWER(LTRIM(RTRIM(email))) LIKE ? ESCAPE '\\'
"""


def padrao_email():
    """Sufixo literal do domínio, com ao menos um caractere antes do @."""
    dominio = (
        DOMINIO_DEMO.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return "%_" + dominio


def _candidatos_sql():
    return f"""
        SELECT TOP (?) id_usuario
        FROM dbo.usuarios
        WHERE conta_demo = 1
          AND id_usuario <> ?
          AND data_entrada < ?
          AND {_EMAIL}
        ORDER BY data_entrada ASC
    """


def _revalidar_sql(exigir_idade):
    idade = "AND data_entrada < ?" if exigir_idade else ""
    return f"""
        SELECT id_usuario
        FROM dbo.usuarios WITH (UPDLOCK, ROWLOCK, HOLDLOCK)
        WHERE id_usuario = ?
          AND conta_demo = 1
          AND id_usuario <> ?
          {idade}
          AND {_EMAIL}
    """


def _parametros(id_usuario, agora, exigir_idade):
    parametros = [id_usuario, ID_CONTA_DEMO]
    if exigir_idade:
        parametros.append(agora - RETENCAO)
    parametros.append(padrao_email())
    return tuple(parametros)


def _bloquear(cursor, id_usuario):
    cursor.execute(
        """
        SET NOCOUNT ON;
        DECLARE @resultado int;
        EXEC @resultado = sp_getapplock
            @Resource = ?,
            @LockMode = 'Exclusive',
            @LockOwner = 'Transaction',
            @LockTimeout = ?;
        SELECT @resultado;
        SET NOCOUNT OFF;
        """,
        f"trixter:demo:{id_usuario}",
        ESPERA_BLOQUEIO_MS,
    )
    linha = cursor.fetchone()
    proximo = getattr(cursor, "nextset", None)
    if proximo is not None:
        while proximo():
            pass
    return bool(linha) and int(linha[0]) >= 0


def _registrar_falha(erro):
    if isinstance(erro, pyodbc.Error):
        log.error("Expurgo de demonstração falhou (%s).", descrever_erro_sql(erro))
        return
    log.error("Expurgo de demonstração falhou (%s).", type(erro).__name__)


def excluir_demonstracao(conexao, id_usuario, agora=None, *, exigir_idade=False):
    """Apaga uma demonstração numa transação. Não altera conta real nem o modelo.

    exigir_idade restringe à conta anterior ao prazo. Sem isso, o logout ainda
    remove a demonstração recente. Retorna excluida, ignorada ou adiada.
    """
    agora = agora or datetime.now()
    cursor = conexao.cursor()
    try:
        if not _bloquear(cursor, id_usuario):
            conexao.rollback()
            if exigir_idade:
                return "adiada"
            raise RuntimeError("bloqueio da demonstração indisponível")
        cursor.execute(_revalidar_sql(exigir_idade), _parametros(id_usuario, agora, exigir_idade))
        if cursor.fetchone() is None:
            conexao.rollback()
            return "ignorada"
        for tabela in TABELAS:
            cursor.execute(f"DELETE FROM {tabela} WHERE id_usuario = ?", id_usuario)
        conexao.commit()
        return "excluida"
    except Exception:
        conexao.rollback()
        raise
    finally:
        cursor.close()


def expurgar_demonstracoes(conexao, agora=None, limite=LIMITE_POR_EXECUCAO):
    """Remove até `limite` demonstrações abandonadas. Cada uma na sua transação."""
    agora = agora or datetime.now()
    cursor = conexao.cursor()
    try:
        cursor.execute(
            _candidatos_sql(),
            int(limite),
            ID_CONTA_DEMO,
            agora - RETENCAO,
            padrao_email(),
        )
        identificadores = [linha[0] for linha in cursor.fetchall()]
    finally:
        cursor.close()
    conexao.rollback()
    resultado = {"excluidas": 0, "ignoradas": 0, "adiadas": 0, "falhas": 0}
    for identificador in identificadores:
        try:
            situacao = excluir_demonstracao(
                conexao, identificador, agora, exigir_idade=True,
            )
        except Exception as erro:
            resultado["falhas"] += 1
            _registrar_falha(erro)
            continue
        resultado[{"excluida": "excluidas", "ignorada": "ignoradas", "adiada": "adiadas"}[situacao]] += 1
    log.info(
        "Expurgo de demonstrações: excluidas=%s ignoradas=%s adiadas=%s falhas=%s",
        resultado["excluidas"],
        resultado["ignoradas"],
        resultado["adiadas"],
        resultado["falhas"],
    )
    return resultado


def conexao_utilizavel(conexao):
    """Leitura mínima. Não grava e desfaz a transação da consulta."""
    try:
        cursor = conexao.cursor()
        try:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        finally:
            cursor.close()
        conexao.rollback()
        return True
    except Exception:
        return False
