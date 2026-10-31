"""Formulário compartilhado de gasto e de receita."""
import uuid
from contextlib import closing
from datetime import date, datetime

import streamlit as st

from .clientes import normalizar_cliente
from .credencial import exigir_operacao

AJUDA = {
    "gasto": (
        "Fixo: compromisso como aluguel ou mensalidade, mesmo com reajustes. "
        "Variável: acompanha o consumo ou a atividade, como supermercado ou insumos. "
        "Essa classificação é independente da categoria e da recorrência."
    ),
    "receita": (
        "Fixo: valor previsível, como salário ou mensalidade de serviço contratada. "
        "Variável: depende de vendas, comissões ou trabalhos avulsos. "
        "Fixo não é garantia de recebimento. Recorrência é uma informação separada."
    ),
}
EXEMPLO = {
    "gasto": "Ex.: Almoço no restaurante",
    "receita": "Ex.: Salário do mês",
}


@st.fragment
def exibir_lancamento(
    conectar,
    listar,
    tipo_pessoa,
    termo,
    artigo,
    chave,
    tipo_lista,
    tipo_categoria,
    tabela,
):
    """Cadastro de um lançamento. Receita também pede o cliente, depois da classificação."""
    if not exigir_operacao(conectar):
        return
    if tabela not in ("gastos", "receitas"):
        raise ValueError(tabela)
    com_cliente = tabela == "receitas"
    novo = "uma nova" if artigo == "a" else "um novo"
    rotulo = f"d{artigo} {termo.lower()}"

    st.header(f"Cadastrar {termo}")
    st.write(f"Preencha as informações abaixo para registrar {novo} {termo.lower()}.")

    if st.session_state.get(f"limpar_campos_{chave}", False):
        st.session_state[f"data_{chave}"] = date.today()
        st.session_state[f"valor_{chave}"] = 0.0
        st.session_state[f"descrição_{chave}"] = ""
        st.session_state.pop(f"categoria_{chave}", None)
        st.session_state.pop(f"classificacao_{chave}", None)
        st.session_state[f"limpar_campos_{chave}"] = False

    # Converte o valor antigo do campo de texto em sessoes ja abertas.
    if isinstance(st.session_state.get(f"data_{chave}"), str):
        try:
            st.session_state[f"data_{chave}"] = datetime.strptime(
                st.session_state[f"data_{chave}"], "%d/%m/%Y"
            ).date()
        except ValueError:
            st.session_state[f"data_{chave}"] = date.today()

    data_lancamento = st.date_input(
        f"Data {rotulo}:",
        format="DD/MM/YYYY",
        key=f"data_{chave}",
    )

    with closing(conectar()) as conexao_categorias:
        with closing(conexao_categorias.cursor()) as cursor_categorias:
            categorias = listar(
                cursor_categorias,
                st.session_state.usuario_atual["id_usuario"],
                tipo_pessoa,
                tipo_lista,
            )

    categoria = st.selectbox(
        f"Selecione a categoria {rotulo}:",
        categorias,
        key=f"categoria_{chave}",
    )
    if categoria == "Outros":
        categoria = st.text_input(
            f"Digite a categoria {rotulo}:",
            key=f"categoria_{chave}_outros",
        )

    classificacao = st.selectbox(
        f"Classificação {rotulo}:",
        [None, "Fixo", "Variável"],
        format_func=lambda valor: "Não classificado" if valor is None else valor,
        key=f"classificacao_{chave}",
        help=AJUDA[chave],
    )
    valor = st.number_input(
        f"Digite o valor {rotulo}:",
        min_value=0.0,
        step=10.0,
        key=f"valor_{chave}",
    )
    descricao = st.text_input(
        f"Digite uma descrição {rotulo}:",
        placeholder=EXEMPLO[chave],
        key=f"descrição_{chave}",
        help=(
        "Informe apenas o necessário para identificar a movimentação. "
        "Evite CPF, diagnósticos, informações de saúde ou outros "
        "dados pessoais sensíveis."
    ),
    )
    cliente = None
    if com_cliente:
        cliente = normalizar_cliente(st.text_input(
            "Cliente:",
            placeholder="Ex.: Aurora Serviços",
            max_chars=80,
            key="cliente_receita",
            help= ("Opcional. Serve para analisar concentração e atraso. "
            "Não cria cadastro de tomador. Informe apenas o nome "
            "necessário à organização financeira. Evite CPF, "
            "diagnósticos e informações pessoais sensíveis."
        ),
        ))

    rotulo_botao = "Salvar Receita" if com_cliente else f"Salvar {termo.lower()}"
    if st.button(rotulo_botao, type="primary"):
        if data_lancamento is None:
            st.error("Selecione uma data antes de salvar.")
        elif not categoria.strip():
            st.error(
                f"A categoria {rotulo} não pode estar vazia. "
                "Por favor, preencha a categoria."
            )
        elif valor <= 0:
            st.error(
                f"O valor {rotulo} deve ser maior que zero. "
                "Por favor, insira um valor válido."
            )
        else:
            _gravar(
                conectar,
                tabela,
                tipo_categoria,
                st.session_state.usuario_atual["id_usuario"],
                data_lancamento,
                categoria,
                valor,
                descricao,
                classificacao,
                cliente,
            )
            st.session_state[f"limpar_campos_{chave}"] = True
            st.session_state[f"mensagem_{chave}"] = True
            st.rerun()

    if st.session_state.get(f"mensagem_{chave}", False):
        termo_cadastrado = "cadastrada" if artigo == "a" else "cadastrado"
        st.success(f"✅ {termo} {termo_cadastrado} com sucesso!")
        st.session_state[f"mensagem_{chave}"] = False


def _gravar(conectar, tabela, tipo_categoria, usuario_id, data_lancamento, categoria, valor, descricao, classificacao, cliente):
    conexao = conectar()
    cursor = conexao.cursor()
    if tabela == "receitas":
        cursor.execute(
            """
            INSERT INTO dbo.receitas(
               id_transacao,
               id_usuario,
               data,
               categoria,
               valor,
               descricao,
               classificacao,
               cliente)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            str(uuid.uuid4()),
            usuario_id,
            data_lancamento,
            categoria,
            valor,
            descricao,
            classificacao,
            cliente,
        )
    else:
        cursor.execute(
            """
            INSERT INTO dbo.gastos(
             id_transacao,
             id_usuario,
             data,
             categoria,
             valor,
             descricao,
             classificacao)
            VALUES (?,?,?,?,?,?,?)
            """,
            str(uuid.uuid4()),
            usuario_id,
            data_lancamento,
            categoria,
            valor,
            descricao,
            classificacao,
        )
    conexao.commit()
    cursor.close()
    conexao.close()

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(
        """
        SELECT 1
        FROM dbo.categorias
        WHERE id_usuario = ?
        AND nome = ?
        AND tipo = ?
        """,
        usuario_id,
        categoria,
        tipo_categoria,
    )
    categoria_ja_existe = cursor.fetchone() is not None
    cursor.close()
    conexao.close()

    if categoria_ja_existe:
        return

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(
        """
        INSERT INTO dbo.categorias(
          id_usuario,
          nome,
          tipo
          )
        VALUES (?,?,?)
        """,
        usuario_id,
        categoria,
        tipo_categoria,
    )
    conexao.commit()
    cursor.close()
    conexao.close()
