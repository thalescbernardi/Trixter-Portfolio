"""Margem de contribuição do mês a partir da receita e da classificação já gravada. Não aloca custo por cliente."""
from datetime import date
from decimal import Decimal

from .classificacao import classe_custo
from .relatorios import formatar_moeda


def _dinheiro(valor):
    if valor is None:
        return Decimal(0)
    return Decimal(str(valor))


def _categoria(nome):
    texto = str(nome or "").strip()
    return texto or "Sem categoria"


def calcular_margem(receitas, gastos):
    """Contribuição é receita menos variável. Depois do fixo desconta o fixo. Não classificado fica de fora."""
    por_receita = {}
    receita = Decimal(0)
    for linha in receitas:
        valor = _dinheiro(linha.get("valor"))
        if valor == 0:
            continue
        categoria = _categoria(linha.get("categoria"))
        por_receita[categoria] = por_receita.get(categoria, Decimal(0)) + valor
        receita += valor

    totais = {"Fixo": Decimal(0), "Variável": Decimal(0), "Não classificado": Decimal(0)}
    por_gasto = {}
    for linha in gastos:
        valor = _dinheiro(linha.get("valor"))
        if valor == 0:
            continue
        classe = classe_custo(linha.get("classificacao"))
        categoria = _categoria(linha.get("categoria"))
        totais[classe] += valor
        chave = (classe, categoria)
        por_gasto[chave] = por_gasto.get(chave, Decimal(0)) + valor

    contribuicao = receita - totais["Variável"]
    depois_do_fixo = contribuicao - totais["Fixo"]

    def participacao(parte):
        if receita <= 0:
            return None
        return parte / receita

    categorias = [
        {
            "lado": "receita",
            "categoria": categoria,
            "classificacao": "",
            "valor": valor,
            "participacao": participacao(valor),
        }
        for categoria, valor in por_receita.items()
    ]
    categorias.sort(key=lambda item: (-item["valor"], item["categoria"]))
    ordem = {"Variável": 0, "Fixo": 1, "Não classificado": 2}
    custos = [
        {
            "lado": "gasto",
            "categoria": categoria,
            "classificacao": classe,
            "valor": valor,
            "participacao": participacao(valor),
        }
        for (classe, categoria), valor in por_gasto.items()
    ]
    custos.sort(key=lambda item: (ordem[item["classificacao"]], -item["valor"], item["categoria"]))
    categorias.extend(custos)
    return {
        "receita": receita,
        "variavel": totais["Variável"],
        "fixo": totais["Fixo"],
        "nao_classificado": totais["Não classificado"],
        "contribuicao": contribuicao,
        "depois_do_fixo": depois_do_fixo,
        "participacao_contribuicao": participacao(contribuicao),
        "participacao_depois_do_fixo": participacao(depois_do_fixo),
        "categorias": categorias,
    }


def consultar_margem_mes(cursor, id_usuario, hoje):
    inicio = hoje.replace(day=1)
    fim = date(hoje.year + (hoje.month == 12), hoje.month % 12 + 1, 1)
    cursor.execute(
        """
        SELECT categoria, classificacao, COALESCE(SUM(valor), 0)
        FROM dbo.gastos
        WHERE id_usuario = ? AND data >= ? AND data < ?
        GROUP BY categoria, classificacao
        """,
        id_usuario, inicio, fim,
    )
    gastos = [
        {"categoria": categoria, "classificacao": classificacao, "valor": valor}
        for categoria, classificacao, valor in cursor.fetchall()
    ]
    cursor.execute(
        """
        SELECT categoria, COALESCE(SUM(valor), 0)
        FROM dbo.receitas
        WHERE id_usuario = ? AND data >= ? AND data < ?
        GROUP BY categoria
        """,
        id_usuario, inicio, fim,
    )
    receitas = [
        {"categoria": categoria, "valor": valor}
        for categoria, valor in cursor.fetchall()
    ]
    return calcular_margem(receitas, gastos)


def _moeda(valor):
    return formatar_moeda(abs(valor) if valor < 0 else valor).strip()


def exibir_margem(resumo, termo_gasto):
    import pandas as pd
    import streamlit as st

    st.subheader("Margem de contribuição do mês")
    st.caption(
        "A margem de contribuição corresponde à receita do mês menos as despesas variáveis. "
        "Ela indica quanto resta para cobrir as despesas fixas e contribuir para o resultado da empresa. "
        "Este valor não é o lucro líquido. "
        f"{termo_gasto}s sem classificação ficam de fora desse cálculo e não são reclassificadas automaticamente."
    )
    vazio = (
        resumo["receita"] == 0
        and resumo["variavel"] == 0
        and resumo["fixo"] == 0
        and resumo["nao_classificado"] == 0
    )
    if vazio:
        st.info("Nenhuma receita ou despesa registrada neste mês." if termo_gasto == "Despesa"
                else "Nenhuma receita ou gasto registrado neste mês.")
        return

    contribuicao, depois = st.columns(2)
    contribuicao.metric("Margem de contribuição", formatar_moeda(resumo["contribuicao"]).strip())
    depois.metric("Depois do fixo", formatar_moeda(resumo["depois_do_fixo"]).strip())

    if resumo["contribuicao"] < 0:
        st.write(f"A margem de contribuição é negativa em {_moeda(resumo['contribuicao'])}.")
    elif resumo["receita"] > 0:
        st.write(
            f"A margem de contribuição é {_moeda(resumo['contribuicao'])}, "
            f"{resumo['participacao_contribuicao']:.0%} da receita."
        )
    if resumo["receita"] <= 0:
        st.info(
            "Não há receitas neste mês, então o percentual da margem de contribuição não é calculado."
        )
    if resumo["depois_do_fixo"] < 0:
        st.write(f"Depois do fixo, faltam {_moeda(resumo['depois_do_fixo'])}.")
    elif resumo["depois_do_fixo"] == 0:
        st.write("Depois do fixo, o mês empata com o custo fixo.")
    else:
        st.write(f"Depois do fixo, sobram {_moeda(resumo['depois_do_fixo'])}.")
    if resumo["nao_classificado"] > 0:
        st.write(
            f"Há {_moeda(resumo['nao_classificado'])} sem classificação. "
            "Esse valor não entrou nas duas contas."
        )

    tabela = pd.DataFrame(resumo["categorias"])
    tabela["Lado"] = tabela["lado"].map({"receita": "Receita", "gasto": termo_gasto})
    tabela["Valor"] = tabela["valor"].map(lambda valor: formatar_moeda(valor).strip())
    tabela["Participação"] = tabela["participacao"].map(
        lambda valor: "" if valor is None else f"{valor:.0%}"
    )
    st.dataframe(
        tabela.rename(columns={"categoria": "Categoria", "classificacao": "Classificação"})[
            ["Lado", "Categoria", "Classificação", "Valor", "Participação"]
        ],
        use_container_width=True,
        hide_index=True,
    )
