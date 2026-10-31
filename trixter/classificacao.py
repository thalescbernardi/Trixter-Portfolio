"""Leitura de custos fixos e variáveis a partir da classificação já gravada."""
from datetime import date
from decimal import Decimal

from .relatorios import formatar_moeda


def _dinheiro(valor):
    if valor is None:
        return Decimal(0)
    return Decimal(str(valor))


def classe_custo(valor):
    if valor is None:
        return "Não classificado"
    texto = str(valor).strip().lower()
    if texto in ("", "não classificado", "nao classificado", "none", "nan"):
        return "Não classificado"
    if texto == "fixo":
        return "Fixo"
    if texto in ("variável", "variavel"):
        return "Variável"
    return "Não classificado"


def resumir_custos(linhas, receita=0):
    """Soma gastos do período por classificação e categoria."""
    totais = {"Fixo": Decimal(0), "Variável": Decimal(0), "Não classificado": Decimal(0)}
    por_categoria = {}
    for linha in linhas:
        valor = _dinheiro(linha.get("valor"))
        if valor == 0:
            continue
        classe = classe_custo(linha.get("classificacao"))
        categoria = str(linha.get("categoria") or "Sem categoria").strip() or "Sem categoria"
        totais[classe] += valor
        chave = (classe, categoria)
        por_categoria[chave] = por_categoria.get(chave, Decimal(0)) + valor
    receita = _dinheiro(receita)
    categorias = [
        {"classificacao": classe, "categoria": categoria, "valor": valor}
        for (classe, categoria), valor in por_categoria.items()
    ]
    categorias.sort(key=lambda item: (-item["valor"], item["classificacao"], item["categoria"]))

    def participacao(parte):
        if receita <= 0:
            return None
        return parte / receita

    return {
        "fixo": totais["Fixo"],
        "variavel": totais["Variável"],
        "nao_classificado": totais["Não classificado"],
        "total": totais["Fixo"] + totais["Variável"] + totais["Não classificado"],
        "receita": receita,
        "participacao_fixo": participacao(totais["Fixo"]),
        "participacao_variavel": participacao(totais["Variável"]),
        "categorias": categorias,
    }


def frase_natureza(total, fixo, variavel):
    """Frase curta para o alerta de orçamento. Vazia quando não há gasto."""
    total = _dinheiro(total)
    fixo = _dinheiro(fixo)
    variavel = _dinheiro(variavel)
    if total <= 0:
        return ""
    resto = total - fixo - variavel
    if resto < 0:
        resto = Decimal(0)
    if fixo == total:
        return "Esse valor é fixo: ele continua mesmo se a venda cair."
    if variavel == total:
        return "Esse valor é variável: ele acompanha a venda."
    if fixo == 0 and variavel == 0:
        return "Esse valor ainda não está classificado como fixo ou variável."
    partes = []
    if fixo > 0:
        partes.append(f"{formatar_moeda(fixo).strip()} é fixo")
    if variavel > 0:
        partes.append(f"{formatar_moeda(variavel).strip()} é variável")
    if resto > 0:
        partes.append(f"{formatar_moeda(resto).strip()} não está classificado")
    if len(partes) == 2:
        texto = f"{partes[0]} e {partes[1]}"
    else:
        texto = f"{partes[0]}, {partes[1]} e {partes[2]}"
    return f"Desse total, {texto}."


def detalhe_custos(total, fixo, variavel):
    total = _dinheiro(total)
    if total <= 0:
        return ""
    fixo = _dinheiro(fixo)
    variavel = _dinheiro(variavel)
    resto = total - fixo - variavel
    if resto < 0:
        resto = Decimal(0)
    return (
        f"Fixo {formatar_moeda(fixo).strip()} · "
        f"Variável {formatar_moeda(variavel).strip()} · "
        f"Não classificado {formatar_moeda(resto).strip()}"
    )


def consultar_custos_mes(cursor, id_usuario, hoje):
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
    linhas = [
        {"categoria": categoria, "classificacao": classificacao, "valor": valor}
        for categoria, classificacao, valor in cursor.fetchall()
    ]
    cursor.execute(
        """
        SELECT COALESCE(SUM(valor), 0)
        FROM dbo.receitas
        WHERE id_usuario = ? AND data >= ? AND data < ?
        """,
        id_usuario, inicio, fim,
    )
    return resumir_custos(linhas, cursor.fetchone()[0])


def exibir_custos_mes(resumo, termo_gasto):
    import pandas as pd
    import streamlit as st

    flexao = "fixas e variáveis" if termo_gasto == "Despesa" else "fixos e variáveis"
    st.subheader(f"{termo_gasto}s {flexao}")


    if termo_gasto == "Despesa":
     explicacao = (
        "Fixa se repete regularmente. Variável muda conforme a atividade ou o volume de vendas. "
        "Não classificado ainda fica de fora dessa comparação."
    )
    else:
     explicacao = (
        "Fixo se repete regularmente. Variável muda conforme seu consumo ou necessidade. "
        "Não classificado ainda fica de fora dessa comparação."
    )

    st.caption(explicacao)

    if resumo["total"] == 0:
        if termo_gasto == "Despesa":
            st.info("Nenhuma despesa registrada neste mês.")
        else:
            st.info("Nenhum gasto registrado neste mês.")
        return
    fixo, variavel, aberto = st.columns(3)
    fixo.metric("Fixo", formatar_moeda(resumo["fixo"]).strip())
    variavel.metric("Variável", formatar_moeda(resumo["variavel"]).strip())
    aberto.metric("Não classificado", formatar_moeda(resumo["nao_classificado"]).strip())
    if resumo["participacao_fixo"] is None:
        st.write("Ainda não há receita neste mês para comparar com " \
        f"{'essas despesas' if termo_gasto == 'Despesa' else 'esses gastos'}.")
    else:
        if termo_gasto == "Despesa":
            st.write(
                f"A despesa fixa consome {resumo['participacao_fixo']:.0%} da receita do mês. "
                f"A despesa variável representa {resumo['participacao_variavel']:.0%} da receita do mês."
            )
        else:
            st.write(
                f"O gasto fixo consome {resumo['participacao_fixo']:.0%} da receita do mês. "
                f"O gasto variável representa {resumo['participacao_variavel']:.0%} da receita do mês."
            )
    tabela = pd.DataFrame(resumo["categorias"])
    tabela["Valor"] = tabela["valor"].map(lambda valor: formatar_moeda(valor).strip())
    st.dataframe(
        tabela.rename(columns={"classificacao": "Classificação", "categoria": "Categoria"})[
            ["Classificação", "Categoria", "Valor"]
        ],
        use_container_width=True,
        hide_index=True,
    )
