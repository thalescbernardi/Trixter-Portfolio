"""Tela de dashboard."""
import pandas as pd
import plotly.express as px
import streamlit as st

from .relatorios import formatar_moeda


def exibir_dashboard(conectar_banco, termo_gasto):
    st.header("Dashboard Financeiro")

    st.write(
     "Acompanhe os principais indicadores e a evolução das suas finanças."
    )


    data_inicio_dashboard = st.date_input(
       "Data Inicial",
       format="DD/MM/YYYY",
       key="data_inicio_dashboard"
    )

    data_fim_dashboard = st.date_input(
       "Data Final",
       format="DD/MM/YYYY",
       key="data_fim_dashboard"
    )

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT id_transacao,
              data,
              'Receita' AS tipo,
              valor,
              categoria,
              descricao
              FROM dbo.receitas
              WHERE id_usuario = ?
       UNION ALL
       SELECT id_transacao,
              data,
              'Gasto' AS tipo,
              valor,
              categoria,
              descricao
              FROM dbo.gastos
              WHERE id_usuario = ?
              """,
              st.session_state.usuario_atual["id_usuario"],
              st.session_state.usuario_atual["id_usuario"]
    )

    resultados = [tuple(linha) for linha in cursor.fetchall()]
    colunas = [coluna[0] for coluna in cursor.description]

    df_dashboard = pd.DataFrame(resultados,columns=colunas)

    cursor.close()
    conexao.close()

    df_dashboard["data"] = pd.to_datetime(df_dashboard["data"])

    data_inicio_dashboard = pd.to_datetime(data_inicio_dashboard)
    data_fim_dashboard = pd.to_datetime(data_fim_dashboard)

    df_dashboard = df_dashboard[
       (df_dashboard["data"] >= data_inicio_dashboard)
       &
       (df_dashboard["data"] <= data_fim_dashboard)
    ]


    total_receitas = df_dashboard.loc[df_dashboard["tipo"] == "Receita", "valor"].sum()

    total_gastos = df_dashboard.loc[df_dashboard["tipo"] == "Gasto", "valor"].sum()


    saldo_periodo = total_receitas - total_gastos

    percentual_receita_consumida = (
       total_gastos / total_receitas
       if total_receitas > 0
       else 0
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
       st.metric("Receitas do Período", formatar_moeda(total_receitas))
    with col2:
       st.metric(f"{termo_gasto}s do Período", formatar_moeda(total_gastos))
    with col3:
       st.metric("Saldo do Período", formatar_moeda(saldo_periodo))
    with col4:
       total_transacoes = len(df_dashboard)
       st.metric("Transações", total_transacoes)

       st.metric(
                "Receita Comprometida",
                f"{percentual_receita_consumida:.1%}".replace(".", ",")
             )

    tipo_visualizacao_dashboard = st.selectbox(
       "Visualizar gráfico por:",
       ["Resumo", "Categoria"],
       key="tipo_visualizacao_dashboard"
    )

    if tipo_visualizacao_dashboard == "Resumo":
       df_receitas_gastos = pd.DataFrame({
          "Tipo": ["Receitas",f" {termo_gasto}s"],
          "Valor": [total_receitas, total_gastos]
       })

       fig = px.bar(
             df_receitas_gastos,
             x="Tipo",
             y="Valor",
             color="Tipo",
             color_discrete_map={
                "Receitas": "#2E8B57",
                f" {termo_gasto}s": "#C94C4C"
             },
             title=f"Receitas x {termo_gasto}s",
             text_auto=".2f"
         )

    else:

       movimentacoes_dashboard = df_dashboard[
          ["categoria", "valor", "tipo"]
       ].copy()



       df_categoria_dashboard = (
          movimentacoes_dashboard
          .groupby(["categoria", "tipo"], as_index=False)["valor"]
          .sum()
       )

       fig = px.bar(
          df_categoria_dashboard,
          x="categoria",
          y="valor",
          color="tipo",
          color_discrete_map={
             "Receita": "#2E8B57",
             "Gasto": "#C94C4C",
             "Despesa": "#C94C4C"
          },
          barmode="group",
          title= "Movimentações por Categoria",
          text_auto=".2f"
       )



    st.plotly_chart(fig, use_container_width=True)
