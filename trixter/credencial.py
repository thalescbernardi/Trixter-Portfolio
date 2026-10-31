"""Versão da credencial. Não cria cookie e não substitui o XSRF do Streamlit."""
import hashlib
from contextlib import closing

import pyodbc
import streamlit as st

from .sessao import encerrar_sessao_local

MENSAGEM_SESSAO_INDISPONIVEL = (
    "Não foi possível confirmar a sessão agora. Tente novamente em instantes."
)


class SessaoIndisponivel(Exception):
    """O banco não confirmou a sessão. A operação autenticada não segue."""


def adotar_versao(estado, versao):
    usuario = estado.get("usuario_atual")
    if isinstance(usuario, dict) and versao is not None:
        usuario["credencial_versao"] = int(versao)


def gravar_senha(cursor, id_usuario, senha_hash, email=None):
    """Grava a senha e incrementa a versão na mesma instrução. Sem linha, devolve None."""
    if email is None:
        cursor.execute(
            """
            UPDATE dbo.usuarios
            SET senha = ?, credencial_versao = credencial_versao + 1
            OUTPUT INSERTED.credencial_versao
            WHERE id_usuario = ?
            """,
            senha_hash,
            id_usuario,
        )
    else:
        cursor.execute(
            """
            UPDATE dbo.usuarios
            SET senha = ?, credencial_versao = credencial_versao + 1
            OUTPUT INSERTED.credencial_versao
            WHERE id_usuario = ? AND email = ?
            """,
            senha_hash,
            id_usuario,
            email,
        )
    linha = cursor.fetchone()
    if linha is None or linha[0] is None:
        return None
    return int(linha[0])


def gravar_email(cursor, id_usuario, email_atual, email_novo):
    """Troca o e-mail e incrementa a versão na mesma instrução. Sem linha, devolve None.

    A ausência do endereço novo é conferida na mesma instrução. Sem índice único,
    quem chama ainda precisa serializar o endereço novo até o commit.
    """
    cursor.execute(
        """
        UPDATE dbo.usuarios
        SET email = ?, credencial_versao = credencial_versao + 1
        OUTPUT INSERTED.credencial_versao
        WHERE id_usuario = ?
          AND email = ?
          AND NOT EXISTS (
              SELECT 1
              FROM dbo.usuarios AS ocupado
              WHERE ocupado.email = ?
                AND ocupado.id_usuario <> ?
          )
        """,
        email_novo,
        id_usuario,
        email_atual,
        email_novo,
        id_usuario,
    )
    linha = cursor.fetchone()
    if linha is None or linha[0] is None:
        return None
    return int(linha[0])


ESPERA_EMAIL_MS = 5000


def endereco_email(email):
    return str(email or "").strip().lower()


def recurso_email(email):
    """Recurso exclusivo do endereço normalizado. O texto do e-mail não entra no nome."""
    resumo = hashlib.sha256(endereco_email(email).encode("utf-8")).hexdigest()
    return f"trixter.email|{resumo}"


def segurar_email(cursor, email):
    """Bloqueio exclusivo até o fim da transação do chamador.

    Devolve False em timeout, cancelamento, deadlock ou retorno inválido.
    Não confirma nem desfaz a transação.
    """
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
        recurso_email(email),
        ESPERA_EMAIL_MS,
    )
    linha = cursor.fetchone()
    proximo = getattr(cursor, "nextset", None)
    if callable(proximo):
        while proximo():
            pass
    if linha is None or linha[0] is None:
        return False
    try:
        return int(linha[0]) >= 0
    except (TypeError, ValueError):
        return False


def email_ocupado(cursor, email, id_usuario=None):
    """True quando outro usuário já possui o endereço. Roda na transação corrente."""
    cursor.execute(
        """
        SELECT id_usuario
        FROM dbo.usuarios
        WHERE email = ?
        """,
        endereco_email(email),
    )
    linha = cursor.fetchone()
    if not linha or linha[0] is None:
        return False
    if id_usuario is not None and str(linha[0]) == str(id_usuario):
        return False
    return True


def reservar_email(cursor, email, id_usuario=None):
    """Serializa o endereço e confirma que ele está livre para este usuário.

    A verificação e a gravação seguinte precisam permanecer na mesma transação.
    False pede que o chamador desfaça a transação, sem gravar o e-mail.
    """
    if not segurar_email(cursor, email):
        return False
    return not email_ocupado(cursor, email, id_usuario)


def preparar_operacao(conectar_banco, estado):
    """'ok' libera a operação. 'revogada' já encerrou a aba. 'anonima' não consulta o banco.

    Falha de conexão levanta SessaoIndisponivel e preserva a sessão.
    """
    if not estado.get("usuario_logado"):
        return "anonima"
    usuario = estado.get("usuario_atual") or {}
    identificador = usuario.get("id_usuario")
    versao = usuario.get("credencial_versao")
    if not identificador or versao is None:
        encerrar_sessao_local(estado)
        return "revogada"
    try:
        with closing(conectar_banco()) as conexao:
            try:
                with closing(conexao.cursor()) as cursor:
                    cursor.execute(
                        """
                        SELECT credencial_versao
                        FROM dbo.usuarios
                        WHERE id_usuario = ?
                        """,
                        identificador,
                    )
                    linha = cursor.fetchone()
            except pyodbc.Error:
                conexao.rollback()
                raise
    except pyodbc.Error as erro:
        raise SessaoIndisponivel("sessao indisponivel") from erro
    if linha is None or int(linha[0]) != int(versao):
        encerrar_sessao_local(estado)
        return "revogada"
    return "ok"


def exigir_operacao(conectar_banco, estado=None):
    """Libera o restante do fragmento. Sessão revogada reconstrói a aplicação inteira."""
    destino = st.session_state if estado is None else estado
    try:
        situacao = preparar_operacao(conectar_banco, destino)
    except SessaoIndisponivel:
        st.error(MENSAGEM_SESSAO_INDISPONIVEL)
        st.button("Tentar novamente", key="btn_confirmar_sessao_local")
        return False
    if situacao == "revogada":
        st.rerun()
    return situacao == "ok"
