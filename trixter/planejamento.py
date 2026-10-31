"""Consultas e cálculos de planejamento, independentes da sessão do Streamlit."""
from datetime import date
from decimal import Decimal

import pandas as pd

from .clientes import normalizar_cliente
from .compromissos import em_aberto
from .recorrencias import normalizar_data, ocorrencias_no_mes


def excluir_planejamento(cursor, id_planejamento, id_usuario):
    """Remove uma linha da conta. Não apaga receita, gasto nem outro módulo."""
    if not str(id_planejamento or "").strip() or not str(id_usuario or "").strip():
        return False
    cursor.execute(
        """
        DELETE FROM dbo.planejamentos
        WHERE id_planejamento = ?
          AND id_usuario = ?
        """,
        id_planejamento,
        id_usuario,
    )
    return cursor.rowcount == 1


def _desfazer_transacao(conexao):
    try:
        conexao.rollback()
    except Exception:
        return False
    return True


def _fechar_recurso_planejamento(recurso):
    if recurso is None:
        return
    try:
        recurso.close()
    except Exception:
        return


def concluir_exclusao_planejamento(conectar, id_planejamento, id_usuario):
    """'excluido', 'ausente' ou 'falha'. Sucesso só com exatamente uma linha."""
    try:
        conexao = conectar()
    except Exception:
        return "falha"
    cursor = None
    try:
        cursor = conexao.cursor()
        if not excluir_planejamento(cursor, id_planejamento, id_usuario):
            if not _desfazer_transacao(conexao):
                return "falha"
            return "ausente"
        conexao.commit()
        return "excluido"
    except Exception:
        _desfazer_transacao(conexao)
        return "falha"
    finally:
        _fechar_recurso_planejamento(cursor)
        _fechar_recurso_planejamento(conexao)


def atualizar_texto_planejamento(
    cursor, id_planejamento, id_usuario, descricao, cliente, alterar_cliente
):
    """Corrige descrição e, na receita, cliente. Não mexe em valor nem em lançamento."""
    if not str(id_planejamento or "").strip() or not str(id_usuario or "").strip():
        return False
    texto = str("" if descricao is None else descricao).strip()
    if alterar_cliente:
        cursor.execute(
            """
            UPDATE dbo.planejamentos
            SET descricao = ?, cliente = ?
            WHERE id_planejamento = ?
              AND id_usuario = ?
            """,
            texto,
            normalizar_cliente(cliente),
            id_planejamento,
            id_usuario,
        )
    else:
        cursor.execute(
            """
            UPDATE dbo.planejamentos
            SET descricao = ?
            WHERE id_planejamento = ?
              AND id_usuario = ?
            """,
            texto,
            id_planejamento,
            id_usuario,
        )
    return cursor.rowcount == 1


def concluir_atualizacao_texto_planejamento(
    conectar, id_planejamento, id_usuario, descricao, cliente, alterar_cliente
):
    """'atualizado', 'ausente' ou 'falha'. Sucesso só com exatamente uma linha."""
    try:
        conexao = conectar()
    except Exception:
        return "falha"
    cursor = None
    try:
        cursor = conexao.cursor()
        if not atualizar_texto_planejamento(
            cursor,
            id_planejamento,
            id_usuario,
            descricao,
            cliente,
            alterar_cliente,
        ):
            if not _desfazer_transacao(conexao):
                return "falha"
            return "ausente"
        conexao.commit()
        return "atualizado"
    except Exception:
        _desfazer_transacao(conexao)
        return "falha"
    finally:
        _fechar_recurso_planejamento(cursor)
        _fechar_recurso_planejamento(conexao)


def deslocar_mes(data, meses):
    indice = data.year * 12 + data.month - 1 + meses
    ano, mes = divmod(indice, 12)
    return date(ano, mes + 1, 1)


def consultar_base_simulador(cursor, id_usuario, hoje):
    fim = hoje.replace(day=1)
    inicio = deslocar_mes(fim, -3)
    medias = []
    tem_historico = False
    for tabela in ("receitas", "gastos"):
        cursor.execute(
            f"SELECT COALESCE(SUM(valor), 0), COUNT(*) FROM dbo.{tabela} "
            "WHERE id_usuario = ? AND data >= ? AND data < ?",
            id_usuario, inicio, fim,
        )
        total, quantidade = cursor.fetchone()
        medias.append(float(total) / 3)
        tem_historico = tem_historico or quantidade > 0
    return medias[0], medias[1], tem_historico, inicio, fim


def consultar_planejamento_anual(cursor, id_usuario, ano, recorrencias, contar_ocorrencias):
    inicio, fim = date(ano, 1, 1), date(ano + 1, 1, 1)
    linhas = [{
        "mes": mes, "receitas_realizadas": Decimal(0), "gastos_realizados": Decimal(0),
        "receitas_planejadas": Decimal(0), "gastos_planejados": Decimal(0),
        "receitas_recorrentes": Decimal(0), "gastos_recorrentes": Decimal(0),
    } for mes in range(1, 13)]
    for tabela, coluna in (("receitas", "receitas_realizadas"), ("gastos", "gastos_realizados")):
        cursor.execute(
            f"SELECT MONTH(data), SUM(valor) FROM dbo.{tabela} "
            "WHERE id_usuario = ? AND data >= ? AND data < ? GROUP BY MONTH(data)",
            id_usuario, inicio, fim,
        )
        for mes, valor in cursor.fetchall():
            linhas[mes - 1][coluna] = Decimal(str(valor))
    cursor.execute(
        "SELECT MONTH(data), LOWER(tipo), SUM(valor) FROM dbo.planejamentos "
        "WHERE id_usuario = ? AND data >= ? AND data < ? GROUP BY MONTH(data), LOWER(tipo)",
        id_usuario, inicio, fim,
    )
    for mes, tipo, valor in cursor.fetchall():
        if tipo in ("receita", "gasto", "despesa"):
            coluna = "receitas_planejadas" if tipo == "receita" else "gastos_planejados"
            linhas[mes - 1][coluna] += Decimal(str(valor))
    for linha in linhas:
        for recorrencia in recorrencias:
            if not recorrencia["ativa"]:
                continue
            tipo = recorrencia["tipo"].lower()
            if tipo not in ("receita", "gasto", "despesa"):
                continue
            coluna = "receitas_recorrentes" if tipo == "receita" else "gastos_recorrentes"
            linha[coluna] += Decimal(str(recorrencia["valor"])) * contar_ocorrencias(
                recorrencia, linha["mes"], ano
            )
        for sufixo in ("realizadas", "planejadas", "recorrentes"):
            sufixo_gastos = {"realizadas": "realizados", "planejadas": "planejados"}.get(sufixo, sufixo)
            linha[f"saldo_{sufixo}"] = linha[f"receitas_{sufixo}"] - linha[f"gastos_{sufixo_gastos}"]
    return pd.DataFrame(linhas)


def consultar_comparacao_categorias(cursor, id_usuario, ano):
    inicio, fim = date(ano, 1, 1), date(ano + 1, 1, 1)
    registros = {}

    def obter(mes, tipo, categoria):
        return registros.setdefault((mes, tipo, categoria), {
            "mes": mes, "tipo": tipo, "Categoria": categoria,
            "Planejado": Decimal(0), "Realizado": Decimal(0),
            "Tem planejamento": False,
        })

    for tabela, tipo in (("receitas", "Receita"), ("gastos", "Gasto")):
        cursor.execute(
            f"SELECT MONTH(data), categoria, SUM(valor) FROM dbo.{tabela} "
            "WHERE id_usuario = ? AND data >= ? AND data < ? GROUP BY MONTH(data), categoria",
            id_usuario, inicio, fim,
        )
        for mes, categoria, valor in cursor.fetchall():
            obter(mes, tipo, categoria)["Realizado"] += Decimal(str(valor))
    cursor.execute(
        "SELECT MONTH(data), LOWER(tipo), categoria, SUM(valor) FROM dbo.planejamentos "
        "WHERE id_usuario = ? AND data >= ? AND data < ? GROUP BY MONTH(data), LOWER(tipo), categoria",
        id_usuario, inicio, fim,
    )
    for mes, tipo, categoria, valor in cursor.fetchall():
        if tipo not in ("receita", "gasto", "despesa"):
            continue
        registro = obter(mes, "Receita" if tipo == "receita" else "Gasto", categoria)
        registro["Planejado"] += Decimal(str(valor))
        registro["Tem planejamento"] = True
    for registro in registros.values():
        registro["Diferença"] = (
            registro["Realizado"] - registro["Planejado"]
            if registro["Tem planejamento"] else None
        )
    return pd.DataFrame(registros.values(), columns=[
        "mes", "tipo", "Categoria", "Planejado", "Realizado", "Tem planejamento", "Diferença"
    ])


def consultar_custo_fixo_mensal(cursor, id_usuario, inicio, fim, meses=3):
    """Média mensal do que já está classificado como Fixo no período da base."""
    cursor.execute(
        """
        SELECT COALESCE(SUM(CASE WHEN classificacao = N'Fixo' THEN valor ELSE 0 END), 0)
        FROM dbo.gastos
        WHERE id_usuario = ? AND data >= ? AND data < ?
        """,
        id_usuario, inicio, fim,
    )
    total = cursor.fetchone()[0]
    if meses <= 0:
        return 0.0
    return float(total) / meses


def _dinheiro(valor):
    if valor is None:
        return Decimal(0)
    return Decimal(str(valor))


def _mesmo_tipo(origem, esperado):
    nome = str(origem or "").strip().lower()
    pedido = str(esperado or "").strip().lower()
    if pedido == "receita":
        return nome == "receita"
    if pedido in ("gasto", "despesa"):
        return nome in ("gasto", "despesa")
    return nome == pedido


def _no_mes(valor, mes, ano):
    data = normalizar_data(valor)
    return data is not None and data.month == mes and data.year == ano


def _pares_efetivados(lancamentos):
    """Pares id_recorrencia e data. Lançamento sem o identificador não entra."""
    pares = set()
    for linha in lancamentos:
        identificador = linha.get("id_recorrencia")
        if identificador is None or identificador == "":
            continue
        data = normalizar_data(linha.get("data"))
        if data is None:
            continue
        pares.add((str(identificador), data))
    return pares


def _soma_realizada(linhas, mes, ano, categoria=None):
    total = Decimal(0)
    for linha in linhas:
        if not _no_mes(linha.get("data"), mes, ano):
            continue
        if categoria is not None and linha.get("categoria") != categoria:
            continue
        total += _dinheiro(linha.get("valor"))
    return total


def _soma_planos_abertos(planejamentos, mes, ano, tipo, categoria=None):
    total = Decimal(0)
    for plano in planejamentos:
        if not _mesmo_tipo(plano.get("tipo"), tipo):
            continue
        if not em_aberto(plano.get("situacao")):
            continue
        if not _no_mes(plano.get("data"), mes, ano):
            continue
        if categoria is not None and plano.get("categoria") != categoria:
            continue
        total += _dinheiro(plano.get("valor"))
    return total


def _soma_recorrencias_pendentes(recorrencias, lancamentos, mes, ano, tipo, categoria=None):
    efetivadas = _pares_efetivados(lancamentos)
    total = Decimal(0)
    for recorrencia in recorrencias:
        if not _mesmo_tipo(recorrencia.get("tipo"), tipo):
            continue
        if categoria is not None and recorrencia.get("categoria") != categoria:
            continue
        identificador = recorrencia.get("id_recorrencia")
        for data_ocorrencia in ocorrencias_no_mes(recorrencia, mes, ano):
            if (
                identificador is not None
                and identificador != ""
                and (str(identificador), data_ocorrencia) in efetivadas
            ):
                continue
            total += _dinheiro(recorrencia.get("valor"))
    return total


def compor_projecao_mensal(receitas, gastos, planejamentos, recorrencias, mes, ano):
    """Realizado, pendente e projetado do mês, sem somar de novo o que já foi lançado."""
    receitas_realizadas = _soma_realizada(receitas, mes, ano)
    gastos_realizados = _soma_realizada(gastos, mes, ano)
    receitas_planos = _soma_planos_abertos(planejamentos, mes, ano, "Receita")
    gastos_planos = _soma_planos_abertos(planejamentos, mes, ano, "Gasto")
    receitas_recorrentes = _soma_recorrencias_pendentes(
        recorrencias, receitas, mes, ano, "Receita"
    )
    gastos_recorrentes = _soma_recorrencias_pendentes(
        recorrencias, gastos, mes, ano, "Gasto"
    )
    receitas_projetadas = receitas_realizadas + receitas_planos + receitas_recorrentes
    gastos_projetados = gastos_realizados + gastos_planos + gastos_recorrentes
    return {
        "receitas_realizadas": receitas_realizadas,
        "gastos_realizados": gastos_realizados,
        "receitas_planos_abertos": receitas_planos,
        "gastos_planos_abertos": gastos_planos,
        "receitas_recorrentes_pendentes": receitas_recorrentes,
        "gastos_recorrentes_pendentes": gastos_recorrentes,
        "receitas_projetadas": receitas_projetadas,
        "gastos_projetados": gastos_projetados,
        "saldo_projetado": receitas_projetadas - gastos_projetados,
    }


def compor_gasto_categoria(gastos, planejamentos, recorrencias, categoria, mes, ano):
    """A fatia de uma categoria usa a mesma regra do indicador geral."""
    realizado = _soma_realizada(gastos, mes, ano, categoria)
    recorrentes = _soma_recorrencias_pendentes(
        recorrencias, gastos, mes, ano, "Gasto", categoria
    )
    manuais = _soma_planos_abertos(planejamentos, mes, ano, "Gasto", categoria)
    return {
        "realizado": realizado,
        "recorrentes_previstos": recorrentes,
        "planejado_manual": manuais,
        "projetado": realizado + recorrentes + manuais,
    }


def simular_reserva(saldo_atual, custo_fixo_mensal, meses_desejados, receita_mensal):
    """Meses de custo fixo cobertos pelo saldo e faturamento mensal para cobrir o fixo."""
    saldo = Decimal(str(saldo_atual or 0))
    fixo = Decimal(str(custo_fixo_mensal or 0))
    meses = Decimal(str(meses_desejados or 0))
    receita = Decimal(str(receita_mensal or 0))
    if fixo <= 0:
        return {
            "custo_fixo_mensal": fixo,
            "meses_cobertos": None,
            "reserva_desejada": None,
            "falta": None,
            "faturamento_para_cobrir": None,
            "falta_mensal": None,
        }
    reserva = fixo * meses
    falta = reserva - saldo
    if falta < 0:
        falta = Decimal(0)
    falta_mensal = fixo - receita
    if falta_mensal < 0:
        falta_mensal = Decimal(0)
    return {
        "custo_fixo_mensal": fixo,
        "meses_cobertos": saldo / fixo if saldo > 0 else Decimal(0),
        "reserva_desejada": reserva,
        "falta": falta,
        "faturamento_para_cobrir": fixo,
        "falta_mensal": falta_mensal,
    }


def exibir_reserva_simulador(saldo_atual, custo_fixo_mensal, receita_simulada, tipo_pessoa="Pessoa Jurídica"):
    import streamlit as st
    from .relatorios import formatar_moeda

    pessoa_fisica = tipo_pessoa == "Pessoa Física"
    fixo = "gasto fixo" if pessoa_fisica else "custo fixo"
    titulo = "Reserva de emergência" if pessoa_fisica else "Reserva de caixa"
    exemplos = (
        "moradia, contas e os demais gastos fixos"
        if pessoa_fisica else "folha, aluguel e os demais custos fixos"
    )
    cobertura = "a renda" if pessoa_fisica else "o faturamento"
    pergunta = (
        "Quantos meses de gasto fixo você quer manter em reserva?"
        if pessoa_fisica else "Quantos meses de custo fixo você quer manter em caixa?"
    )
    st.subheader(titulo)
    st.caption(
        f"O {fixo} mensal é a média do que foi classificado como Fixo nos três meses da base. "
        "O saldo é o de todas as movimentações registradas."
    )
    if Decimal(str(custo_fixo_mensal or 0)) <= 0:
        st.info(
            f"Não há {fixo} classificado nessa base. "
            f"Classifique {exemplos} para calcular a reserva."
        )
        return
    meses = st.number_input(
        pergunta,
        min_value=1,
        max_value=24,
        value=3,
        step=1,
        key="meses_reserva_caixa",
    )
    reserva = simular_reserva(saldo_atual, custo_fixo_mensal, meses, receita_simulada)
    custo, cobertos, desejada, falta = st.columns(4)
    custo.metric(
        "Gasto fixo mensal" if pessoa_fisica else "Custo fixo mensal",
        formatar_moeda(reserva["custo_fixo_mensal"]).strip(),
    )
    cobertos.metric("Meses cobertos pelo saldo", f"{reserva['meses_cobertos']:.1f}")
    desejada.metric("Reserva desejada", formatar_moeda(reserva["reserva_desejada"]).strip())
    falta.metric("Falta para a reserva", formatar_moeda(reserva["falta"]).strip())
    st.write(
        f"Para cobrir o {fixo}, {cobertura} do mês precisa chegar a "
        f"{formatar_moeda(reserva['faturamento_para_cobrir']).strip()}."
    )
    if reserva["falta_mensal"] == 0:
        st.success(f"No cenário simulado, a receita mensal cobre o {fixo}.")
    else:
        st.warning(
            "No cenário simulado, ainda faltam "
            f"{formatar_moeda(reserva['falta_mensal']).strip()} por mês para cobrir o {fixo}."
        )


def exibir_planejamento_anual(dados, ano, termo_gasto, detalhes=None):
    import streamlit as st

    @st.fragment
    def painel(dados, ano, termo_gasto, detalhes):
        _exibir_painel_anual(dados, ano, termo_gasto, detalhes)

    painel(dados, ano, termo_gasto, detalhes)


def _exibir_painel_anual(dados, ano, termo_gasto, detalhes=None):
    import streamlit as st
    import plotly.express as px
    from .relatorios import formatar_moeda

    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    st.subheader(f"Planejamento Anual — {ano}")
    st.caption("Realizado, planejamento manual e recorrências futuras são apresentados separadamente. "
               "Os valores não são somados, pois um planejamento pode já ter sido realizado ou incluir uma recorrência.")
    visao = st.radio("Valores para visualizar", ["Realizado", "Planejamento manual", "Recorrências futuras"],
                    horizontal=True, key="visao_planejamento_anual")
    sufixo = {"Realizado": "realizadas", "Planejamento manual": "planejadas",
              "Recorrências futuras": "recorrentes"}[visao]
    sufixo_gastos = {"realizadas": "realizados", "planejadas": "planejados"}.get(sufixo, sufixo)
    tabela = dados[[f"receitas_{sufixo}", f"gastos_{sufixo_gastos}", f"saldo_{sufixo}"]].copy()
    tabela.columns = ["Receitas", f"{termo_gasto}s", "Saldo"]
    tabela.index = pd.Index(meses, name="Mês")
    totais = tabela.sum()
    for coluna, area in zip(tabela.columns, st.columns(3)):
        area.metric(f"{coluna} — {visao.lower()}", formatar_moeda(totais[coluna]))
    exibicao = tabela.copy()
    exibicao.loc["Total do ano"] = totais
    st.dataframe(exibicao.style.format(formatar_moeda), use_container_width=True)
    grafico = tabela.astype(float).reset_index()
    st.plotly_chart(px.line(grafico, x="Mês", y=list(tabela.columns), markers=True,
         title=f"{visao} por mês", labels={"value": "Valor (R$)","variable": "Movimentação"}), use_container_width=True)
    com_valores = tabela[(tabela["Receitas"] != 0) | (tabela[f"{termo_gasto}s"] != 0)]
    if com_valores.empty:
        st.info("Não há valores registrados nesta visão para o ano selecionado.")
    else:
        st.caption(f"{len(com_valores)} de 12 meses têm valores nesta visão. Meses sem valores não indicam estabilidade financeira.")
        negativos = com_valores.index[com_valores["Saldo"] < 0].tolist()
        if negativos:
            st.warning("Meses com saldo negativo nesta visão: " + ", ".join(negativos))
        st.write(f"Maior saldo entre os meses com valores: {com_valores['Saldo'].idxmax()}.")
    comparacao = dados[["receitas_planejadas", "receitas_realizadas", "gastos_planejados", "gastos_realizados"]].copy()
    sufixo = "as" if termo_gasto == "Despesa" else "os"
    comparacao.columns = ["Receitas planejadas", "Receitas realizadas", f"{termo_gasto}s planejad{sufixo}", f"{termo_gasto}s realizad{sufixo}"]
    comparacao.index = pd.Index(meses, name="Mês")
    with st.expander("Comparar planejamento manual e realizado"):
        st.dataframe(comparacao.style.format(formatar_moeda), use_container_width=True)
        st.caption("Comparação dos totais mensais; não confirma que um lançamento específico do planejamento foi realizado.")
        if detalhes is not None:
            st.markdown("#### Detalhamento por categoria")
            mes = st.selectbox("Mês para detalhar", range(1, 13),
                               index=date.today().month - 1,
                               format_func=lambda m: meses[m - 1], key="mes_detalhe_anual")
            tipo = st.radio("Tipo de movimentação", ["Receita", termo_gasto],
                            horizontal=True, key="tipo_detalhe_anual")
            tipo_interno = "Receita" if tipo == "Receita" else "Gasto"
            selecionados = detalhes[(detalhes["mes"] == mes) & (detalhes["tipo"] == tipo_interno)].copy()
            if selecionados.empty:
                st.info("Nenhum planejamento ou lançamento para esse mês e tipo.")
            else:
                exibicao = selecionados[["Categoria", "Planejado", "Realizado", "Diferença"]].copy()
                exibicao["Planejado"] = [formatar_moeda(v) if tem else "Sem planejamento"
                                          for v, tem in zip(selecionados["Planejado"], selecionados["Tem planejamento"])]
                exibicao["Realizado"] = selecionados["Realizado"].map(formatar_moeda)
                exibicao["Diferença"] = selecionados["Diferença"].map(
                    lambda v: "—" if pd.isna(v) else formatar_moeda(v))
                st.dataframe(exibicao, hide_index=True, use_container_width=True)
                st.caption("Diferença = realizado − planejado. Nas despesas, valor negativo indica gasto abaixo do planejado; "
                           "nas receitas, indica recebimento abaixo do planejado. Categorias sem planejamento não têm diferença calculada.")
                if not selecionados["Tem planejamento"].all():
                    st.info("Há categorias realizadas sem planejamento neste mês; a comparação dos totais cobre um planejamento parcial.")
