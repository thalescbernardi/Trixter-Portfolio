"""Primeira entrada depois do cadastro."""
import streamlit as st

from . import estilo


def exibir_onboarding(area_onboarding, conectar_banco, nome_exibicao):

       estilo.publicar(estilo.ESTILO_ONBOARDING)


       tipo_pessoa = st.session_state.usuario_atual["tipo_pessoa"]


       st.markdown(
          f"""
          <div style="text-align: center; margin-bottom: 32px;">
             <div style="
                   font-size: 34px;
                   font-weight: 700;
                   color: #181818;
                   margin-bottom: 8px;
             ">
                   Bem-vindo(a), {nome_exibicao}! 👋
             </div>

             <div style="
                   font-size: 17px;
                   color: #5F6470;
                   line-height: 1.5;
             ">
                   Seu espaço para organizar, acompanhar e planejar
                   suas finanças começa aqui.
             </div>
          </div>
          """,
          unsafe_allow_html=True
       )

       st.markdown(
       """
       <div style="
          font-size: 24px;
          font-weight: 700;
          color: #181818;
          margin-bottom: 18px;
       ">
          O que você pode fazer por aqui
       </div>
       """,
       unsafe_allow_html=True
    )

       col1, col2, col3 = st.columns(3)

       with col1:
          st.markdown(
             f"""
             <div class="onboarding-card">
                   <div class="onboarding-card-title">
                      Controle
                   </div>
                   <div class="onboarding-card-text">
                      Registre receitas e {"despesas" if tipo_pessoa == "Pessoa Jurídica" else "gastos"} e acompanhe
                      seu saldo e histórico financeiro.
                   </div>
             </div>
             """,
             unsafe_allow_html=True
          )

       with col2:
          st.markdown(
             """
             <div class="onboarding-card">
                   <div class="onboarding-card-title">
                      Planejamento
                   </div>
                   <div class="onboarding-card-text">
                      Organize metas, orçamentos,
                      recorrências e planejamentos.
                   </div>
             </div>
             """,
             unsafe_allow_html=True
          )

       with col3:
          st.markdown(
             """
             <div class="onboarding-card">
                   <div class="onboarding-card-title">
                      Visão financeira
                   </div>
                   <div class="onboarding-card-text">
                      Analise seu dashboard, relatórios
                      e importe movimentações por PDF.
                   </div>
             </div>
             """,
             unsafe_allow_html=True
          )

       st.markdown(
          """
          <div style="
             text-align: center;
             color: #5F6470;
             font-size: 14px;
             margin-top: 26px;
             margin-bottom: 14px;
          ">
             Tudo pronto para começar. Você poderá explorar e ajustar
             suas finanças pelo menu principal.
          </div>
          """,
          unsafe_allow_html=True
       )

       col_esq, col_btn, col_dir = st.columns([1, 1.15, 1])

       with col_btn:

        btn_concluir_onboarding = st.button(
           "Começar a usar o Trixter",
           type="primary",
           use_container_width=True,
           key="btn_concluir_onboarding")

       if btn_concluir_onboarding:
          conexao = conectar_banco()
          cursor = conexao.cursor()

          try:
             cursor.execute(
                """
                UPDATE dbo.usuarios
                SET onboarding_concluido = 1
                WHERE id_usuario = ?
                """,
                st.session_state.usuario_atual["id_usuario"]
             )
             conexao.commit()
             st.session_state.usuario_atual["onboarding_concluido"] = 1
             st.session_state.tela_atual = "menu"
             area_onboarding.empty()
             st.rerun()
          finally:
             cursor.close()
             conexao.close()

       st.stop()
