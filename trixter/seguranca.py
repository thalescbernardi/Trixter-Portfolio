"""Tela de troca de senha e de e-mail."""
import re
import secrets
from contextlib import closing
from datetime import datetime

import bcrypt
import pyodbc
import streamlit as st

from . import estilo, limite_acesso, verificacao
from .credencial import adotar_versao, exigir_operacao, gravar_email, gravar_senha, reservar_email
from .exportacao import concluir_exportacao
from .privacidade import abrir_politica, exibir_politica, fechar_politica, politica_aberta
from .senha import gerar_hash_senha, mensagem_senha
from .sessao import (
    arquivo_autorizado,
    descartar_exportacao,
    encerrar_sessao_local,
    guardar_exportacao,
)

FLUXO_EMAIL = "email"
_ENVIO_EMAIL = "alteracao_email_envio"
_CODIGO_EMAIL = "alteracao_email_codigo"
_EMAIL_VALIDO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ASSUNTO_CODIGO_EMAIL = "Código para confirmar a alteração de e-mail"
ASSUNTO_AVISO_EMAIL = "Aviso de alteração de e-mail"
AVISO_DEMO = (
    "Troca de senha, troca de e-mail e exclusão de conta "
    "não estão disponíveis na demonstração."
)


def em_demonstracao(estado):
    usuario = (estado or {}).get("usuario_atual") or {}
    return bool(usuario.get("conta_demo"))


def _botao_politica():
    if st.button(
        "Política de Privacidade e Termos de Uso",
        key="btn_politica_seguranca",
        use_container_width=True,
    ):
        abrir_politica("seguranca")
        st.rerun(scope="app")
_AVISO_EMAIL = (
    "Olá!\n\n"
    "O endereço de e-mail de acesso da sua conta Trixter foi alterado.\n\n"
    "Se você não reconhece esta alteração, entre em contato pelos canais de suporte da sua conta.\n\n"
    "Atenciosamente,\nTrixter"
)


def normalizar_email(valor):
    texto = (valor or "").strip().lower()
    if not _EMAIL_VALIDO.fullmatch(texto):
        return None
    return texto


def _codigo_numerico():
    return f"{secrets.randbelow(1_000_000):06d}"


def _corpo_codigo(codigo):
    return (
        "Olá!\n\n"
        f"Seu código para confirmar a alteração de e-mail é: {codigo}\n\n"
        "Este código é válido por 10 minutos.\n"
        "Se você não solicitou a alteração, ignore esta mensagem."
    )


def confirmar_troca_email(cursor, id_usuario, email_anterior, email_novo):
    """Trava o endereço novo e a conta. Não confirma a transação."""
    if not reservar_email(cursor, email_novo, id_usuario):
        return None
    cursor.execute(
        """
        SELECT email
        FROM dbo.usuarios WITH (UPDLOCK, ROWLOCK, HOLDLOCK)
        WHERE id_usuario = ?
        """,
        id_usuario,
    )
    linha = cursor.fetchone()
    if not linha or linha[0] is None:
        return None
    atual = str(linha[0]).strip().lower()
    if atual != str(email_anterior).strip().lower():
        return None
    return gravar_email(cursor, id_usuario, linha[0], email_novo)


def _cota_email(conectar_banco, fluxo, email, ip, registrar):
    try:
        with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
            return limite_acesso.confirmar_reserva(
                conexao, cursor, fluxo, email, ip, registrar=registrar,
            )
    except limite_acesso.ErroLimite:
        return None


def _senha_confere(informada, armazenada):
    if not informada or armazenada is None:
        return False
    try:
        hash_bytes = armazenada if isinstance(armazenada, bytes) else str(armazenada).encode("utf-8")
        return bcrypt.checkpw(informada.encode("utf-8"), hash_bytes)
    except (TypeError, ValueError):
        return False


def pedir_confirmacao_email(estado, conectar_banco, usuario_id, novo, confirmar, senha, enviar_email, ip, agora=None):
    """Envia o código. Não grava dbo.usuarios."""
    if em_demonstracao(estado):
        return "demo"
    agora = agora or datetime.now()
    if not (novo or "").strip() or not (confirmar or "").strip() or not senha:
        return "incompleto"
    email_novo = normalizar_email(novo)
    email_confirmar = normalizar_email(confirmar)
    if email_novo is None or email_confirmar is None:
        return "invalido"
    if email_novo != email_confirmar:
        return "diferente"
    try:
        with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
            try:
                cursor.execute(
                    """
                    SELECT senha, email
                    FROM dbo.usuarios
                    WHERE id_usuario = ?
                    """,
                    usuario_id,
                )
                conta = cursor.fetchone()
                if not conta:
                    conexao.rollback()
                    return "ausente"
                if not _senha_confere(senha, conta[0]):
                    conexao.rollback()
                    return "senha"
                email_atual = str(conta[1]).strip().lower() if conta[1] is not None else ""
                if email_novo == email_atual:
                    conexao.rollback()
                    return "igual"
                cursor.execute(
                    """
                    SELECT id_usuario
                    FROM dbo.usuarios
                    WHERE email = ?
                    """,
                    email_novo,
                )
                ocupado = cursor.fetchone()
                if ocupado and str(ocupado[0]) != str(usuario_id):
                    conexao.rollback()
                    return "ocupado"
                espera = estado.get(f"reenvio_{FLUXO_EMAIL}")
                if espera and agora < espera:
                    conexao.rollback()
                    return "espera"
                permitido = limite_acesso.confirmar_reserva(
                    conexao, cursor, _ENVIO_EMAIL, email_novo, ip, registrar=True,
                )
            except limite_acesso.ErroLimite:
                conexao.rollback()
                return "limite_indisponivel"
            except pyodbc.Error:
                conexao.rollback()
                return "limite_indisponivel"
    except pyodbc.Error:
        return "limite_indisponivel"
    if not permitido:
        return "limite"
    verificacao.iniciar_solicitacao(estado, FLUXO_EMAIL, agora)
    if enviar_email is None:
        verificacao.limpar(estado, FLUXO_EMAIL)
        return "envio"
    codigo = _codigo_numerico()
    try:
        enviar_email(
            destinatario=email_novo,
            assunto=ASSUNTO_CODIGO_EMAIL,
            corpo=_corpo_codigo(codigo),
        )
    except Exception:
        verificacao.limpar(estado, FLUXO_EMAIL)
        return "envio"
    verificacao.registrar(
        estado, FLUXO_EMAIL, codigo, email_novo, usuario_id, agora,
        proteger=True, email_anterior=email_atual,
    )
    return "enviado"


def concluir_alteracao_email(estado, conectar_banco, usuario_id, codigo, enviar_email, ip, agora=None):
    """Confirma o código e só então troca o e-mail. O aviso sai depois do commit."""
    if em_demonstracao(estado):
        return "demo", None, None
    agora = agora or datetime.now()
    desafio = estado.get(f"verificacao_{FLUXO_EMAIL}") or {}
    email_cota = desafio.get("email")
    resultado = verificacao.validar(estado, FLUXO_EMAIL, codigo, agora)
    if resultado in ("invalido", "limite") and email_cota:
        if _cota_email(conectar_banco, _CODIGO_EMAIL, email_cota, ip, True) is None:
            verificacao.limpar(estado, FLUXO_EMAIL)
            return "limite_indisponivel", None, None
    if resultado != "sucesso":
        return resultado, None, None
    auth = verificacao.autorizacao(estado, FLUXO_EMAIL, agora)
    email_novo = auth.get("email") if auth else None
    email_anterior = auth.get("email_anterior") if auth else None
    if (
        not auth
        or str(auth.get("usuario_id")) != str(usuario_id)
        or auth.get("finalidade") != FLUXO_EMAIL
        or not email_novo
        or not email_anterior
    ):
        verificacao.limpar(estado, FLUXO_EMAIL)
        return "ausente", None, None
    permitido = _cota_email(conectar_banco, _CODIGO_EMAIL, email_novo, ip, False)
    if permitido is None:
        verificacao.limpar(estado, FLUXO_EMAIL)
        return "limite_indisponivel", None, None
    if not permitido:
        verificacao.limpar(estado, FLUXO_EMAIL)
        return "limite", None, None
    try:
        with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
            try:
                versao = confirmar_troca_email(cursor, usuario_id, email_anterior, email_novo)
                if versao is None:
                    conexao.rollback()
                    verificacao.limpar(estado, FLUXO_EMAIL)
                    return "nao_alterou", None, None
                conexao.commit()
            except pyodbc.Error:
                conexao.rollback()
                verificacao.limpar(estado, FLUXO_EMAIL)
                return "nao_alterou", None, None
    except pyodbc.Error:
        verificacao.limpar(estado, FLUXO_EMAIL)
        return "nao_alterou", None, None
    verificacao.limpar(estado, FLUXO_EMAIL)
    try:
        if enviar_email is not None:
            enviar_email(
                destinatario=email_anterior,
                assunto=ASSUNTO_AVISO_EMAIL,
                corpo=_AVISO_EMAIL,
            )
    except Exception:
        return "aviso_falhou", versao, email_novo
    return "alterado", versao, email_novo


def _exibir_exportacao(conectar_banco, sessao_demo):
    """Pede a senha da conta real e entrega o JSON só depois da consulta completa."""
    if st.session_state.pop("_limpar_senha_exportacao", False):
        st.session_state.pop("senha_exportacao", None)
    st.divider()
    st.subheader("Exportar meus dados")
    st.write(
        "Gere um arquivo JSON com os dados cadastrais e financeiros desta conta."
    )
    senha = ""
    if not sessao_demo:
        senha = st.text_input(
            "Senha atual para exportar",
            type="password",
            key="senha_exportacao",
        )
    if st.button("Exportar meus dados", key="btn_exportar_dados"):
        st.session_state._limpar_senha_exportacao = True
        if not exigir_operacao(conectar_banco):
            descartar_exportacao(st.session_state)
            st.session_state.exportacao_conta_aviso = "falha"
            st.rerun()
        try:
            with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
                situacao, arquivo = concluir_exportacao(
                    cursor,
                    st.session_state.usuario_atual["id_usuario"],
                    "" if sessao_demo else senha,
                    sessao_demo,
                    True,
                )
                conexao.rollback()
        except Exception:
            situacao, arquivo = "falha", None
        if situacao != "ok" or not arquivo:
            descartar_exportacao(st.session_state)
            if situacao == "senha" and not sessao_demo:
                st.session_state.exportacao_conta_aviso = "senha"
            else:
                st.session_state.exportacao_conta_aviso = "falha"
        else:
            guardar_exportacao(
                st.session_state,
                st.session_state.usuario_atual["id_usuario"],
                arquivo,
            )
            st.session_state.exportacao_conta_aviso = None
        st.rerun()
    aviso = st.session_state.get("exportacao_conta_aviso")
    if aviso == "senha":
        st.error("Senha atual incorreta.")
    elif aviso == "falha":
        st.error("Não foi possível exportar os dados da conta.")
    arquivo = arquivo_autorizado(
        st.session_state,
        st.session_state.usuario_atual["id_usuario"],
    )
    if arquivo:
        st.download_button(
            "Baixar arquivo JSON",
            data=arquivo,
            file_name="trixter-dados-conta.json",
            mime="application/json",
            key="btn_baixar_exportacao",
            on_click=descartar_exportacao,
            args=(st.session_state,),
        )


@st.fragment
def exibir_seguranca(conectar_banco, enviar_email=None):
    if not exigir_operacao(conectar_banco):
        return
    if politica_aberta("seguranca"):
        estilo.publicar(estilo.ESTILO_SEGURANCA)
        exibir_politica()
        if st.button(
            "← Voltar",
            key="btn_fechar_politica",
            width="content",
        ):
            fechar_politica()
            st.rerun(scope="app")
        return
    if em_demonstracao(st.session_state):
        _botao_politica()
        st.info(AVISO_DEMO)
        _exibir_exportacao(conectar_banco, True)
        return

    estilo.publicar(estilo.ESTILO_SEGURANCA)
    st.markdown(
       """
       <div class="titulo-seguranca">
          <span class= "icone-seguranca"></span>
          <span> Segurança</span>
       </div>
       """,
       unsafe_allow_html=True
    )

    st.write(
       "Gerencie a senha de acesso à sua conta."
    )

    _botao_politica()

    st.subheader("Alterar senha")

    senha_atual = st.text_input(
       "Senha atual",
       type="password",
       key="seguranca_senha_atual"
    )

    nova_senha = st.text_input(
       "Nova senha",
       type="password",
       key="seguranca_nova_senha"
    )

    confirmar_nova_senha = st.text_input(
       "Confirmar nova senha",
       type="password",
       key="seguranca_confirmar_senha"
    )

    btn_alterar_senha = st.button(
       "Alterar senha",
       key="btn_alterar_senha"
    )

    if btn_alterar_senha and em_demonstracao(st.session_state):
       st.info(AVISO_DEMO)
       btn_alterar_senha = False

    if btn_alterar_senha:

       conexao = conectar_banco()
       cursor = conexao.cursor()

       cursor.execute(
          """
          SELECT senha
          FROM usuarios
          WHERE id_usuario = ?
          """,
          st.session_state.usuario_atual["id_usuario"]
       )

       resultado = cursor.fetchone()
       senha_hash_atual = resultado[0]

       senha_atual_correta = bcrypt.checkpw(
          senha_atual.encode("utf-8"),
          senha_hash_atual.encode("utf-8")
       )

       if not senha_atual_correta:
          st.error("Senha atual incorreta.")

       elif not nova_senha or not confirmar_nova_senha:
          st.error("Preencha os campos da nova senha.")

       elif nova_senha != confirmar_nova_senha:
          st.error("As novas senhas não coincidem.")

       elif nova_senha == senha_atual:
          st.error("A nova senha deve ser diferente da senha atual.")

       elif aviso := mensagem_senha(nova_senha):
          st.error(aviso)

       else:
          nova_senha_hash = gerar_hash_senha(nova_senha)
          nova_versao = gravar_senha(
             cursor, st.session_state.usuario_atual["id_usuario"], nova_senha_hash,
          )
          if nova_versao is None:
             conexao.rollback()
             cursor.close()
             conexao.close()
             st.rerun()
          else:
             conexao.commit()
             adotar_versao(st.session_state, nova_versao)
             st.success("Senha alterada com sucesso.")

       cursor.close()
       conexao.close()


    st.divider()

    st.subheader("Alterar e-mail")

    st.write("Atualize o endereço de e-mail utilizado para acessar sua conta.")

    if "verificacao_email" not in st.session_state:
       st.session_state.pop("codigo_digitado_email", None)

    aviso_email = st.session_state.pop("aviso_email", None)
    if aviso_email:
       nivel, texto = aviso_email
       if nivel == "sucesso":
          st.success(texto)
       elif nivel == "aviso":
          st.warning(texto)
       else:
          st.error(texto)

    novo_email = st.text_input(
       "Novo e-mail",
       key="novo_email_seguranca"
    )

    confirmar_email = st.text_input(
       "Confirmar novo e-mail",
       key="confirmar_email_seguranca"
    )

    senha_email = st.text_input(
       "Senha atual",
       type="password",
       key="senha_email_seguranca"
    )

    btn_alterar_email = st.button(
       "Alterar e-mail",
       key="btn_alterar_email"
    )

    if btn_alterar_email and em_demonstracao(st.session_state):
       st.info(AVISO_DEMO)
       btn_alterar_email = False

    if btn_alterar_email:
       from .acesso import ip_cliente
       situacao = pedir_confirmacao_email(
          st.session_state,
          conectar_banco,
          st.session_state.usuario_atual["id_usuario"],
          novo_email,
          confirmar_email,
          senha_email,
          enviar_email,
          ip_cliente(),
       )
       if situacao == "enviado":
          st.success("Enviamos um código de confirmação para o novo e-mail. Ele vale 10 minutos.")
       elif situacao == "espera":
          limite = st.session_state.get("reenvio_email")
          segundos = 60
          if limite:
             segundos = max(1, int((limite - datetime.now()).total_seconds()) + 1)
          st.warning(f"Aguarde {segundos} segundo(s) antes de solicitar outro código.")
       elif situacao == "limite":
          st.error("Muitas solicitações. Aguarde para tentar de novo.")
       elif situacao == "envio":
          st.error("Não foi possível enviar o código de confirmação.")
       elif situacao == "senha":
          st.error("Senha atual incorreta.")
       elif situacao == "ocupado":
          st.error("Este e-mail já está sendo utilizado por outra conta.")
       elif situacao == "igual":
          st.error("O novo e-mail deve ser diferente do e-mail atual.")
       elif situacao == "diferente":
          st.error("Os e-mails não coincidem.")
       elif situacao == "invalido":
          st.error("Digite um endereço válido de e-mail.")
       elif situacao == "demo":
          st.info(AVISO_DEMO)
       elif situacao == "incompleto":
          st.error("Preencha todos os campos.")
       elif situacao == "ausente":
          st.error("Não foi possível localizar os dados da conta.")
       else:
          st.error("Não foi possível concluir agora. Tente novamente.")

    if st.session_state.get("verificacao_email"):
       codigo_email = st.text_input(
          "Código de confirmação",
          max_chars=6,
          key="codigo_digitado_email",
       )
       if st.button("Confirmar código", key="btn_confirmar_email"):
          from .acesso import ip_cliente
          situacao, versao, email_definido = concluir_alteracao_email(
             st.session_state,
             conectar_banco,
             st.session_state.usuario_atual["id_usuario"],
             codigo_email,
             enviar_email,
             ip_cliente(),
          )
          if situacao in ("alterado", "aviso_falhou") and versao is not None:
             adotar_versao(st.session_state, versao)
             st.session_state.usuario_atual["email"] = email_definido
             if situacao == "alterado":
                st.session_state.aviso_email = ("sucesso", "E-mail alterado com sucesso.")
             else:
                st.session_state.aviso_email = (
                   "aviso",
                   "E-mail alterado, mas não foi possível avisar o endereço anterior.",
                )
             st.rerun()
          elif situacao == "invalido":
             st.error(verificacao.mensagem(st.session_state, FLUXO_EMAIL, situacao))
          elif situacao in ("expirado", "limite", "ausente"):
             st.session_state.aviso_email = (
                "erro",
                verificacao.mensagem(st.session_state, FLUXO_EMAIL, situacao),
             )
             st.rerun()
          elif situacao == "limite_indisponivel":
             st.session_state.aviso_email = (
                "erro",
                "Não foi possível concluir agora. Tente novamente.",
             )
             st.rerun()
          elif situacao == "demo":
             st.info(AVISO_DEMO)
          else:
             st.session_state.aviso_email = ("erro", "Não foi possível alterar o e-mail.")
             st.rerun()

    st.divider()

    st.subheader("Informações de acesso")

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT data_entrada, ultimo_acesso
       FROM usuarios
       WHERE id_usuario = ?
       """,
       st.session_state.usuario_atual["id_usuario"]
    )

    dados_acesso = cursor.fetchone()

    if dados_acesso:
       data_entrada = dados_acesso[0]
       ultimo_acesso = dados_acesso[1]

       st.write(
          f"Data de entrada: {data_entrada.strftime('%d/%m/%Y às %H:%M')}"
          )
       st.write(
          f"Último acesso: {ultimo_acesso.strftime('%d/%m/%Y às %H:%M')}"
         )

    cursor.close()
    conexao.close()

    _exibir_exportacao(conectar_banco, False)

    st.divider()

    st.subheader("Excluir conta")

    st.write(
       "A exclusão da conta é permanente. "
       "Seus dados financeiros e configurações serão apagados."
    )

    senha_exclusao = st.text_input(
       "Senha atual",
       type="password",
       key="senha_exclusao"
    )

    confirmar_exclusao = st.checkbox(
       "Estou ciente de que a exclusão da conta é permanente.",
    )

    btn_excluir_conta = st.button(
       "Excluir minha conta",
       type="primary",
       key="btn_excluir_conta"
    )

    if btn_excluir_conta and em_demonstracao(st.session_state):
       st.info(AVISO_DEMO)
       btn_excluir_conta = False

    if btn_excluir_conta:

     if not confirmar_exclusao:
       st.error("Confirme que está ciente de que a exclusão é permanente.")

     elif not senha_exclusao:
       st.error("Digite sua senha atual.")

     else:
       conexao = conectar_banco()
       cursor = conexao.cursor()

       cursor.execute(
             """
             SELECT senha
             FROM usuarios
             WHERE id_usuario = ?
             """,
             st.session_state.usuario_atual["id_usuario"]
       )

       resultado = cursor.fetchone()



       senha_correta = (
             resultado
             and bcrypt.checkpw(
                senha_exclusao.encode("utf-8"),
                resultado[0].encode("utf-8")
             )
       )

       cursor.close()
       conexao.close()

       if not senha_correta:
             st.error("Senha atual incorreta.")

       else:
          conexao = conectar_banco()
          cursor = conexao.cursor()

          id_usuario = st.session_state.usuario_atual["id_usuario"]
          exclusao_realizada = False

          try:
             cursor.execute(
                   """
                   SELECT email
                   FROM dbo.usuarios
                   WHERE id_usuario = ?
                   """,
                   id_usuario,
             )
             linha_email = cursor.fetchone()
             limite_acesso.apagar_chaves_do_email(
                cursor, linha_email[0] if linha_email else None,
             )

             cursor.execute(
                   "DELETE FROM gastos WHERE id_usuario = ?",
                   id_usuario
             )

             cursor.execute(
                   "DELETE FROM receitas WHERE id_usuario = ?",
                   id_usuario
             )

             cursor.execute(
                   "DELETE FROM orcamentos WHERE id_usuario = ?",
                   id_usuario
             )

             cursor.execute(
                   "DELETE FROM planejamentos WHERE id_usuario = ?",
                   id_usuario
             )

             cursor.execute(
                   "DELETE FROM recorrencias WHERE id_usuario = ?",
                   id_usuario
             )

             cursor.execute(
                   "DELETE FROM categorias WHERE id_usuario = ?",
                   id_usuario
             )

             cursor.execute(
                   "DELETE FROM dbo.envios_automaticos WHERE id_usuario = ?",
                   id_usuario
             )

             cursor.execute(
                   "DELETE FROM usuarios WHERE id_usuario = ?",
                   id_usuario
             )

             conexao.commit()
             exclusao_realizada=True

          except Exception as erro:
             conexao.rollback()
             st.error("Não foi possível excluir a conta.")

          finally:
             cursor.close()
             conexao.close()

          if exclusao_realizada:
             st.session_state.mensagem_conta_excluida = True
             encerrar_sessao_local(st.session_state)
             st.rerun()
