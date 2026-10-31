"""Regras compartilhadas de alertas, sem dependência do Streamlit."""
from .classificacao import frase_natureza
from .provisao import gerar_alertas_provisao
from .relatorios import formatar_moeda


def gerar_alertas_orcamento(cursor, id_usuario, hoje):

    cursor.execute(
        """
        SELECT
            o.categoria,
            o.valor_limite,
            COALESCE(SUM(g.valor), 0) AS total_gasto,
            COALESCE(SUM(CASE WHEN g.classificacao = N'Fixo' THEN g.valor ELSE 0 END), 0) AS total_fixo,
            COALESCE(SUM(CASE WHEN g.classificacao = N'Variável' THEN g.valor ELSE 0 END), 0) AS total_variavel
        FROM dbo.orcamentos o

        LEFT JOIN dbo.gastos g
            ON g.categoria = o.categoria
            AND g.id_usuario = o.id_usuario
            AND MONTH(g.data) = o.mes
            AND YEAR(g.data) = o.ano

        WHERE o.id_usuario = ?
            AND o.mes = ?
            AND o.ano = ?

        GROUP BY
            o.categoria,
            o.valor_limite
        """,
        id_usuario, hoje.month, hoje.year
    )

    orcamentos_ativos = cursor.fetchall()

    alertas = []

    for orcamento in orcamentos_ativos:
        categoria = orcamento[0]
        valor_limite = float(orcamento[1])
        total_gasto = float(orcamento[2])

        if valor_limite <= 0:
            continue

        percentual_consumido = (
            total_gasto / valor_limite
        ) * 100

        natureza = ""
        if len(orcamento) > 4:
            natureza = frase_natureza(total_gasto, orcamento[3], orcamento[4])
            if natureza:
                natureza = f" {natureza}"

        if percentual_consumido >= 100:
            alertas.append({
                "tipo": "orcamento",
                "nivel": "critico",
                "categoria": categoria,
                "mensagem": (
                    f"O orçamento da categoria {categoria} foi excedido. "
                    f"Você já utilizou {percentual_consumido:.1f}% do limite.{natureza}"
                )
            })

        elif percentual_consumido >= 80:
            alertas.append({
                "tipo": "orcamento",
                "nivel": "atencao",
                "categoria": categoria,
                "mensagem": (
                    f"O orçamento da categoria {categoria} está próximo do limite. "
                    f"Você já utilizou {percentual_consumido:.1f}%.{natureza}"
                )
            })


    return alertas


def gerar_alertas_recorrencias(cursor, id_usuario, hoje):

    cursor.execute(
        """
        SELECT
            categoria,
            tipo,
            descricao,
            valor,
            proxima_execucao
        FROM dbo.recorrencias
        WHERE id_usuario = ?
          AND ativa = 1
        """,
        id_usuario
    )

    recorrencias_ativas = cursor.fetchall()

    data_atual = hoje

    alertas = []

    for recorrencia in recorrencias_ativas:
        categoria = recorrencia[0]
        tipo = recorrencia[1]
        descricao = recorrencia[2]
        valor = float(recorrencia[3])
        proxima_execucao = recorrencia[4]

        dias_restantes = (proxima_execucao - data_atual).days

        if 0 <= dias_restantes <= 3:
            alertas.append({
                "tipo": "recorrencia",
                "nivel": "atencao",
                "categoria": categoria,
                "movimento": tipo,
                "valor": valor,
                "dias": dias_restantes,
                "mensagem": (
                    f"{descricao} ({categoria}), no valor de "
                    f"{formatar_moeda(valor)}, possui próxima execução "
                    f"em {dias_restantes} dia(s)."
                )
            })


    return alertas




def gerar_alertas_meta(cursor, id_usuario, hoje):

    cursor.execute(
        """
        SELECT
            objetivo_financeiro,
            valor_objetivo,
            data_objetivo,
            valor_acumulado_meta
        FROM dbo.usuarios
        WHERE id_usuario = ?
        """,
        id_usuario
    )

    dados_meta = cursor.fetchone()

    alertas = []

    if dados_meta:
        objetivo_financeiro = dados_meta[0]
        valor_objetivo = dados_meta[1]
        data_objetivo = dados_meta[2]
        valor_acumulado_meta = dados_meta[3]

        if objetivo_financeiro and valor_objetivo and data_objetivo:
            valor_objetivo = float(valor_objetivo)
            valor_acumulado_meta = float(valor_acumulado_meta or 0)

            dias_para_meta = (data_objetivo - hoje).days

            if (
                valor_acumulado_meta < valor_objetivo
                and 0 <= dias_para_meta <= 30
            ):
                valor_faltante = (
                    valor_objetivo - valor_acumulado_meta
                )

                alertas.append({
                    "tipo": "meta",
                    "nivel": "atencao",
                    "categoria": "meta_financeira",
                    "mensagem": (
                        f"Sua meta {objetivo_financeiro} vence em "
                        f"{dias_para_meta} dia(s). Ainda faltam "
                        f"{formatar_moeda(valor_faltante)} "
                        f"para atingir o objetivo."
                    )
                })


    return alertas


def texto_para_email(alerta):
    """Frase enviada. A recorrência omite a descrição; os demais tipos usam a mensagem da tela."""
    if alerta.get("tipo") != "recorrencia":
        return alerta["mensagem"]
    return (
        f"Recorrência de {_rotulo_movimento(alerta.get('movimento'))} em {alerta['categoria']}, "
        f"no valor de {formatar_moeda(alerta['valor'])}, possui próxima execução "
        f"em {alerta['dias']} dia(s)."
    )


def _rotulo_movimento(tipo):
    texto = str(tipo or "").strip().lower()
    if texto == "receita":
        return "receita"
    if texto == "gasto":
        return "gasto"
    return "lançamento"


def coletar_alertas(cursor, id_usuario, hoje):
    return (gerar_alertas_orcamento(cursor, id_usuario, hoje)
            + gerar_alertas_recorrencias(cursor, id_usuario, hoje)
            + gerar_alertas_meta(cursor, id_usuario, hoje)
            + gerar_alertas_provisao(cursor, id_usuario, hoje))
