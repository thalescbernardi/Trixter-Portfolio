"""Resumo diário, gráfico e caixa previsto a partir de recorrências e planejamentos."""
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal

import pandas as pd
import plotly.graph_objects as go

from .compromissos import em_aberto, situacao_efetiva
from .relatorios import formatar_moeda


def resumir_por_dia(movimentacoes):
    dados = movimentacoes.copy()
    dados["data"] = pd.to_datetime(dados["data"]).dt.normalize()
    diario = dados.pivot_table(
        index="data", columns="tipo", values="valor", aggfunc="sum", fill_value=0
    ).reindex(columns=["Entrada", "Saída"], fill_value=0).sort_index()
    diario["Saldo acumulado"] = (diario["Entrada"] - diario["Saída"]).cumsum()
    return diario.reset_index()


def criar_grafico(diario):
    # Categorias de data evitam um eixo artificial quando há apenas um dia.
    datas = diario["data"].dt.strftime("%d/%m/%Y").tolist()
    fig = go.Figure()
    for coluna, nome, cor in [
        ("Entrada", "Entradas", "#288577"),
        ("Saída", "Saídas", "#B87928"),
    ]:
        fig.add_bar(
            x=datas, y=[float(v) for v in diario[coluna]], name=nome,
            marker_color=cor,
            customdata=[formatar_moeda(v) for v in diario[coluna]],
            hovertemplate="%{x}<br>%{customdata}<extra>%{fullData.name}</extra>",
        )
    fig.add_scatter(
        x=datas, y=[float(v) for v in diario["Saldo acumulado"]],
        name="Saldo acumulado", mode="lines+markers" if len(diario) > 1 else "markers",
        line=dict(color="#172033", width=3), marker=dict(size=9),
        customdata=[formatar_moeda(v) for v in diario["Saldo acumulado"]],
        hovertemplate="%{x}<br>%{customdata}<extra>Saldo acumulado</extra>",
    )
    fig.update_layout(
        barmode="group", height=380, hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#172033"), separators=",.",
        margin=dict(l=20, r=20, t=45, b=20),
        legend=dict(orientation="h", y=1.15, x=0),
        xaxis=dict(type="category", title=None),
        yaxis=dict(title="Valor (R$)", tickprefix="R$ ", tickformat=",.0f",
                   gridcolor="#E3E7ED", zerolinecolor="#A0A7B0"),
    )
    return fig


def _como_data(valor):
    if valor is None or valor is pd.NaT:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        for formato in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(texto[:10], formato).date()
            except ValueError:
                continue
    return None


def _dinheiro(valor):
    if valor is None:
        return Decimal(0)
    return Decimal(str(valor))


def _tipo_movimento(tipo):
    if tipo is None:
        return None
    nome = str(tipo).strip().lower()
    if nome == "receita":
        return "Entrada"
    if nome in ("gasto", "despesa"):
        return "Saída"
    return None


def _dia_valido(ano, mes, dia):
    dia = int(dia)
    if dia < 1:
        return None
    return min(dia, monthrange(ano, mes)[1])


def _avancar_ocorrencia(atual, recorrencia):
    frequencia = str(recorrencia.get("frequencia") or "").strip()
    if frequencia == "Diária":
        return atual + timedelta(days=1)
    if frequencia == "Semanal":
        return atual + timedelta(weeks=1)
    if frequencia == "Mensal":
        if recorrencia.get("dia") is None:
            return None
        indice = atual.year * 12 + atual.month
        ano, mes = divmod(indice, 12)
        dia = _dia_valido(ano, mes + 1, recorrencia["dia"])
        if dia is None:
            return None
        return date(ano, mes + 1, dia)
    if frequencia == "Anual":
        if recorrencia.get("dia") is None or recorrencia.get("mes") is None:
            return None
        ano = atual.year + 1
        mes = int(recorrencia["mes"])
        if not 1 <= mes <= 12:
            return None
        dia = _dia_valido(ano, mes, recorrencia["dia"])
        if dia is None:
            return None
        return date(ano, mes, dia)
    return None


def _primeira_ocorrencia(atual, recorrencia, inicio):
    """Primeira data estritamente posterior a inicio, sem percorrer dia a dia."""
    if atual > inicio:
        return atual
    frequencia = str(recorrencia.get("frequencia") or "").strip()
    if frequencia == "Diária":
        return inicio + timedelta(days=1)
    if frequencia == "Semanal":
        passos = (inicio - atual).days // 7 + 1
        return atual + timedelta(weeks=passos)
    proxima = atual
    for _ in range(600):
        if proxima > inicio:
            return proxima
        seguinte = _avancar_ocorrencia(proxima, recorrencia)
        if seguinte is None or seguinte <= proxima:
            return None
        proxima = seguinte
    return None


def ocorrencias_recorrencia(recorrencia, inicio, fim):
    """Datas após inicio e até fim. Recorrência inativa ou sem próxima execução não entra."""
    if "ativa" in recorrencia and not recorrencia["ativa"]:
        return []
    frequencia = str(recorrencia.get("frequencia") or "").strip()
    if frequencia not in ("Diária", "Semanal", "Mensal", "Anual"):
        return []
    atual = _como_data(recorrencia.get("proxima_execucao"))
    if atual is None:
        return []
    atual = _primeira_ocorrencia(atual, recorrencia, inicio)
    datas = []
    while atual is not None and atual <= fim and len(datas) < 500:
        datas.append(atual)
        seguinte = _avancar_ocorrencia(atual, recorrencia)
        if seguinte is None or seguinte <= atual:
            break
        atual = seguinte
    return datas


def projetar_caixa(saldo_atual, recorrencias, planejamentos, hoje, dias):
    """Projeta entradas e saídas de amanhã até hoje + dias.

    O saldo de hoje já está realizado. Ocorrências até hoje ficam de fora
    para não contar de novo um lançamento que a recorrência já deveria ter gerado.
    """
    hoje = _como_data(hoje)
    fim = hoje + timedelta(days=dias)
    movimentos = []

    def acrescentar(data_mov, origem, descricao, tipo, valor, vencimento=None):
        if data_mov is None or data_mov <= hoje or data_mov > fim or valor <= 0 or tipo is None:
            return
        texto = str(descricao or "").strip() or "Sem descrição"
        movimentos.append({
            "data": data_mov,
            "vencimento": vencimento,
            "origem": origem,
            "descricao": texto,
            "tipo": tipo,
            "valor": valor,
        })

    for recorrencia in recorrencias:
        tipo = _tipo_movimento(recorrencia.get("tipo"))
        valor = _dinheiro(recorrencia.get("valor"))
        for data_mov in ocorrencias_recorrencia(recorrencia, hoje, fim):
            acrescentar(
                data_mov, "Recorrência",
                recorrencia.get("descricao") or recorrencia.get("categoria"),
                tipo, valor,
            )
    for planejamento in planejamentos:
        if not em_aberto(planejamento.get("situacao")):
            continue
        vencimento = _como_data(planejamento.get("data"))
        status = situacao_efetiva(vencimento, planejamento.get("situacao"), hoje)
        data_caixa = hoje + timedelta(days=1) if status == "Atrasado" else vencimento
        acrescentar(
            data_caixa,
            "Atrasado" if status == "Atrasado" else "Planejamento",
            planejamento.get("descricao") or planejamento.get("categoria"),
            _tipo_movimento(planejamento.get("tipo")),
            _dinheiro(planejamento.get("valor")),
            vencimento if status == "Atrasado" else None,
        )

    movimentos.sort(key=lambda item: (item["data"], item["origem"], item["descricao"]))
    saldo = _dinheiro(saldo_atual)
    ja_negativo = saldo < 0
    primeiro_negativo = None
    entradas = Decimal(0)
    saidas = Decimal(0)
    indice = 0
    while indice < len(movimentos):
        data_mov = movimentos[indice]["data"]
        while indice < len(movimentos) and movimentos[indice]["data"] == data_mov:
            item = movimentos[indice]
            if item["tipo"] == "Entrada":
                saldo += item["valor"]
                entradas += item["valor"]
            else:
                saldo -= item["valor"]
                saidas += item["valor"]
            indice += 1
        if not ja_negativo and primeiro_negativo is None and saldo < 0:
            primeiro_negativo = data_mov
    return {
        "dias": dias,
        "ate": fim,
        "entradas": entradas,
        "saidas": saidas,
        "saldo_final": saldo,
        "primeiro_dia_negativo": primeiro_negativo,
        "ja_negativo": ja_negativo,
        "movimentos": movimentos,
    }


def consultar_caixa_previsto(cursor, id_usuario, saldo_atual, hoje, horizontes=(30, 90)):
    fim = hoje + timedelta(days=max(horizontes))
    cursor.execute(
        """
        SELECT tipo, categoria, descricao, valor, frequencia, proxima_execucao, ativa, dia, mes
        FROM dbo.recorrencias
        WHERE id_usuario = ? AND ISNULL(ativa, 0) = 1
        """,
        id_usuario,
    )
    colunas = [coluna[0] for coluna in cursor.description]
    recorrencias = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    cursor.execute(
        """
        SELECT tipo, categoria, descricao, valor, data, situacao
        FROM dbo.planejamentos
        WHERE id_usuario = ?
          AND (situacao IS NULL OR situacao NOT IN (N'Recebido', N'Pago'))
          AND ((data > ? AND data <= ?) OR data < ?)
        """,
        id_usuario, hoje, fim, hoje,
    )
    colunas = [coluna[0] for coluna in cursor.description]
    planejamentos = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    return [
        projetar_caixa(saldo_atual, recorrencias, planejamentos, hoje, dias)
        for dias in horizontes
    ]


def exibir_caixa_previsto(previsoes):
    import streamlit as st

    st.subheader("Caixa previsto")
    st.caption(
        "Conta as recorrências ativas e os planejamentos em aberto, de amanhã até o fim de cada período. "
        "Compromisso recebido ou pago não entra. Compromisso atrasado entra na projeção de amanhã, "
        "com a data original na lista. "
        "Um compromisso cadastrado na recorrência e no planejamento entra duas vezes. "
        "Lançamentos já registrados continuam apenas no saldo realizado."
    )
    for previsao in previsoes:
        st.markdown(f"**Próximos {previsao['dias']} dias** · até {previsao['ate']:%d/%m/%Y}")
        entrada, saida, saldo = st.columns(3)
        entrada.metric("Entradas previstas", formatar_moeda(previsao["entradas"]).strip())
        saida.metric("Saídas previstas", formatar_moeda(previsao["saidas"]).strip())
        saldo.metric("Saldo previsto", formatar_moeda(previsao["saldo_final"]).strip())
        if previsao["ja_negativo"]:
            st.error("O saldo realizado já está negativo.")
        elif previsao["primeiro_dia_negativo"]:
            st.warning(
                "O saldo previsto fica negativo em "
                f"{previsao['primeiro_dia_negativo']:%d/%m/%Y}."
            )
        else:
            st.success(
                f"O saldo previsto não fica negativo nos próximos {previsao['dias']} dias."
            )
    movimentos = previsoes[-1]["movimentos"] if previsoes else []
    if not movimentos:
        st.info("Nenhum recebimento ou pagamento previsto no maior período.")
        return
    tabela = pd.DataFrame(movimentos)
    def data_exibida(linha):
        vencimento = linha.get("vencimento")
        if vencimento is not None and not pd.isna(vencimento):
            return vencimento
        return linha["data"]
    tabela["Data"] = tabela.apply(lambda linha: data_exibida(linha).strftime("%d/%m/%Y"), axis=1)
    tabela["Valor"] = tabela.apply(
        lambda linha: formatar_moeda(linha["valor"] if linha["tipo"] == "Entrada" else -linha["valor"]).strip(),
        axis=1,
    )
    st.dataframe(
        tabela.rename(columns={"origem": "Origem", "descricao": "Descrição"})[
            ["Data", "Origem", "Descrição", "Valor"]
        ],
        use_container_width=True,
        hide_index=True,
    )
