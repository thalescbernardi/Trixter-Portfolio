import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("pessoa", ["Pessoa Física", "Pessoa Jurídica"])
@pytest.mark.parametrize("tipo", ["Gasto", "Receita"])
@pytest.mark.parametrize("inicial,nova", [(None, "Fixo"), ("Fixo", "Variável"), ("Variável", None)])
def test_historico_edita_classificacao(pessoa, tipo, inicial, nova):
    fonte = (Path(__file__).resolve().parents[1] / "Gerenciador de Gastos V2.py").read_text(encoding="utf-8")
    bloco = next(n for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.If)
                 and ast.unparse(n.test) == "st.session_state.tela_atual == 'visualizar_historico'")
    setup = '''
from trixter.historico_tela import exibir_historico
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
def formatar_moeda(valor): return f"R$ {valor:.2f}"
st.session_state.setdefault("usuario_atual", {"id_usuario": "usuario-teste"})
st.session_state.setdefault("gravacoes", [])
st.session_state.tela_atual = "visualizar_historico"
area_visualizar_historico = st.empty()
class Cursor:
    description = [(c,) for c in ("id_transacao", "id_usuario", "data", "descricao", "valor", "categoria", "tipo", "classificacao", "cliente")]
    def execute(self, sql, *args):
        self.rowcount = 1
        if "UPDATE" in sql:
            assert "classificacao = ?" in sql
            assert "AND id_usuario = ?" in sql
            st.session_state.gravacoes.append((sql, args))
            st.session_state.classificacao_salva = args[4]
        else:
            assert sql.count("classificacao") == 2
            assert args == ("usuario-teste", "usuario-teste")
    def fetchall(self):
        return [("transacao-teste", "usuario-teste", datetime(2026, 9, 29), "Teste", 50.0, "Categoria", tipo, st.session_state.classificacao_salva, None)]
    def close(self): pass
class Conexao:
    def cursor(self): return Cursor()
    def commit(self): pass
    def close(self): pass
def conectar_banco(): return Conexao()
'''
    setup += f"\ntipo_pessoa = {pessoa!r}\ntipo = {tipo!r}\ntermo_gasto = {'Despesa' if pessoa == 'Pessoa Jurídica' else 'Gasto'!r}\nst.session_state.setdefault('classificacao_salva', {inicial!r})\n"
    app = AppTest.from_string(setup + ast.unparse(bloco), default_timeout=15).run()
    assert not app.exception
    assert app.dataframe[0].value["Classificação"].iloc[0] == (inicial or "Não classificado")
    app.button(key="btn_alterar_transacao").click().run()
    assert not app.exception
    assert app.selectbox(key="editar_classificacao").value == (inicial or "Não classificado")
    app.selectbox(key="editar_classificacao").select(nova or "Não classificado").run()
    assert not app.exception
    next(b for b in app.button if b.label == "Salvar Alterações").click().run()
    assert not app.exception
    sql, args = app.session_state.gravacoes[0]
    assert ("dbo.gastos" if tipo == "Gasto" else "dbo.receitas") in sql
    assert args[4:] == (nova, "transacao-teste", "usuario-teste")
    assert app.dataframe[0].value["Classificação"].iloc[0] == (nova or "Não classificado")
    assert app.success

    # AppTest 1.51 acumula deltas do editor antes do st.rerun() do salvamento,
    # embora o Streamlit já tenha removido seus estados. Reconstrói a árvore
    # sem serializar esses widgets obsoletos, preservando a sessão e o código real.
    assert "editando_movimentacao" not in app.session_state
    app._run()
    assert not app.exception
    assert not any(w.key == "editar_categoria" for w in app.text_input)
    assert len(app.session_state.gravacoes) == 1

    # O filtro afeta a tabela e os totais, incluindo registros sem classificação.
    correspondente = nova or "Não classificado"
    app.selectbox(key="filtro_classificacao_historico").select(correspondente).run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 1
    assert app.metric[0 if tipo == "Receita" else 1].value == "R$ 50.00"
    diferente = "Fixo" if correspondente != "Fixo" else "Variável"
    app.selectbox(key="filtro_classificacao_historico").select(diferente).run()
    assert not app.exception
    assert app.dataframe[0].value.empty
    assert all(m.value == "R$ 0.00" for m in app.metric)
    assert app.info
    app.selectbox(key="filtro_classificacao_historico").select("Todos").run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 1


def test_historico_sem_movimentacao_avisa():
    app = AppTest.from_string('''
import streamlit as st
from trixter.historico_tela import exibir_historico
st.session_state.usuario_atual = {"id_usuario": "u"}
class Cursor:
    description = [(c,) for c in ("id_transacao", "id_usuario", "data", "descricao", "valor", "categoria", "tipo", "classificacao", "cliente")]
    def execute(self, sql, *a): pass
    def fetchall(self): return []
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def close(self): pass
exibir_historico(Conn, "Pessoa F\\u00edsica", "Gasto", lambda valor: valor)
''').run()
    assert not app.exception
    assert any("Nenhuma movimentação cadastrada" in aviso.value for aviso in app.info)
    assert not app.dataframe
