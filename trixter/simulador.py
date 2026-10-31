"""Tela do simulador financeiro e da reserva."""
from datetime import date, timedelta

import streamlit as st

from .planejamento import (
    consultar_base_simulador,
    consultar_custo_fixo_mensal,
    exibir_reserva_simulador,
)
from .relatorios import formatar_moeda


def exibir_simulador(conectar_banco, tipo_pessoa, termo_gasto):

    st.header("Simulador Financeiro")

    st.write(
     "Simule diferentes cenários e veja como eles podem impactar suas finanças."
    )

    conexao = conectar_banco()
    cursor = conexao.cursor()

    media_receitas, media_gastos, tem_historico, inicio_base, fim_base = consultar_base_simulador(
        cursor, st.session_state.usuario_atual["id_usuario"], date.today()
    )
    if not tem_historico:
        st.warning("Sem movimentações nos três meses completos anteriores. As médias ficam zeradas; o mês atual não entra nesta base.")

    saldo_medio = media_receitas - media_gastos


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



    st.caption(f"Base: {inicio_base:%d/%m/%Y} a {fim_base - timedelta(days=1):%d/%m/%Y}. Médias sobre os mesmos três meses completos, incluindo meses sem movimentação.")

    col1, col2, col3 = st.columns(3)

    with col1:
       st.metric("Receita média mensal", formatar_moeda(media_receitas))

    with col2:
       st.metric(f"{termo_gasto} médio mensal", formatar_moeda(media_gastos))

    with col3:
       st.metric("Saldo médio mensal", formatar_moeda(saldo_medio))


    st.write("### Monte seu cenário")

    percentual_reducao_gastos = st.slider(
     f"Quanto você pretende reduzir dos seus {termo_gasto}s ?",
       min_value=0,
       max_value=100,
       value=0,
       step=5,
       format="%d%%"
    )

    percentual_aumento_receita = st.slider(
       "Quanto você espera aumentar sua receita?",
       min_value=0,
       max_value=100,
       value=0,
       step=5,
       format="%d%%"
    )

    meses_simulacao = st.number_input(
       "Por quantos meses deseja simular ?",
       min_value=1,
       max_value=120,
       value=12,
       step=1
    )

    receita_simulada = media_receitas * (1 + percentual_aumento_receita / 100)

    gasto_simulado = media_gastos * (1 - percentual_reducao_gastos / 100)

    saldo_simulado = receita_simulada - gasto_simulado

    melhora_mensal = saldo_simulado - saldo_medio

    st.caption("Os acumulados representam o resultado futuro do cenário, sem somar o saldo atual da conta.")
    saldo_acumulado_atual = saldo_medio *  meses_simulacao

    saldo_acumulado_simulado = saldo_simulado * meses_simulacao

    ganho_acumulado = saldo_acumulado_simulado - saldo_acumulado_atual



    st.write("### Resultado da simulação")

    col1, col2, col3 = st.columns(3)

    with col1:
     st.metric(
          "Receita mensal simulada",
          formatar_moeda(receita_simulada)
     )

    with col2:
     st.metric(
        f"{termo_gasto} mensal simulado",
        formatar_moeda(gasto_simulado)
     )

    with col3:
     st.metric(
        "Saldo mensal simulado",
        formatar_moeda(saldo_simulado),
        delta=formatar_moeda(melhora_mensal)
     )


    st.write(f"### Projeção para {meses_simulacao} meses")

    col1, col2, col3 = st.columns(3)

    with col1:
       st.metric(
          "Acumulado no cenário atual",
          formatar_moeda(saldo_acumulado_atual)
       )

    with col2:
       st.metric(
          "Acumulado no cenário simulado",
          formatar_moeda(saldo_acumulado_simulado)
       )

    with col3:
       st.metric(
          "Ganho adicional no período",
          formatar_moeda(ganho_acumulado)
       )


    if tipo_pessoa == "Pessoa Física":
        cursor.execute(
           """
           SELECT objetivo_financeiro, valor_objetivo, data_objetivo, valor_acumulado_meta
           FROM dbo.usuarios
           WHERE id_usuario = ?
           """,
           st.session_state.usuario_atual["id_usuario"]
        )

        meta_usuario = cursor.fetchone()

        if meta_usuario:
           objetivo_financeiro = meta_usuario[0]
           valor_objetivo = meta_usuario[1]
           data_objetivo = meta_usuario[2]
           valor_acumulado_meta = meta_usuario[3]



        if meta_usuario and meta_usuario[1]:
           valor_objetivo = float(meta_usuario[1])


           valor_acumulado_meta = float(meta_usuario[3] or 0)

           valor_restante_meta = max(
            valor_objetivo - valor_acumulado_meta,
           0
        )


           if saldo_medio > 0:
            meses_meta_atual = valor_restante_meta / saldo_medio
           else:
            meses_meta_atual = None


           if saldo_simulado > 0:
            meses_meta_simulado = valor_restante_meta / saldo_simulado
           else:
            meses_meta_simulado = None


           if meses_meta_atual is not None and meses_meta_simulado is not None:
            meses_antecipados = meses_meta_atual - meses_meta_simulado
           else:
            meses_antecipados = None





        if meta_usuario and meta_usuario[1]:


           if valor_restante_meta == 0:
              st.success(
                f"🎉 Meta '{objetivo_financeiro}' já atingida!"
              )
           else:

              col1, col2 = st.columns(2)

              col3, col4 = st.columns(2)

              with col1:
                 st.metric(
                       "Valor restante da meta",
                       formatar_moeda(valor_restante_meta)
                    )

              with col2:
                 st.metric(
                       "Tempo estimado atual",
                       f"{meses_meta_atual:.1f} meses" if meses_meta_atual is not None else "Não estimável"
                    )

              with col3:
                 st.metric(
                       "Tempo no cenário simulado",
                       f"{meses_meta_simulado:.1f} meses" if meses_meta_simulado is not None else "Não estimável"
                    )

              with col4:
                 st.metric(
                       "Tempo antecipado",
                       f"{meses_antecipados:.1f} meses" if meses_antecipados is not None else "Não estimável"
                    )


    custo_fixo_mensal = consultar_custo_fixo_mensal(
        cursor,
        st.session_state.usuario_atual["id_usuario"],
        inicio_base,
        fim_base,
    )
    exibir_reserva_simulador(
        saldo_atual, custo_fixo_mensal, receita_simulada, tipo_pessoa
    )

    cursor.close()
    conexao.close()
