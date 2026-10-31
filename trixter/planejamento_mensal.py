"""Tela de planejamento do mês, com compromissos e recorrências previstas."""
import html
import uuid
from contextlib import closing
from datetime import date

import streamlit as st

from .categorias import listar_categorias
from .clientes import normalizar_cliente
from .compromissos import (
    baixar_compromisso,
    em_aberto,
    exibir_compromissos,
    listar_compromissos,
)
from .planejamento import (
    compor_gasto_categoria,
    compor_projecao_mensal,
    concluir_atualizacao_texto_planejamento,
    concluir_exclusao_planejamento,
)
from .relatorios import formatar_moeda


def composicao_exibida(projecao, direcao):
    """Realizado e previsto pendente já calculados, apenas para a legenda."""
    realizado = projecao[f"{direcao}_realizadas" if direcao == "receitas" else f"{direcao}_realizados"]
    pendente = (
        projecao[f"{direcao}_planos_abertos"]
        + projecao[f"{direcao}_recorrentes_pendentes"]
    )
    projetado = projecao[f"{direcao}_projetadas" if direcao == "receitas" else f"{direcao}_projetados"]
    return realizado, pendente, projetado


def criar_grafico_projecao_mensal(dados):
    """Limite, realizado e projetado lado a lado, sem somar as barras."""
    import plotly.graph_objects as go

    categorias = [item["categoria"] for item in dados]
    uma_categoria = len(categorias) == 1
    espessura = 0.12 if uma_categoria else None
    deslocamentos = (-0.21, -0.06, 0.09) if uma_categoria else (None, None, None)
    figura = go.Figure()
    for indice, (chave, nome, cor) in enumerate((
        ("limite", "Limite", "#172033"),
        ("realizado", "Realizado", "#288577"),
        ("projetado", "Projetado", "#B87928"),
    )):
        valores = [float(item[chave]) for item in dados]
        barra = dict(
            x=categorias,
            y=valores,
            name=nome,
            marker_color=cor,
            marker_line_width=0,
            customdata=[formatar_moeda(valor).strip() for valor in valores],
            hovertemplate="%{x}<br>%{customdata}<extra>%{fullData.name}</extra>",
        )
        if uma_categoria:
            barra["width"] = espessura
            barra["offset"] = deslocamentos[indice]
        figura.add_bar(**barra)
    figura.update_layout(
        barmode="group",
        height=250,
        bargap=0.32,
        bargroupgap=0.06,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#172033", size=13),
        separators=",.",
        margin=dict(l=8, r=8, t=8, b=4),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
            font=dict(size=12),
        ),
        xaxis=dict(
            type="category",
            title=None,
            tickangle=0 if len(categorias) <= 4 else -30,
            automargin=True,
            tickfont=dict(size=12),
        ),
        yaxis=dict(
            title=dict(text="Valor (R$)", font=dict(size=12)),
            tickprefix="R$ ",
            tickformat=",.0f",
            gridcolor="#E3E7ED",
            zerolinecolor="#A0A7B0",
            rangemode="tozero",
            tickfont=dict(size=12),
        ),
    )
    if uma_categoria:
        figura.update_layout(width=460, height=230, autosize=False)
    return figura


def montar_cartoes_projecao(
    projecao,
    termo_gasto,
    receitas_realizadas,
    receitas_pendentes,
    gastos_realizados,
    gastos_pendentes,
):
    """Cartões com o detalhamento dentro do próprio bloco, sem recalcular valores."""
    def cartao(titulo, valor, detalhes=()):
        miolo = ""
        if detalhes:
            linhas = "".join(
                "<div class='trixter-cartao-linha'>"
                f"<span>{html.escape(rotulo)}</span>"
                f"<strong>{html.escape(formatar_moeda(quantia).strip())}</strong>"
                "</div>"
                for rotulo, quantia in detalhes
            )
            miolo = f"<div class='trixter-cartao-detalhe'>{linhas}</div>"
        return (
            "<article class='trixter-cartao'>"
            f"<p class='trixter-cartao-rotulo'>{html.escape(titulo)}</p>"
            f"<p class='trixter-cartao-valor'>{html.escape(formatar_moeda(valor).strip())}</p>"
            f"{miolo}</article>"
        )

    receitas = cartao(
        "Receitas projetadas",
        projecao["receitas_projetadas"],
        (("Realizado", receitas_realizadas), ("Previsto pendente", receitas_pendentes)),
    )
    gastos = cartao(
        termo_gasto,
        projecao["gastos_projetados"],
        (("Realizado", gastos_realizados), ("Previsto pendente", gastos_pendentes)),
    )
    saldo = cartao("Saldo projetado", projecao["saldo_projetado"])
    return f"""
<style>
.trixter-indicadores {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    align-items: stretch;
    margin: 4px 0 8px;
    font-family: inherit;
}}
.trixter-cartao {{
    background: #F7F4EE;
    border: 1px solid rgba(198, 161, 91, 0.30);
    border-radius: 12px;
    padding: 12px 14px 14px;
    min-width: 0;
    box-sizing: border-box;
}}
.trixter-cartao-rotulo {{
    margin: 0 0 6px;
    color: #526077;
    font-size: 0.9rem;
    line-height: 1.3;
}}
.trixter-cartao-valor {{
    margin: 0;
    color: #172033;
    font-size: clamp(1.15rem, 2vw, 1.55rem);
    font-weight: 600;
    line-height: 1.25;
    overflow-wrap: anywhere;
}}
.trixter-cartao-detalhe {{
    margin-top: 12px;
    padding-top: 8px;
    border-top: 1px solid rgba(198, 161, 91, 0.28);
}}
.trixter-cartao-linha {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 6px;
    color: #526077;
    font-size: 0.82rem;
    line-height: 1.4;
}}
.trixter-cartao-linha strong {{
    margin-left: auto;
    color: #172033;
    font-weight: 600;
    text-align: right;
}}
@media (max-width: 760px) {{
    .trixter-indicadores {{ grid-template-columns: 1fr; }}
}}
</style>
<div class="trixter-indicadores">{receitas}{gastos}{saldo}</div>
"""


def montar_paineis_categoria(paineis):
    """Resumo visual da categoria. Os números já chegam calculados."""
    blocos = []
    for painel in paineis:
        campos = (
            ("Limite", painel["limite"]),
            ("Realizado", painel["realizado"]),
            ("Restante", painel["restante"]),
            ("Projetado", painel["projetado"]),
            ("Recorrentes previstos", painel["recorrentes"]),
            ("Planejado manual", painel["manual"]),
        )
        grade = "".join(
            "<div><dt>"
            f"{html.escape(rotulo)}</dt><dd>"
            f"{html.escape(formatar_moeda(valor).strip())}</dd></div>"
            for rotulo, valor in campos
        )
        percentual = f"{painel['percentual']:.0%}"
        blocos.append(
            "<article class='trixter-categoria'>"
            "<header><h4>"
            f"{html.escape(str(painel['categoria']))}</h4>"
            f"<span>{html.escape(percentual)}</span></header>"
            f"<dl>{grade}</dl></article>"
        )
    return f"""
<style>
.trixter-categorias {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 2px 0 12px;
    font-family: inherit;
}}
.trixter-categoria {{
    flex: 1 1 280px;
    max-width: min(440px, 100%);
    box-sizing: border-box;
    background: #F7F4EE;
    border: 1px solid rgba(198, 161, 91, 0.30);
    border-radius: 12px;
    padding: 10px 12px 12px;
    min-width: 0;
}}
.trixter-categoria header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 10px;
    margin-bottom: 8px;
}}
.trixter-categoria h4 {{
    margin: 0;
    color: #172033;
    font-size: 0.98rem;
    font-weight: 600;
    line-height: 1.3;
    overflow-wrap: anywhere;
}}
.trixter-categoria header span {{
    color: #526077;
    font-size: 0.78rem;
    line-height: 1.3;
    white-space: nowrap;
}}
.trixter-categoria dl {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px 12px;
    margin: 0;
}}
.trixter-categoria dt {{
    margin: 0;
    color: #526077;
    font-size: 0.72rem;
    line-height: 1.3;
}}
.trixter-categoria dd {{
    margin: 2px 0 0;
    color: #172033;
    font-size: 0.86rem;
    font-weight: 600;
    line-height: 1.3;
    overflow-wrap: anywhere;
}}
@media (max-width: 760px) {{
    .trixter-categoria dl {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}
</style>
<div class="trixter-categorias">{''.join(blocos)}</div>
"""


@st.fragment
def exibir_indicadores_do_mes(conectar_banco, termo_gasto, recorrencias_ativas):
    """Mês e indicadores atualizam sozinhos para a página não voltar ao topo."""
    meses = {
       1: "Janeiro",

       2: "Fevereiro",

       3: "Março",

       4: "Abril",

       5: "Maio",

       6: "Junho",

       7: "Julho",

       8: "Agosto",

       9: "Setembro",

       10: "Outubro",

       11: "Novembro",

       12: "Dezembro"
    }

    mes_planejamento = st.selectbox(
       "Selecione o mês:",
       range(1,13),
       format_func=lambda x: meses[x],
       key="mes_planejamento"
    )

    ano_planejamento = st.number_input(
       "Selecione o ano:",
       min_value=2026,
       step=1,
       key="ano_planejamento"
    )

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT *
       FROM dbo.planejamentos
       WHERE id_usuario = ?
       AND MONTH(data) = ?
       AND YEAR(data) = ?
       """,
       st.session_state.usuario_atual["id_usuario"],
       mes_planejamento,
       ano_planejamento
    )
    planejamentos_mes = cursor.fetchall()


    colunas = [coluna[0] for coluna in cursor.description]
    planejamentos_mes = [dict(zip(colunas,linha)) for linha in planejamentos_mes]

    cursor.close()
    conexao.close()



    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT *
       FROM dbo.receitas
       WHERE id_usuario = ?
       AND MONTH(data) = ?
       AND YEAR(data) = ?
       """,
       st.session_state.usuario_atual["id_usuario"],
       mes_planejamento,
       ano_planejamento
    )
    planejamento_receitas = cursor.fetchall()
    colunas = [coluna[0] for coluna in cursor.description]
    planejamento_receitas = [dict(zip(colunas,linha)) for linha in planejamento_receitas]

    cursor.close()
    conexao.close()


    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT *
       FROM dbo.gastos
       WHERE id_usuario = ?
       AND MONTH(data) = ?
       AND YEAR(data) = ?
       """,
       st.session_state.usuario_atual["id_usuario"],
       mes_planejamento,
       ano_planejamento
    )
    planejamento_gastos = cursor.fetchall()
    colunas = [coluna[0] for coluna in cursor.description]
    planejamento_gastos = [dict(zip(colunas,linha)) for linha in planejamento_gastos]

    cursor.close()
    conexao.close()


    mes = int(mes_planejamento)
    ano = int(ano_planejamento)
    projecao = compor_projecao_mensal(
       planejamento_receitas,
       planejamento_gastos,
       planejamentos_mes,
       recorrencias_ativas,
       mes,
       ano,
    )

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT *
       FROM dbo.orcamentos
       WHERE id_usuario = ?
       AND mes = ?
       AND ano = ?
       """,
       st.session_state.usuario_atual["id_usuario"],
       mes_planejamento,
       ano_planejamento
    )
    planejamento_orcamentos = cursor.fetchall()
    colunas = [coluna[0] for coluna in cursor.description]
    planejamento_orcamentos = [dict(zip(colunas,linha)) for linha in planejamento_orcamentos]

    cursor.close()
    conexao.close()




    dados_projecao_categorias = []
    paineis_categoria = []
    avisos_projecao = []

    for orcamento in planejamento_orcamentos:
       categoria = orcamento["categoria"]
       valor_limite = orcamento["valor_limite"]
       fatia = compor_gasto_categoria(
          planejamento_gastos,
          planejamentos_mes,
          recorrencias_ativas,
          categoria,
          mes,
          ano,
       )
       gasto_realizado = fatia["realizado"]
       gastos_recorrentes_categoria = fatia["recorrentes_previstos"]
       gastos_manuais_categoria = fatia["planejado_manual"]
       gasto_projetado_categoria = fatia["projetado"]
       valor_restante_orcamento = valor_limite - gasto_realizado
       percentual_utilizado = (
          float(gasto_realizado) / float(valor_limite)
          if valor_limite > 0
          else 0
       )
       percentual_projetado = (
          float(gasto_projetado_categoria) / float(valor_limite)
          if valor_limite > 0
          else 0
       )

       dados_projecao_categorias.append(
          {
             "categoria": categoria,
             "limite": float(valor_limite),
             "realizado": float(gasto_realizado),
             "projetado": float(gasto_projetado_categoria),
          }
       )
       paineis_categoria.append({
          "categoria": categoria,
          "percentual": percentual_utilizado,
          "limite": valor_limite,
          "realizado": gasto_realizado,
          "restante": valor_restante_orcamento,
          "projetado": gasto_projetado_categoria,
          "recorrentes": gastos_recorrentes_categoria,
          "manual": gastos_manuais_categoria,
       })

       if percentual_utilizado < 1 and percentual_projetado >= 1:
          avisos_projecao.append(
              f"⚠️ {categoria}: "
              f"o orçamento ainda não foi estourado, mas a projeção indica "
              f"{percentual_projetado:.0%} de utilização."
          )

    if paineis_categoria:
       st.markdown(
          montar_paineis_categoria(paineis_categoria),
          unsafe_allow_html=True,
       )
    for aviso in avisos_projecao:
       st.warning(aviso)

    if dados_projecao_categorias:
       grafico = criar_grafico_projecao_mensal(dados_projecao_categorias)
       st.plotly_chart(
          grafico,
          use_container_width=len(dados_projecao_categorias) > 1,
       )

    termo_projetado = "Gastos projetados" if termo_gasto == "Gasto" else "Despesas projetadas"
    receitas_realizadas, receitas_pendentes, _ = composicao_exibida(projecao, "receitas")
    gastos_realizados, gastos_pendentes, _ = composicao_exibida(projecao, "gastos")
    st.markdown(
       montar_cartoes_projecao(
          projecao,
          termo_projetado,
          receitas_realizadas,
          receitas_pendentes,
          gastos_realizados,
          gastos_pendentes,
       ),
       unsafe_allow_html=True,
    )


def _rotulo_planejamento(registro):
    """Identifica a linha escolhida, com o cliente quando a receita tiver um."""
    texto = (
        f"{registro[2]} - {registro[3]} - {formatar_moeda(registro[4])} - {registro[5]}"
    )
    cliente = registro[6] if len(registro) > 6 else None
    if cliente:
        texto += f" - {cliente}"
    return texto


def opcoes_planejamento(registros):
    """Uma opção por id_planejamento."""
    opcoes = {}
    for registro in registros:
        identificador = str(registro[0])
        if identificador in opcoes:
            continue
        opcoes[identificador] = registro
    return opcoes


def rotulos_para_exibicao(registros):
    """Rótulo legível. O id completo só entra quando o texto se repetiria."""
    opcoes = opcoes_planejamento(registros)
    rotulos = {
        identificador: _rotulo_planejamento(registro)
        for identificador, registro in opcoes.items()
    }
    while True:
        repetidos = {
            texto
            for texto in rotulos.values()
            if sum(item == texto for item in rotulos.values()) > 1
        }
        if not repetidos:
            return rotulos
        for identificador, texto in list(rotulos.items()):
            if texto in repetidos:
                rotulos[identificador] = f"{texto} · {identificador}"


def confirmacao_corresponde(pendente, id_usuario, id_planejamento):
    """A confirmação só vale para a conta e o identificador ainda selecionados."""
    return (
        isinstance(pendente, dict)
        and pendente.get("id_usuario") == str(id_usuario)
        and pendente.get("id_planejamento") == str(id_planejamento)
    )


def _interromper_selecao_invalida(limpar_chave):
    """Descarta a confirmação. st.rerun impede o clique de chegar à escrita."""
    if limpar_chave:
        st.session_state.pop("planejamento_mensal_selecionado", None)
    st.session_state.pop("planejamento_exclusao_pendente", None)
    st.rerun()


def selecionar_planejamento(registros):
    """Devolve o id escolhido e a linha correspondente."""
    opcoes = opcoes_planejamento(registros)
    identificadores = list(opcoes)
    rotulos = rotulos_para_exibicao(registros)
    guardado = st.session_state.get("planejamento_mensal_selecionado")
    selecao_invalida = guardado is not None and str(guardado) not in opcoes
    if selecao_invalida:
        st.session_state.pop("planejamento_mensal_selecionado", None)
        st.session_state.pop("planejamento_exclusao_pendente", None)
    escolhido = st.selectbox(
        "Selecione o planejamento que deseja alterar:",
        identificadores,
        format_func=lambda identificador: rotulos[str(identificador)],
        key="planejamento_mensal_selecionado",
    )
    if selecao_invalida or str(escolhido) not in opcoes:
        _interromper_selecao_invalida(str(escolhido) not in opcoes)
    return str(escolhido), opcoes[str(escolhido)]


def exibir_confirmacao_exclusao(conectar_banco):
    """Pede confirmação do planejamento já escolhido. Não apaga outra conta."""
    pendente = st.session_state.get("planejamento_exclusao_pendente")
    usuario = str(st.session_state.usuario_atual["id_usuario"])
    if not isinstance(pendente, dict) or pendente.get("id_usuario") != usuario:
        st.session_state.pop("planejamento_exclusao_pendente", None)
        return
    st.warning(
        "Excluir este planejamento: "
        f"{pendente.get('rotulo')}? "
        "A receita ou o gasto já lançado não será apagado."
    )
    confirmar = st.button(
        "Confirmar exclusão",
        key="btn_confirmar_exclusao_planejamento",
        type="primary",
    )
    cancelar = st.button(
        "Cancelar exclusão",
        key="btn_cancelar_exclusao_planejamento",
    )
    if cancelar:
        st.session_state.pop("planejamento_exclusao_pendente", None)
        st.rerun()
    if not confirmar:
        return
    situacao = concluir_exclusao_planejamento(
        conectar_banco,
        pendente.get("id_planejamento"),
        usuario,
    )
    st.session_state.pop("planejamento_exclusao_pendente", None)
    if situacao == "excluido":
        st.session_state.planejamento_excluido_sucesso = True
    elif situacao == "ausente":
        st.session_state.planejamento_exclusao_aviso = (
            "Não foi possível excluir esse planejamento."
        )
    else:
        st.session_state.planejamento_exclusao_aviso = (
            "Não foi possível excluir esse planejamento agora."
        )
    st.rerun()


def _eh_receita(tipo):
    return str(tipo or "").strip().lower() == "receita"


def _sincronizar_campos_do_planejamento(id_planejamento):
    """Troca de UUID descarta o texto digitado para o registro anterior."""
    identificador = str(id_planejamento)
    if st.session_state.get("planejamento_mensal_campos_id") == identificador:
        return
    st.session_state.pop("planejamento_mensal_descricao", None)
    st.session_state.pop("planejamento_mensal_cliente", None)
    st.session_state["planejamento_mensal_campos_id"] = identificador


def exibir_correcao_texto_planejamento(conectar_banco, planejamento):
    """Corrige descrição e, na receita, cliente. Não altera valor nem lançamento."""
    if st.session_state.get("planejamento_texto_sucesso"):
        st.success(st.session_state.planejamento_texto_sucesso)
        st.session_state.planejamento_texto_sucesso = None
    if st.session_state.get("planejamento_texto_aviso"):
        st.error(st.session_state.planejamento_texto_aviso)
        st.session_state.planejamento_texto_aviso = None

    _sincronizar_campos_do_planejamento(planejamento[0])
    receita = _eh_receita(planejamento[1])
    situacao = planejamento[7] if len(planejamento) > 7 else None
    if em_aberto(situacao):
        st.info("A próxima baixa utilizará os dados corrigidos.")
    else:
        st.warning("O lançamento financeiro já realizado não será alterado.")

    descricao_atual = planejamento[3] if planejamento[3] is not None else ""
    nova_descricao = st.text_input(
        "Descrição:",
        value=str(descricao_atual),
        key="planejamento_mensal_descricao",
        help=(
            "Informe apenas o necessário para identificar o planejamento. "
            "Evite CPF, diagnósticos, informações de saúde ou outros "
            "dados pessoais sensíveis."
        ),
    )
    novo_cliente = None
    if receita:
        cliente_atual = planejamento[6] if len(planejamento) > 6 and planejamento[6] else ""
        novo_cliente = st.text_input(
            "Cliente:",
            value=str(cliente_atual),
            max_chars=80,
            key="planejamento_mensal_cliente",
            help=(
                "Opcional. O atraso deste compromisso aparece por cliente. "
                "Informe apenas o nome necessário à organização financeira. "
                "Evite CPF, diagnósticos, informações de saúde ou outros "
                "dados pessoais sensíveis."
            ),
        )
    if not st.button("Salvar descrição e cliente" if receita else "Salvar descrição",
                     key="btn_salvar_texto_planejamento"):
        return
    situacao_texto = concluir_atualizacao_texto_planejamento(
        conectar_banco,
        planejamento[0],
        st.session_state.usuario_atual["id_usuario"],
        nova_descricao,
        novo_cliente,
        receita,
    )
    if situacao_texto == "atualizado":
        st.session_state.planejamento_texto_sucesso = (
            "Descrição e cliente atualizados." if receita else "Descrição atualizada."
        )
    elif situacao_texto == "ausente":
        st.session_state.planejamento_texto_aviso = "Não foi possível salvar esses dados."
    else:
        st.session_state.planejamento_texto_aviso = (
            "Não foi possível salvar esses dados agora."
        )
    st.rerun()


def exibir_planejamento_mensal(conectar_banco, tipo_pessoa, termo_gasto, recorrencias_ativas):

    st.header("Planejamento Mensal")

    st.write(
     "Planeje suas finanças do mês e acompanhe os valores realizados."
    )

    if st.session_state.usuario_atual["tipo_pessoa"] == "Pessoa Jurídica":
       opcoes_tipo = ["Receitas", "Despesas"]

    else:
       opcoes_tipo = ["Receitas", "Gastos"]

    tipo_planejamento = st.selectbox(
       "O que deseja planejar?",
       opcoes_tipo,
       key="tipo_planejamento"
    )


    if tipo_planejamento == "Receitas":
       tipo_planejamento_interno = "Receita"
    else:
       tipo_planejamento_interno = "Despesa"



    with closing(conectar_banco()) as conexao_categorias:
        with closing(conexao_categorias.cursor()) as cursor_categorias:
            categorias_planejamento = listar_categorias(
                cursor_categorias,
                st.session_state.usuario_atual["id_usuario"],
                tipo_pessoa,
                tipo_planejamento_interno,
            )

    categoria_planejamento = st.selectbox(
       "Categoria:",
       categorias_planejamento,
       key="categoria_planejamento"
    )

    descricao_planejamento = st.text_input(
       "Descrição:",
       key="descicao_planejamento",
       placeholder=("Ex: Salário, freelance ou comissão"
                    if tipo_planejamento == "Receitas"
                    else "Ex: Aluguel, mercado ou transporte"
    ),
        help=(
            "Informe apenas o necessário para identificar o planejamento. "
            "Evite CPF, diagnósticos, informações de saúde ou outros "
            "dados pessoais sensíveis."
        ),
    )

    valor_planejamento = st.number_input(
       "Valor previsto:",
       min_value=0.0,
       step=10.0,
       key="valor_planejamento"
    )

    data_planejamento = st.date_input(
       "Data prevista:",
       key="data_planejamento"
    )

    cliente_planejamento = None
    if tipo_planejamento_interno == "Receita":
       cliente_planejamento = normalizar_cliente(st.text_input(
          "Cliente:",
          placeholder="Ex.: Aurora Serviços",
          max_chars=80,
          key="cliente_planejamento",
         help=(
            "Opcional. O atraso deste compromisso aparece por cliente. "
            "Informe apenas o nome necessário à organização financeira. "
            "Evite CPF, diagnósticos, informações de saúde ou outros "
            "dados pessoais sensíveis."
        ),
       ))

    planejamento = {
       "id_planejamento": str(uuid.uuid4()),
       "id_usuario": st.session_state.usuario_atual["id_usuario"],
       "tipo": tipo_planejamento_interno,
       "categoria": categoria_planejamento,
       "descricao": descricao_planejamento,
       "valor": valor_planejamento,
       "data": data_planejamento.strftime("%d/%m/%Y")
    }

    btn_salvar_planejamento = st.button("Salvar Planejamento",
          key="btn_salvar_planejamento",
          type="primary"
    )

    if st.session_state.get("planejamento_mensal_salvo_sucesso", False):
       st.success("Planejamento mensal salvo com sucesso!")
       st.session_state.planejamento_mensal_salvo_sucesso = False

    if btn_salvar_planejamento:
       if valor_planejamento <= 0:
          st.error("O valor do planejamento deve ser maior do que zero.")
       else:
          conexao = conectar_banco()
          cursor = conexao.cursor()



          cursor.execute(
             """
             INSERT INTO dbo.planejamentos(
                id_planejamento,
                id_usuario,
                tipo,
                categoria,
                descricao,
                valor,
                data,
                cliente
                )
                VALUES (?,?,?,?,?,?,?,?)
             """,
             planejamento["id_planejamento"],
             planejamento["id_usuario"],
             planejamento["tipo"],
             planejamento["categoria"],
             planejamento["descricao"],
             planejamento["valor"],
             data_planejamento,
             cliente_planejamento


          )
          conexao.commit()
          cursor.close()
          conexao.close()
          st.session_state.planejamento_mensal_salvo_sucesso = True
          st.rerun()


    with closing(conectar_banco()) as conexao_contas:
        with closing(conexao_contas.cursor()) as cursor_contas:
            compromissos = listar_compromissos(
                cursor_contas,
                st.session_state.usuario_atual["id_usuario"],
                date.today(),
            )
    exibir_compromissos(compromissos)
    abertos = [
        item for item in compromissos["itens"]
        if item["situacao"] in ("Previsto", "Atrasado")
    ]
    if abertos:
        rotulos_compromisso = {
            (
                f"{item['data']:%d/%m/%Y} · "
                f"{(item.get('cliente') + ' · ') if item.get('cliente') else ''}"
                f"{item['categoria']} · {item['descricao']} · {item['situacao']}"
            ): item
            for item in abertos
        }
        escolha_compromisso = st.selectbox(
            "Selecione o compromisso em aberto:",
            list(rotulos_compromisso.keys()),
            key="compromisso_em_aberto",
        )
        compromisso_escolhido = rotulos_compromisso[escolha_compromisso]
        verbo_baixa = "recebido" if compromisso_escolhido["direcao"] == "receber" else "pago"
        if st.button(
            f"Marcar como {verbo_baixa}",
            key="btn_baixar_compromisso",
            type="primary",
        ):
            if baixar_compromisso(
                conectar_banco,
                st.session_state.usuario_atual["id_usuario"],
                compromisso_escolhido,
            ):
                st.session_state.compromisso_baixado_sucesso = True
                st.rerun()
            st.error("Não foi possível baixar esse compromisso.")
    if st.session_state.get("compromisso_baixado_sucesso", False):
        st.success("Compromisso lançado no saldo realizado.")
        st.session_state.compromisso_baixado_sucesso = False


    st.subheader("Alterar Planejamento Mensal")

    if st.session_state.get("planejamento_excluido_sucesso", False):
       st.success("Planejamento excluído.")
       st.session_state.planejamento_excluido_sucesso = False
    if st.session_state.get("planejamento_exclusao_aviso"):
       st.error(st.session_state.planejamento_exclusao_aviso)
       st.session_state.planejamento_exclusao_aviso = None

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT id_planejamento, tipo, categoria, descricao, valor, data, cliente, situacao
       FROM dbo.planejamentos
       WHERE id_usuario = ?
       ORDER BY data DESC
       """,
       st.session_state.usuario_atual["id_usuario"]
    )
    planejamentos_salvos = cursor.fetchall()

    cursor.close()
    conexao.close()

    if planejamentos_salvos:

       id_planejamento_selecionado, planejamento_selecionado = selecionar_planejamento(
          planejamentos_salvos
       )
       exibir_correcao_texto_planejamento(conectar_banco, planejamento_selecionado)
       valor_atual = float(planejamento_selecionado[4])

       novo_valor_planejamento = st.number_input(
          "Novo valor:",
          min_value=0.0,
          value=valor_atual,
          step=10.0
       )

       btn_alterar_planejamento = st.button(
          "Alterar planejamento",
          key="btn_alterar_planejamento",
          type="primary"
       )

       if st.session_state.get("planejamento_mensal_alterado_sucesso", False):
          st.success("Planejamento mensal alterado com sucesso!")
          st.session_state.planejamento_mensal_alterado_sucesso = False

       if btn_alterar_planejamento:

          if novo_valor_planejamento <= 0:
             st.error("O valor do planejamento deve ser maior do que zero.")

          else:
             conexao = conectar_banco()
             cursor = conexao.cursor()

             cursor.execute(
                """
                UPDATE dbo.planejamentos
                set valor = ?
                WHERE id_planejamento = ?
                AND id_usuario = ?
                """,
                novo_valor_planejamento,
                id_planejamento_selecionado,
                st.session_state.usuario_atual["id_usuario"]
             )

             conexao.commit()
             cursor.close()
             conexao.close()

             st.session_state.planejamento_mensal_alterado_sucesso = True
             st.rerun()

       usuario_exclusao = str(st.session_state.usuario_atual["id_usuario"])
       pendente_exclusao = st.session_state.get("planejamento_exclusao_pendente")
       if not confirmacao_corresponde(
          pendente_exclusao, usuario_exclusao, id_planejamento_selecionado
       ):
          st.session_state.pop("planejamento_exclusao_pendente", None)
          if st.button("Excluir planejamento", key="btn_excluir_planejamento"):
             st.session_state.planejamento_exclusao_pendente = {
                "id_usuario": usuario_exclusao,
                "id_planejamento": str(id_planejamento_selecionado),
                "rotulo": rotulos_para_exibicao(planejamentos_salvos)[
                    str(id_planejamento_selecionado)
                ],
             }
             st.rerun()
       else:
          exibir_confirmacao_exclusao(conectar_banco)

    else:
       st.info("Nenhum planejamento encontrado para o mês e ano selecionados.")


    exibir_indicadores_do_mes(conectar_banco, termo_gasto, recorrencias_ativas)
