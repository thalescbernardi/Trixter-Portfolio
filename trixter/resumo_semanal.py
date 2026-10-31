"""Leitura curta da semana. Não gera PDF e não substitui o relatório mensal."""
from datetime import timedelta
from decimal import Decimal

from .clientes import atrasos_por_cliente
from .compromissos import listar_compromissos
from .relatorios import formatar_moeda


def _dinheiro(valor):
    if valor is None:
        return Decimal(0)
    return Decimal(str(valor))


def segunda_da_semana(hoje):
    return hoje - timedelta(days=hoje.weekday())


def semana_devida(usuario, hoje):
    """A semana corrente fica devida da segunda ao domingo. Semanas anteriores não são recuperadas."""
    if not usuario.get("receber_resumo_semanal") or usuario.get("conta_demo"):
        return None
    return segunda_da_semana(hoje)


def consultar_resumo_semanal(cursor, id_usuario, hoje):
    totais = []
    for tabela in ("receitas", "gastos"):
        cursor.execute(
            f"SELECT COALESCE(SUM(valor), 0) FROM dbo.{tabela} WHERE id_usuario = ?",
            id_usuario,
        )
        totais.append(_dinheiro(cursor.fetchone()[0]))
    compromissos = listar_compromissos(cursor, id_usuario, hoje)
    limite = hoje + timedelta(days=7)
    vencimentos = [
        item for item in compromissos["itens"]
        if item["situacao"] == "Previsto" and item["data"] and hoje <= item["data"] <= limite
    ]
    cursor.execute(
        """
        SELECT
            o.categoria,
            o.valor_limite,
            COALESCE(SUM(g.valor), 0)
        FROM dbo.orcamentos o
        LEFT JOIN dbo.gastos g
            ON g.categoria = o.categoria
            AND g.id_usuario = o.id_usuario
            AND MONTH(g.data) = o.mes
            AND YEAR(g.data) = o.ano
        WHERE o.id_usuario = ?
            AND o.mes = ?
            AND o.ano = ?
        GROUP BY o.categoria, o.valor_limite
        """,
        id_usuario, hoje.month, hoje.year,
    )
    estouradas = []
    for categoria, limite_valor, gasto in cursor.fetchall():
        limite_valor = _dinheiro(limite_valor)
        if limite_valor <= 0:
            continue
        gasto = _dinheiro(gasto)
        percentual = gasto / limite_valor
        if percentual >= 1:
            estouradas.append({
                "categoria": categoria,
                "limite": limite_valor,
                "gasto": gasto,
                "percentual": percentual,
            })
    estouradas.sort(key=lambda item: (-item["percentual"], item["categoria"]))
    return {
        "semana": segunda_da_semana(hoje),
        "ate": limite,
        "saldo": totais[0] - totais[1],
        "vencimentos": vencimentos,
        "estouradas": estouradas,
        "atrasos": atrasos_por_cliente(compromissos["itens"]),
    }


def _linha_vencimento(item):
    conta = "A receber" if item["direcao"] == "receber" else "A pagar"
    return (
        f"- {item['data']:%d/%m/%Y} · {conta} · {item['categoria']} · "
        f"{formatar_moeda(item['valor']).strip()}"
    )


def _texto_estouro(estouradas):
    if not estouradas:
        return "Nenhuma categoria estourou o orçamento neste mês."
    pior = estouradas[0]
    texto = (
        f"Categoria estourada: {pior['categoria']} já usou {pior['percentual']:.0%} do limite "
        f"({formatar_moeda(pior['gasto']).strip()} de {formatar_moeda(pior['limite']).strip()})."
    )
    extra = len(estouradas) - 1
    if extra == 1:
        texto += " Mais uma categoria também passou do limite."
    elif extra > 1:
        texto += f" Mais {extra} categorias também passaram do limite."
    return texto


def _texto_atraso(atrasos):
    if not atrasos:
        return "Nenhum cliente em atraso."
    maior = atrasos[0]
    texto = f"Recebimento em atraso: {formatar_moeda(maior['valor']).strip()}."
    extra = len(atrasos) - 1
    if extra == 1:
        texto += " Mais um cliente também está em atraso."
    elif extra > 1:
        texto += f" Mais {extra} clientes também estão em atraso."
    return texto


def texto_resumo(dados):
    linhas = [
        "Olá!",
        "",
        f"Resumo da semana que começa em {dados['semana']:%d/%m/%Y}.",
        "",
        f"Saldo: {formatar_moeda(dados['saldo']).strip()}",
        "",
        f"Vence até {dados['ate']:%d/%m/%Y}:",
    ]
    if dados["vencimentos"]:
        linhas.extend(_linha_vencimento(item) for item in dados["vencimentos"])
    else:
        linhas.append("Nada vence nos próximos 7 dias.")
    linhas.extend(["", _texto_estouro(dados["estouradas"]), "", _texto_atraso(dados["atrasos"]),
                   "", "Atenciosamente,", "Trixter"])
    return "\n".join(linhas)
