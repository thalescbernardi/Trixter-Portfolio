import ast
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest


@pytest.mark.parametrize("classificacao", [None, "Fixo", "Variável"])
def test_sql_recorrencias_classificacao(classificacao):
    fonte = (Path(__file__).resolve().parents[1] / "trixter" / "recorrencias_tela.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    blocos = [n for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef)
              and n.name in ("exibir_recorrencias", "gravar_ocorrencia")]
    chamadas = [n for bloco in blocos for n in ast.walk(bloco) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == "execute"
                and n.args and isinstance(n.args[0], ast.Constant)
                and "classificacao" in str(n.args[0].value)]
    assert len(chamadas) == 4  # Cadastro, edição e geração de receita/gasto.
    class Cursor:
        def execute(self, sql, *args):
            assert sql.count("?") == len(args)
            if "INSERT" in sql:
                colunas = sql.split("(", 1)[1].split(")", 1)[0].split(",")
                assert len(colunas) == len(args)
                assert args[-1] == classificacao
            else:
                assert args[-4:] == (classificacao, "proxima-ficticia", "r1", "u1")
                assert "proxima_execucao = ?" in sql
                assert "AND id_usuario = ?" in sql
    contexto = dict(cursor=Cursor(), uuid=uuid,
        st=SimpleNamespace(session_state=SimpleNamespace(usuario_atual={"id_usuario": "u1"})),
        recorrencia={"id_usuario": "u1", "id_recorrencia": "r1", "categoria": "Casa", "valor": 10,
                     "descricao": "Teste", "classificacao": classificacao},
        recorrencia_encontrada={"id_recorrencia": "r1"}, nova_proxima_execucao="proxima-ficticia",
        classificacao_recorrencia=classificacao, nova_classificacao_recorrencia=classificacao)
    for nome in ("tipo_recorrencia_interno", "categoria_recorrencia", "descricao_recorrencia", "valor_recorrencia",
                 "frequencia_recorrencia", "data_inicio_recorrencia", "dia_semana_recorrencia", "dia_recorrencia",
                 "mes_recorrencia", "data_execucao", "novo_valor_recorrencia", "nova_descricao_recorrencia",
                 "nova_categoria_recorrencia", "nova_frequencia_recorrencia", "novo_dia", "novo_mes", "novo_dia_semana"):
        contexto[nome] = 1
    for chamada in chamadas:
        exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.Expr(chamada)], type_ignores=[])), "<sql>", "exec"), contexto)
