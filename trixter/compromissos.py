"""Compromissos de caixa a partir do planejamento manual, sem boleto nem nota."""
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from .clientes import atrasos_por_cliente, normalizar_cliente
from .relatorios import formatar_moeda

LIQUIDADOS = ("Recebido", "Pago")


def _como_data(valor):
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


def direcao(tipo):
    nome = str(tipo or "").strip().lower()
    if nome == "receita":
        return "receber"
    if nome in ("gasto", "despesa"):
        return "pagar"
    return None


def em_aberto(situacao):
    return str(situacao or "").strip().capitalize() not in LIQUIDADOS


def situacao_efetiva(data, situacao, hoje):
    """Previsto e Atrasado são calculados. Recebido e Pago vêm gravados."""
    gravada = str(situacao or "").strip().capitalize()
    if gravada in LIQUIDADOS:
        return gravada
    vencimento = _como_data(data)
    referencia = _como_data(hoje)
    if vencimento is None or referencia is None or vencimento >= referencia:
        return "Previsto"
    return "Atrasado"


def preparar_compromissos(linhas, hoje):
    itens = []
    totais = {
        "A receber previsto": Decimal(0),
        "A receber atrasado": Decimal(0),
        "A pagar previsto": Decimal(0),
        "A pagar atrasado": Decimal(0),
    }
    for linha in linhas:
        sentido = direcao(linha.get("tipo"))
        if sentido is None:
            continue
        status = situacao_efetiva(linha.get("data"), linha.get("situacao"), hoje)
        valor = _dinheiro(linha.get("valor"))
        item = {
            "id_planejamento": linha.get("id_planejamento"),
            "tipo": linha.get("tipo"),
            "categoria": linha.get("categoria"),
            "descricao": str(linha.get("descricao") or "").strip() or "Sem descrição",
            "cliente": normalizar_cliente(linha.get("cliente")),
            "valor": valor,
            "data": _como_data(linha.get("data")),
            "situacao": status,
            "direcao": sentido,
        }
        itens.append(item)
        if status == "Previsto":
            chave = "A receber previsto" if sentido == "receber" else "A pagar previsto"
            totais[chave] += valor
        elif status == "Atrasado":
            chave = "A receber atrasado" if sentido == "receber" else "A pagar atrasado"
            totais[chave] += valor
    itens.sort(key=lambda item: (item["data"] or date.min, item["direcao"], item["descricao"]))
    return {"itens": itens, "totais": totais}


def listar_compromissos(cursor, id_usuario, hoje):
    cursor.execute(
        """
        SELECT id_planejamento, tipo, categoria, descricao, valor, data, situacao, cliente
        FROM dbo.planejamentos
        WHERE id_usuario = ?
        ORDER BY data
        """,
        id_usuario,
    )
    colunas = [coluna[0] for coluna in cursor.description]
    linhas = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    return preparar_compromissos(linhas, hoje)


def baixar_compromisso(conectar, id_usuario, item):
    """Grava o lançamento realizado e fecha o compromisso. Não gera documento fiscal."""
    sentido = item.get("direcao")
    if sentido == "receber":
        tabela, situacao = "receitas", "Recebido"
    elif sentido == "pagar":
        tabela, situacao = "gastos", "Pago"
    else:
        return False
    with closing(conectar()) as conexao:
        try:
            with closing(conexao.cursor()) as cursor:
                if tabela == "receitas":
                    cursor.execute(
                        """
                        INSERT INTO dbo.receitas (
                            id_transacao, id_usuario, data, descricao, valor, categoria, cliente
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        str(uuid4()),
                        id_usuario,
                        item.get("data"),
                        item.get("descricao"),
                        item.get("valor"),
                        item.get("categoria"),
                        normalizar_cliente(item.get("cliente")),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO dbo.gastos (
                            id_transacao, id_usuario, data, descricao, valor, categoria
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        str(uuid4()),
                        id_usuario,
                        item.get("data"),
                        item.get("descricao"),
                        item.get("valor"),
                        item.get("categoria"),
                    )
                cursor.execute(
                    """
                    UPDATE dbo.planejamentos
                    SET situacao = ?
                    WHERE id_planejamento = ?
                      AND id_usuario = ?
                      AND (situacao IS NULL OR situacao NOT IN (N'Recebido', N'Pago'))
                    """,
                    situacao,
                    item.get("id_planejamento"),
                    id_usuario,
                )
                if cursor.rowcount != 1:
                    conexao.rollback()
                    return False
            conexao.commit()
        except Exception:
            conexao.rollback()
            raise
    return True


def exibir_compromissos(resumo):
    import pandas as pd
    import streamlit as st

    st.subheader("Contas a receber e a pagar")
    st.caption(
        "Cada planejamento em aberto é um compromisso de caixa. "
        "Previsto ainda não venceu. Atrasado venceu e continua em aberto. "
        "Recebido ou pago sai do caixa previsto e entra no saldo realizado. "
        "Isso não emite boleto nem nota."
    )
    colunas = st.columns(4)
    for coluna, (rotulo, valor) in zip(colunas, resumo["totais"].items()):
        coluna.metric(rotulo, formatar_moeda(valor).strip())
    if not resumo["itens"]:
        st.info("Nenhum compromisso cadastrado.")
        return
    tabela = pd.DataFrame(resumo["itens"])
    if "cliente" not in tabela:
        tabela["cliente"] = None
    tabela["Cliente"] = tabela["cliente"].map(lambda valor: valor or "Sem cliente")
    tabela["Data"] = tabela["data"].map(lambda valor: valor.strftime("%d/%m/%Y") if valor else "")
    tabela["Valor"] = tabela["valor"].map(lambda valor: formatar_moeda(valor).strip())
    tabela["Conta"] = tabela["direcao"].map({"receber": "A receber", "pagar": "A pagar"})
    st.dataframe(
        tabela.rename(columns={
            "descricao": "Descrição",
            "categoria": "Categoria",
            "situacao": "Situação",
        })[["Data", "Conta", "Cliente", "Categoria", "Descrição", "Valor", "Situação"]],
        use_container_width=True,
        hide_index=True,
    )
    atrasos = atrasos_por_cliente(resumo["itens"])
    if atrasos:
        st.write("Atraso por cliente")
        for atraso in atrasos:
            st.caption(f"{atraso['cliente']}: {formatar_moeda(atraso['valor']).strip()}")
