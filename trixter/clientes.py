"""Nome de cliente no lançamento. Não é cadastro de tomador nem de nota."""
from datetime import date
from decimal import Decimal

from .relatorios import formatar_moeda


def normalizar_cliente(nome):
    if nome is None:
        return None
    texto = " ".join(str(nome).split())[:80]
    return texto or None


def _dinheiro(valor):
    if valor is None:
        return Decimal(0)
    return Decimal(str(valor))


def concentrar_clientes(linhas):
    grupos = {}
    for linha in linhas:
        nome = normalizar_cliente(linha.get("cliente")) or "Sem cliente"
        grupos[nome] = grupos.get(nome, Decimal(0)) + _dinheiro(linha.get("valor"))
    total = sum(grupos.values(), Decimal(0))
    itens = []
    for nome, valor in grupos.items():
        itens.append({
            "cliente": nome,
            "valor": valor,
            "percentual": valor / total if total else None,
        })
    itens.sort(key=lambda item: (-item["valor"], item["cliente"]))
    return {"total": total, "itens": itens}


def consultar_concentracao_mes(cursor, id_usuario, hoje):
    inicio = hoje.replace(day=1)
    fim = date(hoje.year + (hoje.month == 12), hoje.month % 12 + 1, 1)
    cursor.execute(
        """
        SELECT cliente, COALESCE(SUM(valor), 0)
        FROM dbo.receitas
        WHERE id_usuario = ? AND data >= ? AND data < ?
        GROUP BY cliente
        """,
        id_usuario, inicio, fim,
    )
    return concentrar_clientes(
        [{"cliente": cliente, "valor": valor} for cliente, valor in cursor.fetchall()]
    )


def atrasos_por_cliente(itens):
    grupos = {}
    for item in itens:
        if item.get("situacao") != "Atrasado" or item.get("direcao") != "receber":
            continue
        nome = normalizar_cliente(item.get("cliente")) or "Sem cliente"
        grupos[nome] = grupos.get(nome, Decimal(0)) + _dinheiro(item.get("valor"))
    return [
        {"cliente": nome, "valor": valor}
        for nome, valor in sorted(grupos.items(), key=lambda par: (-par[1], par[0]))
    ]


def exibir_concentracao(resumo):
    import pandas as pd
    import streamlit as st

    st.subheader("Concentração de clientes")
    st.caption("Participação de cada cliente nas receitas deste mês. O nome fica no lançamento; não há cadastro de tomador.")
    if resumo["total"] == 0:
        st.info("Nenhuma receita registrada neste mês.")
        return
    nomeados = [item for item in resumo["itens"] if item["cliente"] != "Sem cliente"]
    if not nomeados:
        st.info("Nenhuma receita deste mês tem cliente informado.")
        return
    maior = nomeados[0]
    st.write(f"{maior['cliente']} representa {maior['percentual']:.0%} da receita do mês.")
    tabela = pd.DataFrame(resumo["itens"])
    tabela["Participação"] = tabela["percentual"].map(lambda valor: f"{valor:.0%}")
    tabela["Valor"] = tabela["valor"].map(lambda valor: formatar_moeda(valor).strip())
    st.dataframe(
        tabela.rename(columns={"cliente": "Cliente"})[["Cliente", "Valor", "Participação"]],
        use_container_width=True,
        hide_index=True,
    )
