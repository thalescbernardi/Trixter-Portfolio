"""Tela de fluxo de caixa. O cálculo do caixa previsto continua em fluxo_caixa.py."""
from contextlib import closing
from datetime import date

import pandas as pd
import streamlit as st

from .fluxo_caixa import (
    consultar_caixa_previsto,
    criar_grafico,
    exibir_caixa_previsto,
    resumir_por_dia,
)
from .relatorios import formatar_moeda


def exibir_fluxo_caixa(conectar_banco, tipo_pessoa, termo_gasto):



    st.header("Fluxo de Caixa")

    st.write(
       "Acompanhe suas entradas, saídas e a evolução do saldo acumulado ao longo do tempo."
    )

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT COALESCE(SUM(valor), 0)
       FROM dbo.receitas
       WHERE id_usuario = ?
       """,
       st.session_state.usuario_atual["id_usuario"]
    )
    total_receitas = float(cursor.fetchone()[0])

    cursor.execute(
       """
       SELECT COALESCE(SUM(valor), 0)
       FROM dbo.gastos
       WHERE id_usuario = ?
       """,
       st.session_state.usuario_atual["id_usuario"]
    )
    total_gastos = float(cursor.fetchone()[0])
    saldo_atual = total_receitas - total_gastos

    cursor.close()
    conexao.close()

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT data,
             'Entrada' AS tipo,
              valor
       FROM dbo.receitas
       WHERE id_usuario = ?

       UNION ALL

       SELECT data,
              'Saída' AS tipo,
              valor
       FROM dbo.gastos
       WHERE id_usuario = ?
       """,
       st.session_state.usuario_atual["id_usuario"],
       st.session_state.usuario_atual["id_usuario"]
    )

    resultados = cursor.fetchall()
    colunas = [coluna[0] for coluna in cursor.description]

    df_fluxo_caixa = pd.DataFrame([tuple(linha) for linha in resultados], columns=colunas)

    cursor.close()
    conexao.close()



    if not df_fluxo_caixa.empty:

        fluxo_diario = resumir_por_dia(df_fluxo_caixa)
        st.plotly_chart(criar_grafico(fluxo_diario), use_container_width=True)
        st.caption("Entradas e saídas por dia com movimentação. O saldo acumula todo o histórico registrado.")
        if len(fluxo_diario) == 1:
            st.info("Há movimentações em apenas um dia. A evolução aparecerá quando houver outras datas.")
        df_exibicao = fluxo_diario.copy()
        df_exibicao["data"] = df_exibicao["data"].dt.strftime("%d/%m/%Y")
        for coluna in ("Entrada", "Saída", "Saldo acumulado"):
            df_exibicao[coluna] = df_exibicao[coluna].apply(formatar_moeda)
        df_exibicao = df_exibicao.rename(columns={"data": "Data"})
        st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

    else:
        st.info(
           "Nenhuma movimentação financeira encontrada. "
           f"Cadastre uma receita ou {termo_gasto.lower()} para visualizar seu fluxo de caixa."
        )

    with closing(conectar_banco()) as conexao_prevista:
        with closing(conexao_prevista.cursor()) as cursor_previsto:
            previsoes_caixa = consultar_caixa_previsto(
                cursor_previsto,
                st.session_state.usuario_atual["id_usuario"],
                saldo_atual,
                date.today(),
            )
    exibir_caixa_previsto(previsoes_caixa)
