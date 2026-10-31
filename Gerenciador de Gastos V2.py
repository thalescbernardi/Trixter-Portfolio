from trixter.fluxo_tela import exibir_fluxo_caixa
from trixter.demo import criar_demo_pj, hash_senha_demo
from trixter.demo_expurgo import ID_CONTA_DEMO, excluir_demonstracao
from trixter.categorias import listar_categorias
from trixter.lancamento import exibir_lancamento
from trixter.saldo import exibir_saldo
from trixter.meta import exibir_meta
from trixter.dashboard import exibir_dashboard
from trixter.orcamento import exibir_orcamento
from trixter.relatorio_mensal import exibir_relatorio_mensal
from trixter.configuracoes import exibir_configuracoes
from trixter.importacao import exibir_importacao_pdf
from trixter.planejamento_mensal import exibir_planejamento_mensal
from trixter.recorrencias_tela import exibir_recorrencias
from trixter.acesso import (
    abrir_sessao,
    descartar_credenciais_digitadas,
    exibir_cadastro,
    exibir_landing,
    exibir_login,
    exibir_recuperacao,
    ip_cliente,
)
from trixter.onboarding import exibir_onboarding
from trixter.credencial import (
    MENSAGEM_SESSAO_INDISPONIVEL,
    SessaoIndisponivel,
    preparar_operacao,
    reservar_email,
)
from trixter.sessao import (
    descartar_exportacao,
    encerrar_sessao_local,
    garantir_acesso,
    garantir_navegacao,
    limpar_pdf_da_conta,
)
from trixter.privacidade import descartar_politica_fora_de_seguranca
from trixter.historico_tela import exibir_historico
from trixter.planejamento_anual import exibir_planejamento_do_ano
from trixter.simulador import exibir_simulador
from trixter.inteligencia import exibir_inteligencia
from trixter.alertas_tela import exibir_alertas
from trixter.seguranca import exibir_seguranca
from html import escape
from pathlib import Path
from trixter.inicio import aplicar_estilo, consultar_resumo, renderizar_resumo
from trixter.senha import gerar_hash_senha, senha_confere
from trixter import estilo
from trixter import limite_acesso
from trixter import diagnostico_login
from trixter import verificacao
from trixter import alertas as regras_alertas
from contextlib import closing
from trixter.relatorios import gerar_pdf_relatorio, formatar_moeda
from trixter.infra import abrir_com_retomada, enviar_email as enviar_email_smtp
import uuid
from datetime import datetime, date
import streamlit as st
from pypdf import PdfReader
import pyodbc
estilo.publicar(estilo.ESTILO_BASE)


garantir_acesso(st.session_state)
if st.session_state.usuario_logado:
    descartar_credenciais_digitadas(st.session_state)

# Oculta o painel anterior antes das consultas e da reconstrução do cabeçalho.
estilo.publicar_menus(
    st.session_state.menu_conta_aberto,
    st.session_state.menu_alertas_aberto,
)




if st.session_state.usuario_logado:
    estilo.publicar(estilo.ESTILO_LOGADO)

if not st.session_state.usuario_logado:
   estilo.publicar_fundo()

if (
   not st.session_state.usuario_logado
   and st.session_state.criar_conta
):
   estilo.publicar(estilo.ESTILO_CADASTRO)



if not st.session_state.usuario_logado:
   estilo.publicar(estilo.ESTILO_SEM_SESSAO)




def abrir_acesso(tela, area):
    area.empty()
    st.session_state.entrar = tela == "entrar"
    st.session_state.criar_conta = tela == "criar_conta"
    st.session_state.recuperar_senha = False
    if tela == "criar_conta":
        st.session_state.pop("declaracao_maioridade", None)


if not st.session_state.usuario_logado:

    if (
       not st.session_state.criar_conta
       and not st.session_state.entrar
       and not st.session_state.recuperar_senha
    ):

       area_landing = st.empty()

       with area_landing.container():
         exibir_landing(area_landing, abrir_acesso)






def buscar_recorrencias_usuario(id_usuario):
   conexao = conectar_banco()
   cursor = conexao.cursor()

   cursor.execute(
      """
      SELECT *
      FROM dbo.recorrencias
      WHERE id_usuario = ?
      """,
      id_usuario
   )

   resultados = cursor.fetchall()
   colunas = [coluna[0] for coluna in cursor.description]
   cursor.close()
   conexao.close()

   return [dict(zip(colunas,linha)) for linha in resultados]




def conectar_banco():

   def abrir():
      return pyodbc.connect(
         f"DRIVER={{{st.secrets['database']['driver']}}};"
         f"SERVER={st.secrets['database']['server']};"
         f"DATABASE={st.secrets['database']['database']};"
         f"UID={st.secrets['database']['username']};"
         f"PWD={st.secrets['database']['password']};"
         "Encrypt=yes;"
         "TrustServerCertificate=no;",
         timeout=15
      )

   return abrir_com_retomada(abrir)


def criar_demo_temporaria(id_usuario_original, tipo_pessoa="Pessoa Física"):
   if tipo_pessoa == "Pessoa Jurídica":
      return criar_demo_pj(conectar_banco)

   conexao = conectar_banco()
   cursor = conexao.cursor()
   try:
      usuario_demo = _preencher_demo_temporaria(conexao, cursor)
   except Exception:
      conexao.rollback()
      raise
   finally:
      cursor.close()
      conexao.close()
   return usuario_demo


def _preencher_demo_temporaria(conexao, cursor):
   cursor.execute(
      """
      SELECT *
         FROM dbo.usuarios
         WHERE id_usuario = ?
      """,
      ID_CONTA_DEMO
   )

   usuario_demo = cursor.fetchone()
   if usuario_demo is None:
      raise ValueError("A demonstração PF não está disponível: a conta modelo não foi encontrada neste banco.")
   colunas = [coluna[0] for coluna in cursor.description]

   usuario_demo = dict(zip(colunas, usuario_demo))

   usuario_demo["id_usuario"] = str(uuid.uuid4())

   usuario_demo["email"] = f"{usuario_demo['id_usuario']}@demo.trixter.local"

   usuario_demo["cpf"] = None
   usuario_demo["cnpj"] = None
   usuario_demo["senha"] = hash_senha_demo()

   if not reservar_email(cursor, usuario_demo["email"], usuario_demo["id_usuario"]):
      raise RuntimeError("Não foi possível reservar o e-mail da conta demonstrativa.")

   cursor.execute(
      """
      INSERT INTO dbo.usuarios (
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
        objetivo_financeiro,
        valor_objetivo,
        data_objetivo,
        valor_acumulado_meta,
        onboarding_concluido,
        conta_demo
      )
        VALUES (
        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
        """,
        (
        usuario_demo["id_usuario"],
        usuario_demo["senha"],
        usuario_demo["tipo_pessoa"],
        datetime.now(),
        None,
        usuario_demo["email"],
        usuario_demo["nome"],
        usuario_demo["cpf"],
        usuario_demo["renda_mensal"],
        usuario_demo["nome_empresa"],
        usuario_demo["cnpj"],
        usuario_demo["faturamento_mensal"],
        usuario_demo["objetivo_financeiro"],
        usuario_demo["valor_objetivo"],
        usuario_demo["data_objetivo"],
        usuario_demo["valor_acumulado_meta"],
        1,
        1
   )
   )

   cursor.execute(
      """
      INSERT INTO dbo.categorias (
      id_usuario,
      nome,
      tipo
      )
      SELECT
        ?,
        nome,
        tipo
      FROM dbo.categorias
      WHERE id_usuario = ?
      """,
      usuario_demo["id_usuario"],
      ID_CONTA_DEMO
   )

   cursor.execute(
    """
    INSERT INTO dbo.receitas (
        id_transacao,
        id_usuario,
        data,
        descricao,
        valor,
        categoria
    )
    SELECT
        CONVERT(VARCHAR(36), NEWID()),
        ?,
        data,
        descricao,
        valor,
        categoria
    FROM dbo.receitas
    WHERE id_usuario = ?
    """,
    usuario_demo["id_usuario"],
    ID_CONTA_DEMO
)

   cursor.execute(
    """
    INSERT INTO dbo.gastos (
        id_transacao,
        id_usuario,
        data,
        descricao,
        valor,
        categoria
    )
    SELECT
        CONVERT(VARCHAR(36), NEWID()),
        ?,
        data,
        descricao,
        valor,
        categoria
    FROM dbo.gastos
    WHERE id_usuario = ?
    """,
    usuario_demo["id_usuario"],
    ID_CONTA_DEMO
)

   cursor.execute(
    """
    INSERT INTO dbo.orcamentos (
        id_orcamento,
        id_usuario,
        categoria,
        mes,
        ano,
        valor_limite
    )
    SELECT
        CONVERT(VARCHAR(36), NEWID()),
        ?,
        categoria,
        mes,
        ano,
        valor_limite
    FROM dbo.orcamentos
    WHERE id_usuario = ?
    """,
    usuario_demo["id_usuario"],
    ID_CONTA_DEMO
)

   cursor.execute(
    """
    INSERT INTO dbo.recorrencias (
        id_recorrencia,
        id_usuario,
        tipo,
        categoria,
        descricao,
        valor,
        frequencia,
        proxima_execucao,
        ativa,
        dia_semana,
        dia,
        mes
    )
    SELECT
        CONVERT(VARCHAR(36), NEWID()),
        ?,
        tipo,
        categoria,
        descricao,
        valor,
        frequencia,
        proxima_execucao,
        ativa,
        dia_semana,
        dia,
        mes
    FROM dbo.recorrencias
    WHERE id_usuario = ?
    """,
    usuario_demo["id_usuario"],
    ID_CONTA_DEMO
)

   cursor.execute(
    """
    INSERT INTO dbo.planejamentos (
        id_planejamento,
        id_usuario,
        tipo,
        categoria,
        descricao,
        valor,
        data
    )
    SELECT
        CONVERT(VARCHAR(36), NEWID()),
        ?,
        tipo,
        categoria,
        descricao,
        valor,
        data
    FROM dbo.planejamentos
    WHERE id_usuario = ?
    """,
    usuario_demo["id_usuario"],
    ID_CONTA_DEMO
)

   conexao.commit()

   usuario_demo.pop("senha", None)
   usuario_demo["conta_demo"] = True
   usuario_demo["credencial_versao"] = 1
   return usuario_demo



def excluir_demo_temporaria(id_usuario_demo):
   conexao = conectar_banco()
   try:
      excluir_demonstracao(conexao, id_usuario_demo)
   finally:
      conexao.close()








def enviar_email(destinatario, assunto, corpo, anexo=None):
    return enviar_email_smtp(
        {"email": dict(st.secrets["email"])}, destinatario, assunto, corpo, anexo
    )


def confirmar_entrada(area_login):
    email = st.session_state.email_entrada.strip().lower()
    ip = ip_cliente()
    usuario_encontrado = None
    try:
        with closing(diagnostico_login.executar("conexao_1", conectar_banco)) as conexao, closing(diagnostico_login.executar("cursor_1", conexao.cursor)) as cursor:
            try:
                with diagnostico_login.etapa("consulta_usuario"):
                    cursor.execute(
                        """
                        SELECT * FROM dbo.usuarios
                        WHERE email = ?
                        """,
                        email,
                    )
                    linha = cursor.fetchone()
                    if linha:
                        colunas = [coluna[0] for coluna in cursor.description]
                        usuario_encontrado = dict(zip(colunas, linha))
            except pyodbc.Error:
                diagnostico_login.executar("rollback_login", conexao.rollback)
                raise
    except pyodbc.Error:
        st.session_state.aviso_banco = (
            "O banco está pausado e ainda está voltando. "
            "Espere cerca de um minuto e toque em Entrar de novo."
        )
        return

    hash_armazenado = usuario_encontrado["senha"] if usuario_encontrado else None
    senha_correta = senha_confere(st.session_state.senha, hash_armazenado)
    try:
        with closing(diagnostico_login.executar("conexao_2", conectar_banco)) as conexao, closing(diagnostico_login.executar("cursor_2", conexao.cursor)) as cursor:
            try:
                if not (usuario_encontrado and senha_correta):
                    diagnostico_login.executar(
                        "registrar_tentativa", limite_acesso.confirmar_reserva,
                        conexao, cursor, "login", email, ip, registrar=True,
                    )
                    st.session_state.erro_login = True
                    return
                if not diagnostico_login.executar(
                    "verificar_limites", limite_acesso.confirmar_reserva,
                    conexao, cursor, "login", email, ip, registrar=False,
                ):
                    st.session_state.erro_login = True
                    return
                diagnostico_login.executar("liberar_controles", limite_acesso.liberar_par, cursor, "login", email, ip)
                with diagnostico_login.etapa("atualizar_ultimo_acesso"):
                    cursor.execute(
                       """
                       UPDATE usuarios
                       SET ultimo_acesso = GETDATE()
                       WHERE id_usuario = ?
                       """,
                       usuario_encontrado["id_usuario"]
                    )
                diagnostico_login.executar("commit_login", conexao.commit)
            except pyodbc.Error:
                diagnostico_login.executar("rollback_login", conexao.rollback)
                raise
            except limite_acesso.ErroLimite:
                diagnostico_login.executar("rollback_login", conexao.rollback)
                raise
    except limite_acesso.ErroLimite:
        st.session_state.erro_login = True
        return
    except pyodbc.Error:
        st.session_state.aviso_banco = (
            "O banco está pausado e ainda está voltando. "
            "Espere cerca de um minuto e toque em Entrar de novo."
        )
        return

    area_login.empty()
    tela = "onboarding" if not usuario_encontrado["onboarding_concluido"] else "menu"
    abrir_sessao(usuario_encontrado, tela)



def voltar_para_inicio(area=None):
    if area is not None:
        area.empty()
    st.session_state.criar_conta = False
    st.session_state.entrar = False
    st.session_state.recuperar_senha = False

    verificacao.limpar(st.session_state, "cadastro")
    verificacao.limpar(st.session_state, "recuperacao")
    st.session_state.pop("aviso_recuperacao", None)
    st.session_state.pop("codigo_digitado_cadastro", None)
    st.session_state.pop("codigo_digitado_recuperacao", None)
    st.session_state.pop("codigo_digitado_email", None)
    st.session_state.codigo_cadastro_enviado = False
    st.session_state.codigo_cadastro = None
    st.session_state.novo_usuario_pendente = None
    st.session_state.aviso_conta_existente = None
    st.session_state.pop("declaracao_maioridade", None)
    st.session_state.pop("politica_origem", None)
    st.session_state.pop("politica_campos", None)


def gerar_alertas_orcamento(id_usuario):
    with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
        return regras_alertas.gerar_alertas_orcamento(cursor, id_usuario, date.today())


def gerar_alertas_recorrencias(id_usuario):
    with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
        return regras_alertas.gerar_alertas_recorrencias(cursor, id_usuario, date.today())


def gerar_alertas_meta(id_usuario):
    with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
        return regras_alertas.gerar_alertas_meta(cursor, id_usuario, date.today())


def gerar_alertas_provisao(id_usuario):
    with closing(conectar_banco()) as conexao, closing(conexao.cursor()) as cursor:
        return regras_alertas.gerar_alertas_provisao(cursor, id_usuario, date.today())


def enviar_alertas_por_email(id_usuario, email):
    alertas = (
        gerar_alertas_orcamento(id_usuario)
        + gerar_alertas_recorrencias(id_usuario)
        + gerar_alertas_meta(id_usuario)
        + gerar_alertas_provisao(id_usuario)
    )

    mensagens_alertas = []

    for alerta in alertas:
        mensagens_alertas.append(
            f"- {alerta['mensagem']}"
        )

    assunto_alertas = "Seus alertas financeiros - Trixter"

    corpo_alertas = (
        "Olá! \n\n"
        "Estes são os seus alertas financeiros atuais:\n\n"
        + "\n".join(mensagens_alertas)
        + "\n\nAtenciosamente,\n"
        "Trixter"
    )

    enviar_email(
        destinatario=email,
        assunto=assunto_alertas,
        corpo=corpo_alertas
    )


def marcar_validacao_codigo():
    st.session_state.validar_codigo = True



def entrar_conta_demo():
    original = st.session_state.usuario_atual.copy()
    usuario_demo_temporario = criar_demo_temporaria(
       original["id_usuario"],
       original["tipo_pessoa"],
    )
    usuario_demo_temporario.pop("senha", None)
    st.session_state.usuario_original = original
    descartar_exportacao(st.session_state)
    st.session_state.usuario_atual = usuario_demo_temporario
    st.session_state.tela_atual = "menu"

def voltar_conta_original():

    id_demo_temporaria = (
      st.session_state.usuario_atual["id_usuario"]
   )

    excluir_demo_temporaria(id_demo_temporaria)
    limpar_pdf_da_conta(st.session_state, id_demo_temporaria)
    descartar_exportacao(st.session_state)

    st.session_state.usuario_atual = (
      st.session_state.usuario_original
   )
    st.session_state.usuario_original = None
    st.session_state.tela_atual = "menu"


def limpar_tela_aberta(area_conteudo, area_voltar=None):
    # Todas as telas dividem o mesmo espaço. Esvaziar esse espaço
    # também cobre a meta, que se chama visualizar_meta.
    if area_voltar is not None:
        area_voltar.empty()
    if area_conteudo is not None:
        area_conteudo.empty()


def alternar_menu_conta():
    st.session_state.menu_conta_aberto = (
        not st.session_state.menu_conta_aberto
    )

    if st.session_state.menu_conta_aberto:
        st.session_state.menu_alertas_aberto = False


def alternar_menu_alertas():
    abrir_alertas = not st.session_state.menu_alertas_aberto
    if abrir_alertas:
        st.session_state.menu_conta_aberto = False
    st.session_state.menu_alertas_aberto = abrir_alertas




def abrir_tela_alertas():
    st.session_state.menu_alertas_aberto = False
    st.session_state.tela_atual = "alertas"


def abrir_tela_cadastro(tela, area_conteudo=None, area_voltar=None):
    from trixter.inicio import abrir_cadastro
    abrir_cadastro(tela, st.session_state, area_conteudo, area_voltar)


def abrir_tela_menu_conta(tela, slot_menu_conta, area_aplicacao=None):
    slot_menu_conta.empty()
    if area_aplicacao is not None:
        area_aplicacao.empty()
    st.session_state.menu_conta_aberto = False
    st.session_state.menu_alertas_aberto = False
    st.session_state.tela_atual = tela


def sair_conta(area_menu_conta, area_aplicacao=None):
    atual = st.session_state.get("usuario_atual") or {}
    original = st.session_state.get("usuario_original")
    if atual.get("conta_demo") and isinstance(original, dict) and original.get("id_usuario"):
        try:
            excluir_demo_temporaria(atual["id_usuario"])
        except Exception:
            st.session_state.aviso_saida_demo = (
                "Não foi possível encerrar a demonstração. Tente novamente."
            )
            return
        st.session_state.pop("aviso_saida_demo", None)

    if area_aplicacao is not None:
        # Substitui o conteúdo e oculta a navegação na mesma atualização.
        # Este estilo temporário desaparece quando a landing é reconstruída.
        area_aplicacao.markdown(
            estilo.folha(estilo.ESTILO_OCULTAR_NAVEGACAO),
            unsafe_allow_html=True,
        )
    else:
        area_menu_conta.empty()

    encerrar_sessao_local(st.session_state)










st.set_page_config(
    page_title = "Trixter | Gestão Financeira",
    page_icon = str(Path(__file__).parent / "assets" / "saquinho.svg"),
    layout = "wide",
)



garantir_navegacao(st.session_state)
descartar_politica_fora_de_seguranca(st.session_state)




falha_sessao = False
if st.session_state.usuario_logado:
    try:
        if preparar_operacao(conectar_banco, st.session_state) == "revogada":
            st.rerun()
    except SessaoIndisponivel:
        falha_sessao = True

area_aplicacao = st.empty()
if falha_sessao:
    st.error(MENSAGEM_SESSAO_INDISPONIVEL)
    st.button("Tentar novamente", key="btn_confirmar_sessao")
elif not st.session_state.usuario_logado:

     area_cadastro = st.empty()

     if st.session_state.criar_conta:
       with area_cadastro.container():
         exibir_cadastro(area_cadastro, conectar_banco, gerar_hash_senha, enviar_email, voltar_para_inicio)


     area_login = st.empty()

     if (
            not st.session_state.usuario_logado
            and st.session_state.entrar
            and not st.session_state.recuperar_senha
    ):
            with area_login.container():
               exibir_login(area_login, confirmar_entrada, voltar_para_inicio)



     area_recuperacao = st.empty()
     if st.session_state.recuperar_senha:

         with area_recuperacao.container():
             exibir_recuperacao(area_recuperacao, conectar_banco, gerar_hash_senha, enviar_email, voltar_para_inicio)



else:

         aviso_saida = st.session_state.pop("aviso_saida_demo", None)
         if aviso_saida:
             st.error(aviso_saida)

         with area_aplicacao.container():
             tipo_pessoa = st.session_state.usuario_atual["tipo_pessoa"]

             if tipo_pessoa == "Pessoa Física":
                nome_exibicao = st.session_state.usuario_atual["nome"]
             elif tipo_pessoa == "Pessoa Jurídica":
                nome_exibicao = st.session_state.usuario_atual["nome_empresa"]

             artigo_gasto = "a" if tipo_pessoa == "Pessoa Jurídica" else "o"
             sufixo_gasto = "a" if tipo_pessoa == "Pessoa Jurídica" else "o"
             termo_gasto = "Despesa" if tipo_pessoa == "Pessoa Jurídica" else "Gasto"



             aplicar_estilo(st.session_state.tela_atual)

             area_onboarding = st.empty()
             if st.session_state.tela_atual ==  "onboarding":
              with area_onboarding.container():
                exibir_onboarding(area_onboarding, conectar_banco, nome_exibicao)


             if(
                st.session_state.usuario_logado
                and st.session_state.tela_atual == "menu"
             ):
              # O banco responde antes de qualquer texto do menu.
              # A saudação, os alertas e o resumo entram juntos.
              id_menu = st.session_state.usuario_atual["id_usuario"]
              alertas_sininho = (
                   gerar_alertas_orcamento(id_menu)
                   + gerar_alertas_recorrencias(id_menu)
                   + gerar_alertas_meta(id_menu)
                   + gerar_alertas_provisao(id_menu)
              )
              try:
                  with closing(conectar_banco()) as conexao_resumo:
                      numeros_resumo = consultar_resumo(conexao_resumo, id_menu, date.today())
              except Exception:
                  numeros_resumo = None

              with st.container(key="cabecalho_menu"):


                col_saudacao, col_alertas, col_perfil = st.columns([8,0.5,0.5])

                partes_nome = nome_exibicao.split()

                if len(partes_nome) >= 2:
                   iniciais = partes_nome[0][0] + partes_nome[-1][0]
                else:
                   iniciais = partes_nome[0][0]

                iniciais = iniciais.upper()

                estilo.publicar(estilo.ESTILO_BOTOES_MENU)

                with col_saudacao:



                   st.markdown(
                      f"""
                      <div class="trixter-saudacao">
                         Olá, {escape(((nome_exibicao or "").split() or ["você"])[0] if tipo_pessoa == "Pessoa Física" else (nome_exibicao or "você"))}! 👋
                      </div>
                      """,
                      unsafe_allow_html=True
                      )


                   st.write(
                    "Veja como estão suas finanças neste mês."
                   )



                with col_perfil:
                   with st.container(key="ancora_menu_conta"):
                      slot_menu_conta = st.empty()
                with col_alertas:
                   with st.container(key="ancora_menu_alertas"):
                      slot_menu_alertas = st.empty()

                tem_alertas = bool(alertas_sininho)



                if tem_alertas:
                 estilo.publicar(estilo.ESTILO_ALERTA)


                with col_alertas:
                   st.button(
                      "",
                      key="btn_alertas",
                      on_click=alternar_menu_alertas
                   )

                with col_perfil:
                   st.button(
                      iniciais,
                      key="btn_perfil",
                      on_click=alternar_menu_conta,
                   )





                if st.session_state.menu_conta_aberto:

                   with slot_menu_conta.container():

                      area_menu_conta = st.empty()

                      with area_menu_conta.container(border=True, key="menu_conta_box"):

                         if st.session_state.usuario_atual["tipo_pessoa"] == "Pessoa Jurídica":
                          nome_exibicao = st.session_state.usuario_atual["nome_empresa"]
                         else:
                          nome_exibicao = st.session_state.usuario_atual["nome"]

                         st.markdown(
                            f"""
                            <div class="dados-menu-conta">
                              <div class="nome-menu-conta">{escape(nome_exibicao)}</div>
                              <div class="email-menu-conta">{escape(st.session_state.usuario_atual["email"])}</div>
                              <div class="tipo-menu-conta">{escape(st.session_state.usuario_atual["tipo_pessoa"])}</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                         )

                         st.button(
                             'Configurações',
                             key="menu_configuracoes",
                             use_container_width=True,
                             on_click=abrir_tela_menu_conta,
                             args=("configuracoes", slot_menu_conta, area_aplicacao),
                         )

                         st.button(
                             'Segurança',
                             key="menu_seguranca",
                             use_container_width=True,
                             on_click=abrir_tela_menu_conta,
                             args=("seguranca", slot_menu_conta, area_aplicacao),
                         )

                         st.divider()

                         st.button(
                            "Sair",
                            key="menu_sair",
                            use_container_width=True,
                            on_click=sair_conta,
                            args=(area_menu_conta, area_aplicacao)
                         )



                if st.session_state.menu_alertas_aberto:


                   with slot_menu_alertas.container():


                      with st.container(border=True, key="menu_alertas_box"):
                         st.markdown("**Notificações**")

                         id_usuario = st.session_state.usuario_atual["id_usuario"]



                         if alertas_sininho:


                            for alerta in alertas_sininho:
                               if alerta["nivel"] == "crtico":
                                  st.error(alerta["mensagem"].replace("$", "\\$"))
                               elif alerta["nivel"] == "atencao":
                                  st.warning(alerta["mensagem"].replace("$", "\\$"))

                         else:
                            st.write("Nenhuma notificação no momento.")


                         if st.session_state.get("alertas_email_sucesso"):
                            st.success(st.session_state.alertas_email_sucesso)

                         st.button(
                            "Ver todos os alertas",
                            key="btn_ver_todos_alertas",
                            use_container_width=True,
                            on_click=abrir_tela_alertas
                         )


                renderizar_resumo(
                    conectar_banco,
                    st.session_state.usuario_atual,
                    termo_gasto,
                    numeros_resumo,
                )

             area_transicao = st.empty()
             with area_transicao.container():
                 area_funcionalidade = st.empty()
                 area_botao_voltar = st.empty()



             if st.session_state.usuario_logado:

              with st.sidebar:


                   st.markdown(
                      """
                   <div style="display:flex; align-items: center; justify-content: center; gap:8px;">
                   <svg width="42" height="48" viewBox= "0 0 64 72" xmlns="https://www.w3.org/2000/svg">
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
                   <div style="font-size: 34px; font-weight: 800; color: #172033; line-height: 1;">
                   Trixter
                   </div>
                   </div>
                   <div style = "text-align: center; color:#B87928; font-size:10px; font-weight:600; letter-spacing:2px; margin-top:4px; margin-bottom:24px;">
                      SEU DINHEIRO, SEU FUTURO
                   </div>
                   """,
                   unsafe_allow_html=True
                   )


                   st.markdown(
                   """
                   <div style="display:flex; align-items:center; gap:10px; margin-bottom:18px;">
                   <svg width="27" height="27" viewBox="0 0 24 24" fill="none">
                   <path d="M3 11L12 3L21 11" stroke="#B87928" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
                   <path d="M5.5 9.5V21H18.5V9.5" stroke="#B87928" stroke-width="2.4" stroke-linejoin="round"/>
                   <path d="M9.5 21V14H14.5V21" stroke="#B87928" stroke-width="2.4" stroke-linejoin="round"/>
                   </svg>
                   <div style="font-size:22px; font-weight:700; color:#172033;">
                   Menu Principal
                   </div>
                   </div>
                   """,
                   unsafe_allow_html=True
                   )

                   if not st.session_state.usuario_atual.get("conta_demo", False):
                      btn_conta_demo = st.sidebar.button(
                         "Explorar Demo",
                         key="btn_conta_demo",
                         use_container_width=True
                      )

                   else:
                      btn_voltar_conta = st.sidebar.button(
                         "Minha Conta",
                         key="btn_voltar_conta",
                         use_container_width=True
                      )


                   st.markdown(
                      """
                   <div class="titulo-secao-sidebar" style=" display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                   <svg width="32" height="28" viewBox="0 0 32 28" xmlns="http://www.w3.org/2000/svg" style="flex-shrink: 0;">
                   <path d="M3 8 H25 M20 3 L26 8 L20 13" fill="none" stroke="#B87928" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                   <path d="M29 20 H7 M12 15 L6 20 L12 25" fill="none" stroke="#B87928" stroke-width="3" stroke-linecap="round stroke-linejoin="round"/>
                   </svg>
                   <div style="font-size:20px; font-weight:700; color:#172033;">
                   Movimentações
                   </div>
                   </div>
                   """,
                   unsafe_allow_html=True
                   )


                   btn_cadastrar_gasto = st.sidebar.button(
                   f"Cadastrar {termo_gasto}",
                   key="btn_cadastrar_gasto",
                   use_container_width=True,
                   on_click=abrir_tela_cadastro,
                   args=("cadastrar_gasto", area_transicao)
                   )


                   btn_cadastrar_receita = st.sidebar.button(
                   "Cadastrar Receita",
                   key="btn_cadastrar_receita",
                   use_container_width=True,
                   on_click=abrir_tela_cadastro,
                   args=("cadastrar_receita", area_transicao)
                   )


                   btn_importar_pdf = st.sidebar.button(
                   "Importar Extrato PDF",
                   key="btn_importar_pdf",
                   use_container_width=True,
                      on_click=abrir_tela_cadastro,
                      args=("importar_pdf", area_transicao)
                   )


                   st.markdown(
                   """
                   <div class="titulo-secao-sidebar" style="display:flex; align-items:center; gap:8px; margin-top:12px; margin-bottom:8px;">
                   <div style=" display:flex; align-items:flex-end; gap:3px; height:25px;">
                   <span style="width:5px; height:10px; background:#B87928; border-radius:1px;"></span>
                   <span style="width:5px; height:17px; background:#B87928; border-radius:1px;"></span>
                   <span style="width:5px; height:24px; background:#B87928; border-radius:1px;"></span>
                   </div>
                   <div style="font-size:20px; font-weight:700; color:#172033;">
                   Acompanhamento
                   </div>
                   </div>
                   """,
                   unsafe_allow_html=True
                   )

                   btn_visualizar_saldo = st.sidebar.button(
                      "Resumo Financeiro",
                      key="btn_visualizar_saldo",
                      use_container_width=True,
                      on_click=abrir_tela_cadastro,
                      args=("visualizar_saldo", area_transicao)
                   )

                   btn_visualizar_historico = st.sidebar.button(
                      f"Visualizar Histórico  \n{termo_gasto}s e Receitas",
                      key="btn_visualizar_historico",
                      use_container_width=True,
                      on_click=abrir_tela_cadastro,
                      args=("visualizar_historico", area_transicao)
                   )

                   if tipo_pessoa == "Pessoa Física":
                      btn_visualizar_meta = st.sidebar.button(
                         "Acompanhar Meta Financeira",
                         key="btn_acompanhar_meta",
                         use_container_width=True,
                         on_click=abrir_tela_cadastro,
                         args=("visualizar_meta", area_transicao)
                      )

                   if tipo_pessoa in ("Pessoa Física", "Pessoa Jurídica"):
                      btn_visualizar_fluxo_caixa = st.sidebar.button(
                         "Visualizar Fluxo de Caixa",
                         key="btn_fluxo_caixa",
                         use_container_width=True,
                         on_click=abrir_tela_cadastro,
                         args=("visualizar_fluxo_caixa", area_transicao)
                      )

                   btn_visualizar_dashboard = st.sidebar.button(
                      "Visualizar Dashboard",
                      key="btn_visualizar_dashboard",
                      use_container_width=True,
                      on_click=abrir_tela_cadastro,
                      args=("visualizar_dashboard", area_transicao)
                   )




                   st.markdown(
                   """
                   <div class="titulo-secao-sidebar" style="display:flex; align-items:center; gap:8px; margin-top:12px; margin-bottom:8px;">

                   <div style="
                   width:24px;
                   height:24px;
                   border:2px solid #B87928;
                   border-radius:4px;
                   position:relative;
                   box-sizing:border-box;
                   ">
                   <div style="
                      position:absolute;
                      top:5px;
                      left:0;
                      width:100%;
                      height:2px;
                      background:#B87928;
                   "></div>

                   <div style="
                      position:absolute;
                      top:-4px;
                      left:5px;
                      width:2px;
                      height:6px;
                      background:#B87928;
                      border-radius:1px;
                   "></div>

                   <div style="
                      position:absolute;
                      top:-4px;
                      right:5px;
                      width:2px;
                      height:6px;
                      background:#B87928;
                      border-radius:1px;
                   "></div>
                   </div>

                   <div style="
                   font-size:20px;
                   font-weight:700;
                   color:#172033;
                   ">
                   Planejamento
                   </div>

                   </div>
                   """,
                   unsafe_allow_html=True
                )

                   btn_orcamento = st.sidebar.button(
                      "Gerenciar Orçamento",
                      key="btn_orcamento",
                      use_container_width=True,
                      on_click=abrir_tela_cadastro,
                      args=("gerenciar_orcamento", area_transicao)
                   )
                   btn_recorrencias = st.sidebar.button(
                      "Gerenciar Recorrências",
                      key="btn_recorrencias",
                      use_container_width=True,
                      on_click=abrir_tela_cadastro,
                      args=("gerenciar_recorrencias", area_transicao)
                   )
                   btn_planejamento_mensal = st.sidebar.button(
                      "Planejamento Mensal",
                      key="btn_planejamento_mensal",
                      use_container_width=True,
                      on_click=abrir_tela_cadastro,
                      args=("planejamento_mensal", area_transicao)
                   )
                   btn_planejamento_anual = st.sidebar.button(
                      "Planejamento Anual",
                      key="btn_planejamento_anual",
                      use_container_width=True,
                      on_click=abrir_tela_cadastro,
                      args=("planejamento_anual", area_transicao)
                   )
                   btn_simulador = st.sidebar.button(
                      "Simulador Financeiro",
                      key="btn_simulador_financeiro",
                      use_container_width=True,
                      on_click=abrir_tela_cadastro,
                      args=("simulador", area_transicao)
                   )




                   st.markdown(
                   """
                      <div class="titulo-secao-sidebar" style="display:flex; align-items:center; gap:8px; margin-top:12px; margin-bottom:8px;">
                      <div style="width:30px; height:30px; display:flex; align-items:center; justify-content:center; flex-shrink:0; ">
                      <svg width="29" height="29" viewBox="2 1 20 22" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                      <path d="M14 2.5H5.5A1.5 1.5 0 0 0 4 4v16a1.5 1.5 0 0 0 1.5 1.5h13A1.5 1.5 0 0 0 20 20V8.5L14 2.5Z" stroke="#B87928" stroke-width="1.7" stroke-linejoin="round"/>
                      <path d="M14 2.5v6h6M7.5 8h3" stroke="#B87928" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M8 17v-3M12 17v-6M16 17v-4" stroke="#B87928" stroke-width="2" stroke-linecap="round"/>
                      </svg>
                      </div>
                      <div style="font-size:20px;font-weight:700;color:#172033;white-space:nowrap;">
                      Análises e Relatórios
                      </div>
                      </div>
                      """,
                      unsafe_allow_html=True
                   )

                   btn_inteligencia_financeira = st.sidebar.button(
                      "Inteligência Financeira",
                      key="btn_inteligencia_financeira",
                      use_container_width=True,
                      on_click=abrir_tela_cadastro,
                      args=("inteligencia_financeira", area_transicao)
                   )

                   btn_relatorio_mensal = st.sidebar.button(
                      "Relatório Mensal",
                      key="btn_relatorio_mensal",
                      use_container_width=True,
                      on_click=abrir_tela_cadastro,
                      args=("relatorio_mensal", area_transicao)
                   )









             area_cadastrar_gasto = area_funcionalidade
             if st.session_state.tela_atual == "cadastrar_gasto":
              with area_cadastrar_gasto.container():
                exibir_lancamento(
                    conectar_banco,
                    listar_categorias,
                    tipo_pessoa,
                    termo_gasto,
                    artigo_gasto,
                    "gasto",
                    "Gasto",
                    "gasto",
                    "gastos",
                )

             area_cadastrar_receita = area_funcionalidade
             if st.session_state.tela_atual == "cadastrar_receita":
              with area_cadastrar_receita.container():
                exibir_lancamento(
                    conectar_banco,
                    listar_categorias,
                    tipo_pessoa,
                    "Receita",
                    "a",
                    "receita",
                    "Receita",
                    "receita",
                    "receitas",
                )

             area_visualizar_saldo = area_funcionalidade
             if st.session_state.tela_atual == "visualizar_saldo":
              with area_visualizar_saldo.container():
                exibir_saldo(conectar_banco, tipo_pessoa, termo_gasto)

             area_visualizar_historico = area_funcionalidade
             if st.session_state.tela_atual == "visualizar_historico":
              with area_visualizar_historico.container():
                exibir_historico(conectar_banco, tipo_pessoa, termo_gasto, formatar_moeda)



             area_visualizar_meta = area_funcionalidade
             if st.session_state.tela_atual == "visualizar_meta":
              with area_visualizar_meta.container():
                exibir_meta(conectar_banco, tipo_pessoa)




             area_visualizar_fluxo_caixa = area_funcionalidade
             if st.session_state.tela_atual == "visualizar_fluxo_caixa":
              with area_visualizar_fluxo_caixa.container():
                exibir_fluxo_caixa(conectar_banco, tipo_pessoa, termo_gasto)


             area_visualizar_dashboard = area_funcionalidade
             if st.session_state.tela_atual == "visualizar_dashboard":
                 with area_visualizar_dashboard.container():
                   exibir_dashboard(conectar_banco, termo_gasto)


             area_gerenciar_orcamento = area_funcionalidade
             if st.session_state.tela_atual == "gerenciar_orcamento":
              with area_gerenciar_orcamento.container():
                   exibir_orcamento(conectar_banco, tipo_pessoa, termo_gasto, sufixo_gasto)



             area_gerenciar_recorrencias = area_funcionalidade
             if st.session_state.tela_atual == "gerenciar_recorrencias":
              with area_gerenciar_recorrencias.container():
                exibir_recorrencias(conectar_banco, tipo_pessoa, termo_gasto)
             recorrencias_usuario = buscar_recorrencias_usuario(
                st.session_state.usuario_atual["id_usuario"]
             )

             recorrencias_ativas = [
                recorrencia
                for recorrencia in recorrencias_usuario
                if recorrencia["ativa"]
             ]


             area_planejamento_mensal = area_funcionalidade
             if st.session_state.tela_atual == "planejamento_mensal":
              with area_planejamento_mensal.container():
                exibir_planejamento_mensal(conectar_banco, tipo_pessoa, termo_gasto, recorrencias_ativas)
             area_planejamento_anual = area_funcionalidade
             if st.session_state.tela_atual == "planejamento_anual":
              with area_planejamento_anual.container():
                exibir_planejamento_do_ano(conectar_banco, termo_gasto, recorrencias_ativas)

             area_simulador = area_funcionalidade
             if st.session_state.tela_atual == "simulador":
              with area_simulador.container():
                exibir_simulador(conectar_banco, tipo_pessoa, termo_gasto)



             area_inteligencia_financeira = area_funcionalidade
             if st.session_state.tela_atual == "inteligencia_financeira":
              with area_inteligencia_financeira.container():
                exibir_inteligencia(conectar_banco, tipo_pessoa, termo_gasto)


             area_alertas = area_funcionalidade
             if st.session_state.tela_atual == "alertas":
              with area_alertas.container():
                exibir_alertas(gerar_alertas_orcamento, gerar_alertas_recorrencias, gerar_alertas_meta, gerar_alertas_provisao, enviar_email)



             area_relatorio_mensal = area_funcionalidade
             if st.session_state.tela_atual == "relatorio_mensal":
              with area_relatorio_mensal.container():
                exibir_relatorio_mensal(conectar_banco, termo_gasto, gerar_pdf_relatorio, enviar_email)


             area_configuracoes = area_funcionalidade
             if st.session_state.tela_atual == "configuracoes":
              with area_configuracoes.container():
                exibir_configuracoes(conectar_banco)


             area_seguranca = area_funcionalidade
             if st.session_state.tela_atual == "seguranca":
              with area_seguranca.container():
                exibir_seguranca(conectar_banco, enviar_email)



             area_importar_pdf = area_funcionalidade
             if st.session_state.tela_atual == "importar_pdf":
              with area_importar_pdf.container():
                exibir_importacao_pdf(conectar_banco, listar_categorias, formatar_moeda, PdfReader, tipo_pessoa, termo_gasto)




             if "btn_conta_demo" in locals() and btn_conta_demo:

                limpar_tela_aberta(area_funcionalidade, area_botao_voltar)
                try:
                   entrar_conta_demo()
                except ValueError:
                   st.warning("A demonstração não está disponível neste ambiente. A conta modelo precisa ser preparada pelo responsável.")
                else:
                   st.rerun()


             if "btn_voltar_conta" in locals() and btn_voltar_conta:

                limpar_tela_aberta(area_funcionalidade, area_botao_voltar)
                voltar_conta_original()
                st.rerun()

             if (st.session_state.tela_atual != "menu"
                 and st.session_state.get("politica_origem") != "seguranca"):
              with area_botao_voltar.container():


               st.button(
                   "← Voltar ao Menu Principal",
                   key="voltar_menu_principal",
                   on_click=abrir_tela_cadastro,
                   args=("menu", area_transicao),
               )
