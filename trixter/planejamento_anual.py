"""Tela do planejamento do ano. O painel rolável continua em planejamento.py."""
from contextlib import closing
from datetime import date

import streamlit as st

from .planejamento import (
    consultar_comparacao_categorias,
    consultar_planejamento_anual,
    exibir_planejamento_anual,
)
from .recorrencias import calcular_recorrencias_periodo


def exibir_planejamento_do_ano(conectar_banco, termo_gasto, recorrencias_ativas):


    st.header("Planejamento Anual")

    st.write(
     "Acompanhe seu planejamento financeiro e seus resultados ao longo do ano."
    )

    ano_planejamento_anual = st.number_input(
       "Selecione o ano:",
       min_value=2026,
       step=1,
       value=date.today().year,
       key="ano_planejamento_anual"
    )

    with closing(conectar_banco()) as conexao_anual:
        with closing(conexao_anual.cursor()) as cursor_anual:
            dados_anual = consultar_planejamento_anual(
                cursor_anual,
                st.session_state.usuario_atual["id_usuario"],
                int(ano_planejamento_anual),
                recorrencias_ativas,
                calcular_recorrencias_periodo,
            )
            detalhes_anual = consultar_comparacao_categorias(
                cursor_anual, st.session_state.usuario_atual["id_usuario"], int(ano_planejamento_anual)
            )
    exibir_planejamento_anual(dados_anual, ano_planejamento_anual, termo_gasto, detalhes_anual)
