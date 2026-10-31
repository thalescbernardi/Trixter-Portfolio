"""Tela de histórico das movimentações."""
import pandas as pd
import plotly.express as px
import streamlit as st

from .clientes import normalizar_cliente

_CHAVE_MOVIMENTACAO = "historico_movimentacao_selecionada"
_CHAVES_CLIENTE = (
    "historico_cliente",
    "historico_cliente_id",
    "historico_cliente_sucesso",
    "historico_cliente_aviso",
)


def identidade_movimentacao(tipo, id_transacao):
    """Tipo e id juntos. O mesmo UUID pode existir em receita e em gasto."""
    return f"{tipo}|{id_transacao}"


def opcoes_movimentacao(transacoes):
    """Uma opção por tipo e id_transacao."""
    opcoes = {}
    for _, transacao in transacoes.iterrows():
        ident = identidade_movimentacao(transacao["tipo"], transacao["id_transacao"])
        if ident in opcoes:
            continue
        opcoes[ident] = transacao
    return opcoes


def _rotulo_movimentacao(transacao, formatar_moeda):
    return (
        f"{transacao['tipo']} - {transacao['data']} - "
        f"{transacao['categoria']} - {formatar_moeda(transacao['valor'])}"
    )


def rotulos_movimentacao(transacoes, formatar_moeda):
    """Rótulo legível. A identidade completa só entra quando o texto se repetiria."""
    opcoes = opcoes_movimentacao(transacoes)
    rotulos = {
        ident: _rotulo_movimentacao(linha, formatar_moeda)
        for ident, linha in opcoes.items()
    }
    while True:
        repetidos = {
            texto
            for texto in rotulos.values()
            if sum(item == texto for item in rotulos.values()) > 1
        }
        if not repetidos:
            return rotulos
        for ident, texto in list(rotulos.items()):
            if texto in repetidos:
                rotulos[ident] = f"{texto} · {ident}"


def atualizar_cliente_receita(cursor, id_transacao, id_usuario, cliente):
    """Grava só dbo.receitas.cliente da conta autenticada."""
    if not str(id_transacao or "").strip() or not str(id_usuario or "").strip():
        return False
    cursor.execute(
        """
        UPDATE dbo.receitas
        SET cliente = ?
        WHERE id_transacao = ?
          AND id_usuario = ?
        """,
        normalizar_cliente(cliente),
        id_transacao,
        id_usuario,
    )
    return cursor.rowcount == 1


_AVISO_MOVIMENTACAO_AUSENTE = (
    "Não foi possível encontrar ou atualizar essa movimentação."
)
_AVISO_EXCLUSAO_FALHA = "Não foi possível excluir a movimentação agora."
_AVISO_ALTERACAO_FALHA = "Não foi possível alterar a movimentação agora."


def _reverter_transacao(conexao):
    try:
        conexao.rollback()
    except Exception:
        return False
    return True


def _fechar_recurso(recurso):
    if recurso is None:
        return
    try:
        recurso.close()
    except Exception:
        return


def concluir_gravacao_financeira(conectar, sql, parametros):
    """'confirmado', 'ausente' ou 'falha'. Confirma só uma linha com commit."""
    try:
        conexao = conectar()
    except Exception:
        return "falha"
    cursor = None
    try:
        cursor = conexao.cursor()
        cursor.execute(sql, *parametros)
        afetadas = cursor.rowcount
        if afetadas == 1:
            conexao.commit()
            return "confirmado"
        if not _reverter_transacao(conexao):
            return "falha"
        return "ausente" if afetadas == 0 else "falha"
    except Exception:
        _reverter_transacao(conexao)
        return "falha"
    finally:
        _fechar_recurso(cursor)
        _fechar_recurso(conexao)


def _publicar_resultado_financeiro(
    chave_sucesso, chave_aviso, situacao, aviso_ausente, aviso_falha
):
    if situacao == "confirmado":
        st.session_state[chave_sucesso] = True
        st.session_state.pop(chave_aviso, None)
        return
    st.session_state.pop(chave_sucesso, None)
    st.session_state[chave_aviso] = (
        aviso_ausente if situacao == "ausente" else aviso_falha
    )


def _exibir_aviso_financeiro(texto):
    if texto == _AVISO_MOVIMENTACAO_AUSENTE:
        st.warning(texto)
    else:
        st.error(texto)


def concluir_atualizacao_cliente_receita(conectar, id_transacao, id_usuario, cliente):
    """'atualizado', 'ausente' ou 'falha'. Sucesso só com exatamente uma linha."""
    try:
        conexao = conectar()
    except Exception:
        return "falha"
    cursor = None
    try:
        cursor = conexao.cursor()
        if not atualizar_cliente_receita(cursor, id_transacao, id_usuario, cliente):
            if not _reverter_transacao(conexao):
                return "falha"
            return "ausente"
        conexao.commit()
        return "atualizado"
    except Exception:
        _reverter_transacao(conexao)
        return "falha"
    finally:
        _fechar_recurso(cursor)
        _fechar_recurso(conexao)


def _descartar_cliente_historico():
    for chave in _CHAVES_CLIENTE:
        st.session_state.pop(chave, None)


def _texto_cliente(transacao):
    if "cliente" not in transacao.index:
        return ""
    valor = transacao["cliente"]
    if valor is None or pd.isna(valor):
        return ""
    return str(valor)


def _sincronizar_cliente_historico(identidade_conta):
    """Outra conta ou outra movimentação descarta o texto da anterior."""
    if st.session_state.get("historico_cliente_id") == identidade_conta:
        return
    st.session_state.pop("historico_cliente", None)
    st.session_state.pop("historico_cliente_sucesso", None)
    st.session_state.pop("historico_cliente_aviso", None)
    st.session_state["historico_cliente_id"] = identidade_conta


def _exibir_correcao_cliente_historico(
    conectar_banco, transacao, id_transacao, identidade
):
    """Corrige o cliente da receita. Não grava valor, data, categoria nem descrição."""
    _sincronizar_cliente_historico(
        f"{st.session_state.usuario_atual['id_usuario']}|{identidade}"
    )
    if st.session_state.get("historico_cliente_sucesso"):
        st.success(st.session_state.historico_cliente_sucesso)
        st.session_state.historico_cliente_sucesso = None
    if st.session_state.get("historico_cliente_aviso"):
        st.error(st.session_state.historico_cliente_aviso)
        st.session_state.historico_cliente_aviso = None

    novo_cliente = st.text_input(
        "Cliente:",
        value=_texto_cliente(transacao),
        max_chars=80,
        key="historico_cliente",
        placeholder="Ex.: Aurora Serviços",
        help=(
        "Opcional. Não cria cadastro de tomador. "
        "Informe apenas o nome necessário à organização financeira. "
        "Evite CPF, diagnósticos, informações de saúde "
        "ou outros dados pessoais sensíveis."
    ),
    )
    if not st.button("Salvar cliente", key="btn_salvar_cliente_historico"):
        return
    if str(transacao["id_transacao"]) != id_transacao or transacao["tipo"] != "Receita":
        _descartar_cliente_historico()
        st.rerun()
    situacao = concluir_atualizacao_cliente_receita(
        conectar_banco,
        id_transacao,
        st.session_state.usuario_atual["id_usuario"],
        novo_cliente,
    )
    if situacao == "atualizado":
        st.session_state.historico_cliente_sucesso = "Cliente atualizado."
    elif situacao == "ausente":
        st.session_state.historico_cliente_aviso = "Não foi possível salvar o cliente."
    else:
        st.session_state.historico_cliente_aviso = (
            "Não foi possível salvar o cliente agora."
        )
    st.rerun()


def selecionar_movimentacao(transacoes, formatar_moeda):
    """Devolve a identidade escolhida e a linha correspondente."""
    opcoes = opcoes_movimentacao(transacoes)
    rotulos = rotulos_movimentacao(transacoes, formatar_moeda)
    identificadores = list(opcoes)
    guardado = st.session_state.get(_CHAVE_MOVIMENTACAO)
    selecao_invalida = guardado is not None and guardado not in opcoes
    if selecao_invalida:
        st.session_state.pop(_CHAVE_MOVIMENTACAO, None)
        st.session_state.pop("editando_movimentacao", None)
        _descartar_cliente_historico()
    escolhido = st.selectbox(
        "Selecione a movimentação que deseja alterar ou excluir:",
        identificadores,
        format_func=lambda ident: rotulos[ident],
        key=_CHAVE_MOVIMENTACAO,
    )
    if selecao_invalida or escolhido not in opcoes:
        if escolhido not in opcoes:
            st.session_state.pop(_CHAVE_MOVIMENTACAO, None)
        st.session_state.pop("editando_movimentacao", None)
        _descartar_cliente_historico()
        st.rerun()
    return escolhido, opcoes[escolhido]


def exibir_historico(conectar_banco, tipo_pessoa, termo_gasto, formatar_moeda):

    st.header("Histórico de Movimentações")

    st.write(
      f"Consulte e filtre as receitas e {termo_gasto}s registrados na sua conta."
    )
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT
             id_transacao,
             id_usuario,
             data,
             descricao,
             valor,
             categoria,
             'Gasto' AS tipo,
             classificacao,
             CAST(NULL AS nvarchar(80)) AS cliente
       FROM dbo.gastos
       WHERE id_usuario = ?

       UNION ALL

       SELECT
             id_transacao,
             id_usuario,
             data,
             descricao,
             valor,
             categoria,
             'Receita' AS tipo,
             classificacao,
             cliente
       FROM dbo.receitas
       WHERE id_usuario = ?

       ORDER BY data DESC
       """,
       st.session_state.usuario_atual["id_usuario"],
       st.session_state.usuario_atual["id_usuario"]
    )

    resultados = [tuple(linha) for linha in cursor.fetchall()]

    colunas = [coluna[0] for coluna in cursor.description]
    historico_transacoes = pd.DataFrame(resultados, columns=colunas)

    cursor.close()
    conexao.close()


    if not historico_transacoes.empty:
     st.write("Histórico de Transações:")

     df_historico = historico_transacoes.drop(columns=["cliente"], errors="ignore").copy()
     df_historico["data"] = pd.to_datetime(df_historico["data"])
     df_historico = df_historico.sort_values(by="data", ascending=False)
     df_historico = df_historico.rename(columns={"tipo": "Tipo", "data": "Data", "categoria": "Categoria" , "valor": "Valor", "descrição":"Descrição"})
     df_historico = df_historico.rename(columns={"classificacao": "Classificação"})
     df_historico["Classificação"] = df_historico["Classificação"].fillna("Não classificado")
     if tipo_pessoa == "Pessoa Jurídica":
        opcoes_tipo = ["Todos", "Receita", "Despesa"]
     else:
        opcoes_tipo = ["Todos", "Receita", "Gasto"]
     tipo_filtro = st.selectbox("Filtrar por tipo de transação:",
                                opcoes_tipo)
     df_filtrado = df_historico.copy()
     tipo_filtro_interno = tipo_filtro
     if tipo_filtro == "Despesa":
        tipo_filtro_interno = "Gasto"
     if tipo_filtro != "Todos":
      df_filtrado = df_filtrado[df_filtrado["Tipo"] == tipo_filtro_interno]
     categorias_disponiveis = ["Todas"] + sorted(df_filtrado["Categoria"].unique().tolist())
     categoria_filtro = st.selectbox("Filtrar por categoria:", categorias_disponiveis)
     if categoria_filtro != "Todas":
        df_filtrado = df_filtrado[df_filtrado["Categoria"] == categoria_filtro]
     if not df_filtrado.empty:

        data_inicial = st.date_input(
            "Data inicial:",
            value=df_filtrado["Data"].min().date(),
            format="DD/MM/YYYY",
            key="filtro_data_inicial"
        )

        data_final = st.date_input(
            "Data final:",
            value=df_filtrado["Data"].max().date(),
            format="DD/MM/YYYY",
            key="filtro_data_final"
        )

        df_filtrado = df_filtrado[
            (df_filtrado["Data"].dt.date >= data_inicial)
            &
            (df_filtrado["Data"].dt.date <= data_final)
        ]

     classificacao_filtro = st.selectbox(
        "Filtrar por classificação:",
        ["Todos", "Fixo", "Variável", "Não classificado"],
        key="filtro_classificacao_historico"
     )
     if classificacao_filtro != "Todos":
        df_filtrado = df_filtrado[
           df_filtrado["Classificação"] == classificacao_filtro
        ]
     if df_filtrado.empty:
        st.info("Nenhuma movimentação encontrada para os filtros selecionados.")

     total_receitas_filtrado = df_filtrado.loc[df_filtrado["Tipo"] == "Receita", "Valor"].sum()
     total_gastos_filtrado = df_filtrado.loc[df_filtrado["Tipo"] == "Gasto", "Valor"].sum()
     saldo_atual_filtrado = total_receitas_filtrado - total_gastos_filtrado

     col_receitas, col_gastos, col_saldo = st.columns(3)

     with col_receitas:
        st.metric(
           "Receitas",
           formatar_moeda(total_receitas_filtrado),
        )

     with col_gastos:
        st.metric(
           f"{termo_gasto}s",
           formatar_moeda(total_gastos_filtrado),
        )

     with col_saldo:
        st.metric(
           "Saldo do Período",
           formatar_moeda(saldo_atual_filtrado)
        )


     if tipo_filtro != "Todos":

        df_grafico_tempo = (
            df_filtrado
            .groupby("Data", as_index=False)["Valor"]
            .sum()
        )

        fig_tempo = px.line(
            df_grafico_tempo,
            x="Data",
            y="Valor",
            title="Evolução das Movimentações",
            markers=True,
            text="Valor",
            hover_data={"Data": "|%d/%m/%Y"},
        )

        fig_tempo.update_traces(texttemplate="R$  %{text:.2f}", textposition="top center")
        fig_tempo.update_xaxes(tickformat="%d/%m/%Y", hoverformat="%d/%m/%Y")

        st.plotly_chart(
            fig_tempo,
            use_container_width=True
        )
     else:
        df_grafico_tempo = (
           df_filtrado
           .groupby(["Data","Tipo"], as_index=False)["Valor"]
           .sum()
        )

        fig_tempo = px.line(
           df_grafico_tempo,
           x="Data",
           y="Valor",
           color="Tipo",
           markers=True,
           title="Evolução de Receitas e Gastos",
           hover_data={"Data": "|%d/%m/%Y"},
        )
        fig_tempo.update_xaxes(tickformat="%d/%m/%Y", hoverformat="%d/%m/%Y")
        st.plotly_chart(
           fig_tempo, use_container_width=True
        )

     df_exibicao = df_filtrado.copy()

     df_exibicao["Data"] = df_exibicao["Data"].dt.strftime("%d/%m/%Y")

     df_exibicao["Valor"] = df_exibicao["Valor"].apply(formatar_moeda)

     st.dataframe(df_exibicao, use_container_width=True)

     identidade_selecionada, transacao_escolhida = selecionar_movimentacao(
        historico_transacoes, formatar_moeda
     )
     tipo_transacao_selecionada, id_transacao_selecionada = identidade_selecionada.split("|", 1)
     usuario_historico = st.session_state.usuario_atual["id_usuario"]
     if st.session_state.get("editando_movimentacao") != (
        usuario_historico, id_transacao_selecionada, tipo_transacao_selecionada
     ):
        st.session_state.pop("editando_movimentacao", None)


     btn_excluir_transacao = st.button("Excluir Movimentação Selecionada")

     if st.session_state.get("movimentacao_excluida_sucesso", False):
        st.success("Movimentação excluída com sucesso!")
        st.session_state.movimentacao_excluida_sucesso=False

     if st.session_state.get("movimentacao_excluida_aviso"):
        _exibir_aviso_financeiro(st.session_state.movimentacao_excluida_aviso)
        st.session_state.movimentacao_excluida_aviso = None

     if btn_excluir_transacao:
        if tipo_transacao_selecionada == "Receita":
           instrucao_exclusao = """
           DELETE FROM dbo.receitas
           WHERE id_transacao = ?
           AND id_usuario = ?
           """
        else:
           instrucao_exclusao = """
          DELETE FROM dbo.gastos
          WHERE id_transacao = ?
          AND id_usuario = ?
          """
        situacao_exclusao = concluir_gravacao_financeira(
           conectar_banco,
           instrucao_exclusao,
           (
              id_transacao_selecionada,
              st.session_state.usuario_atual["id_usuario"],
           ),
        )
        _publicar_resultado_financeiro(
           "movimentacao_excluida_sucesso",
           "movimentacao_excluida_aviso",
           situacao_exclusao,
           _AVISO_MOVIMENTACAO_AUSENTE,
           _AVISO_EXCLUSAO_FALHA,
        )
        st.rerun()

     btn_alterar_transacao = st.button(
        "Alterar Movimentação Selecionada",
        key="btn_alterar_transacao")
     if btn_alterar_transacao:
        st.session_state.editando_movimentacao = (
           usuario_historico, id_transacao_selecionada, tipo_transacao_selecionada
        )
        for campo in ("editar_data", "editar_categoria", "editar_valor", "editar_descricao", "editar_classificacao"):
           st.session_state.pop(campo, None)

     if st.session_state.get("movimentacao_alterada_sucesso"):
        st.success("Movimentação alterada com sucesso!")
        st.session_state.movimentacao_alterada_sucesso = False

     if st.session_state.get("movimentacao_alterada_aviso"):
        _exibir_aviso_financeiro(st.session_state.movimentacao_alterada_aviso)
        st.session_state.movimentacao_alterada_aviso = None

     if st.session_state.get("editando_movimentacao") == (
        usuario_historico, id_transacao_selecionada, tipo_transacao_selecionada
     ):
        transacao_para_alterar = transacao_escolhida

        nova_data = st.date_input(
           "Data:",
           value=pd.Timestamp(transacao_para_alterar["data"]).date(),
           format="DD/MM/YYYY",
           key="editar_data"
        )

        nova_categoria = st.text_input(
           "Categoria:",
           value=transacao_para_alterar["categoria"],
           key="editar_categoria"
        )

        novo_valor = st.number_input(
           "Valor:",
           min_value=0.0,
           value=float(transacao_para_alterar["valor"]),
           step=10.0,
           key="editar_valor"
        )

        nova_descricao = st.text_input(
           "Descrição:",
           value=transacao_para_alterar["descricao"],
           key="editar_descricao",
           help=(
            "Informe apenas o necessário para identificar a movimentação. "
            "Evite CPF, diagnósticos, informações de saúde ou outros "
            "dados pessoais sensíveis."
        ),
        )

        opcoes_classificacao = ["Não classificado", "Fixo", "Variável"]
        classificacao_atual = transacao_para_alterar["classificacao"]
        if pd.isna(classificacao_atual):
           classificacao_atual = "Não classificado"
        nova_classificacao = st.selectbox(
           "Classificação:",
           opcoes_classificacao,
           index=opcoes_classificacao.index(classificacao_atual),
           key="editar_classificacao"
        )
        if nova_classificacao == "Não classificado":
           nova_classificacao = None

        if (
           tipo_transacao_selecionada == "Receita"
           and transacao_para_alterar["tipo"] == "Receita"
        ):
           _exibir_correcao_cliente_historico(
              conectar_banco,
              transacao_para_alterar,
              id_transacao_selecionada,
              identidade_selecionada,
           )

        btn_salvar_alteracoes = st.button("Salvar Alterações")

        if btn_salvar_alteracoes:
           if transacao_para_alterar["tipo"] == "Gasto":
              instrucao_alteracao = """
                 UPDATE dbo.gastos
                 SET data = ?, categoria = ?, valor = ?, descricao = ?, classificacao = ?
                 WHERE id_transacao = ?
                 AND id_usuario = ?
                 """
           else:
              instrucao_alteracao = """
                 UPDATE dbo.receitas
                 SET data = ?, categoria = ?, valor = ?, descricao = ?, classificacao = ?
                 WHERE id_transacao = ?
                 AND id_usuario = ?
                 """
           situacao_alteracao = concluir_gravacao_financeira(
              conectar_banco,
              instrucao_alteracao,
              (
                 nova_data,
                 nova_categoria,
                 novo_valor,
                 nova_descricao,
                 nova_classificacao,
                 id_transacao_selecionada,
                 st.session_state.usuario_atual["id_usuario"],
              ),
           )
           _publicar_resultado_financeiro(
              "movimentacao_alterada_sucesso",
              "movimentacao_alterada_aviso",
              situacao_alteracao,
              _AVISO_MOVIMENTACAO_AUSENTE,
              _AVISO_ALTERACAO_FALHA,
           )
           if situacao_alteracao == "confirmado":
              st.session_state.pop("editando_movimentacao", None)
           st.rerun()

    else:
        st.info("Nenhuma movimentação cadastrada até o momento.")
