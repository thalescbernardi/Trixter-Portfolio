"""Leitura do mês: resultado e percentual da referência cadastrada."""
from contextlib import closing
from datetime import date

import streamlit as st

from .inicio import comparar_faturamento, consultar_resumo
from .relatorios import formatar_moeda


def exibir_saldo(conectar_banco, tipo_pessoa, termo_gasto):
    st.header("Resumo Financeiro")

    if tipo_pessoa == "Pessoa Jurídica":
        intro = (
            "Acompanhe suas receitas registradas em relação ao faturamento mensal informado "
            "e veja o resultado financeiro do mês."
        )
        titulo_percentual = "Receitas em relação ao faturamento informado"
        referencia = "faturamento informado"
    else:
        intro = (
            "Acompanhe suas receitas registradas em relação à renda mensal informada "
            "e veja o resultado financeiro do mês."
        )
        titulo_percentual = "Receitas em relação à renda informada"
        referencia = "renda informada"
    st.write(intro)

    with closing(conectar_banco()) as conexao:
        _saldo_acumulado, receitas_mes, gastos_mes = consultar_resumo(
            conexao,
            st.session_state.usuario_atual["id_usuario"],
            date.today(),
        )
    resultado_mes = receitas_mes - gastos_mes

    if tipo_pessoa == "Pessoa Jurídica":
        comparacao = comparar_faturamento(
            st.session_state.usuario_atual["faturamento_mensal"] or 0,
            receitas_mes,
        )
    else:
        comparacao = comparar_faturamento(
            st.session_state.usuario_atual.get("renda_mensal") or 0,
            receitas_mes,
            nome="renda",
        )

    if comparacao["percentual"] is None:
        texto_percentual = "Sem referência"
    else:
        texto_percentual = f"{comparacao['percentual'] * 100:.1f}%".replace(".", ",")

    if resultado_mes > 0:
        cor_resultado = "#2E7D32"
    elif resultado_mes < 0:
        cor_resultado = "#C62828"
    else:
        cor_resultado = "#5F6470"

    detalhe_percentual = (
        f"{formatar_moeda(receitas_mes)} em receitas registradas de "
        f"{formatar_moeda(comparacao['cadastrado'])} de {referencia}."
    )
    detalhe_resultado = (
        f"{formatar_moeda(receitas_mes)} em receitas − "
        f"{formatar_moeda(gastos_mes)} em gastos"
    )
    coluna_percentual, coluna_resultado = st.columns(2)
    coluna_percentual.markdown(
        _card_resumo(titulo_percentual, texto_percentual, detalhe_percentual, "#172033"),
        unsafe_allow_html=True,
    )
    coluna_resultado.markdown(
        _card_resumo("Resultado do mês", formatar_moeda(resultado_mes), detalhe_resultado, cor_resultado),
        unsafe_allow_html=True,
    )
    if comparacao["percentual"] is None:
        st.caption(comparacao["texto"])


def _card_resumo(titulo, valor, detalhe, cor_valor):
    """Card no mesmo visual das métricas da Home.

    titulo é o rótulo de cima. valor é o número grande. detalhe é a frase
    menor embaixo. cor_valor pinta só o número grande.
    """
    return f"""
    <div style="padding-bottom:28px;">
    <div style="
       background:#FFFFFF;
       border:1px solid #E3E7ED;
       border-top:3px solid #B87928;
       border-radius:14px;
       padding:20px;
       box-shadow:0 3px 12px rgba(23,32,51,0.04);
       min-height:100%;
    ">
       <div style="color:#526077; font-size:14px;">{titulo}</div>
       <div style="font-size:clamp(1.3rem,2.3vw,2rem); font-weight:600; color:{cor_valor}; margin:8px 0 6px; line-height:1.2;">
          {valor}
       </div>
       <div style="color:#526077; font-size:0.95rem; line-height:1.4;">{detalhe}</div>
    </div>
    </div>
    """
