"""Tela de preferências de e-mail."""
import streamlit as st

from .credencial import exigir_operacao


def _carregar_preferencias(conectar_banco, id_usuario):
    conexao = conectar_banco()
    cursor = conexao.cursor()
    cursor.execute(
        """
        SELECT
             receber_relatorio_mensal,
             dia_relatorio_mensal,
             receber_alertas,
             receber_resumo_semanal
        FROM dbo.usuarios
        WHERE id_usuario = ?
        """,
        id_usuario,
    )
    preferencias = cursor.fetchone()
    cursor.close()
    conexao.close()
    return preferencias


@st.fragment
def exibir_configuracoes(conectar_banco):
    if not exigir_operacao(conectar_banco):
        return

    st.header("Configurações")

    st.write(
        "Configure suas preferências de relatórios e alertas."
    )

    id_usuario = st.session_state.usuario_atual["id_usuario"]
    chaves_preferencias = (
        "config_receber_relatorio", "config_receber_alertas", "config_receber_resumo",
    )
    if (st.session_state.get("_config_usuario") != id_usuario
            or any(chave not in st.session_state for chave in chaves_preferencias)):
        preferencias = _carregar_preferencias(conectar_banco, id_usuario)
        st.session_state._config_usuario = id_usuario
        st.session_state.config_receber_relatorio = bool(preferencias[0])
        st.session_state.config_dia_relatorio = int(preferencias[1]) if preferencias[1] is not None else 1
        st.session_state.config_receber_alertas = bool(preferencias[2])
        st.session_state.config_receber_resumo = bool(preferencias[3])

    novo_receber_relatorio = st.checkbox(
        "Receber relatório mensal por e-mail",
        key="config_receber_relatorio",
    )

    if novo_receber_relatorio:
        novo_dia_relatorio = int(st.number_input(
            "Dia do mês para receber o relatório",
            min_value=1,
            max_value=28,
            step=1,
            key="config_dia_relatorio",
        ))
    else:
        novo_dia_relatorio = None

    novo_receber_alertas = st.checkbox(
        "Receber alertas por e-mail",
        key="config_receber_alertas",
    )

    novo_receber_resumo = st.checkbox(
        "Receber resumo semanal por e-mail",
        key="config_receber_resumo",
        help="Na segunda, ou na próxima execução daquela semana: saldo, o que vence em 7 dias, categoria estourada e cliente em atraso.",
    )

    if st.button("Salvar preferências"):
        conexao = conectar_banco()
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE dbo.usuarios
            SET
                receber_relatorio_mensal = ?,
                dia_relatorio_mensal = ?,
                receber_alertas = ?,
                receber_resumo_semanal = ?
            WHERE id_usuario = ?
            """,
            int(novo_receber_relatorio),
            novo_dia_relatorio,
            int(novo_receber_alertas),
            int(novo_receber_resumo),
            id_usuario,
        )
        conexao.commit()
        cursor.close()
        conexao.close()
        st.success("Preferências salvas com sucesso!")
