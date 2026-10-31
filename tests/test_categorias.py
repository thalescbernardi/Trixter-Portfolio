from copy import deepcopy
import sqlite3

import pytest

from trixter.categorias import CATEGORIAS, listar_categorias


class CursorCategorias:
    def execute(self, sql, *parametros):
        self.sql = sql
        self.parametros = parametros

    def fetchall(self):
        return [("Marketing",), ("Embalagens",), ("Embalagens",)]


@pytest.mark.parametrize("tipo", ["Gasto", "Despesa", " despesa "])
def test_categorias_personalizadas_sem_duplicar_ou_modificar_padrao(tipo):
    cursor = CursorCategorias()
    original = deepcopy(CATEGORIAS)
    resultado = listar_categorias(cursor, "empresa-a", "Pessoa Jurídica", tipo)
    assert resultado.count("Marketing") == 1
    assert resultado.count("Embalagens") == 1
    assert resultado[:len(original["Pessoa Jurídica"]["Gasto"])] == original["Pessoa Jurídica"]["Gasto"]
    assert CATEGORIAS == original
    assert "WHERE id_usuario = ? AND LOWER(tipo) IN (?, ?)" in cursor.sql
    assert cursor.parametros[:3] == ("empresa-a", "gasto", "despesa")


def test_receitas_sem_categorias_salvas():
    cursor = CursorCategorias()
    cursor.fetchall = lambda: []
    resultado = listar_categorias(cursor, "pessoa-b", "Pessoa Física", "Receita")
    assert resultado == CATEGORIAS["Pessoa Física"]["Receita"]
    assert resultado is not CATEGORIAS["Pessoa Física"]["Receita"]
    assert cursor.parametros[:3] == ("pessoa-b", "receita", "receita")


def test_tipo_invalido_nao_consulta_banco():
    cursor = CursorCategorias()
    with pytest.raises(ValueError):
        listar_categorias(cursor, "empresa-a", "Pessoa Jurídica", "invalido")
    assert not hasattr(cursor, "sql")


def test_recupera_historico_sem_misturar_contas_ou_tipos():
    # Executa a consulta em banco temporário, sem acessar o Azure.
    with sqlite3.connect(":memory:") as banco:
        banco.execute("ATTACH DATABASE ':memory:' AS dbo")
        for tabela in ("categorias", "gastos", "receitas", "recorrencias", "planejamentos", "orcamentos"):
            coluna = "nome" if tabela == "categorias" else "categoria"
            banco.execute(f"CREATE TABLE dbo.{tabela} (id_usuario TEXT, {coluna} TEXT, tipo TEXT)")
            banco.execute(f"INSERT INTO dbo.{tabela} VALUES (?, ?, ?)", ("a", tabela, "Despesa"))
            banco.execute(f"INSERT INTO dbo.{tabela} VALUES (?, ?, ?)", ("b", "Outra conta", "Despesa"))
        banco.execute("INSERT INTO dbo.planejamentos VALUES ('a', 'Receita antiga', 'Receita')")

        class Cursor:
            def execute(self, sql, *args):
                self.resultado = banco.execute(sql, args)

            def fetchall(self):
                return self.resultado.fetchall()

        gastos = listar_categorias(Cursor(), "a", "Pessoa Jurídica", "Despesa")
        receitas = listar_categorias(Cursor(), "a", "Pessoa Jurídica", "Receita")
        assert {"categorias", "gastos", "recorrencias", "planejamentos", "orcamentos"} <= set(gastos)
        assert "Outra conta" not in gastos + receitas
        assert "Receita antiga" not in gastos
        assert "receitas" not in gastos
        assert "Receita antiga" in receitas
        assert "receitas" in receitas
        assert "orcamentos" not in receitas
        assert "Fornecedores" not in gastos
