"""Tela de inteligência financeira."""
from contextlib import closing
from datetime import date

import streamlit as st

from .classificacao import consultar_custos_mes, exibir_custos_mes
from .clientes import consultar_concentracao_mes, exibir_concentracao
from .margem import consultar_margem_mes, exibir_margem
from .provisao import consultar_provisao_mes, exibir_provisao, formulario_provisao
from .relatorios import formatar_moeda


@st.fragment
def exibir_reserva_tributos(conectar_banco):
    """Percentual e botões atualizam sozinhos para a página não voltar ao topo."""
    if st.session_state.get("provisao_salva_sucesso"):
        st.success("Percentual a reservar salvo.")
        st.session_state.provisao_salva_sucesso = False

    aliquota = st.session_state.usuario_atual.get("aliquota_imposto")
    dia = st.session_state.usuario_atual.get("dia_vencimento_imposto")
    with closing(conectar_banco()) as conexao:
        with closing(conexao.cursor()) as cursor:
            resumo = consultar_provisao_mes(
                cursor,
                st.session_state.usuario_atual["id_usuario"],
                date.today(),
                aliquota,
            )
    exibir_provisao(resumo)
    escolha = formulario_provisao(aliquota, dia)
    if not escolha:
        return

    with closing(conectar_banco()) as conexao:
        with closing(conexao.cursor()) as cursor:
            cursor.execute(
                """
                UPDATE dbo.usuarios
                SET aliquota_imposto = ?, dia_vencimento_imposto = ?
                WHERE id_usuario = ?
                """,
                escolha["aliquota"],
                escolha["dia"],
                st.session_state.usuario_atual["id_usuario"],
            )
        conexao.commit()
    st.session_state.usuario_atual["aliquota_imposto"] = escolha["aliquota"]
    st.session_state.usuario_atual["dia_vencimento_imposto"] = escolha["dia"]
    st.session_state.provisao_salva_sucesso = True
    st.rerun(scope="fragment")


def exibir_inteligencia(conectar_banco, tipo_pessoa, termo_gasto):

            st.header("Inteligência Financeira")

            st.write(
             "Confira análises e padrões identificados a partir das suas movimentações."
            )

            conexao = conectar_banco()
            cursor = conexao.cursor()

            cursor.execute(
               """
               SELECT COALESCE(SUM(valor), 0), COUNT(*)
               FROM dbo.receitas
               WHERE id_usuario = ?
               AND YEAR(data) = YEAR(GETDATE())
               AND MONTH(data) = MONTH(GETDATE())
               """,
               st.session_state.usuario_atual["id_usuario"]
            )

            total, quantidade_receita_mes_atual = cursor.fetchone()
            receita_mes_atual = float(total)


            cursor.execute(
               """
               SELECT COALESCE(SUM(valor), 0), COUNT(*)
               FROM dbo.gastos
               WHERE id_usuario = ?
               AND YEAR(data) = YEAR(GETDATE())
               AND MONTH(data) = MONTH(GETDATE())
               """,
               st.session_state.usuario_atual["id_usuario"]
            )

            total, quantidade_gasto_mes_atual = cursor.fetchone()
            gasto_mes_atual = float(total)

            if receita_mes_atual > 0:
               taxa_poupanca = (
                  (receita_mes_atual - gasto_mes_atual)
                  / receita_mes_atual
               ) * 100
            else:
               taxa_poupanca = 0.0


            st.write("### Diagnóstico do mês")

            col1, col2, col3 = st.columns(3)

            with col1:
               st.metric(
                  "Receitas do mês",
                  formatar_moeda(receita_mes_atual)
               )


            with col2:
               st.metric(
                  f"{termo_gasto}s do mês",
                  formatar_moeda(gasto_mes_atual)
               )


            with col3:
               st.metric(
                  "Taxa de poupança",
                  f"{taxa_poupanca:.1f}%"
               )


            if taxa_poupanca < 0:
               diagnostico_poupanca = (
                  f"Seu mês está deficitário: "
                  f"{'suas despesas' if termo_gasto == 'Despesa' else 'seus gastos'} "
                  f"superaram suas receitas."
               )

            elif taxa_poupanca < 10:
               diagnostico_poupanca = "Sua taxa de poupança está baixa. Há pouca margem financeira no mês."

            elif taxa_poupanca < 20:
               diagnostico_poupanca = "Sua taxa de poupança está moderada."

            else:
               diagnostico_poupanca = "Sua taxa de poupança está saudável."


            st.info(diagnostico_poupanca)

            resumo_custos = consultar_custos_mes(
                cursor,
                st.session_state.usuario_atual["id_usuario"],
                date.today(),
            )
            exibir_custos_mes(resumo_custos, termo_gasto)

            if tipo_pessoa == "Pessoa Jurídica":
                exibir_margem(consultar_margem_mes(
                    cursor,
                    st.session_state.usuario_atual["id_usuario"],
                    date.today(),
                ), termo_gasto)
                exibir_reserva_tributos(conectar_banco)
                exibir_concentracao(consultar_concentracao_mes(
                    cursor,
                    st.session_state.usuario_atual["id_usuario"],
                    date.today(),
                ))


            cursor.execute(
               """
               SELECT COALESCE(SUM(valor), 0), COUNT(*)
               FROM dbo.gastos
               WHERE id_usuario = ?
               AND YEAR(data) = YEAR(DATEADD(MONTH, -1, GETDATE()))
               AND MONTH(data) = MONTH(DATEADD(MONTH, -1, GETDATE()))
               """,
               st.session_state.usuario_atual["id_usuario"]
            )

            total, quantidade_gasto_mes_anterior = cursor.fetchone()
            gasto_mes_anterior = float(total)

            if quantidade_gasto_mes_atual and quantidade_gasto_mes_anterior and gasto_mes_anterior > 0:
               variacao_gastos = (
                  (gasto_mes_atual - gasto_mes_anterior)
                  / gasto_mes_anterior
               ) * 100
            else:
               variacao_gastos = None

            if not quantidade_gasto_mes_anterior:
               diagnostico_gastos = "Não há gastos registrados no mês anterior para comparar."
            elif not quantidade_gasto_mes_atual:
               diagnostico_gastos = "Não há gastos registrados no mês atual para comparar."
            elif gasto_mes_anterior == 0:
               diagnostico_gastos = (
                  "Os gastos registrados no mês anterior somam R$ 0,00; "
                  "a variação percentual não pode ser calculada com base zero."
               )
            elif variacao_gastos is None:
               diagnostico_gastos = "Não há base positiva de gastos anteriores para calcular a variação percentual."

            elif variacao_gastos > 10:
               diagnostico_gastos = (
                  f"Seus gastos aumentaram {variacao_gastos:.1f}% em relação ao mês anterior."
               )

            elif variacao_gastos < -10:
               diagnostico_gastos = (
                  f"Seus gastos diminuíram {abs(variacao_gastos):.1f}% em relação ao mês anterior."
               )

            else:
               diagnostico_gastos = (
                  f"Seus gastos permaneceram relativamente estáveis, com variação de {variacao_gastos:.1f}%."
               )

            st.info(diagnostico_gastos)


            cursor.execute(
               """
               SELECT TOP 1
               categoria,
               SUM(valor) AS total_categoria
               FROM dbo.gastos
               WHERE id_usuario = ?
               AND YEAR(data) = YEAR(GETDATE())
               AND MONTH(data) = MONTH(GETDATE())
               GROUP BY categoria
               ORDER BY total_categoria DESC
               """,
               st.session_state.usuario_atual["id_usuario"]
            )

            categoria_principal = cursor.fetchone()


            if categoria_principal:
               nome_categoria_principal = categoria_principal[0]
               valor_categoria_principal = float(categoria_principal[1])
            else:
               nome_categoria_principal = None
               valor_categoria_principal = 0.0


            if gasto_mes_atual > 0 and nome_categoria_principal:
               percentual_categoria_principal = (
                  valor_categoria_principal / gasto_mes_atual
               ) * 100
            else:
               percentual_categoria_principal = 0.0


            if nome_categoria_principal:
               diagnostico_categoria = (
                  f"A categoria que mais pesou no seu mês foi "
                  f"{nome_categoria_principal}, representando "
                  f"{percentual_categoria_principal:.1f}% dos seus gastos."
               )
            else:
               diagnostico_categoria = (
                  "Ainda não há gastos suficientes neste mês para identificar uma categoria principal."
               )


            st.info(diagnostico_categoria)

            orcamento_categoria = None

            if nome_categoria_principal:
               cursor.execute(
                  """
                  SELECT TOP 1 valor_limite
                  FROM dbo.orcamentos
                  WHERE id_usuario = ?
                    AND categoria = ?
                    AND mes = ?
                    AND ano = ?
                    ORDER BY id_orcamento DESC
                    """,
                  st.session_state.usuario_atual["id_usuario"],
                  nome_categoria_principal,
                  date.today().month,
                  date.today().year
               )

               resultado_orcamento = cursor.fetchone()

               if resultado_orcamento:
                  orcamento_categoria = float(resultado_orcamento[0])


            if orcamento_categoria and orcamento_categoria > 0:
                  percentual_orcamento_consumido = (
                     valor_categoria_principal / orcamento_categoria
                  ) * 100
            else:
                  percentual_orcamento_consumido = None


            if percentual_orcamento_consumido is None:
                 diagnostico_orcamento = (
                 "Não há orçamento cadastrado para a categoria que mais pesou no mês."
            )

            elif percentual_orcamento_consumido >= 100:
                 diagnostico_orcamento = (
                 f"A categoria {nome_categoria_principal} já ultrapassou o orçamento "
                 f"em {percentual_orcamento_consumido - 100:.1f}%."
            )

            elif percentual_orcamento_consumido >= 80:
                 diagnostico_orcamento = (
                 f"A categoria {nome_categoria_principal} já consumiu "
                 f"{percentual_orcamento_consumido:.1f}% do orçamento."
            )

            else:
                 diagnostico_orcamento = (
                 f"A categoria {nome_categoria_principal} consumiu "
                 f"{percentual_orcamento_consumido:.1f}% do orçamento."
            )


            st.info(diagnostico_orcamento)


            cursor.execute(
               """
               SELECT COALESCE(SUM(valor), 0), COUNT(*)
               FROM dbo.receitas
               WHERE id_usuario = ?
                AND YEAR(data) = YEAR(DATEADD(MONTH, -1, GETDATE()))
                AND MONTH(data) = MONTH(DATEADD(MONTH, -1, GETDATE()))
               """,
               st.session_state.usuario_atual["id_usuario"]
            )

            total, quantidade_receita_mes_anterior = cursor.fetchone()
            receita_mes_anterior = float(total)


            if quantidade_receita_mes_atual and quantidade_receita_mes_anterior and receita_mes_anterior > 0:
               variacao_receitas = (
                  (receita_mes_atual - receita_mes_anterior)
                  / receita_mes_anterior

               ) * 100
            else: variacao_receitas = None


            if variacao_receitas is None or variacao_gastos is None:
             diagnostico_tendencia = (
               "Ainda não há dados suficientes para comparar completamente "
               "seu desempenho com o mês anterior."
    )

            elif variacao_receitas > 0 and variacao_gastos < 0:
             diagnostico_tendencia = (
               f"Seu cenário financeiro melhorou: suas receitas aumentaram "
               f"enquanto seus {termo_gasto}s diminuíram."
    )

            elif variacao_receitas < 0 and variacao_gastos > 0:
             diagnostico_tendencia = (
               f"Atenção: suas receitas diminuíram enquanto seus {termo_gasto}s aumentaram."
    )

            elif variacao_receitas > variacao_gastos:
             diagnostico_tendencia = (
              f"Suas receitas cresceram proporcionalmente mais que seus {termo_gasto}s."
    )

            elif variacao_gastos > variacao_receitas:
             diagnostico_tendencia = (
              f"Seus {termo_gasto}s cresceram proporcionalmente mais que suas receitas."
    )

            else:
             diagnostico_tendencia = (
               f"Receitas e {termo_gasto}s apresentaram variações semelhantes."
    )
            st.info(diagnostico_tendencia)


            saldo_mes_atual = receita_mes_atual - gasto_mes_atual
            saldo_mes_anterior = receita_mes_anterior - gasto_mes_anterior

            variacao_saldo = saldo_mes_atual - saldo_mes_anterior


            tem_movimentos_atual = quantidade_receita_mes_atual + quantidade_gasto_mes_atual > 0
            tem_movimentos_anterior = quantidade_receita_mes_anterior + quantidade_gasto_mes_anterior > 0
            if not tem_movimentos_anterior:
             diagnostico_saldo = (
                "Não há movimentações registradas no mês anterior. "
                f"O saldo registrado neste mês é {formatar_moeda(saldo_mes_atual)}; "
                "não há base para concluir melhora ou piora."
             )
            elif not tem_movimentos_atual:
             diagnostico_saldo = "Não há movimentações registradas no mês atual para comparar o saldo."
            elif variacao_saldo > 0:
             diagnostico_saldo = (
             f"Seu saldo mensal melhorou em {formatar_moeda(variacao_saldo)} "
             "em relação ao mês anterior."
    )

            elif variacao_saldo < 0:
             diagnostico_saldo = (
             f"Seu saldo mensal piorou em {formatar_moeda(abs(variacao_saldo))} "
             "em relação ao mês anterior."
    )

            else:
             diagnostico_saldo = (
             "Seu saldo mensal permaneceu igual ao mês anterior."
    )

            if tem_movimentos_atual and tem_movimentos_anterior:
             if not quantidade_gasto_mes_anterior:
                diagnostico_saldo += " O mês anterior contém apenas receitas, sem gastos registrados."
             elif not quantidade_receita_mes_anterior:
                diagnostico_saldo += " O mês anterior contém apenas gastos, sem receitas registradas."
             if not quantidade_gasto_mes_atual:
                diagnostico_saldo += " O mês atual contém apenas receitas, sem gastos registrados."
             elif not quantidade_receita_mes_atual:
                diagnostico_saldo += " O mês atual contém apenas gastos, sem receitas registradas."

            st.info(diagnostico_saldo)


            st.write("### Resumo Inteligente")


            resumo_inteligente = (
               f"Neste mês, sua taxa de poupança está em {taxa_poupanca:.1f}%. "
               f"{diagnostico_tendencia} "
               f"{diagnostico_saldo} "
               f"{diagnostico_categoria} "
            )

            st.success(resumo_inteligente)


            prioridade_mes = None

            if taxa_poupanca < 0:
               prioridade_mes = (
                  f"Prioridade do mês: seus {termo_gasto}s est]ao acima das suas receitas. "
                  "O principal foco deve ser recuperar um saldo mensal positivo."
               )

            elif percentual_orcamento_consumido is not None and percentual_orcamento_consumido >=100:
               prioridade_mes = (
                  f"Prioridade do mês: a categoria {nome_categoria_principal} "
                  f"já ultrapassou o orçamento em "
                  f"{percentual_orcamento_consumido - 100:.1f}%."
               )

            elif percentual_orcamento_consumido is not None and percentual_orcamento_consumido >= 80:
               prioridade_mes = (
                  f"Prioridade do mês: a categoria {nome_categoria_principal} "
                  f"já consumiu {percentual_orcamento_consumido:.1f}% do orçamento."
               )


            elif variacao_gastos is not None and variacao_gastos > 20:
               prioridade_mes = (
                 f"Prioridade do mês: seus {termo_gasto}s aumentaram "
                 f"{variacao_gastos:.1f}% em relação ao mês anterior. "
                 "Vale revisar quais despesas mais contribuíram para essa alta."
               )


            elif variacao_receitas is not None and variacao_receitas < -15:
               prioridade_mes = (
               f"Prioridade do mês: suas receitas caíram "
               f"{abs(variacao_receitas):.1f}% em relação ao mês anterior. "
               "O foco deve ser preservar margem e controlar novos gastos."

               )


            elif nome_categoria_principal and percentual_categoria_principal >= 40:
              prioridade_mes = (
              f"Prioridade do mês: a categoria {nome_categoria_principal} "
              f"representa {percentual_categoria_principal:.1f}% de todos os seus gastos. "
              "Vale verificar se essa concentração está adequada ao seu planejamento."
               )


            else:
              prioridade_mes = (
              "Seu cenário financeiro não apresenta nenhum sinal de atenção prioritária "
              "entre os indicadores analisados neste mês."
               )


            st.write("### Prioridade do mês")
            st.info(prioridade_mes)


            cursor.execute(
               """
               SELECT
                  categoria,
                  SUM(valor) AS total_categoria
               FROM dbo.gastos
               WHERE id_usuario = ?
                  AND YEAR(data) = YEAR(GETDATE())
                  AND MONTH(data) = MONTH(GETDATE())
               GROUP BY categoria
               """,
               st.session_state.usuario_atual["id_usuario"]
            )

            gastos_categoria_atual = {
               linha[0]: float(linha[1])
               for linha in cursor.fetchall()
            }


            cursor.execute(
               """
               SELECT
                  categoria,
                  SUM(valor) AS total_categoria
               FROM dbo.gastos
               WHERE id_usuario = ?
                  AND YEAR(data) = YEAR(DATEADD(MONTH, -1, GETDATE()))
                  AND MONTH(data) = MONTH(DATEADD(MONTH, -1, GETDATE()))
               GROUP BY categoria
               """,
               st.session_state.usuario_atual["id_usuario"]
            )

            gastos_categoria_anterior = {
             linha[0]: float(linha[1])
             for linha in cursor.fetchall()
            }


            maior_aumento_categoria = None
            maior_aumento_valor = 0.0

            for categoria, valor_atual in gastos_categoria_atual.items():
             valor_anterior = gastos_categoria_anterior.get(categoria, 0.0)

             aumento = valor_atual - valor_anterior

             if aumento > maior_aumento_valor:
              maior_aumento_valor = aumento
              maior_aumento_categoria = categoria


            if not quantidade_gasto_mes_anterior or not quantidade_gasto_mes_atual:
             diagnostico_maior_aumento = (
                "Não há gastos registrados nos dois meses para comparar aumentos por categoria."
             )
            elif maior_aumento_categoria:
             diagnostico_maior_aumento = (
             f"A categoria que mais aumentou seus {termo_gasto}s neste mês foi "
             f"{maior_aumento_categoria}, com um aumento de "
             f"{formatar_moeda(maior_aumento_valor)} em relação ao mês anterior."
            )
            else:
             diagnostico_maior_aumento = (
             f"Nenhuma categoria apresentou aumento de {termo_gasto}s "
             "em relação ao mês anterior."
            )

            if (quantidade_gasto_mes_anterior and quantidade_gasto_mes_atual
                and maior_aumento_categoria and maior_aumento_categoria not in gastos_categoria_anterior):
             diagnostico_maior_aumento += (
                " Essa categoria não teve gastos registrados no mês anterior; "
                "a comparação usa R$ 0,00 como referência para ela."
             )

            st.info(diagnostico_maior_aumento)

            cursor.close()
            conexao.close()
