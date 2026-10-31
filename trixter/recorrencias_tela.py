"""Tela de recorrências. Gera os lançamentos e avança a próxima data."""
import uuid
from contextlib import closing
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta

from .categorias import listar_categorias
from .recorrencias import ajustar_dia_mes, normalizar_data
from .relatorios import formatar_moeda
from .sessao import encerrar_edicao_recorrencia

DIAS_SEMANA = {
    1: "Segunda-feira",
    2: "Terça-feira",
    3: "Quarta-feira",
    4: "Quinta-feira",
    5: "Sexta-feira",
    6: "Sábado",
    7: "Domingo",
}
CENTAVO = Decimal("0.01")


def _valor(recorrencia):
    return Decimal(str(recorrencia.get("valor") or 0)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _ativa(recorrencia):
    return bool(recorrencia.get("ativa"))


def texto_tipo(recorrencia, tipo_pessoa):
    tipo = str(recorrencia.get("tipo") or "").strip().capitalize()
    if tipo_pessoa == "Pessoa Jurídica" and tipo == "Gasto":
        return "Despesa"
    return tipo or "Não informado"


def texto_classificacao(valor):
    if valor is None:
        return "Não classificado"
    try:
        if valor != valor:
            return "Não classificado"
    except Exception:
        pass
    texto = str(valor).strip()
    if texto.lower() in {"", "none", "nan", "nat"}:
        return "Não classificado"
    return texto


def _inteiro(valor):
    if valor is None or valor == "":
        return None
    try:
        if valor != valor:
            return None
    except Exception:
        pass
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def texto_periodo(recorrencia):
    """O dia da regra vem de dia, dia_semana ou mes. Não é a próxima execução."""
    frequencia = recorrencia.get("frequencia")
    if frequencia == "Diária":
        return "Todos os dias"
    if frequencia == "Semanal":
        nome = DIAS_SEMANA.get(_inteiro(recorrencia.get("dia_semana")))
        return f"Toda {nome}" if nome else "Semanal"
    if frequencia == "Mensal":
        dia = _inteiro(recorrencia.get("dia"))
        return f"Todo dia {dia}" if dia else "Mensal"
    if frequencia == "Anual":
        dia = _inteiro(recorrencia.get("dia"))
        mes = _inteiro(recorrencia.get("mes"))
        if dia and mes:
            return f"Todo dia {dia:02d}/{mes:02d}"
        return "Anual"
    return str(frequencia or "Não informada")


def texto_proxima(valor):
    if valor is None or valor == "":
        return "Não disponível"
    try:
        if valor != valor:
            return "Não disponível"
    except Exception:
        pass
    if hasattr(valor, "strftime"):
        try:
            return valor.strftime("%d/%m/%Y")
        except (ValueError, OSError):
            return "Não disponível"
    texto = str(valor)[:10]
    partes = texto.split("-")
    if len(partes) == 3 and all(parte.isdigit() for parte in partes):
        ano, mes, dia = partes
        return f"{dia}/{mes}/{ano}"
    return str(valor)


def valor_mensal_previsto(recorrencia):
    """Converte a recorrência ativa para um mês. Não lê lançamentos realizados."""
    if not _ativa(recorrencia):
        return Decimal("0.00")
    valor = _valor(recorrencia)
    frequencia = recorrencia.get("frequencia")
    if frequencia == "Mensal":
        mensal = valor
    elif frequencia == "Anual":
        mensal = valor / Decimal(12)
    elif frequencia == "Semanal":
        mensal = valor * Decimal(52) / Decimal(12)
    elif frequencia == "Diária":
        mensal = valor * Decimal(30)
    else:
        mensal = Decimal(0)
    return mensal.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def resumir_recorrencias(recorrencias):
    ativas = [item for item in recorrencias if _ativa(item)]
    receitas = sum(
        (valor_mensal_previsto(item) for item in ativas if str(item.get("tipo") or "").strip().lower() == "receita"),
        Decimal("0.00"),
    )
    gastos = sum(
        (valor_mensal_previsto(item) for item in ativas if str(item.get("tipo") or "").strip().lower() != "receita"),
        Decimal("0.00"),
    )
    return {
        "ativas": len(ativas),
        "receitas": receitas,
        "gastos": gastos,
    }


def exibir_resumo_e_cartoes(recorrencias, tipo_pessoa, termo_gasto, conectar_banco):
    resumo = resumir_recorrencias(recorrencias)
    st.subheader("Recorrências cadastradas")
    st.caption(
     "Os valores apresentados são estimativas mensais calculadas a partir das recorrências ativas e não representam movimentações já realizadas. "

     "Para facilitar a comparação, consideramos o valor integral das recorrências mensais, 1/12 das anuais, 52/12 das semanais e 30 ocorrências para as recorrências diárias. "

     "Esses valores são apenas referências de planejamento e podem diferir dos recebimentos e pagamentos efetivos de cada mês. "
    )

    coluna_ativas, coluna_receitas, coluna_gastos = st.columns(3)
    coluna_ativas.metric("Recorrências ativas", resumo["ativas"])
    coluna_receitas.metric("Receitas recorrentes previstas", formatar_moeda(resumo["receitas"]).strip())
    coluna_gastos.metric(
        f"{termo_gasto}s recorrentes previstos",
        formatar_moeda(resumo["gastos"]).strip(),
    )

    for recorrencia in recorrencias:
        with st.container(border=True):
            st.markdown(f"**{recorrencia.get('categoria') or 'Sem categoria'}**")
            if recorrencia.get("descricao"):
                st.caption(str(recorrencia["descricao"]))
            tipo, valor, periodo = st.columns(3)
            tipo.markdown(f"Tipo  \n{texto_tipo(recorrencia, tipo_pessoa)}")
            valor.markdown(f"Valor  \n{formatar_moeda(recorrencia.get('valor')).strip()}")
            periodo.markdown(f"Frequência  \n{texto_periodo(recorrencia)}")
            classificacao, status, proxima = st.columns(3)
            classificacao.markdown(f"Classificação  \n{texto_classificacao(recorrencia.get('classificacao'))}")
            status.markdown(f"Status  \n{'Ativa' if _ativa(recorrencia) else 'Inativa'}")
            proxima.markdown(f"Próxima execução  \n{texto_proxima(recorrencia.get('proxima_execucao'))}")

            texto_botao = "Desativar" if _ativa(recorrencia) else "Reativar"
            if st.button(
                texto_botao,
                key=f"status_recorrencia_{recorrencia['id_recorrencia']}",
            ):
                conexao = conectar_banco()
                cursor = conexao.cursor()
                cursor.execute(
                    """
                    UPDATE dbo.recorrencias
                    SET ativa = ?
                    WHERE id_recorrencia = ?
                    AND id_usuario = ?
                    """,
                    not _ativa(recorrencia),
                    recorrencia["id_recorrencia"],
                    st.session_state.usuario_atual["id_usuario"],
                )
                conexao.commit()
                cursor.close()
                conexao.close()
                st.rerun(scope="fragment")


def avancar_execucao(data_execucao, recorrencia):
    """Próxima data pela frequência já usada na geração. None encerra a série."""
    frequencia = recorrencia["frequencia"]
    if frequencia == "Diária":
        return data_execucao + relativedelta(days=1)
    if frequencia == "Semanal":
        return data_execucao + relativedelta(weeks=1)
    if frequencia == "Mensal":
        proximo_mes = data_execucao + relativedelta(months=1)
        dia_valido = ajustar_dia_mes(
            proximo_mes.year,
            proximo_mes.month,
            recorrencia["dia"],
        )
        return proximo_mes.replace(day=dia_valido)
    if frequencia == "Anual":
        proximo_ano = data_execucao + relativedelta(years=1)
        dia_valido = ajustar_dia_mes(
            proximo_ano.year,
            proximo_ano.month,
            recorrencia["dia"],
        )
        return proximo_ano.replace(day=dia_valido)
    return None


def proxima_apos_edicao(recorrencia, frequencia, dia, mes, dia_semana, hoje):
    """Mantem o ponteiro sem mudanca de regra; recalcula so ocorrencias futuras.

    Preserva o periodo de inicio futuro e nao descarta pendencias vencidas.
    As pendencias ativas sao processadas pela rotina existente antes da edicao.
    """
    def regra(freq, d, m, semana):
        return (freq, d if freq in ("Mensal", "Anual") else None,
                m if freq == "Anual" else None,
                semana if freq == "Semanal" else None)
    ponteiro = normalizar_data(recorrencia.get("proxima_execucao"))
    if regra(frequencia, dia, mes, dia_semana) == regra(
        recorrencia["frequencia"], recorrencia.get("dia"),
        recorrencia.get("mes"), recorrencia.get("dia_semana"),
    ):
        return ponteiro
    if ponteiro is not None and ponteiro <= hoje:
        raise ValueError("Resolva as ocorrencias vencidas antes de alterar a regra de frequencia.")
    base = ponteiro or hoje
    if frequencia == "Di\u00e1ria":
        return max(base, hoje + relativedelta(days=1))
    if frequencia == "Semanal":
        proxima = base + relativedelta(days=(dia_semana - 1 - base.weekday()))
        while proxima <= hoje:
            proxima += relativedelta(weeks=1)
        return proxima
    if frequencia == "Mensal":
        proxima = base.replace(day=ajustar_dia_mes(base.year, base.month, dia))
        if proxima <= hoje:
            base = base + relativedelta(months=1)
            proxima = base.replace(day=ajustar_dia_mes(base.year, base.month, dia))
        return proxima
    if frequencia == "Anual":
        proxima = base.replace(month=mes, day=ajustar_dia_mes(base.year, mes, dia))
        if proxima <= hoje:
            base = base + relativedelta(years=1)
            proxima = base.replace(month=mes, day=ajustar_dia_mes(base.year, mes, dia))
        return proxima
    raise ValueError("Frequencia desconhecida.")


def gravar_ocorrencia(cursor, recorrencia, data_execucao, proxima):
    """Insere o lançamento se ainda não existe e grava a próxima data. Não faz commit.

    A trava fica na linha da recorrência. O lançamento pode ainda não existir,
    então duas sessões não têm linha para disputar em receitas ou gastos.
    Quem espera relê proxima_execucao e não grava a data que a outra já passou.
    """
    cursor.execute(
        """
        SELECT proxima_execucao
        FROM dbo.recorrencias WITH (UPDLOCK, ROWLOCK, HOLDLOCK)
        WHERE id_recorrencia = ?
        AND id_usuario = ?
        """,
        recorrencia["id_recorrencia"],
        recorrencia["id_usuario"],
    )
    linha = cursor.fetchone()
    if linha is None:
        return None
    ponteiro = normalizar_data(linha[0])
    if ponteiro != data_execucao:
        return ponteiro

    if recorrencia["tipo"] == "Receita":
        tabela = "receitas"
    else:
        tabela = "gastos"

    cursor.execute(
        f"""
        SELECT COUNT (*)
        FROM dbo.{tabela}
        WHERE id_usuario = ?
        AND id_recorrencia = ?
        AND data = ?
        """,
        recorrencia["id_usuario"],
        recorrencia["id_recorrencia"],
        data_execucao,
    )
    transacao_ja_existe = cursor.fetchone()[0] > 0

    if not transacao_ja_existe:
        if recorrencia["tipo"] == "Receita":
            cursor.execute(
                """
                INSERT INTO dbo.receitas(
                id_transacao,
                id_usuario,
                id_recorrencia,
                categoria,
                valor,
                data,
                descricao,
                classificacao
                )
                VALUES (?,?,?,?,?,?,?,?)
                """,
                str(uuid.uuid4()),
                recorrencia["id_usuario"],
                recorrencia["id_recorrencia"],
                recorrencia["categoria"],
                recorrencia["valor"],
                data_execucao,
                recorrencia["descricao"],
                recorrencia.get("classificacao"),
            )
        elif recorrencia["tipo"] == "Gasto":
            cursor.execute(
                """
                INSERT INTO dbo.gastos(
                id_transacao,
                id_usuario,
                id_recorrencia,
                categoria,
                valor,
                data,
                descricao,
                classificacao
                )
                VALUES(?,?,?,?,?,?,?,?)
                """,
                str(uuid.uuid4()),
                recorrencia["id_usuario"],
                recorrencia["id_recorrencia"],
                recorrencia["categoria"],
                recorrencia["valor"],
                data_execucao,
                recorrencia["descricao"],
                recorrencia.get("classificacao"),
            )

    cursor.execute(
        """
        UPDATE dbo.recorrencias
        SET proxima_execucao = ?
        WHERE id_recorrencia = ?
        AND id_usuario = ?
        """,
        proxima,
        recorrencia["id_recorrencia"],
        recorrencia["id_usuario"],
    )
    return proxima


def processar_pendencias(conectar_banco, recorrencia, hoje, ao_pendente=None):
    """Lança o que já venceu e devolve a próxima data. Cada volta avança ou para."""
    data_execucao = normalizar_data(recorrencia.get("proxima_execucao"))
    if data_execucao is None:
        return None
    while data_execucao <= hoje:
        proxima = avancar_execucao(data_execucao, recorrencia)
        if proxima is None or proxima <= data_execucao:
            break
        if ao_pendente is not None:
            ao_pendente(recorrencia, data_execucao)
        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            try:
                cursor.execute("SET LOCK_TIMEOUT 5000")
                seguimento = gravar_ocorrencia(cursor, recorrencia, data_execucao, proxima)
                conexao.commit()
            except Exception:
                conexao.rollback()
                raise
            finally:
                try:
                    cursor.execute("SET LOCK_TIMEOUT -1")
                except Exception:
                    pass
                cursor.close()
        finally:
            conexao.close()
        if seguimento is None or seguimento <= data_execucao:
            break
        data_execucao = seguimento
    return data_execucao


@st.fragment
def exibir_recorrencias(conectar_banco, tipo_pessoa, termo_gasto):

    st.header("Gerenciar Recorrências")

    st.write(
     "Cadastre e acompanhe receitas e gastos que se repetem periodicamente."
    )

    tipo_recorrencia = st.selectbox(
       "Selecione o tipo de recorrência:",
       ["Receita", termo_gasto],
       key= "tipo_recorrencia"
    )


    tipo_recorrencia_interno = tipo_recorrencia
    if tipo_recorrencia == "Despesa":
       tipo_recorrencia_interno = "Gasto"


    with closing(conectar_banco()) as conexao_categorias:
        with closing(conexao_categorias.cursor()) as cursor_categorias:
            categorias_recorrencia = listar_categorias(
                cursor_categorias,
                st.session_state.usuario_atual["id_usuario"],
                tipo_pessoa,
                tipo_recorrencia_interno,
            )


    categoria_recorrencia = st.selectbox(
       "Selecione a categoria da recorrência:",
       categorias_recorrencia,
       key= "categoria_recorrencia"
    )

    classificacao_recorrencia = st.selectbox(
       "Classificação da recorrência:",
       ["Não classificado", "Fixo", "Variável"],
       key="classificacao_recorrencia",
       help="A frequência indica quando lançar; a classificação é independente dela. "
            "Os novos lançamentos receberão esta classificação. O valor lançado continua "
            "sendo o cadastrado, mesmo quando a classificação é Variável."
    )
    classificacao_recorrencia = None if classificacao_recorrencia == "Não classificado" else classificacao_recorrencia

    valor_recorrencia = st.number_input(
       f"Defina o valor da recorrência para {categoria_recorrencia}:",
       min_value=0.0,
       step=10.0,
       key="valor_recorrencia"
    )

    frequencia_recorrencia = st.selectbox(
       "Selecione a frequência da recorrência:",
       ["Diária", "Semanal", "Mensal", "Anual"]
    )

    dia_recorrencia = None
    mes_recorrencia = None
    dia_semana_recorrencia = None

    dias_semana = {
       "Segunda-feira": 1,
       "Terça-feira": 2,
       "Quarta-feira": 3,
       "Quinta-feira": 4,
       "Sexta-feira": 5,
       "Sábado": 6,
       "Domingo": 7
       }

    meses = {
       "Janeiro":1,
       "Fevereiro":2,
       "Março":3,
       "Abril":4,
       "Maio":5,
       "Junho":6,
       "Julho":7,
       "Agosto":8,
       "Setembro":9,
       "Outubro":10,
       "Novembro":11,
       "Dezembro":12
    }

    if frequencia_recorrencia == "Semanal":
       dia_semana_recorrencia = st.selectbox(
          "Selecione o dia da semana:",
          ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
       )
       dia_semana_recorrencia = dias_semana[dia_semana_recorrencia]


    elif frequencia_recorrencia == "Mensal":
       dia_recorrencia = st.number_input(
          "Selecione o dia do mês:",
          min_value=1,
          max_value=31,
          step=1,
          key="dia_recorrencia_mensal"
       )


    elif frequencia_recorrencia == "Anual":
       dia_recorrencia = st.number_input(
          "Selecione o dia:",
          min_value=1,
          max_value=31,
          step=1,
          key="dia_recorrencia_anual"
       )
       mes_recorrencia = st.selectbox(
          "Selecione o mês:",
          ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
       )

       mes_recorrencia = meses[mes_recorrencia]


    descricao_recorrencia = st.text_input(
       "Digite uma descrição para a recorrência:",
       placeholder="Ex.: Aluguel",
       key= "descricao_recorrencia",
       help=(
        "Informe apenas o necessário para identificar a recorrência. "
        "Evite CPF, diagnósticos, informações de saúde ou outros "
        "dados pessoais sensíveis."
    ),
    )

    data_inicio_recorrencia = st.date_input(
       "Selecione a data de início da recorrência:",
       key="data_inicio_recorrencia"
    )


    btn_salvar_recorrencia = st.button("Salvar Recorrência",
                                       type="primary")

    if st.session_state.get("recorrencia_salva_sucesso", False):
       st.success("Recorrência salva com sucesso!")
       st.session_state.recorrencia_salva_sucesso = False

    if btn_salvar_recorrencia:


       if valor_recorrencia <= 0:
          st.error("O valor da recorrência deve ser maior do que zero.")
       else:
          conexao = conectar_banco()
          cursor = conexao.cursor()

          cursor.execute(
          """
          INSERT INTO dbo.recorrencias(
             id_recorrencia,
             id_usuario,
             tipo,
             categoria,
             descricao,
             valor,
             frequencia,
             proxima_execucao,
             ativa,
             dia_semana,
             dia,
             mes,
             classificacao
          )
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)

          """,
          str(uuid.uuid4()),
          st.session_state.usuario_atual["id_usuario"],
          tipo_recorrencia_interno,
          categoria_recorrencia,
          descricao_recorrencia,
          valor_recorrencia,
          frequencia_recorrencia,
          data_inicio_recorrencia,
          1,
          dia_semana_recorrencia,
          dia_recorrencia,
          mes_recorrencia,
          classificacao_recorrencia
          )



          conexao.commit()
          cursor.close()
          conexao.close()
          st.session_state.recorrencia_salva_sucesso = True
          st.rerun(scope="fragment")



    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
       """
       SELECT *
       FROM dbo.recorrencias
       WHERE id_usuario = ?
       """,
       st.session_state.usuario_atual["id_usuario"]
    )

    recorrencias_usuario = cursor.fetchall()
    colunas = [coluna[0] for coluna in cursor.description]

    df_recorrencias = pd.DataFrame(
       [tuple(recorrencia) for recorrencia in recorrencias_usuario], columns=colunas)

    recorrencias_usuario = df_recorrencias.to_dict("records")
    cursor.close()
    conexao.close()



    hoje = datetime.today().date()
    for recorrencia in recorrencias_usuario:
       if(
          recorrencia["id_usuario"] == st.session_state.usuario_atual["id_usuario"]
          and recorrencia["ativa"]
       ):
          def avisar_pendente(item, _data):
             st.write(
                f"Recorrência pendente: {item['categoria']} - "
                f"{formatar_moeda(item['valor'])}"
             )

          recorrencia["proxima_execucao"] = processar_pendencias(
              conectar_banco, recorrencia, hoje, avisar_pendente,
          )


    if recorrencias_usuario:
          exibir_resumo_e_cartoes(
              recorrencias_usuario, tipo_pessoa, termo_gasto, conectar_banco
          )

          usuario_selecao = st.session_state.usuario_atual["id_usuario"]
          opcoes_recorrencias = {
             str(item["id_recorrencia"]): item for item in recorrencias_usuario
          }
          usuario_anterior = st.session_state.get("_recorrencias_usuario")
          selecionada_anterior = st.session_state.get("recorrencia_selecionada")
          selecao_invalidada = (
             usuario_anterior is not None and usuario_anterior != usuario_selecao
          ) or (
             selecionada_anterior is not None
             and selecionada_anterior not in opcoes_recorrencias
          )
          if selecao_invalidada:
             st.session_state.pop("recorrencia_selecionada", None)
             st.session_state.pop("_recorrencia_em_edicao", None)
             st.session_state.alterar_recorrencia = False
          st.session_state._recorrencias_usuario = usuario_selecao
          rotulos = {
             ident: f"{item['categoria']} - {item['descricao']}"
             for ident, item in opcoes_recorrencias.items()
          }
          # Desambiguar somente os rotulos repetidos; o valor e sempre o ID.
          contagens = {}
          for rotulo in rotulos.values():
             contagens[rotulo] = contagens.get(rotulo, 0) + 1
          ocorrencias = {}
          for ident, rotulo in rotulos.items():
             ocorrencias[rotulo] = ocorrencias.get(rotulo, 0) + 1
             if contagens[rotulo] > 1:
                rotulos[ident] = f"{rotulo} (opção {ocorrencias[rotulo]})"
          id_recorrencia_selecionada = st.selectbox(
             "Selecione uma recorrência:",
             list(opcoes_recorrencias),
             format_func=lambda ident: rotulos[ident],
             key="recorrencia_selecionada",
          )
          recorrencia_encontrada = opcoes_recorrencias[id_recorrencia_selecionada]
          identidade = (usuario_selecao, id_recorrencia_selecionada)
          if st.session_state.get("_recorrencia_em_edicao") != identidade:
             st.session_state.alterar_recorrencia = False

          btn_alterar_recorrencia = st.button(
                "Alterar Recorrência Selecionada",
                key="btn_alterar_recorrencia")

          if st.session_state.get("recorrencia_alterada_sucesso", False):
                st.success("Recorrência alterada com sucesso!")
                st.session_state.recorrencia_alterada_sucesso = False

          if btn_alterar_recorrencia and not selecao_invalidada:
                for prefixo in ("novo_dia_semana_recorrencia_", "novo_dia_recorrencia_",
                                "novo_dia_anual_recorrencia_", "novo_mes_anual_recorrencia_"):
                    st.session_state.pop(f"{prefixo}{id_recorrencia_selecionada}", None)
                st.session_state.alterar_recorrencia = True
                st.session_state._recorrencia_em_edicao = identidade

          if st.session_state.alterar_recorrencia and recorrencia_encontrada is not None:
                novo_valor_recorrencia = st.number_input(
                   "Novo valor:",
                   min_value=0.0,
                   value=float(recorrencia_encontrada["valor"]),
                   step=10.0,
                   key=f"novo_valor_recorrencia_{id_recorrencia_selecionada}"
                )

                nova_descricao_recorrencia = st.text_input(
                   "Nova descrição:",
                   value=recorrencia_encontrada["descricao"],
                   key=f"nova_descricao_recorrencia_{id_recorrencia_selecionada}",
                   help=(
                    "Informe apenas o necessário para identificar a recorrência. "
                    "Evite CPF, diagnósticos, informações de saúde ou outros "
                    "dados pessoais sensíveis."
                ),
                )

                tipo_edicao = recorrencia_encontrada["tipo"].capitalize()

                with closing(conectar_banco()) as conexao_categorias:
                    with closing(conexao_categorias.cursor()) as cursor_categorias:
                        categorias_edicao = listar_categorias(
                            cursor_categorias,
                            st.session_state.usuario_atual["id_usuario"],
                            tipo_pessoa,
                            tipo_edicao,
                        )
                # Preserva a categoria atual mesmo se ela nao estiver no cadastro.
                if recorrencia_encontrada["categoria"] not in categorias_edicao:
                    categorias_edicao.append(recorrencia_encontrada["categoria"])


                nova_categoria_recorrencia = st.selectbox(
                   "Nova categoria:",
                   categorias_edicao,
                   index=categorias_edicao.index(recorrencia_encontrada["categoria"]),
                   key=f"nova_categoria_recorrencia_{id_recorrencia_selecionada}"
                )

                opcoes_classificacao = ["Não classificado", "Fixo", "Variável"]
                classificacao_atual = recorrencia_encontrada.get("classificacao")
                if pd.isna(classificacao_atual):
                   classificacao_atual = "Não classificado"
                nova_classificacao_recorrencia = st.selectbox(
                   "Nova classificação:",
                   opcoes_classificacao,
                   index=opcoes_classificacao.index(classificacao_atual),
                   key=f"nova_classificacao_recorrencia_{id_recorrencia_selecionada}",
                   help="Aplica-se aos próximos lançamentos gerados. Não altera lançamentos anteriores."
                )
                if nova_classificacao_recorrencia == "Não classificado":
                   nova_classificacao_recorrencia = None

                frequencias = ["Diária", "Semanal", "Mensal", "Anual"]

                nova_frequencia_recorrencia = st.selectbox(
                   "Nova frequência:",
                   frequencias,
                   index=frequencias.index(recorrencia_encontrada["frequencia"]),
                   key=f"nova_frequencia_recorrencia_{id_recorrencia_selecionada}"
                )

                dia_salvo = recorrencia_encontrada.get("dia")
                mes_salvo = recorrencia_encontrada.get("mes")
                semana_salva = recorrencia_encontrada.get("dia_semana")
                novo_dia = None
                novo_mes = None
                novo_dia_semana = None

                if nova_frequencia_recorrencia == "Semanal":
                   novo_dia_semana = st.selectbox(
                      "Dia da semana:",
                      ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"],
                      index=int(semana_salva) - 1 if pd.notna(semana_salva) else 0,
                      key=f"novo_dia_semana_recorrencia_{id_recorrencia_selecionada}"
                   )
                   novo_dia_semana = dias_semana[novo_dia_semana]

                elif nova_frequencia_recorrencia == "Mensal":
                   novo_dia = st.number_input(
                      "Dia do mês:",
                      min_value=1,
                      max_value=31,
                      step=1,
                      value=int(dia_salvo) if pd.notna(dia_salvo) else 1,
                      key=f"novo_dia_recorrencia_{id_recorrencia_selecionada}"
                   )

                elif nova_frequencia_recorrencia == "Anual":
                   novo_dia = st.number_input(
                      "Dia:",
                      min_value=1,
                      max_value=31,
                      step=1,
                      value=int(dia_salvo) if pd.notna(dia_salvo) else 1,
                      key=f"novo_dia_anual_recorrencia_{id_recorrencia_selecionada}"
                   )
                   novo_mes = st.number_input(
                      "Mês:",
                      min_value=1,
                      max_value=12,
                      value=int(mes_salvo) if pd.notna(mes_salvo) else 1,
                      key=f"novo_mes_anual_recorrencia_{id_recorrencia_selecionada}"
                   )

                btn_salvar_alteracoes_recorrencia = st.button("Salvar Alterações")

                if btn_salvar_alteracoes_recorrencia:
                   if novo_valor_recorrencia <= 0:
                      st.error("O valor da recorrência deve ser maior do que zero.")
                   else:


                      try:
                         nova_proxima_execucao = proxima_apos_edicao(
                             recorrencia_encontrada, nova_frequencia_recorrencia,
                             novo_dia, novo_mes, novo_dia_semana, hoje,
                         )
                      except ValueError as erro:
                         st.error(str(erro))
                         return

                      conexao = conectar_banco()
                      cursor = conexao.cursor()

                      cursor.execute(

                         """
                         UPDATE dbo.recorrencias
                         SET valor = ?,
                               descricao = ?,
                               categoria = ?,
                               frequencia = ?,
                               dia = ?,
                               mes = ?,
                               dia_semana = ?,
                               classificacao = ?,
                               proxima_execucao = ?
                            WHERE id_recorrencia = ?
                            AND id_usuario = ?
                            """,
                            novo_valor_recorrencia,
                            nova_descricao_recorrencia,
                            nova_categoria_recorrencia,
                            nova_frequencia_recorrencia,
                            novo_dia,
                            novo_mes,
                            novo_dia_semana,
                            nova_classificacao_recorrencia,
                            nova_proxima_execucao,
                            recorrencia_encontrada["id_recorrencia"],
                            st.session_state.usuario_atual["id_usuario"]
                      )
                      conexao.commit()
                      cursor.close()
                      conexao.close()
                      encerrar_edicao_recorrencia(st.session_state)
                      st.session_state.recorrencia_alterada_sucesso = True
                      st.rerun(scope="fragment")




          btn_excluir_recorrencia = st.button(
                "Excluir Recorrência Selecionada",
                key="btn_excluir_recorrencia")

          if st.session_state.get("recorrencia_excluida_sucesso", False):
                st.success("Recorrência excluída com sucesso!")
                st.session_state.recorrencia_excluida_sucesso = False

          if btn_excluir_recorrencia and not selecao_invalidada:
             conexao = conectar_banco()
             cursor = conexao.cursor()

             cursor.execute(
                """
                SELECT
                      (SELECT COUNT(*)
                      FROM dbo.receitas
                      WHERE id_recorrencia = ? AND id_usuario = ?)
                      +
                      (SELECT COUNT(*)
                      FROM dbo.gastos
                      WHERE id_recorrencia = ? AND id_usuario = ?)
                """,
                recorrencia_encontrada["id_recorrencia"],
                st.session_state.usuario_atual["id_usuario"],
                recorrencia_encontrada["id_recorrencia"],
                st.session_state.usuario_atual["id_usuario"]
             )

             possui_historico = cursor.fetchone()[0] > 0

             if possui_historico:
                cursor.execute(
                      """
                      UPDATE dbo.recorrencias
                      SET ativa = 0
                      WHERE id_recorrencia = ?
                      AND id_usuario = ?
                      """,
                      recorrencia_encontrada["id_recorrencia"],
                      st.session_state.usuario_atual["id_usuario"]
                )

             else:
                cursor.execute(
                      """
                      DELETE FROM dbo.recorrencias
                      WHERE id_recorrencia = ?
                      AND id_usuario = ?
                      """,
                      recorrencia_encontrada["id_recorrencia"],
                      st.session_state.usuario_atual["id_usuario"]
                )

             conexao.commit()
             cursor.close()
             conexao.close()

             st.session_state.pop("recorrencia_selecionada", None)
             st.session_state.pop("_recorrencia_em_edicao", None)
             st.session_state.alterar_recorrencia = False
             st.session_state.recorrencia_excluida_sucesso = True
             st.rerun(scope="fragment")
    else:
        st.session_state.pop("recorrencia_selecionada", None)
        st.session_state.pop("_recorrencia_em_edicao", None)
        st.session_state.alterar_recorrencia = False
        st.session_state._recorrencias_usuario = st.session_state.usuario_atual["id_usuario"]
        exibir_resumo_e_cartoes([], tipo_pessoa, termo_gasto, conectar_banco)
        st.info("Nenhuma recorrência cadastrada.")
