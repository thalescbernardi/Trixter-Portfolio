import ast
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


def _app_lancamento(tipo, pessoa="Pessoa Física"):
    fonte = (Path(__file__).resolve().parents[1] / "Gerenciador de Gastos V2.py").read_text(encoding="utf-8")
    bloco = next(n for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.If)
                 and ast.unparse(n.test) == f"st.session_state.tela_atual == 'cadastrar_{tipo}'")
    setup = '''
import streamlit as st
from datetime import datetime, date
from contextlib import closing
import uuid
from trixter.clientes import normalizar_cliente
from trixter.lancamento import exibir_lancamento
st.session_state.setdefault("usuario_logado", True)
st.session_state.setdefault("usuario_atual", {"id_usuario": "teste", "credencial_versao": 1})
st.session_state.setdefault("versao_banco", 1)
st.session_state.setdefault("verificacoes", [])
st.session_state.setdefault("fragmentos_verificados", [])
st.session_state.setdefault("listagens", [])
st.session_state.setdefault("gravacoes", [])
termo_gasto = "Gasto"
artigo_gasto = "o"
tipo_pessoa = "Pessoa Física"
CATEGORIAS = {tipo_pessoa: {"Gasto": ["Casa", "Outros", ""], "Receita": ["Salário", "Outros", ""]}}
class Cursor:
    def execute(self, sql, *args):
        self.sql = sql
        if "SELECT credencial_versao" in sql:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            st.session_state.verificacoes.append(args)
            st.session_state.fragmentos_verificados.append(get_script_run_ctx().current_fragment_id)
        if "INSERT INTO dbo.gastos" in sql or "INSERT INTO dbo.receitas" in sql:
            st.session_state.gravacoes.append(args)
    def fetchone(self):
        if "SELECT credencial_versao" in self.sql:
            return None if st.session_state.get("conta_excluida") else (st.session_state.versao_banco,)
        return (1,)
    def close(self): pass
class Conexao:
    def cursor(self): return Cursor()
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass
def conectar_banco():
    if st.session_state.get("falha_banco"):
        import pyodbc
        raise pyodbc.OperationalError("08S01", "falha ficticia")
    return Conexao()
def listar_categorias(cursor, id_usuario, tipo_pessoa, tipo):
    st.session_state.listagens.append((id_usuario, tipo_pessoa, tipo))
    return CATEGORIAS[tipo_pessoa][tipo]
'''
    setup += f'''
tipo_pessoa = {pessoa!r}
termo_gasto = "Despesa" if tipo_pessoa == "Pessoa Jurídica" else "Gasto"
artigo_gasto = "a" if tipo_pessoa == "Pessoa Jurídica" else "o"
CATEGORIAS[tipo_pessoa] = CATEGORIAS["Pessoa Física"]
st.session_state.tela_atual = "cadastrar_{tipo}"
st.session_state.setdefault("data_{tipo}", "24/09/2026")
area_cadastrar_{tipo} = st.empty()
'''
    return AppTest.from_string(setup + ast.unparse(bloco)).run()


@pytest.mark.parametrize("tipo,pessoa,classificacao", [
    (tipo, pessoa, classificacao)
      for tipo in ("gasto", "receita")
      for pessoa in ("Pessoa Física", "Pessoa Jurídica")
      for classificacao in (None, "Fixo", "Variável")
])
def test_calendario_validacao_gravacao_e_limpeza(tipo, pessoa, classificacao):
    app = _app_lancamento(tipo, pessoa)
    assert not app.exception
    assert app.date_input[0].value == date(2026, 9, 24)

    # Valor inválido não grava, não limpa a data e não anuncia sucesso.
    app.button[0].click().run()
    assert not app.exception and app.error and not app.success
    assert not app.session_state.gravacoes
    assert app.date_input[0].value == date(2026, 9, 24)

    app.number_input[0].set_value(50).run()
    app.selectbox[0].select("").run()
    app.button[0].click().run()
    assert app.error and not app.success and not app.session_state.gravacoes

    app.selectbox[0].select("Casa" if tipo == "gasto" else "Salário").run()
    app.date_input[0].set_value(None).run()
    app.button[0].click().run()
    assert app.error and not app.success and not app.session_state.gravacoes

    # SQL recebe um objeto date; o rerun restaura a data atual no calendário.
    escolhida = date(2026, 9, 20)
    app.selectbox(key=f"classificacao_{tipo}").select(classificacao).run()
    app.date_input[0].set_value(escolhida).run()
    app.button[0].click().run()
    assert not app.exception and app.success
    assert len(app.session_state.gravacoes) == 1
    assert app.session_state.gravacoes[0][2] == escolhida
    assert app.date_input[0].value == date.today()
    assert app.session_state.gravacoes[0][6] == classificacao
    assert app.selectbox(key=f"classificacao_{tipo}").value is None


@pytest.mark.parametrize("tipo", ["gasto", "receita"])
def test_lancamento_verifica_sessao_dentro_do_fragmento_a_cada_interacao(tipo):
    app = _app_lancamento(tipo)
    verificacoes = len(app.session_state.verificacoes)
    app.selectbox(key=f"classificacao_{tipo}").select("Fixo").run()
    assert not app.exception
    assert len(app.session_state.verificacoes) > verificacoes
    assert all(item == ("teste",) for item in app.session_state.verificacoes)
    assert all(app.session_state.fragmentos_verificados)
    assert app.session_state.gravacoes == []
    assert len(app.date_input) == 1
    assert len(app.selectbox) == 2
    assert len(app.button) == 1


@pytest.mark.parametrize("tipo", ["gasto", "receita"])
@pytest.mark.parametrize("situacao", ["senha_alterada", "conta_excluida"])
def test_lancamento_revogado_na_interacao_nao_consulta_categorias_nem_grava(tipo, situacao):
    app = _app_lancamento(tipo)
    app.number_input[0].set_value(50).run()
    listagens = len(app.session_state.listagens)
    if situacao == "senha_alterada":
        app.session_state.versao_banco = 2
    else:
        app.session_state.conta_excluida = True
    app.button[0].click().run()
    assert not app.exception
    assert not app.session_state.usuario_logado
    assert app.session_state.usuario_atual is None
    assert app.session_state.gravacoes == []
    assert len(app.session_state.listagens) == listagens
    assert not app.date_input and not app.selectbox and not app.number_input


@pytest.mark.parametrize("tipo", ["gasto", "receita"])
def test_lancamento_banco_indisponivel_bloqueia_sem_encerrar_sessao(tipo):
    from trixter.credencial import MENSAGEM_SESSAO_INDISPONIVEL

    app = _app_lancamento(tipo)
    listagens = len(app.session_state.listagens)
    app.session_state.falha_banco = True
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state.usuario_logado
    assert app.session_state.gravacoes == []
    assert len(app.session_state.listagens) == listagens
    assert any(MENSAGEM_SESSAO_INDISPONIVEL in erro.value for erro in app.error)
    assert not app.date_input and not app.selectbox


@pytest.mark.parametrize("tipo", ["gasto", "receita"])
@pytest.mark.parametrize("pessoa", ["Pessoa Física", "Pessoa Jurídica"])
def test_categoria_outros_valida_grava_e_limpa_os_campos(tipo, pessoa):
    app = _app_lancamento(tipo, pessoa)
    assert app.session_state.listagens[-1] == ("teste", pessoa, "Gasto" if tipo == "gasto" else "Receita")
    app.selectbox(key=f"categoria_{tipo}").select("Outros").run()
    app.number_input[0].set_value(25).run()
    app.text_input(key=f"categoria_{tipo}_outros").set_value("   ")
    app.button[0].click().run()
    assert app.error and not app.session_state.gravacoes
    app.text_input(key=f"categoria_{tipo}_outros").set_value("Categoria fictícia")
    app.text_input(key=f"descrição_{tipo}").set_value("Descrição fictícia")
    app.selectbox(key=f"classificacao_{tipo}").select("Variável").run()
    if tipo == "receita":
        app.text_input(key="cliente_receita").set_value("  Cliente   fictício  ")
    app.button[0].click().run()
    assert not app.exception and app.success
    gravado, = app.session_state.gravacoes
    assert gravado[1] == "teste"
    assert gravado[3:7] == ("Categoria fictícia", 25.0, "Descrição fictícia", "Variável")
    if tipo == "receita":
        assert gravado[7] == "Cliente fictício"
    assert app.number_input[0].value == 0.0
    assert app.text_input(key=f"descrição_{tipo}").value == ""
    assert app.selectbox(key=f"classificacao_{tipo}").value is None
    assert app.date_input[0].value == date.today()
