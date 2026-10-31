"""Tela de orçamento e o aviso de limite."""
import uuid
from contextlib import closing
from datetime import date

import streamlit as st

from .categorias import listar_categorias
from .classificacao import consultar_custos_mes, detalhe_custos, exibir_custos_mes, frase_natureza
from .relatorios import formatar_moeda


def exibir_status_orcamento(categoria, percentual_utilizado, gasto_realizado=None, valor_limite=None, natureza=""):
    complemento = f" {natureza}" if natureza and percentual_utilizado >= 0.8 else ""

    if percentual_utilizado >= 1:
        valor_excedido = gasto_realizado - valor_limite
        st.error(
            f"{categoria}: orçamento ultrapassado em "
            f"{formatar_moeda(valor_excedido)}"
            f"({percentual_utilizado:.0%} utilizado).{complemento}"
        )

    elif percentual_utilizado >= 0.8:
        st.warning(
            f"{categoria}: atenção, "
            f"{percentual_utilizado:.0%} do orçamento já foi utilizado.{complemento}"
        )

    else:
        st.success(
            f"{categoria}: "
            f"{percentual_utilizado:.0%} do orçamento utilizado."
        )


def _limpar_edicao_orcamento():
    st.session_state.pop("orcamento_em_edicao", None)
    st.session_state.pop("novo_valor_limite", None)


def exibir_orcamento(conectar_banco, tipo_pessoa, termo_gasto, sufixo_gasto):
    st.header("Gerenciar Orçamento")

    st.write(
     "Defina e acompanhe limites de gastos para manter seu orçamento sob controle."
    )

    with closing(conectar_banco()) as conexao_custos:
        with closing(conexao_custos.cursor()) as cursor_custos:
            resumo_custos = consultar_custos_mes(
                cursor_custos,
                st.session_state.usuario_atual["id_usuario"],
                date.today(),
            )
    exibir_custos_mes(resumo_custos, termo_gasto)

    conexao= conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT *
       FROM dbo.orcamentos
       WHERE id_usuario = ?
       """,
       st.session_state.usuario_atual["id_usuario"]
    )

    resultados = cursor.fetchall()
    colunas = [coluna[0] for coluna in cursor.description]

    orcamentos_usuario = [
       dict(zip(colunas,linha))
       for linha in resultados
    ]

    cursor.close()
    conexao.close()

    usuario_id = st.session_state.usuario_atual["id_usuario"]
    identidades = {(usuario_id, item["id_orcamento"]) for item in orcamentos_usuario}
    if st.session_state.get("orcamento_em_edicao") not in identidades:
       _limpar_edicao_orcamento()

    if not orcamentos_usuario:
       st.info(
          "Você ainda não possui orçamentos cadastrados. "
          "Defina abaixo o seu primeiro orçamento."
       )


    with closing(conectar_banco()) as conexao_categorias:
        with closing(conexao_categorias.cursor()) as cursor_categorias:
            categorias_orcamento = listar_categorias(
                cursor_categorias,
                st.session_state.usuario_atual["id_usuario"],
                tipo_pessoa,
                "Gasto",
            )



    categoria_orcamento = st.selectbox(
       "Selecione a categoria:",
       categorias_orcamento,
       key="categoria_orcamento"
    )

    valor_limite_orcamento = st.number_input(
       f"Defina o limite mensal para {categoria_orcamento}:",
       min_value=0.0,
       step=10.0,
       key="valor_limite_orcamento"
    )

    meses = {
       1: "Janeiro",
       2: "Fevereiro",
       3:"Março",
       4: "Abril",
       5:"Maio",
       6:"Junho",
       7:"Julho",
       8:"Agosto",
       9:"Setembro",
       10:"Outubro",
       11:"Novembro",
       12:"Dezembro"
    }

    mes_orcamento = st.selectbox(
       "Selecione o mês do orçamento:",
       range(1,13),
       format_func=lambda x: meses[x],
       key="mes_orcamento"
    )

    ano_orcamento = st.number_input(
       "Selecione o ano do orçamento;",
       min_value=2026,
       step=1,
       key="ano_orcamento"
    )

    btn_salvar_orcamento = st.button("Salvar Orçamento",
                                     type="primary")


    if st.session_state.get("orcamento_salvo_sucesso", False):
       st.success("Orçamento salvo com sucesso!")
       st.session_state.orcamento_salvo_sucesso = False

    if btn_salvar_orcamento:
       if valor_limite_orcamento <= 0:
          st.error("O valor do limite de orçamento deve ser maior que zero.")
       else:
          orcamento_ja_existe = any(
             orcamento["categoria"] == categoria_orcamento
             and orcamento["mes"] == mes_orcamento
             and orcamento["ano"] == ano_orcamento
             for orcamento in orcamentos_usuario
          )
          if orcamento_ja_existe:
             st.warning(
                "Já existe um orçamento cadastrado para essa categoria neste mês e ano."
             )
          else:
             orcamento = {
                "id_orcamento": str(uuid.uuid4()),
                "id_usuario": st.session_state.usuario_atual["id_usuario"],
                "categoria": categoria_orcamento,
                "mes": mes_orcamento,
                "ano": ano_orcamento,
                "valor_limite": valor_limite_orcamento
             }

             conexao = conectar_banco()
             cursor = conexao.cursor()

             cursor.execute(
                """
                INSERT INTO dbo.orcamentos(
                id_orcamento,
                id_usuario,
                categoria,
                mes,
                ano,
                valor_limite
             )
             VALUES (?,?,?,?,?,?)
             """,
             orcamento["id_orcamento"],
             orcamento["id_usuario"],
             orcamento["categoria"],
             orcamento["mes"],
             orcamento["ano"],
             orcamento["valor_limite"]

             )

             conexao.commit()
             cursor.close()
             conexao.close()


             st.session_state.orcamento_salvo_sucesso = True
             st.rerun()


    if orcamentos_usuario:
       st.subheader("Acompanhamento de Orçamentos")
       conexao = conectar_banco()
       cursor = conexao.cursor()

       for orcamento in orcamentos_usuario:

          cursor.execute(
             """
             SELECT COALESCE(SUM(valor),0),
                    COALESCE(SUM(CASE WHEN classificacao = N'Fixo' THEN valor ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN classificacao = N'Variável' THEN valor ELSE 0 END), 0)
             FROM dbo.gastos
             WHERE id_usuario = ?
             AND categoria = ?
             AND MONTH(data) = ?
             AND YEAR(data) = ?
             """,
             st.session_state.usuario_atual["id_usuario"],
             orcamento["categoria"],
             orcamento["mes"],
             orcamento["ano"]
          )

          gasto_realizado, gasto_fixo, gasto_variavel = cursor.fetchone()

          valor_limite = orcamento["valor_limite"]

          valor_restante = valor_limite - gasto_realizado

          percentual_utilizado = (
             gasto_realizado / valor_limite
             if valor_limite > 0
             else 0
          )

          st.write(f"### {orcamento["categoria"]}")

          st.write(f"Período: {orcamento["mes"]:02d}/{orcamento["ano"]}")

          col1,col2,col3 = st.columns(3)

          with col1:
             st.metric(""
                 "Limite",
                 formatar_moeda(valor_limite)
           )

          with col2:
             st.metric(
                f"{termo_gasto} realizad{sufixo_gasto}",
                formatar_moeda(gasto_realizado)
             )

          with col3:
             st.metric(
                "Valor Restante",
                formatar_moeda(valor_restante)
             )

          progresso = min(float(percentual_utilizado),1.0)

          st.progress(progresso)

          st.write(f"{percentual_utilizado:.0%} do orçamento utilizado.")

          natureza_orcamento = frase_natureza(gasto_realizado, gasto_fixo, gasto_variavel)
          detalhe_orcamento = detalhe_custos(gasto_realizado, gasto_fixo, gasto_variavel)
          if detalhe_orcamento:
             st.caption(detalhe_orcamento.replace("$", "\\$"))

          exibir_status_orcamento(
             orcamento["categoria"],
             percentual_utilizado,
             gasto_realizado,
             valor_limite,
             natureza_orcamento,
          )


       opcoes_orcamentos = {
          f"{orcamento["categoria"]} - {orcamento["mes"]:02d}/{orcamento["ano"]}": orcamento["id_orcamento"]
          for orcamento in orcamentos_usuario
       }

       if st.session_state.get("orcamento_selecionado") not in opcoes_orcamentos:
          st.session_state.pop("orcamento_selecionado", None)
          _limpar_edicao_orcamento()

       orcamento_selecionado = st.selectbox(
          "Selecione um orçamento para editar ou excluir:",
          list(opcoes_orcamentos.keys()),
          key= "orcamento_selecionado"
       )

       id_orcamento_selecionado = opcoes_orcamentos[orcamento_selecionado]
       identidade_selecionada = (usuario_id, id_orcamento_selecionado)
       if st.session_state.get("orcamento_em_edicao") != identidade_selecionada:
          _limpar_edicao_orcamento()

       btn_excluir_orcamento = st.button("Excluir Orçamento Selecionado")

       if st.session_state.get("orcamento_excluido_sucesso", False):
          st.success("Orçamento excluído com sucesso!")
          st.session_state.orcamento_excluido_sucesso = False

       if btn_excluir_orcamento:

        conexao = conectar_banco()
        cursor = conexao.cursor()

        cursor.execute(
          """
          DELETE FROM dbo.orcamentos
          WHERE id_orcamento = ?
          AND id_usuario = ?
          """,
          id_orcamento_selecionado,
          st.session_state.usuario_atual["id_usuario"]
       )


        conexao.commit()
        cursor.close()
        conexao.close()
        _limpar_edicao_orcamento()
        st.session_state.orcamento_excluido_sucesso = True
        st.rerun()



       btn_alterar_orcamento = st.button(
          "Alterar Orçamento Selecionado",
          key="btn_alterar_orcamento")

       if st.session_state.get("orcamento_alterado_sucesso", False):
          st.success("Orçamento alterado com sucesso!")
          st.session_state.orcamento_alterado_sucesso = False

       if btn_alterar_orcamento:
          _limpar_edicao_orcamento()
          st.session_state.orcamento_em_edicao = identidade_selecionada

       if st.session_state.get("orcamento_em_edicao") == identidade_selecionada:
          orcamento_para_alterar = next(
             (item for item in orcamentos_usuario
              if item["id_orcamento"] == id_orcamento_selecionado),
             None,
          )
          if orcamento_para_alterar is None:
             _limpar_edicao_orcamento()
             st.warning("Orçamento não encontrado.")
          else:
             novo_valor_limite = st.number_input(
                "Novo valor limite:",
                min_value=0.0,
                value=float(orcamento_para_alterar["valor_limite"]),
                step=10.0,
                key="novo_valor_limite",
             )
             btn_confirmar_alteracao = st.button("Confirmar Alteração")
             if btn_confirmar_alteracao:
                if novo_valor_limite <= 0:
                   st.error("O novo valor limite deve ser maior do que zero.")
                else:
                   conexao = conectar_banco()
                   cursor = conexao.cursor()
                   cursor.execute(
                      """
                      UPDATE dbo.orcamentos
                      SET valor_limite = ?
                      WHERE id_orcamento = ?
                      AND id_usuario = ?
                      """,
                      novo_valor_limite,
                      id_orcamento_selecionado,
                      usuario_id,
                   )
                   conexao.commit()
                   cursor.close()
                   conexao.close()
                   _limpar_edicao_orcamento()
                   st.session_state.orcamento_alterado_sucesso = True
                   st.rerun()
