"""Contagem de recorrências dentro de um mês."""
import calendar
from datetime import date, datetime

from dateutil.relativedelta import relativedelta


def ajustar_dia_mes(ano, mes, dia):
    """O dia pedido, limitado ao último dia daquele mês."""
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return min(dia, ultimo_dia)


def calcular_recorrencias_periodo(recorrencia, mes, ano, hoje=None):
    """Quantas vezes a recorrência cai no mês.

    No mês atual a contagem começa amanhã. Nos outros meses, no dia 1.
    """
    inicio_periodo = date(ano, mes, 1)
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    fim_periodo = date(ano, mes, ultimo_dia)
    data_execucao = recorrencia["proxima_execucao"]
    quantidade_ocorrencias = 0
    if hoje is None:
        hoje = datetime.today().date()

    if mes == hoje.month and ano == hoje.year:
        inicio_contagem = hoje + relativedelta(days=1)
    else:
        inicio_contagem = inicio_periodo

    while data_execucao <= fim_periodo:
        if data_execucao >= inicio_contagem:
            quantidade_ocorrencias += 1

        if recorrencia["frequencia"] == "Diária":
            data_execucao += relativedelta(days=1)
        elif recorrencia["frequencia"] == "Semanal":
            data_execucao += relativedelta(weeks=1)
        elif recorrencia["frequencia"] == "Mensal":
            proximo_mes = data_execucao + relativedelta(months=1)
            dia_valido = ajustar_dia_mes(
                proximo_mes.year,
                proximo_mes.month,
                recorrencia["dia"],
            )
            data_execucao = proximo_mes.replace(day=dia_valido)
        elif recorrencia["frequencia"] == "Anual":
            proximo_ano = data_execucao + relativedelta(years=1)
            dia_valido = ajustar_dia_mes(
                proximo_ano.year,
                recorrencia["mes"],
                recorrencia["dia"],
            )
            data_execucao = proximo_ano.replace(
                month=recorrencia["mes"],
                day=dia_valido,
            )

    return quantidade_ocorrencias


def normalizar_data(valor):
    """Converte data vinda do banco ou da tela, sem inventar um dia."""
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


def _recorrencia_ativa(recorrencia):
    if "ativa" not in recorrencia:
        return True
    valor = recorrencia["ativa"]
    if isinstance(valor, str):
        return valor.strip().lower() not in ("0", "false", "nao", "não", "inativa")
    return bool(valor)


def _avancar_proxima(data_execucao, recorrencia):
    """Próxima data da série. None interrompe o avanço quando falta dia ou mês."""
    frequencia = recorrencia.get("frequencia")
    if frequencia == "Diária":
        return data_execucao + relativedelta(days=1)
    if frequencia == "Semanal":
        return data_execucao + relativedelta(weeks=1)
    if frequencia == "Mensal":
        if recorrencia.get("dia") is None:
            return None
        proximo_mes = data_execucao + relativedelta(months=1)
        dia_valido = ajustar_dia_mes(
            proximo_mes.year,
            proximo_mes.month,
            recorrencia["dia"],
        )
        return proximo_mes.replace(day=dia_valido)
    if frequencia == "Anual":
        if recorrencia.get("mes") is None or recorrencia.get("dia") is None:
            return None
        proximo_ano = data_execucao + relativedelta(years=1)
        dia_valido = ajustar_dia_mes(
            proximo_ano.year,
            recorrencia["mes"],
            recorrencia["dia"],
        )
        return proximo_ano.replace(month=recorrencia["mes"], day=dia_valido)
    return None


def ocorrencias_no_mes(recorrencia, mes, ano):
    """Datas da recorrência dentro do mês, a partir de proxima_execucao.

    Não reconstrói dias anteriores a proxima_execucao. Uma ocorrência vencida
    entra só quando essa data ainda é a próxima execução guardada.
    """
    if not _recorrencia_ativa(recorrencia):
        return []
    inicio = date(ano, mes, 1)
    fim = date(ano, mes, calendar.monthrange(ano, mes)[1])
    atual = normalizar_data(recorrencia.get("proxima_execucao"))
    if atual is None:
        return []
    datas = []
    passos = 0
    while atual <= fim and passos < 20000:
        if atual >= inicio:
            datas.append(atual)
        seguinte = _avancar_proxima(atual, recorrencia)
        if seguinte is None or seguinte <= atual:
            break
        atual = seguinte
        passos += 1
    return datas
