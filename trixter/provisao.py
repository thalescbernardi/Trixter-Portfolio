"""Reserva estimada: percentual informado pelo usuário sobre a receita do mês. Não apura tributo nem gera guia."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .relatorios import formatar_moeda

CENTAVO = Decimal("0.01")
JANELA_DIAS = 7
AVISO_RESERVA = (
    "Esta reserva é apenas uma estimativa para planejamento financeiro. "
    "O Trixter não calcula impostos nem determina alíquotas tributárias. "
    "Consulte seu contador para definir o percentual adequado à sua empresa."
)
MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _dinheiro(valor):
    if valor is None or valor == "":
        return Decimal(0)
    return Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def aliquota_de(valor):
    """Percentual de 0 a 100, com duas casas. None quando o valor não é um percentual."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, str):
        valor = valor.strip().replace("%", "").replace(",", ".")
        if not valor:
            return None
    try:
        numero = Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    except Exception:
        return None
    if numero < 0 or numero > 100:
        return None
    return numero


def aliquota_para_gravar(valor):
    """Zero volta como ausência de configuração. O banco rejeita percentual igual a zero."""
    numero = aliquota_de(valor)
    if numero is None or numero == 0:
        return None
    return numero


def dia_de(valor):
    if valor is None or valor == "":
        return None
    try:
        dia = int(valor)
    except (TypeError, ValueError):
        return None
    if dia < 1 or dia > 28:
        return None
    return dia


def formatar_aliquota(valor):
    numero = aliquota_de(valor)
    if numero is None:
        return ""
    texto = f"{numero:.2f}".replace(".", ",").rstrip("0").rstrip(",")
    return f"{texto}%"


def calcular_provisao(receita, aliquota):
    percentual = aliquota_de(aliquota)
    if percentual is None:
        return None
    return (_dinheiro(receita) * percentual / Decimal(100)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def mes_seguinte(primeiro_dia):
    return date(
        primeiro_dia.year + (primeiro_dia.month == 12),
        1 if primeiro_dia.month == 12 else primeiro_dia.month + 1,
        1,
    )


def mes_anterior(primeiro_dia):
    return date(
        primeiro_dia.year - (primeiro_dia.month == 1),
        12 if primeiro_dia.month == 1 else primeiro_dia.month - 1,
        1,
    )


def periodo_que_vence(hoje, dia):
    """O dia escolhido deste mês fecha o mês anterior. Depois dele, o próximo dia fecha o mês atual."""
    dia = dia_de(dia)
    if dia is None:
        return None
    if hoje.day <= dia:
        vencimento = date(hoje.year, hoje.month, dia)
        inicio = mes_anterior(hoje.replace(day=1))
    else:
        vencimento = mes_seguinte(hoje.replace(day=1)).replace(day=dia)
        inicio = hoje.replace(day=1)
    return {
        "vencimento": vencimento,
        "inicio": inicio,
        "fim": mes_seguinte(inicio),
        "dias": (vencimento - hoje).days,
    }


def _quando(dias):
    if dias == 0:
        return "hoje"
    if dias == 1:
        return "amanhã"
    return f"em {dias} dias"


def mensagem_provisao(periodo, aliquota, provisao):
    mes = MESES[periodo["inicio"].month - 1]
    return (
        f"A provisão de imposto de {mes} vence {_quando(periodo['dias'])} "
        f"({periodo['vencimento'].strftime('%d/%m/%Y')}). "
        f"O valor estimado é {formatar_moeda(provisao).strip()}, "
        f"{formatar_aliquota(aliquota)} da receita daquele mês. "
        "Isso não é o DAS e não gera guia."
    )


def consultar_provisao_mes(cursor, id_usuario, hoje, aliquota):
    percentual = aliquota_de(aliquota)
    if percentual is None:
        percentual = Decimal("0.00")
    inicio = hoje.replace(day=1)
    cursor.execute(
        """
        SELECT COALESCE(SUM(valor), 0)
        FROM dbo.receitas
        WHERE id_usuario = ? AND data >= ? AND data < ?
        """,
        id_usuario, inicio, mes_seguinte(inicio),
    )
    receita = _dinheiro(cursor.fetchone()[0])
    return {
        "receita": receita,
        "aliquota": percentual,
        "provisao": calcular_provisao(receita, percentual),
        "inicio": inicio,
    }


def gerar_alertas_provisao(cursor, id_usuario, hoje):
    cursor.execute(
        """
        SELECT aliquota_imposto, dia_vencimento_imposto
        FROM dbo.usuarios
        WHERE id_usuario = ?
        """,
        id_usuario,
    )
    linha = cursor.fetchone()
    if not linha:
        return []
    aliquota, dia = linha
    periodo = periodo_que_vence(hoje, dia)
    if periodo is None or not aliquota_de(aliquota) or periodo["dias"] > JANELA_DIAS:
        return []
    cursor.execute(
        """
        SELECT COALESCE(SUM(valor), 0)
        FROM dbo.receitas
        WHERE id_usuario = ? AND data >= ? AND data < ?
        """,
        id_usuario, periodo["inicio"], periodo["fim"],
    )
    provisao = calcular_provisao(cursor.fetchone()[0], aliquota)
    if not provisao:
        return []
    return [{
        "tipo": "provisao",
        "nivel": "atencao",
        "categoria": "Imposto",
        "mensagem": mensagem_provisao(periodo, aliquota, provisao),
    }]


def exibir_provisao(resumo):
    import streamlit as st

    reserva = resumo["provisao"] if resumo["provisao"] is not None else Decimal("0.00")
    st.subheader("Reserva estimada para tributos")
    st.info(AVISO_RESERVA)
    st.metric("Reserva estimada do mês", formatar_moeda(reserva).strip())
    if resumo["receita"] == 0:
        st.info("Não há receitas registradas neste mês. A reserva estimada fica em R$ 0,00.")
        return
    st.write(
        f"{formatar_moeda(reserva).strip()} é {formatar_aliquota(resumo['aliquota']) or '0%'} "
        f"das receitas registradas neste mês ({formatar_moeda(resumo['receita']).strip()})."
    )


def formulario_provisao(aliquota_atual, dia_atual):
    """Devolve a escolha quando o botão é pressionado. Não grava no banco."""
    import streamlit as st

    atual = aliquota_de(aliquota_atual)
    aliquota = aliquota_de(st.number_input(
        "Percentual a reservar (%)",
        min_value=0.0,
        max_value=100.0,
        value=float(atual) if atual is not None else 0.0,
        step=0.01,
        format="%.2f",
        key="provisao_percentual_numero",
    ))
    avisar = st.checkbox(
        "Avisar nos 7 dias anteriores ao pagamento",
        value=dia_de(dia_atual) is not None,
        key="provisao_avisar",
    )
    dia = None
    if avisar:
        dia = dia_de(st.number_input(
            "Dia do pagamento",
            min_value=1,
            max_value=28,
            value=int(dia_de(dia_atual) or 20),
            step=1,
            key="provisao_dia",
        ))
    if st.button("Salvar percentual", key="btn_salvar_provisao"):
        if aliquota is None:
            st.error("Informe um percentual entre 0 e 100.")
            return None
        return {"aliquota": aliquota_para_gravar(aliquota), "dia": dia}
    return None
