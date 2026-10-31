"""Telas de entrada: apresentação, cadastro, login e recuperação de senha."""
import os
import re
import secrets
import uuid
from contextlib import closing
from datetime import datetime

import pyodbc
import streamlit as st

from . import estilo, limite_acesso, verificacao
from .credencial import reservar_email
from .desenvolvimento import cadastro_local_permitido
from .privacidade import abrir_politica, exibir_politica, fechar_politica, politica_aberta
from .sessao import descartar_exportacao


def ip_cliente():
    try:
        contexto = getattr(st, "context", None)
        bruto = getattr(contexto, "ip_address", None) if contexto is not None else None
    except Exception:
        bruto = None
    return limite_acesso.normalizar_ip(bruto)


def exibir_landing(area_landing, abrir_acesso):


          st.markdown(
             """
             <div class="frase-esquerda">
                Boas decisões<br>
                constroem<br>
                <span>grandes conquistas.</span>
             </div>
             """,
             unsafe_allow_html=True
    )

          st.markdown(
             """
             <div class="frase-direita">
                <span class="dourado">Planeje hoje,<br>
                conquiste amanhã.</span><br>
                Seu futuro começa agora.
             </div>
             """,
             unsafe_allow_html=True
          )

          with st.container(key="landing_center"):

               st.markdown(
                  """
                     <div class="landing-trixter" style="transform: translate(62px, 70px);">
                      <div class ="trixter-icon">
                      <svg
                        width="300"
                        height="110"
                        viewBox= "0 0 64 72"
                        style="transform: translateX(-55px);"
                        xmlns="https://www.w3.org/2000/svg">
                      <path
                         d="M20 4
                           C23 2 27 3 32 5
                           C37 3 41 2 44 4
                           C43 8 41 11 39 13
                           L25 13
                           C23 10 21 7 20 4
                           Z"
                         fill="#A67C00"
                      />
                      <path
                          d="M25 14.5
                           C22 20 12 30 10 43
                           C8 57 17 65 32 65
                           C47 65 56 57 54 43
                           C52 30 42 20 39 14
                           Z"
                          fill="#b87928"
                      />
                     <rect
                       x="30.75"
                       y="26"
                       width="2.5"
                       height="6"
                       rx="1.25"
                       fill="#FFFFFF"
                     />
                     <rect
                       x="30.75"
                       y="49.50"
                       width="2.5"
                       height="6"
                       rx="1.25"
                       fill="#FFFFFF"
                     />
                     <text
                       x="32"
                       y="52"
                       text-anchor="middle"
                       fill="#FFFFFF"
                       font-size="30"
                       font-family="Arial, sans-serif"
                       font-weight="500"
                     >S</text>

                     </svg>



                     <div style="
                        font-size: 60px;
                        font-weight: 800;
                        color: #172033;
                        letter-spacing: 1px;
                        white-space: nowrap;
                     ">
                        Trixter
                     </div>



                  </div>
                  """,
                  unsafe_allow_html=True
       )


               estilo.publicar(estilo.ESTILO_LANDING)

               st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)

               if st.session_state.get("mensagem_conta_excluida", False):
                   st.success("Conta excluída com sucesso.")
                   st.session_state.mensagem_conta_excluida = False



               btn_entrar = st.button(
                  "Entrar",
                  key="btn_entrar",
                  type="primary",
                  icon=":material/person:",
                  use_container_width = True,
                  on_click=abrir_acesso,
                  args=("entrar", area_landing),
               )

               btn_criar_conta = st.button(
                  "Criar Conta",
                  key="btn_criar_conta",
                  icon=":material/person_add:",
                  use_container_width = True,
                  on_click=abrir_acesso,
                  args=("criar_conta", area_landing),
               )


               st.markdown(
                  """
                  <div style="
                     display: flex;
                     align-items: center;
                     gap:10px;
                     margin: 6px 0;
                     color: #9b8b7a;
                     font-size: 12px;
                  ">
                     <div style="flex: 1; height: 1px; background: #cbbba9;"></div>
                     <span>ou</span>
                     <div style = "flex: 1; height: 1px; background: #cbbba9;"></div>
                  </div>
                  """,
                  unsafe_allow_html=True
               )

               with st.container(key="forgot_password_wrap"):
                  btn_esqueci_senha = st.button(
                  "Esqueceu sua senha?",
                  key="btn_esqueci_senha",
                  use_container_width=True
               )

               if btn_esqueci_senha:
                  verificacao.limpar(st.session_state, "recuperacao")
                  st.session_state.recuperar_senha = True
                  st.session_state.entrar=False
                  st.session_state.criar_conta=False
                  st.rerun()


def _aplicar_limite_codigo(conectar_banco, fluxo, email, registrar):
    """Decide e grava a cota do código na mesma transação. None recusa."""
    try:
        with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
            return limite_acesso.confirmar_reserva(
                conexao, cursor, fluxo, email, ip_cliente(), registrar=registrar,
            )
    except limite_acesso.ErroLimite:
        return None


def _codigo_bloqueado(conectar_banco, fluxo, email):
    with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
        return limite_acesso.bloqueado(cursor, fluxo, email, ip_cliente())


def _consumir_codigo(conectar_banco, fluxo, email):
    with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
        limite_acesso.consumir(cursor, fluxo, email, ip_cliente())
        conexao.commit()


MENSAGEM_REDEFINICAO = "Se os dados estiverem corretos, entre com a senha informada."
MENSAGEM_CONTA_EXISTENTE = "Este e-mail já possui cadastro."
MENSAGEM_MAIORIDADE = "Confirme que você tem 18 anos completos ou mais para criar a conta."

_CHAVES_PRE_AUTENTICACAO = (
    "declaracao_maioridade",
    "novo_usuario_pendente",
    "codigo_cadastro_enviado",
    "aviso_codigo_cadastro",
    "verificacao_cadastro",
    "autorizacao_cadastro",
    "verificacao_recuperacao",
    "autorizacao_recuperacao",
    "reenvio_cadastro",
    "reenvio_recuperacao",
    "aviso_recuperacao",
    "aviso_conta_existente",
)

_CREDENCIAIS_DIGITADAS = (
    "senha",
    "nova_senha",
    "confirmar_senha",
    "nova_senha_recuperacao",
    "confirmar_nova_senha_recuperacao",
    "codigo_digitado_cadastro",
    "codigo_digitado_recuperacao",
)


def abrir_sessao(usuario, tela, estado=None):
    """Substitui o estado anterior ao login por uma sessão sem o hash da senha."""
    destino = st.session_state if estado is None else estado
    publico = {
        chave: valor
        for chave, valor in dict(usuario).items()
        if chave not in ("senha", "conta_existente", "pedido_opaco", "declaracao_maioridade")
    }
    if publico.get("credencial_versao") is not None:
        publico["credencial_versao"] = int(publico["credencial_versao"])
    for chave in _CHAVES_PRE_AUTENTICACAO:
        destino.pop(chave, None)
    destino.pop("politica_origem", None)
    destino.pop("politica_campos", None)
    descartar_exportacao(destino)
    destino["usuario_atual"] = publico
    destino["usuario_logado"] = True
    destino["criar_conta"] = False
    destino["entrar"] = False
    destino["recuperar_senha"] = False
    destino["tela_atual"] = tela


def descartar_credenciais_digitadas(estado):
    for chave in _CREDENCIAIS_DIGITADAS:
        estado.pop(chave, None)


def _codigo_opaco():
    return f"{secrets.randbelow(1_000_000):06d}"


def _recusar_codigo_cadastro(email):
    """Consome o código de cadastro sem criar conta e sem abrir sessão."""
    verificacao.registrar(
        st.session_state, "cadastro", _codigo_opaco(), email, proteger=True,
    )
    st.session_state.verificacao_cadastro["tentativas"] = 1
    st.session_state.codigo_cadastro_enviado = True
    pendente = st.session_state.get("novo_usuario_pendente") or {}
    pendente.pop("senha", None)
    pendente.pop("conta_existente", None)
    pendente["pedido_opaco"] = True
    st.session_state.novo_usuario_pendente = pendente
    st.error(verificacao.mensagem(st.session_state, "cadastro", "invalido"))


def _exibir_conta_ja_cadastrada(email):
    st.info(MENSAGEM_CONTA_EXISTENTE)
    if st.button(
        "Entrar com senha",
        key="btn_entrar_conta_existente",
        type="primary",
        use_container_width=True,
    ):
        _abrir_tela_entrada(email)
    if st.button(
        "Recuperar senha",
        key="btn_recuperar_conta_existente",
        use_container_width=True,
    ):
        _abrir_tela_recuperacao(email)


def _abrir_tela_entrada(email):
    st.session_state.aviso_conta_existente = None
    st.session_state.criar_conta = False
    st.session_state.recuperar_senha = False
    st.session_state.entrar = True
    st.session_state.email_entrada = email
    st.rerun()


def _abrir_tela_recuperacao(email):
    verificacao.limpar(st.session_state, "recuperacao")
    st.session_state.aviso_conta_existente = None
    st.session_state.criar_conta = False
    st.session_state.entrar = False
    st.session_state.recuperar_senha = True
    st.session_state.email_recuperacao = email
    st.rerun()


def _fechar_pedido_recuperacao(email, codigo, usuario_id):
    """Mesma tela para conta existente, inexistente, bloqueio e falha de envio."""
    verificacao.registrar(
        st.session_state, "recuperacao", codigo, email, usuario_id, proteger=True,
    )
    st.session_state.pop("codigo_digitado_recuperacao", None)
    st.session_state.aviso_recuperacao = limite_acesso.MENSAGEM_RECUPERACAO
    st.rerun()


def _enviar_codigo_cadastro(
    cursor, conexao, email, gerar_hash_senha, enviar_email, tipo_pessoa,
    conta_existente=None, pedido_opaco=False, *, declaracao_maioridade,
):
    if declaracao_maioridade is not True:
        return
    senha_hash = gerar_hash_senha(st.session_state.nova_senha)
    novo_usuario = {
        "id_usuario": str(uuid.uuid4()),
        "tipo_pessoa": tipo_pessoa,
        "email": email,
        "senha": senha_hash,
        "data_de_cadastro": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "data_de_último_acesso": None,
    }
    if conta_existente:
        novo_usuario["conta_existente"] = conta_existente
    if pedido_opaco:
        novo_usuario["pedido_opaco"] = True
    if tipo_pessoa == "Pessoa Física":
        novo_usuario["nome"] = st.session_state.novo_nome
        novo_usuario["renda_mensal"] = st.session_state.renda_mensal
    elif tipo_pessoa == "Pessoa Jurídica":
        novo_usuario["nome_empresa"] = st.session_state.novo_nome_empresa
        novo_usuario["faturamento_mensal"] = st.session_state.faturamento_mensal
    novo_usuario["cpf"] = None
    novo_usuario["cnpj"] = None
    novo_usuario["declaracao_maioridade"] = True

    st.session_state.novo_usuario_pendente = novo_usuario
    codigo_cadastro = f"{secrets.randbelow(1_000_000):06d}"
    corpo_cadastro = f"""
                   Olá!

                   Seu código de confirmação é:

                   {codigo_cadastro}

                   Este código é válido por 10 minutos.

                   Se você não solicitou este cadastro, ignore esta mensagem.
                   """
    try:
        teste_local = cadastro_local_permitido(
            os.getenv("TRIXTER_CADASTRO_LOCAL"),
            st.get_option("server.address"),
            novo_usuario["email"],
        )
        if not pedido_opaco and not teste_local:
            enviar_email(
                destinatario=novo_usuario["email"],
                assunto="Confirme seu cadastro",
                corpo=corpo_cadastro,
            )
        st.session_state.codigo_cadastro_enviado = True
        verificacao.registrar(
            st.session_state, "cadastro", codigo_cadastro, novo_usuario["email"],
            proteger=pedido_opaco or not teste_local,
        )
        st.session_state.verificacao_cadastro["teste_local"] = False if pedido_opaco else teste_local
        st.session_state.pop("codigo_digitado_cadastro", None)
        st.rerun()
    except Exception:
        st.session_state.codigo_cadastro_enviado = False
        verificacao.limpar(st.session_state, "cadastro")
        st.session_state.novo_usuario_pendente = None
        st.error("Não foi possível enviar o código de confirmação.")


def exibir_cadastro(area_cadastro, conectar_banco, gerar_hash_senha, enviar_email, voltar_para_inicio):

    if politica_aberta("cadastro"):
        exibir_politica()
        st.button(
            "← Voltar",
            key="btn_fechar_politica",
            width="content",
            on_click=fechar_politica,
        )
        return

    if st.session_state.get("aviso_conta_existente"):
        _exibir_conta_ja_cadastrada(st.session_state.aviso_conta_existente)
        return

    col_esq, col_form, col_dir= st.columns([1.4,2.2,1.4])

    with col_form:

          st.markdown(
                """
                <div style="text-align: center;margin-bottom: 22px;">
                <svg width="58" height="65" viewBox= "0 0 64 72" xmlns="https://www.w3.org/2000/svg">
                <path
                d="M20 4
                C23 2 27 3 32 5
                C37 3 41 2 44 4
                C43 8 41 11 39 13
                L25 13
                C23 10 21 7 20 4
                Z"
                fill="#A67C00"
                />
                <path
                d="M25 14.5
                C22 20 12 30 10 43
                C8 57 17 65 32 65
                C47 65 56 57 54 43
                C52 30 42 20 39 14
                Z"
                fill="#b87928"
                />
                <rect x="30.75" y="26" width="2.5" height="6" rx="1.25" fill="#FFFFFF"/>
                <rect x="30.75" y="49.50" width="2.5" height="6" rx="1.25" fill="#FFFFFF"/>
                <text x="32" y="52"  text-anchor="middle" fill="#FFFFFF" font-size="30" font-family="Arial, sans-serif" font-weight="500" >S</text>
                </svg>
                <div style="font-size: 34px; font-weight: 800; color: #172033; line-height: 1.1;">
                Trixter
                </div>

                <div style="text-align:left; margin-top:10px;">
                <div style="font-size:20px; font-weight:700; color:#172033;">
                      Criar Conta
                </div>
                <div style="font-size: 13px; color: #5f6470; margin-top: 2px;">
                      Preencha as informações abaixo para começar.
                </div>
                </div>
                """,
                   unsafe_allow_html=True
                )


          tipo_pessoa = st.selectbox(
                "Selecione o tipo de conta:",
                ["Pessoa Física", "Pessoa Jurídica"],
                key = "tipo_pessoa"
          )

          if tipo_pessoa == "Pessoa Física":
                st.text_input("Digite seu nome completo:", placeholder="Seu nome completo", key = "novo_nome")
                st.number_input(
                   "Digite sua renda mensal fixa principal (ex:.salário):",
                   min_value = 0.0,
                   step = 100.0,
                   key = "renda_mensal"
                )



          elif tipo_pessoa == "Pessoa Jurídica":
                st.text_input("Digite o nome da empresa:", placeholder="Nome da Empresa", key = "novo_nome_empresa")
                st.number_input(
                   "Digite o faturamento mensal da empresa:",
                   min_value = 0.0,
                   step = 100.0,
                   key = "faturamento_mensal"
                )


          st.text_input("Digite seu email:", placeholder="seuemail@exemplo.com", key = "novo_email")
          st.text_input("Digite sua senha desejada;", placeholder="Mínimo 8 caracteres", type = "password", key = "nova_senha")
          st.text_input("Confirme sua senha:", placeholder="Digite novamente sua senha", type = "password", key = "confirmar_senha")

          st.checkbox(
             "Declaro que tenho 18 anos completos ou mais.",
             key="declaracao_maioridade",
          )

          st.markdown(
             "<div style='height: 18px;'></div>",
             unsafe_allow_html=True
          )

          st.button(
             "Política de Privacidade e Termos de Uso",
             key="btn_politica_cadastro",
             use_container_width=True,
             on_click=abrir_politica,
             args=("cadastro",),
          )

          if not st.session_state.get("codigo_cadastro_enviado", False):

             btn_salvar_nova_conta = st.button(
                "Criar Conta",
                key="btn_salvar_nova_conta",
                type="primary",
                icon=":material/person_add:",
                use_container_width=True
                )

             btn_voltar = st.button(
             "←  Voltar",
             key="btn_voltar_criar_conta",
             use_container_width=True,
             on_click=voltar_para_inicio,
             args=(area_cadastro,)
             )
          else:
             btn_salvar_nova_conta = False
             btn_voltar = False



    if aviso := st.session_state.pop("aviso_codigo_cadastro", None):
       st.error(aviso)

    if btn_salvar_nova_conta and st.session_state.get("declaracao_maioridade") is not True:
       st.error(MENSAGEM_MAIORIDADE)
       btn_salvar_nova_conta = False

    if btn_salvar_nova_conta:
       espera = verificacao.iniciar_solicitacao(st.session_state, "cadastro")
       st.session_state.novo_usuario_pendente = None
       if espera:
          st.warning(f"Aguarde {espera} segundo(s) antes de solicitar outro código.")
          btn_salvar_nova_conta = False

    if btn_salvar_nova_conta:


          email = st.session_state.novo_email.strip().lower()
          senha = st.session_state.nova_senha

          if not email:
             st.error("O e-mail não pode estar vazio.")
          elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
             st.error("Digite um endereço válido de e-mail.")

          else:

             conexao = conectar_banco()
             cursor = conexao.cursor()

             try:

                cursor.execute(
                   """
                   SELECT id_usuario
                   FROM dbo.usuarios
                   WHERE email = ?
                   """,
                   email
                )

                conta_existente = cursor.fetchone()


                senha = st.session_state.nova_senha

                if len(senha) < 8:
                   st.error("A senha deve ter pelo menos 8 caracteres. Por favor, tente novamente.")
                elif not any(char.isdigit() for char in senha) or not any(char.isalpha() for char in senha):
                   st.error("A senha deve conter pelo menos uma letra e um número. Por favor, tente novamente.")
                elif not any(char.isupper() for char in senha) or not any(char.islower() for char in senha):
                   st.error("A senha deve conter pelo menos uma letra maiúscula e uma letra minúscula. Por favor, tente novamente.")
                elif not any(not char.isalnum() for char in senha):
                   st.error("A senha deve conter pelo menos um caractere especial. Por favor, tente novamente.")

                elif  st.session_state.nova_senha != st.session_state.confirmar_senha:
                   st.error("As senhas não coincidem. Por favor, tente novamente.")

                else:
                   ip = ip_cliente()
                   try:
                      permitido = limite_acesso.confirmar_reserva(
                         conexao, cursor, "cadastro_envio", email, ip, registrar=True,
                      )
                   except limite_acesso.ErroLimite:
                      permitido = False
                   if permitido:
                      _enviar_codigo_cadastro(
                         cursor, conexao, email, gerar_hash_senha, enviar_email,
                         tipo_pessoa,
                         conta_existente=conta_existente[0] if conta_existente else None,
                         declaracao_maioridade=True,
                      )
                   else:
                      _enviar_codigo_cadastro(
                         cursor, conexao, email, gerar_hash_senha, enviar_email,
                         tipo_pessoa, pedido_opaco=True, declaracao_maioridade=True,
                      )





             finally:
              cursor.close()
              conexao.close()



    if st.session_state.get("codigo_cadastro_enviado", False):

          col_esq, col_codigo, col_dir_codigo = st.columns([1.4, 2.2, 1.4])

          with col_codigo:
             desafio_cadastro = st.session_state.get("verificacao_cadastro", {})
             if desafio_cadastro.get("teste_local"):
                 if not cadastro_local_permitido(
                     os.getenv("TRIXTER_CADASTRO_LOCAL"),
                     st.get_option("server.address"),
                     desafio_cadastro.get("email", ""),
                 ):
                     verificacao.limpar(st.session_state, "cadastro")
                     st.session_state.codigo_cadastro_enviado = False
                     st.session_state.novo_usuario_pendente = None
                     st.rerun()
                 st.warning("Teste local: nenhum e-mail foi enviado. A conta sera salva no banco configurado.")
                 st.code(desafio_cadastro["codigo"], language=None)
                 st.caption("Codigo de teste valido por 10 minutos.")
             else:
                 st.info("Enviamos um código ao seu e-mail. Ele vale por 10 minutos. Para reenviar, volte e solicite novamente.")

             with st.form("form_validacao_codigo", border=False):

                codigo_digitado_cadastro = st.text_input(
                "Digite o código de confirmação:",
                max_chars=6,
                key="codigo_digitado_cadastro",
                label_visibility="visible"
                )

                btn_validar_codigo_cadastro = st.form_submit_button(
                "Validar código de confirmação",
                type="primary",
                use_container_width=True

                )

             btn_voltar_codigo = st.button(
                "←  Voltar",
                key="btn_voltar_codigo",
                on_click=voltar_para_inicio,
                args=(area_cadastro,),
                use_container_width=True
                )


          if btn_validar_codigo_cadastro:

             email_codigo = (st.session_state.get("verificacao_cadastro") or {}).get("email", "")
             resultado = verificacao.validar(st.session_state, "cadastro", codigo_digitado_cadastro)
             if resultado == "sucesso":
                decisao = _aplicar_limite_codigo(conectar_banco, "cadastro_codigo", email_codigo, False)
             elif resultado in ("invalido", "limite"):
                decisao = _aplicar_limite_codigo(conectar_banco, "cadastro_codigo", email_codigo, True)
             else:
                decisao = True
             if decisao is None:
                verificacao.limpar(st.session_state, "cadastro")
                st.session_state.codigo_cadastro_enviado = False
                st.session_state.novo_usuario_pendente = None
                st.error("Não foi possível concluir agora. Tente novamente.")
                resultado = "erro_limite"
             elif decisao is False and resultado == "sucesso" and st.session_state.get("novo_usuario_pendente"):
                st.session_state.novo_usuario_pendente["pedido_opaco"] = True
             if resultado == "sucesso" and (st.session_state.novo_usuario_pendente or {}).get("pedido_opaco"):
                _recusar_codigo_cadastro(st.session_state.novo_usuario_pendente["email"])
                resultado = "opaco"
             elif resultado == "sucesso" and (st.session_state.novo_usuario_pendente or {}).get("conta_existente"):
                novo_usuario = st.session_state.novo_usuario_pendente
                with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
                   cursor.execute(
                      "SELECT id_usuario FROM dbo.usuarios WHERE id_usuario = ? AND email = ?",
                      novo_usuario["conta_existente"], novo_usuario["email"],
                   )
                   linha = cursor.fetchone()
                if linha:
                   verificacao.limpar(st.session_state, "cadastro")
                   st.session_state.pop("novo_usuario_pendente", None)
                   st.session_state.codigo_cadastro_enviado = False
                   st.session_state.pop("nova_senha", None)
                   st.session_state.pop("confirmar_senha", None)
                   st.session_state.aviso_conta_existente = novo_usuario["email"]
                   st.rerun()
                else:
                   resultado = "inserir"
             if (
                (resultado == "sucesso" or resultado == "inserir")
                and (st.session_state.get("novo_usuario_pendente") or {}).get("declaracao_maioridade") is not True
             ):
                verificacao.limpar(st.session_state, "cadastro")
                st.session_state.codigo_cadastro_enviado = False
                st.session_state.novo_usuario_pendente = None
                st.error(MENSAGEM_MAIORIDADE)
                resultado = "recusado"
             if resultado == "sucesso" or resultado == "inserir":
                novo_usuario = dict(st.session_state.novo_usuario_pendente)
                versao_gravada = None
                try:
                   with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
                      try:
                         if not reservar_email(
                            cursor, novo_usuario["email"], novo_usuario["id_usuario"],
                         ):
                            conexao.rollback()
                         else:
                            cursor.execute(
                               """
                               INSERT INTO dbo.usuarios(
                                  id_usuario,
                                  senha,
                                  tipo_pessoa,
                                  data_entrada,
                                  ultimo_acesso,
                                  email,
                                  nome,
                                  cpf,
                                  renda_mensal,
                                  nome_empresa,
                                  cnpj,
                                  faturamento_mensal,
                                  receber_relatorio_mensal,
                                  receber_alertas,
                                  receber_resumo_semanal
                               )
                               OUTPUT INSERTED.credencial_versao
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                               """,
                               novo_usuario["id_usuario"],
                               novo_usuario["senha"],
                               novo_usuario["tipo_pessoa"],
                               datetime.now(),
                               None,
                               novo_usuario["email"],
                               novo_usuario.get("nome"),
                               novo_usuario.get("cpf"),
                               novo_usuario.get("renda_mensal"),
                               novo_usuario.get("nome_empresa"),
                               novo_usuario.get("cnpj"),
                               novo_usuario.get("faturamento_mensal"),
                               0,
                               0,
                               0,
                            )
                            linha = cursor.fetchone()
                            if linha is None or linha[0] is None:
                               conexao.rollback()
                            else:
                               versao_gravada = int(linha[0])
                               conexao.commit()
                      except pyodbc.Error:
                         conexao.rollback()
                         raise
                except (pyodbc.Error, TypeError, ValueError):
                   versao_gravada = None
                if versao_gravada is None:
                   st.error("Não foi possível concluir agora. Tente novamente.")
                else:
                   novo_usuario["credencial_versao"] = versao_gravada
                   area_cadastro.empty()
                   abrir_sessao(novo_usuario, "onboarding")
                   st.rerun()

             elif resultado not in ("persistente", "opaco", "erro_limite", "recusado"):
                aviso = verificacao.mensagem(st.session_state, "cadastro", resultado)
                if resultado != "invalido":
                   st.session_state.codigo_cadastro_enviado = False
                   st.session_state.novo_usuario_pendente = None
                   st.session_state.aviso_codigo_cadastro = aviso
                   st.rerun()
                st.error(aviso)


def exibir_login(area_login, confirmar_entrada, voltar_para_inicio):

    if politica_aberta("login"):
        exibir_politica()
        st.button(
            "← Voltar",
            key="btn_fechar_politica",
            width="content",
            on_click=fechar_politica,
        )
        return

    col_esq, col_form, col_dir = st.columns([1.4,2.2,1.4])

    with col_form:

       st.markdown(
          """
       <div style="text-align: center;margin-bottom: 22px;">
       <svg width="58" height="65" viewBox= "0 0 64 72" xmlns="https://www.w3.org/2000/svg">
       <path
       d="M20 4
       C23 2 27 3 32 5
       C37 3 41 2 44 4
       C43 8 41 11 39 13
       L25 13
       C23 10 21 7 20 4
       Z"
       fill="#A67C00"
       />
       <path
       d="M25 14.5
       C22 20 12 30 10 43
       C8 57 17 65 32 65
       C47 65 56 57 54 43
       C52 30 42 20 39 14
       Z"
       fill="#b87928"
       />
       <rect x="30.75" y="26" width="2.5" height="6" rx="1.25" fill="#FFFFFF"/>
       <rect x="30.75" y="49.50" width="2.5" height="6" rx="1.25" fill="#FFFFFF"/>
       <text x="32" y="52"  text-anchor="middle" fill="#FFFFFF" font-size="30" font-family="Arial, sans-serif" font-weight="500" >S</text>
       </svg>
       <div style="font-size: 34px; font-weight: 800; color: #172033; line-height: 1.1;">
       Trixter
       </div>
       <div style="text-align:left; margin-top:10px;">
          <div style="font-size:20px; font-weight:700; color:#172033;">
             Entrar
          </div>
          <div style="font-size:13px; color:#5f6470; margin-top:2px;">
             Informe seu e-mail e senha para acessar sua conta.
          </div>
       </div>
       """,
       unsafe_allow_html=True
       )

       if "mensagem_sucesso" in st.session_state:
          st.success(st.session_state.mensagem_sucesso)
          del st.session_state.mensagem_sucesso

       aviso_banco = st.session_state.pop("aviso_banco", None)
       if aviso_banco:
          st.warning(aviso_banco)

       st.text_input("E-mail:", placeholder= "Digite seu e-mail", key="email_entrada")
       st.text_input("Senha:", placeholder= "Digite sua senha", type="password", key="senha")

       if st.session_state.pop("erro_login", False):
          st.error(limite_acesso.MENSAGEM_LOGIN)

       st.markdown(
          "<div style='height: 18px;'></div>",
          unsafe_allow_html=True
       )


       st.button(
          "Entrar",
          key="btn_confirmar_entrada",
          type="primary",
          icon=":material/person:",
          use_container_width=True,
          on_click=confirmar_entrada,
          args=(area_login,)
       )

       btn_voltar_entrar = st.button(
          "← Voltar",
          key= "voltar_entrar",
          use_container_width=True,
          on_click=voltar_para_inicio,
          args=(area_login,)
          )

       st.button(
          "Política de Privacidade e Termos de Uso",
          key="btn_politica_login",
          use_container_width=True,
          on_click=abrir_politica,
          args=("login",),
       )


def exibir_recuperacao(area_recuperacao, conectar_banco, gerar_hash_senha, enviar_email, voltar_para_inicio):
    col_esq, col_form, col_dir = st.columns([1.4, 2.2, 1.4])

    with col_form:
       st.markdown(
          """
       <div style="text-align: center;margin-bottom: 22px;">
       <svg width="58" height="65" viewBox= "0 0 64 72" xmlns="https://www.w3.org/2000/svg">
       <path
       d="M20 4
       C23 2 27 3 32 5
       C37 3 41 2 44 4
       C43 8 41 11 39 13
       L25 13
       C23 10 21 7 20 4
       Z"
       fill="#A67C00"
       />
       <path
       d="M25 14.5
       C22 20 12 30 10 43
       C8 57 17 65 32 65
       C47 65 56 57 54 43
       C52 30 42 20 39 14
       Z"
       fill="#b87928"
       />
       <rect x="30.75" y="26" width="2.5" height="6" rx="1.25" fill="#FFFFFF"/>
       <rect x="30.75" y="49.50" width="2.5" height="6" rx="1.25" fill="#FFFFFF"/>
       <text x="32" y="52"  text-anchor="middle" fill="#FFFFFF" font-size="30" font-family="Arial, sans-serif" font-weight="500" >S</text>
       </svg>
       <div style="font-size: 34px; font-weight: 800; color: #172033; line-height: 1.1;">
       Trixter
       </div>

       <div style="text-align:left; margin-top:10px;">
          <div style="font-size:20px; font-weight:700; color:#172033;">
              Recuperar senha
          </div>

          <div style="font-size:13px; color:#5f6470; margin-top:2px;">
              Informe o e-mail cadastrado para receber o código de recuperação.
          </div>
       </div>
       """,
       unsafe_allow_html=True
       )


       st.text_input(
       "Digite o e-mail cadastrado:",
       placeholder="Digite o e-mail",
       key="email_recuperacao"
     )

       btn_enviar_codigo = st.button("Enviar código de recuperação")

       if aviso := st.session_state.pop("aviso_recuperacao", None):
          st.info(aviso)

       if btn_enviar_codigo:
          espera = verificacao.iniciar_solicitacao(st.session_state, "recuperacao")
          if espera:
             st.warning(f"Aguarde {espera} segundo(s) antes de solicitar outro código.")
          else:
             email_recuperacao = st.session_state.email_recuperacao.strip().lower()
             ip = ip_cliente()
             with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
                try:
                   permitido = limite_acesso.confirmar_reserva(
                      conexao, cursor, "recuperacao_envio", email_recuperacao, ip, registrar=True,
                   )
                except limite_acesso.ErroLimite:
                   permitido = False
                usuario_recuperacao = None
                codigo_recuperacao = _codigo_opaco()
                if permitido:
                   try:
                      cursor.execute(
                         "SELECT id_usuario FROM dbo.usuarios WHERE email = ?",
                         email_recuperacao,
                      )
                      usuario_recuperacao = cursor.fetchone()
                   except Exception:
                      usuario_recuperacao = None
                      codigo_recuperacao = _codigo_opaco()
             if not permitido or usuario_recuperacao is None:
                _fechar_pedido_recuperacao(email_recuperacao, codigo_recuperacao, None)
             else:
                try:
                   enviar_email(
                      destinatario=email_recuperacao,
                      assunto="Código para redefinição de senha",
                      corpo=(f"Olá!\n\nSeu código para redefinir sua senha é: {codigo_recuperacao}"
                             "\n\nEste código é válido por 10 minutos."
                             "\nSe você não solicitou a redefinição de senha, ignore esta mensagem.")
                   )
                except Exception:
                   _fechar_pedido_recuperacao(email_recuperacao, _codigo_opaco(), None)
                else:
                   _fechar_pedido_recuperacao(
                      email_recuperacao, codigo_recuperacao, usuario_recuperacao[0],
                   )

       if st.session_state.get("verificacao_recuperacao"):
          codigo_digitado = st.text_input(
             "Digite o código de recuperação:", max_chars=6, key="codigo_digitado_recuperacao"
          )
          if st.button("Validar código"):
             email_codigo = (st.session_state.get("verificacao_recuperacao") or {}).get("email", "")
             resultado = verificacao.validar(st.session_state, "recuperacao", codigo_digitado)
             if resultado == "sucesso":
                decisao = _aplicar_limite_codigo(conectar_banco, "recuperacao_codigo", email_codigo, False)
             elif resultado in ("invalido", "limite"):
                decisao = _aplicar_limite_codigo(conectar_banco, "recuperacao_codigo", email_codigo, True)
             else:
                decisao = True
             if decisao is None:
                verificacao.limpar(st.session_state, "recuperacao")
                st.error("Não foi possível concluir agora. Tente novamente.")
                resultado = "erro_limite"
             elif decisao is False and resultado == "sucesso":
                verificacao.registrar(
                    st.session_state, "recuperacao", _codigo_opaco(), email_codigo, None,
                    proteger=True,
                )
                st.session_state.verificacao_recuperacao["tentativas"] = 1
                resultado = "invalido"
             if resultado == "sucesso":
                st.session_state.aviso_recuperacao = "Código validado! Você tem 10 minutos para redefinir a senha."
                st.rerun()
             elif resultado == "invalido":
                st.error(verificacao.mensagem(st.session_state, "recuperacao", resultado))
             elif resultado != "erro_limite":
                st.session_state.aviso_recuperacao = verificacao.mensagem(st.session_state, "recuperacao", resultado)
                st.rerun()

       tinha_autorizacao = bool(st.session_state.get("autorizacao_recuperacao"))
       autorizacao = verificacao.autorizacao(st.session_state, "recuperacao")
       if tinha_autorizacao and not autorizacao:
          st.error("O prazo para redefinir a senha expirou. Solicite um novo código.")

       if autorizacao:
          st.text_input("Digite a nova senha:", type="password", key="nova_senha_recuperacao")
          st.text_input("Confirme a nova senha:", type="password", key="confirmar_nova_senha_recuperacao")
          if st.button("Redefinir Senha"):
             autorizacao = verificacao.autorizacao(st.session_state, "recuperacao")
             senha = st.session_state.nova_senha_recuperacao
             if not autorizacao:
                st.error("O prazo para redefinir a senha expirou. Solicite um novo código.")
             elif senha != st.session_state.confirmar_nova_senha_recuperacao:
                st.error("As senhas não coincidem.")
             elif (len(senha) < 8 or not any(c.isdigit() for c in senha)
                   or not any(c.isupper() for c in senha) or not any(c.islower() for c in senha)
                   or not any(not c.isalnum() for c in senha)):
                st.error("A senha deve ter pelo menos 8 caracteres, letras maiúsculas e minúsculas, número e caractere especial.")
             else:
                senha_hash = gerar_hash_senha(senha)
                if (
                   autorizacao.get("finalidade", "recuperacao") == "recuperacao"
                   and autorizacao.get("usuario_id")
                ):
                   from .credencial import gravar_senha
                   with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
                      if gravar_senha(
                         cursor, autorizacao["usuario_id"], senha_hash, autorizacao["email"],
                      ) is None:
                         conexao.rollback()
                      else:
                         conexao.commit()
                verificacao.limpar(st.session_state, "recuperacao")
                st.session_state.mensagem_sucesso = MENSAGEM_REDEFINICAO
                st.session_state.recuperar_senha = False
                st.session_state.entrar = True
                st.rerun()

       st.button(
           "Voltar", key="voltar_recuperacao_senha",
           on_click=voltar_para_inicio,
           args=(area_recuperacao,),
       )
