"""Resumo da página inicial e apresentação da área autenticada."""
from contextlib import closing
from datetime import date
from decimal import Decimal

import streamlit as st

from .estilo import publicar_area_autenticada

from .relatorios import formatar_moeda


PAGINAS = {
    "cadastrar_gasto": "btn_cadastrar_gasto", "cadastrar_receita": "btn_cadastrar_receita",
    "importar_pdf": "btn_importar_pdf", "visualizar_saldo": "btn_visualizar_saldo",
    "visualizar_historico": "btn_visualizar_historico", "visualizar_meta": "btn_acompanhar_meta",
    "visualizar_fluxo_caixa": "btn_fluxo_caixa", "visualizar_dashboard": "btn_visualizar_dashboard",
    "gerenciar_orcamento": "btn_orcamento", "gerenciar_recorrencias": "btn_recorrencias",
    "planejamento_mensal": "btn_planejamento_mensal", "planejamento_anual": "btn_planejamento_anual",
    "simulador": "btn_simulador_financeiro", "inteligencia_financeira": "btn_inteligencia_financeira",
    "relatorio_mensal": "btn_relatorio_mensal",
}


def aplicar_estilo(tela):
    publicar_area_autenticada(tela, PAGINAS)


def consultar_resumo(conexao, usuario_id, hoje):
    inicio = hoje.replace(day=1)
    fim = date(hoje.year + (hoje.month == 12), hoje.month % 12 + 1, 1)
    totais = []
    with closing(conexao.cursor()) as cursor:
        for tabela in ("receitas", "gastos"):
            # Os nomes de tabela são constantes; usuário e datas são parametrizados.
            cursor.execute(f"""
                SELECT COALESCE(SUM(valor), 0),
                       COALESCE(SUM(CASE WHEN data >= ? AND data < ? THEN valor ELSE 0 END), 0)
                FROM dbo.{tabela} WHERE id_usuario = ?
            """, inicio, fim, usuario_id)
            totais.append(tuple(Decimal(str(v)) for v in cursor.fetchone()))
    return totais[0][0] - totais[1][0], totais[0][1], totais[1][1]


def comparar_faturamento(cadastrado, realizado, nome="faturamento"):
    """O cadastrado é a referência do perfil. O realizado são as receitas do mês."""
    referencia = Decimal(str(cadastrado or 0))
    atual = Decimal(str(realizado or 0))
    diferenca = atual - referencia
    artigo = "A" if nome == "renda" else "O"
    if referencia <= 0:
        texto = f"Não há {nome} cadastrado para comparar com as receitas do mês."
        percentual = None
    elif diferenca > 0:
        texto = f"{artigo} {nome} do mês está {formatar_moeda(diferenca).strip()} acima do cadastrado."
        percentual = atual / referencia
    elif diferenca < 0:
        texto = f"{artigo} {nome} do mês está {formatar_moeda(-diferenca).strip()} abaixo do cadastrado."
        percentual = atual / referencia
    else:
        texto = f"{artigo} {nome} do mês está igual ao cadastrado."
        percentual = Decimal(1)
    return {
        "cadastrado": referencia,
        "realizado": atual,
        "diferenca": diferenca,
        "percentual": percentual,
        "texto": texto,
    }


def exibir_faturamento(cadastrado, realizado):
    comparacao = comparar_faturamento(cadastrado, realizado)
    cadastrado_col, realizado_col = st.columns(2)
    cadastrado_col.metric("Faturamento cadastrado", formatar_moeda(comparacao["cadastrado"]).strip())
    realizado_col.metric("Faturamento do mês", formatar_moeda(comparacao["realizado"]).strip())
    st.caption(comparacao["texto"])


def exibir_renda(cadastrado, realizado):
    comparacao = comparar_faturamento(cadastrado, realizado, nome="renda")
    cadastrado_col, realizado_col = st.columns(2)
    cadastrado_col.metric("Renda cadastrada", formatar_moeda(comparacao["cadastrado"]).strip())
    realizado_col.metric("Renda do mês", formatar_moeda(comparacao["realizado"]).strip())
    st.caption(comparacao["texto"])


def comparar_meta_saldo(saldo, valor_meta):
    """O saldo vem dos lançamentos. O valor da meta é o objetivo informado."""
    atual = Decimal(str(saldo or 0))
    meta = Decimal(str(valor_meta or 0))
    folga = atual - meta
    if folga > 0:
        texto = f"O saldo atual cobre a meta, com {formatar_moeda(folga).strip()} de sobra."
    elif folga == 0:
        texto = "O saldo atual cobre a meta."
    else:
        texto = f"Para a meta caber no saldo, faltam {formatar_moeda(-folga).strip()}."
    return {"saldo": atual, "meta": meta, "folga": folga, "texto": texto}


def abrir_cadastro(tela, estado, area_conteudo=None, area_voltar=None):
    """Tira a funcionalidade aberta no clique e deixa a próxima ocupar o mesmo espaço.

    Só esse miolo sai. A barra lateral permanece. Sem isso, tabela, formulário
    e gráfico da tela anterior ficavam visíveis até a nova terminar de carregar.
    """
    estado.trocando_funcionalidade = True
    if area_conteudo is not None:
        area_conteudo.empty()
    if area_voltar is not None and area_voltar is not area_conteudo:
        area_voltar.empty()
    if tela == "relatorio_mensal" or estado.get("tela_atual") == "relatorio_mensal":
        estado.relatorio_gerado = False
        estado.mes_relatorio = None
        estado.ano_relatorio = None
    estado.menu_conta_aberto = False
    estado.menu_alertas_aberto = False
    estado.tela_atual = tela


def abrir_atalho(tela):
    abrir_cadastro(tela, st.session_state)


def renderizar_resumo(conectar, usuario, termo_gasto, numeros=None):
    hoje = date.today()
    if numeros is None:
        try:
            with closing(conectar()) as conexao:
                numeros = consultar_resumo(conexao, usuario["id_usuario"], hoje)
        except Exception:
            numeros = None
    with st.container(key="resumo_inicio"):
        st.subheader("Seu resumo financeiro")
        st.caption(f"Movimentações de {hoje:%m/%Y} · Saldo acumulado de todas as movimentações registradas.")
        if numeros is None:
            st.warning("Não foi possível carregar o resumo agora. Tente atualizar a página.")
        else:
            saldo, receitas, gastos = numeros
            col_saldo, col_receitas, col_gastos = st.columns(3)
            col_saldo.metric("Saldo acumulado", formatar_moeda(saldo).strip())
            col_receitas.metric("Receitas do mês", formatar_moeda(receitas).strip())
            col_gastos.metric(f"{termo_gasto}s do mês", formatar_moeda(gastos).strip())
            if usuario.get("tipo_pessoa") == "Pessoa Jurídica":
                exibir_faturamento(usuario.get("faturamento_mensal"), receitas)
            elif usuario.get("tipo_pessoa") == "Pessoa Física":
                exibir_renda(usuario.get("renda_mensal"), receitas)
        gasto, receita = st.columns(2)
        gasto.button(f"Cadastrar {termo_gasto.lower()}", key="inicio_cadastrar_gasto", type="primary",
                     use_container_width=True, on_click=abrir_atalho, args=("cadastrar_gasto",))
        receita.button("Cadastrar receita", key="inicio_cadastrar_receita",
                       use_container_width=True, on_click=abrir_atalho, args=("cadastrar_receita",))
