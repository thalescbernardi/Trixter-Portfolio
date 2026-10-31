"""Tela do relatório mensal."""
from contextlib import closing
from datetime import date

import streamlit as st

from .relatorios import calcular_relatorio_mensal, formatar_moeda


@st.fragment
def exibir_relatorio_mensal(conectar_banco, termo_gasto, gerar_pdf_relatorio, enviar_email):

    st.header("Relatório Mensal")


    st.write(
       "Gere um relatório completo de suas movimentações financeiras "
       "para o período selecionado."
       )

    meses = {
       "Janeiro":1,
       "Fevereiro":2,
       "Março":3,
       "Abril":4,
       "Maio":5,
       "Junho":6,
       "Julho":7,
       "Agosto":8,
       "Setembro":9,
       "Outubro":10,
       "Novembro":11,
       "Dezembro":12
       }

    mes_selecionado = st.selectbox(
       "Selecione o mês:",
       list(meses.keys())
    )

    numero_mes = meses[mes_selecionado]

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT DISTINCT YEAR(data) AS ano
       FROM dbo.receitas
       WHERE id_usuario = ?

       UNION

       SELECT DISTINCT YEAR(data) AS ano
       FROM dbo.gastos
       WHERE id_usuario = ?

       ORDER BY ano DESC
       """,
       st.session_state.usuario_atual["id_usuario"],
       st.session_state.usuario_atual["id_usuario"]
    )

    anos_disponiveis = [
       linha[0] for linha in cursor.fetchall() if linha[0] is not None
    ]
    cursor.close()
    conexao.close()

    if not anos_disponiveis:
       anos_disponiveis = [date.today().year]
       st.info(
          "Ainda não há movimentações com data registrada nesta conta. "
          "O ano atual está disponível para consulta."
       )

    ano_selecionado = st.selectbox(
       "Selecione o ano:",
       anos_disponiveis
    )

    if "relatorio_gerado" not in st.session_state:
      st.session_state.relatorio_gerado = False

    if "mes_relatorio" not in st.session_state:
      st.session_state.mes_relatorio = None

    if "ano_relatorio" not in st.session_state:
      st.session_state.ano_relatorio = None



    btn_gerar_relatorio = st.button(
      "Gerar Relatório",
      type="primary"
    )

    if btn_gerar_relatorio:
      st.session_state.relatorio_gerado = True
      st.session_state.mes_relatorio = mes_selecionado
      st.session_state.ano_relatorio = ano_selecionado





    if st.session_state.relatorio_gerado:
       mes_relatorio = st.session_state.mes_relatorio
       ano_relatorio = st.session_state.ano_relatorio
       numero_mes = meses[mes_relatorio]

       with closing(conectar_banco()) as conexao_relatorio:
           with closing(conexao_relatorio.cursor()) as cursor_relatorio:
               dados_relatorio = calcular_relatorio_mensal(
                   cursor_relatorio, st.session_state.usuario_atual["id_usuario"],
                   ano_relatorio, numero_mes
               )
       total_receitas_relatorio = dados_relatorio["total_receitas_relatorio"]
       total_gastos_relatorio = dados_relatorio["total_gastos_relatorio"]
       saldo_relatorio = dados_relatorio["saldo_relatorio"]
       taxa_poupanca_relatorio = dados_relatorio["taxa_poupanca_relatorio"]
       gastos_por_categoria = dados_relatorio["gastos_por_categoria"]
       percentual_por_categoria = dados_relatorio["percentual_por_categoria"]
       variacao_receitas = dados_relatorio["variacao_receitas"]
       variacao_gastos = dados_relatorio["variacao_gastos"]
       principal_categoria = dados_relatorio["principal_categoria"]
       valor_principal_categoria = dados_relatorio["valor_principal_categoria"]
       percentual_principal_categoria = dados_relatorio["percentual_principal_categoria"]

       st.write(f"### Resumo de {mes_relatorio}/{ano_relatorio}")

       col1, col2, col3, col4 = st.columns(4)

       col1.metric("Receitas", formatar_moeda(total_receitas_relatorio))
       col2.metric(f"{termo_gasto}s", formatar_moeda(total_gastos_relatorio))
       col3.metric("Saldo", formatar_moeda(saldo_relatorio))
       col4.metric("Taxa de poupança", f"{taxa_poupanca_relatorio:.1f}%")

       st.write("### Gastos por categoria")

       if total_gastos_relatorio > 0:

          for categoria,valor in gastos_por_categoria.items():
             percentual = (valor / total_gastos_relatorio) * 100
             percentual_por_categoria[categoria] = percentual

             st.write(
                f"**{categoria}** - "
                f"{formatar_moeda(valor)} "
                f"({percentual:.1f}%)"
             )

       else:
          st.write("Nenhum gasto registrado no período.")


       st.write("### Comparação com o mês anterior")

       col1, col2 = st.columns(2)

       if variacao_receitas is not None:
        col1.metric(
          "Receitas",
          formatar_moeda(total_receitas_relatorio),
          f"{variacao_receitas:+.1f}%"
       )
       else:
        col1.metric(
          "Receitas",
          formatar_moeda(total_receitas_relatorio)
          )
        col1.caption("Sem comparação")


       if variacao_gastos is not None:
          col2.metric(
          "Gastos",
          formatar_moeda(total_gastos_relatorio),
          f"{variacao_gastos:+.1f}%"
       )
       else:
          col2.metric(
          "Gastos",
          formatar_moeda(total_gastos_relatorio)
          )
          col2.caption("Sem comparação")


       if principal_categoria is not None:
        st.write("### Destaque do mês")

        st.info(
          f"A categoria com maior {termo_gasto.lower()} no período foi "
          f"{principal_categoria}, com "
          f"{formatar_moeda(valor_principal_categoria)}, "
          f"representando {percentual_principal_categoria:.1f}% "
          f"do total."
       )


       pdf_buffer = gerar_pdf_relatorio(
           mes_relatorio,
           ano_relatorio,
           total_receitas_relatorio,
           total_gastos_relatorio,
           saldo_relatorio,
           taxa_poupanca_relatorio,
           termo_gasto,
           gastos_por_categoria,
           percentual_por_categoria,
           variacao_receitas,
           variacao_gastos,
           principal_categoria,
           valor_principal_categoria,
           percentual_principal_categoria
       )

       st.download_button(
          label= "Baixar Relatório em PDF",
          data=pdf_buffer,
          file_name=f"Relatório_{mes_relatorio}_{ano_relatorio}.pdf",
          mime="application/pdf"
       )

       conta_demo = bool(st.session_state.usuario_atual.get("conta_demo"))
       if conta_demo:
          st.caption("O envio por e-mail não está disponível na demonstração.")

       btn_enviar_relatorio_email = st.button(
        "Enviar relatório por e-mail",
        disabled=conta_demo,
       )

       if btn_enviar_relatorio_email and not conta_demo:

        assunto_relatorio = (
        f"Relatório mensal - "
        f"{mes_relatorio}/{ano_relatorio}"
       )

        corpo_relatorio = f"""
          Olá!

          Segue em anexo o seu relatório mensal referente a
          {mes_relatorio}/{ano_relatorio}.

          Atenciosamente,
          Trixter
          """

        anexo_relatorio = {
           "conteudo": pdf_buffer.getvalue(),
           "nome": (
           f"relatorio_"
           f"{mes_relatorio}_"
           f"{ano_relatorio}.pdf"
           )
           }

        try:
         enviar_email(
          destinatario=st.session_state.usuario_atual["email"],
          assunto=assunto_relatorio,
          corpo=corpo_relatorio,
          anexo=anexo_relatorio
       )

         st.session_state.relatorio_email_sucesso = (
          "Relatório enviado para o seu e-mail!"
       )

        except Exception:
         st.error(
          "Não foi possível enviar o relatório por e-mail."
       )

       if st.session_state.get("relatorio_email_sucesso"):
          st.success(st.session_state.relatorio_email_sucesso)
