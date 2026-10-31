"""Tela de alertas. As regras continuam em alertas.py."""
import streamlit as st


def exibir_alertas(gerar_alertas_orcamento, gerar_alertas_recorrencias, gerar_alertas_meta, gerar_alertas_provisao, enviar_email):
    st.header("Alertas Financeiros")

    st.write(
       "Acompanhe situações importantes que merecem sua atenção."
    )

    alertas = (
       gerar_alertas_orcamento(
          st.session_state.usuario_atual["id_usuario"]
       )
       + gerar_alertas_recorrencias(
          st.session_state.usuario_atual["id_usuario"]
       )
       + gerar_alertas_meta(
          st.session_state.usuario_atual["id_usuario"]
       )
       + gerar_alertas_provisao(
          st.session_state.usuario_atual["id_usuario"]
       )
    )

    if alertas:
       for alerta in alertas:

          if alerta["nivel"] == "critico":
             st.error(alerta["mensagem"])
          elif alerta["nivel"] == "atencao":
             st.warning(alerta["mensagem"])

    else:
       st.success("Nenhum alerta financeiro no momento.")

    if st.session_state.get("alertas_email_sucesso"):
       st.success(st.session_state.alertas_email_sucesso)
       st.session_state.alertas_email_sucesso = None

    if alertas:

     if st.button("Enviar alertas por e-mail"):

       mensagens_alertas = []

       for alerta in alertas:
             mensagens_alertas.append(
                f"- {alerta['mensagem']}"
             )

       assunto_alertas = "Seus alertas financeiros - Trixter"

       corpo_alertas = (
             "Olá!\n\n"
             "Estes são os seus alertas financeiros atuais:\n\n"
             + "\n".join(mensagens_alertas)
             + "\n\nAtenciosamente,\n"
             "Trixter"
       )

       try:
             enviar_email(
                destinatario=st.session_state.usuario_atual["email"],
                assunto=assunto_alertas,
                corpo=corpo_alertas
             )

             st.session_state.alertas_email_sucesso = (
                "Alertas enviados para o seu e-mail!"
             )

             st.rerun()

       except Exception as e:
             st.error("Não foi possível enviar os alertas por e-mail.")
