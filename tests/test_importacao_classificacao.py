import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("pessoa", ["Pessoa Física", "Pessoa Jurídica"])
@pytest.mark.parametrize("modo", ["Comprovante individual", "Extrato bancário"])
@pytest.mark.parametrize("tipo", ["Receita", "Gasto"])
@pytest.mark.parametrize("classificacao", ["Não classificado", "Fixo", "Variável"])
def test_importacao_grava_classificacao(pessoa, modo, tipo, classificacao):
    fonte = (Path(__file__).resolve().parents[1] / "Gerenciador de Gastos V2.py").read_text(encoding="utf-8")
    bloco = next(n for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.If)
                 and ast.unparse(n.test) == "st.session_state.tela_atual == 'importar_pdf'")
    setup = '''
from trixter.importacao import exibir_importacao_pdf
import streamlit as st
import pandas as pd
import re, uuid
from datetime import datetime
from contextlib import closing
from types import SimpleNamespace
st.session_state.setdefault("usuario_atual", {"id_usuario": "u1"})
st.session_state.setdefault("gravacoes", [])
st.session_state.setdefault("commits", 0)
st.session_state.tela_atual = "importar_pdf"
area_importar_pdf = st.empty()
st.file_uploader = lambda *a, **k: b"%PDF-1.4 PDF simulado"
class Cursor:
    def execute(self, sql, *args):
        assert sql.count("?") == len(args)
        if "INSERT INTO" in sql:
            colunas = sql.split("(", 1)[1].split(")", 1)[0].split(",")
            assert len(colunas) == len(args)
            st.session_state.gravacoes.append((sql, args))
    def fetchone(self): return None
    def close(self): pass
class Conexao:
    def cursor(self): return Cursor()
    def commit(self): st.session_state.commits += 1
    def close(self): pass
def conectar_banco(): return Conexao()
def listar_categorias(*args): return ["Teste"]
def formatar_moeda(valor): return str(valor)
def editor(df, **kwargs):
    assert "classificacao" in kwargs["column_config"]
    df = df.copy()
    df["categoria"] = "Teste"
    df["classificacao"] = escolha
    return df
st.data_editor = editor
'''
    texto = ("Valor original: R$ 50,00\nRealizado em 29/09/2026\nPara Teste"
             if modo == "Comprovante individual" else
             f"29/09/2026 Teste {'-' if tipo == 'Gasto' else ''}50,00")
    setup += f'''\ntipo_pessoa = {pessoa!r}
termo_gasto = {('Despesa' if pessoa == 'Pessoa Jurídica' else 'Gasto')!r}
escolha = {classificacao!r}
PdfReader = lambda arquivo: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: {texto!r})])
'''
    app = AppTest.from_string(setup + ast.unparse(bloco), default_timeout=15).run()
    assert not app.exception
    app.selectbox(key="tipo_pdf_importacao").select(modo).run()
    if modo == "Comprovante individual":
        app.selectbox(key="tipo_importacao").select("Receita" if tipo == "Receita" else ("Despesa" if pessoa == "Pessoa Jurídica" else "Gasto")).run()
        app.selectbox(key="classificacao_importacao_pdf").select(classificacao).run()
    chave = "btn_confirmar_importacao_pdf" if modo == "Comprovante individual" else "btn_confirmar_importacao_extrato"
    app.button(key=chave).click().run()
    assert not app.exception
    assert len(app.session_state.gravacoes) == 1
    sql, args = app.session_state.gravacoes[0]
    assert ("dbo.receitas" if tipo == "Receita" else "dbo.gastos") in sql
    assert "tipo_transacao" not in sql
    assert args[-1] == (None if classificacao == "Não classificado" else classificacao)
    assert args[1] == "u1"
    assert app.session_state.commits == 1
    assert app.success
