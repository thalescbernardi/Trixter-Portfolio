"""Modelo empresarial para contas temporárias de demonstração."""
from contextlib import closing
from datetime import date, datetime
from calendar import monthrange
from secrets import token_urlsafe
from .planejamento import deslocar_mes
from uuid import uuid4

from .categorias import CATEGORIAS
from .senha import gerar_hash_senha


def hash_senha_demo():
    """Hash bcrypt de uma senha aleatória. A senha em claro não sai daqui."""
    return gerar_hash_senha(token_urlsafe(32))


def criar_demo_pj(conectar_banco, hoje=None):
    hoje = hoje or date.today()
    usuario = {
        "id_usuario": str(uuid4()), "senha": hash_senha_demo(),
        "tipo_pessoa": "Pessoa Jurídica", "nome": "Empresa Demo",
        "nome_empresa": "Aurora Serviços — Demo", "cpf": None, "cnpj": None,
        "renda_mensal": None, "faturamento_mensal": 20000,
        "objetivo_financeiro": None, "valor_objetivo": 0,
        "data_objetivo": None,
        "valor_acumulado_meta": 0, "onboarding_concluido": True,
        "conta_demo": True, "receber_relatorio_mensal": False,
        "receber_alertas": False,
    }
    usuario["email"] = f'{usuario["id_usuario"]}@demo.trixter.local'
    usuario["data_entrada"] = datetime.now()
    usuario["ultimo_acesso"] = None
    with closing(conectar_banco()) as conexao:
        try:
            with closing(conexao.cursor()) as cursor:
                from .credencial import reservar_email
                if not reservar_email(cursor, usuario["email"], usuario["id_usuario"]):
                    raise RuntimeError(
                        "Não foi possível reservar o e-mail da conta demonstrativa."
                    )
                colunas = list(usuario)
                cursor.execute(
                    f'INSERT INTO dbo.usuarios ({", ".join(colunas)}) '
                    f'VALUES ({", ".join("?" for _ in colunas)})',
                    *(usuario[coluna] for coluna in colunas),
                )
                for tipo, categorias in CATEGORIAS["Pessoa Jurídica"].items():
                    for categoria in categorias:
                        cursor.execute(
                            "INSERT INTO dbo.categorias (id_usuario, nome, tipo) VALUES (?, ?, ?)",
                            usuario["id_usuario"], categoria, tipo.lower(),
                        )
                exemplos = {
                    "receitas": [
                        ("Prestação de Serviços", "Contrato mensal de serviços", 15000),
                        ("Vendas de Produtos", "Venda de materiais", 5000),
                    ],
                    "gastos": [
                        ("Folha de Pagamento", "Equipe administrativa", 6000),
                        ("Aluguel", "Sala comercial", 2000),
                        ("Software e Tecnologia", "Assinaturas de sistemas", 450),
                        ("Marketing", "Campanha de divulgação", 900),
                        ("Mercadorias e Insumos", "Materiais para atendimento", 1800),
                    ],
                }
                for deslocamento in (-3, -2, -1, 0):
                    mes_base = deslocar_mes(hoje, deslocamento)
                    ultimo_dia = hoje.day if deslocamento == 0 else monthrange(mes_base.year, mes_base.month)[1]
                    for tabela, itens in exemplos.items():
                        for indice, (categoria, descricao, valor) in enumerate(itens):
                            cursor.execute(
                                f"INSERT INTO dbo.{tabela} "
                                "(id_transacao, id_usuario, data, categoria, descricao, valor) "
                                "VALUES (?, ?, ?, ?, ?, ?)",
                                str(uuid4()), usuario["id_usuario"], mes_base.replace(day=1 + indice * (ultimo_dia - 1) // max(1, len(itens) - 1)),
                                categoria, descricao, valor,
                            )
                for categoria, limite in [("Marketing", 1000), ("Mercadorias e Insumos", 2500)]:
                    cursor.execute(
                        "INSERT INTO dbo.orcamentos "
                        "(id_orcamento, id_usuario, categoria, mes, ano, valor_limite) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        str(uuid4()), usuario["id_usuario"], categoria, hoje.month, hoje.year, limite,
                    )
                for tipo, categoria, valor in [
                    ("Receita", "Prestação de Serviços", 15000),
                    ("Receita", "Vendas de Produtos", 5000),
                    ("Despesa", "Folha de Pagamento", 6000),
                    ("Despesa", "Aluguel", 2000),
                    ("Despesa", "Software e Tecnologia", 500),
                    ("Despesa", "Marketing", 1000),
                    ("Despesa", "Mercadorias e Insumos", 2500),
                ]:
                    cursor.execute(
                        "INSERT INTO dbo.planejamentos "
                        "(id_planejamento, id_usuario, tipo, categoria, descricao, valor, data) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        str(uuid4()), usuario["id_usuario"], tipo, categoria,
                        "Previsão mensal demonstrativa", valor, hoje,
                    )
            conexao.commit()
        except Exception:
            conexao.rollback()
            raise
    usuario.pop("senha", None)
    usuario["credencial_versao"] = 1
    return usuario
