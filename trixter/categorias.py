"""Categorias padrao de receitas e gastos para PF e PJ."""

CATEGORIAS = {
    "Pessoa Física": {
        "Receita": [
            "Salário",
            "Trabalho Autônomo e Freelance",
            "Aposentadoria e Pensão",
            "Rendimentos Financeiros",
            "Aluguéis Recebidos",
            "Vendas",
            "Reembolsos",
            "Outros"
        ],
        "Gasto": [
            "Alimentação",
            "Moradia",
            "Água, Energia e Internet",
            "Transporte",
            "Saúde",
            "Educação",
            "Lazer",
            "Assinaturas",
            "Compras Pessoais",
            "Impostos e Taxas",
            "Outros"
        ]
    },

    "Pessoa Jurídica": {
        "Receita": [
            "Vendas de Produtos",
            "Prestação de Serviços",
            "Rendimentos Financeiros",
            "Outros"
        ],
        "Gasto": [
            "Folha de Pagamento",
            "Pró-labore",
            "Aluguel",
            "Água, Energia e Internet",
            "Mercadorias e Insumos",
            "Impostos e Taxas",
            "Marketing",
            "Software e Tecnologia",
            "Serviços Contratados",
            "Transporte e Entregas",
            "Tarifas Bancárias e de Pagamento",
            "Equipamentos",
            "Manutenção",
            "Outros"
        ]
    }
}


def listar_categorias(cursor, id_usuario, tipo_pessoa, tipo):
    """Combina categorias padrão e salvas; o chamador gerencia a conexão."""
    # A interface usa "Despesa", mas o dicionário e o banco usam "Gasto".
    tipos = {"gasto": "Gasto", "despesa": "Gasto", "receita": "Receita"}
    tipo_interno = tipos.get(tipo.strip().lower())
    if tipo_interno is None:
        raise ValueError("Tipo deve ser Gasto, Despesa ou Receita.")

    categorias_padrao = CATEGORIAS[tipo_pessoa][tipo_interno]
    # Recupera também nomes usados antes de existir um cadastro de categoria.
    # A tabela é escolhida entre duas constantes, nunca pelo texto do usuário.
    tabela = "gastos" if tipo_interno == "Gasto" else "receitas"
    tipo_banco = tipo_interno.lower()
    tipo_alternativo = "despesa" if tipo_interno == "Gasto" else "receita"
    consulta = f"""
        SELECT nome FROM dbo.categorias
        WHERE id_usuario = ? AND LOWER(tipo) IN (?, ?)
        UNION
        SELECT categoria AS nome FROM dbo.{tabela} WHERE id_usuario = ?
        UNION
        SELECT categoria AS nome FROM dbo.recorrencias
        WHERE id_usuario = ? AND LOWER(tipo) IN (?, ?)
        UNION
        SELECT categoria AS nome FROM dbo.planejamentos
        WHERE id_usuario = ? AND LOWER(tipo) IN (?, ?)
    """
    parametros = [
        id_usuario, tipo_banco, tipo_alternativo,
        id_usuario,
        id_usuario, tipo_banco, tipo_alternativo,
        id_usuario, tipo_banco, tipo_alternativo,
    ]
    if tipo_interno == "Gasto":
        consulta += " UNION SELECT categoria AS nome FROM dbo.orcamentos WHERE id_usuario = ?"
        parametros.append(id_usuario)
    consulta += " ORDER BY nome"
    cursor.execute(consulta, *parametros)
    categorias_usuario = [
        linha[0] for linha in cursor.fetchall()
        if linha[0] is not None and linha[0].strip()
    ]

    # Cria uma nova lista, sem modificar as categorias padrão.
    return list(dict.fromkeys(categorias_padrao + categorias_usuario))
