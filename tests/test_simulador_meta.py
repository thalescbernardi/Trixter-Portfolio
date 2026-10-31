import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


def test_prazo_meta_apresenta_data_brasileira_sem_mudar_valor():
    fonte = Path("trixter/meta.py").read_text(encoding="utf-8")
    campo = next(n for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.Assign)
                 and isinstance(n.value, ast.Call)
                 and ast.unparse(n.value.func) == "st.date_input")
    setup = '''
import streamlit as st
from datetime import date, timedelta
st.session_state.data_objetivo = date.today() + timedelta(days=30)
'''
    app = AppTest.from_string(setup + ast.unparse(campo)).run()
    assert not app.exception
    from datetime import date, timedelta
    widget = app.date_input(key="data_objetivo")
    assert widget.proto.format == "DD/MM/YYYY"
    assert widget.value == date.today() + timedelta(days=30)


@pytest.mark.parametrize("tipo,quantidade", [("Pessoa Física", 4), ("Pessoa Jurídica", 0)])
def test_meta_so_para_pf_mesmo_com_meta_antiga_no_banco(tipo, quantidade):
    fonte = Path("trixter/simulador.py").read_text(encoding="utf-8")
    simulador = next(n for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.FunctionDef)
                     and n.name == "exibir_simulador")
    guarda = next(n for n in ast.walk(simulador) if isinstance(n, ast.If)
                  and ast.unparse(n.test) == "tipo_pessoa == 'Pessoa Física'")
    setup = '''
import streamlit as st
from trixter.relatorios import formatar_moeda
st.session_state.usuario_atual = {"id_usuario": "teste"}
st.session_state.consultas = 0
class Cursor:
    def execute(self, *args): st.session_state.consultas += 1
    def fetchone(self): return ("Meta antiga", 30000, None, 8000)
cursor = Cursor()
saldo_medio = 1000
saldo_simulado = 2000
'''
    app = AppTest.from_string(setup + f"\ntipo_pessoa = {tipo!r}\n" + ast.unparse(guarda)).run()
    assert not app.exception
    assert len(app.metric) == quantidade
    assert app.session_state.consultas == (1 if quantidade else 0)


def test_reserva_nao_entra_no_bloco_da_meta_pf():
    fonte = Path("trixter/simulador.py").read_text(encoding="utf-8")
    simulador = next(n for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.FunctionDef)
                     and n.name == "exibir_simulador")
    guarda = next(n for n in ast.walk(simulador) if isinstance(n, ast.If)
                  and ast.unparse(n.test) == "tipo_pessoa == 'Pessoa Física'")
    assert guarda.orelse == []
    chamadas = [n for n in ast.walk(simulador) if isinstance(n, ast.Call)
                and ast.unparse(n.func) == "exibir_reserva_simulador"]
    assert len(chamadas) == 1
