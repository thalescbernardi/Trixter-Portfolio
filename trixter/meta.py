"""Tela de meta financeira."""
from contextlib import closing
from datetime import date

import streamlit as st

from .inicio import comparar_meta_saldo
from .relatorios import formatar_moeda


def exibir_meta(conectar_banco, tipo_pessoa):

    st.header("Meta Financeira")

    st.write(
     "Acompanhe seu progresso e veja quanto falta para alcançar seu objetivo financeiro."
     )



    if tipo_pessoa == "Pessoa Física":

     objetivo_financeiro = st.selectbox(
                "Qual é o seu principal objetivo financeiro?",
                [
                "Criar uma reserva de emergência",
                "Quitar dívidas",
                "Economizar para uma grande compra",
                "Viajar",
                "Investir",
                "Comprar um imóvel",
                "Comprar um veículo",
                "Organizar melhor as finanças",
                "Outro"
                ],
                key = "objetivo_financeiro_pf"
    )

    elif tipo_pessoa == "Pessoa Jurídica":

     objetivo_financeiro = st.selectbox(
                "Qual é o principal objetivo financeiro da empresa?",
                [
                   "Criar uma reserva de caixa",
                   "Quitar dívidas da empresa",
                   "Aumentar o capital de giro",
                   "Investir no crescimento da empresa",
                   "Comprar equipamentos ou maquinário",
                   "Expandir o negócio",
                   "Reduzir custos",
                   "Organizar melhor as finanças da empresa",
                   "Outro"
             ],
             key = "objetivo_financeiro_pj"
            )

    valor_objetivo = st.number_input(
        "Valor da meta:",
        min_value=0.0,
        step=100.0,
        key="valor_objetivo"
     )

    data_objetivo = st.date_input(
        "Prazo para atingir a meta:",
        min_value=date.today(),
        format="DD/MM/YYYY",
        key="data_objetivo"

     )

    valor_acumulado_meta = st.number_input(
       "Quanto você já tem reservado para essa meta ?",
       min_value= 0.0,
       step=50.0,
       format="%.2f",
       key= "valor_acumulado_meta"
    )

    btn_salvar_meta = st.button("Salvar Meta",
                                type="primary")

    if st.session_state.get("meta_salva_sucesso", False):

     st.success("Meta financeira salva com sucesso!")

     st.session_state.meta_salva_sucesso = False

    if btn_salvar_meta:
       if valor_objetivo <= 0:
          st.error("O valor da meta deve ser maior que zero.")
       elif data_objetivo < date.today():
          st.error("O prazo da meta deve ser uma data futura.")

       else:
          conexao= conectar_banco()
          cursor = conexao.cursor()

          cursor.execute(
             """
             UPDATE dbo.usuarios
             SET objetivo_financeiro = ?, valor_objetivo = ?, data_objetivo = ?, valor_acumulado_meta = ?
             WHERE id_usuario = ?
             """,
             objetivo_financeiro,
             valor_objetivo,
             data_objetivo,
             valor_acumulado_meta,
             st.session_state.usuario_atual["id_usuario"]

          )

          conexao.commit()
          cursor.close()
          conexao.close()

          st.session_state.usuario_atual["objetivo_financeiro"] = objetivo_financeiro
          st.session_state.usuario_atual["valor_objetivo"] = valor_objetivo
          st.session_state.usuario_atual["data_objetivo"] = data_objetivo
          st.session_state.usuario_atual["valor_acumulado_meta"] = valor_acumulado_meta

          st.session_state.meta_salva_sucesso = True
          st.rerun()



    valor_meta = st.session_state.usuario_atual.get("valor_objetivo")
    if valor_meta is not None and valor_meta > 0:

     valor_meta = float(valor_meta)
     valor_acumulado = st.session_state.usuario_atual.get("valor_acumulado_meta", 0)

     valor_acumulado = float(valor_acumulado or 0)

     valor_faltante = max(valor_meta - valor_acumulado, 0)

     progresso_meta = (
        min(valor_acumulado / valor_meta, 1.0) if valor_meta > 0 else 0
        )


     st.subheader("Acompanhamento da Meta Financeira")

     st.write(
            f"Objetivo: {st.session_state.usuario_atual['objetivo_financeiro']}"
                )

     st.write(
            f"Valor da meta: {formatar_moeda(valor_meta)}"
                )

     st.write(
            f"Valor acumulado: {formatar_moeda(valor_acumulado)}"
                )

     with closing(conectar_banco()) as conexao_meta:
        with closing(conexao_meta.cursor()) as cursor_meta:
            cursor_meta.execute(
                "SELECT COALESCE(SUM(valor), 0) FROM dbo.receitas WHERE id_usuario = ?",
                st.session_state.usuario_atual["id_usuario"],
            )
            receitas_meta = cursor_meta.fetchone()[0]
            cursor_meta.execute(
                "SELECT COALESCE(SUM(valor), 0) FROM dbo.gastos WHERE id_usuario = ?",
                st.session_state.usuario_atual["id_usuario"],
            )
            gastos_meta = cursor_meta.fetchone()[0]
     comparacao_meta = comparar_meta_saldo(
        float(receitas_meta) - float(gastos_meta),
        valor_meta,
     )
     st.write(f"Saldo atual: {formatar_moeda(comparacao_meta['saldo']).strip()}")
     st.caption(
        "O valor acumulado é o que você informou nesta meta. "
        "O saldo atual soma as receitas e os gastos lançados."
     )
     st.write(comparacao_meta["texto"])

     st.write(
            f"Valor faltante: {formatar_moeda(valor_faltante)}"
                )

     st.write(
            f"Prazo da meta: {st.session_state.usuario_atual['data_objetivo']}"
                )

     data_meta = st.session_state.usuario_atual.get("data_objetivo")
     dias_restantes = max((data_meta - date.today()).days,0)
     st.write(f"Dias restantes para atingir a meta: {dias_restantes} dias")

     meses_restantes = max(dias_restantes / 30,1)
     valor_mensal_necessario = valor_faltante / meses_restantes
     st.write(f"Para atingir sua meta no prazo, você precisa acumular aproximadamente "
             f"{formatar_moeda(valor_mensal_necessario)} por mês.")

     st.progress(progresso_meta)

     st.write(
     f"Progresso da meta: {progresso_meta * 100:.1f}%"
    )
     st.write("### Adicionar valor à meta")

     valor_aporte = st.number_input(
        "Quanto você quer adicionar à meta?",
        min_value=0.0,
        step=50.0,
        format="%.2f",
        key="valor_aporte_meta"
     )
     btn_adicionar_aporte = st.button("Adicionar à Meta",
                                      type="primary")

     if st.session_state.get("aporte_meta_sucesso", False):

      st.success("Valor adicionado à meta com sucesso!")

      st.session_state.aporte_meta_sucesso = False

     if btn_adicionar_aporte:
        if valor_aporte <= 0:
           st.error("O valor do aporte deve ser maior que zero.")

        elif valor_aporte > valor_faltante:
            st.error(
              f"O aporte não pode ser maior que o valor faltante "
              f"({formatar_moeda(valor_faltante)})."
           )
        else:
           novo_valor_acumulado = valor_acumulado + valor_aporte

           conexao = conectar_banco()
           cursor = conexao.cursor()

           cursor.execute(
             """
                UPDATE dbo.usuarios
                SET valor_acumulado_meta = ?
                WHERE id_usuario = ?
             """,
           novo_valor_acumulado,
           st.session_state.usuario_atual["id_usuario"]
          )

           conexao.commit()
           cursor.close()
           conexao.close()

           st.session_state.usuario_atual["valor_acumulado_meta"] = novo_valor_acumulado

           st.session_state.aporte_meta_sucesso = True
           st.rerun()


    else:
       st.info("Você ainda não possui uma meta financeira cadastrada.")
