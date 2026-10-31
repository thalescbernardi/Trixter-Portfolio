import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("tipo,termo,campo,titulo_percentual", [
    (r"Pessoa F\u00edsica", "Gasto", "renda_mensal", "Receitas em relação à renda informada"),
    (r"Pessoa Jur\u00eddica", "Despesa", "faturamento_mensal", "Receitas em relação ao faturamento informado"),
])
def test_resumo_mostra_resultado_do_mes_e_percentual(tipo, termo, campo, titulo_percentual):
    app = AppTest.from_string(f'''
import streamlit as st
from trixter.saldo import exibir_saldo
st.session_state.usuario_atual = {{"id_usuario": "u", "{campo}": 1000}}
class Cursor:
    def __init__(self):
        self.i = 0
    def execute(self, sql, *a): pass
    def fetchone(self):
        valor = ((5000, 800), (2000, 300))[self.i]
        self.i += 1
        return valor
    def close(self): pass
class Conn:
    def __init__(self):
        self.c = Cursor()
    def cursor(self): return self.c
    def close(self): pass
exibir_saldo(Conn, "{tipo}", "{termo}")
''').run()
    assert not app.exception
    assert app.header[0].value == "Resumo Financeiro"
    texto = " ".join(bloco.value for bloco in app.markdown)
    assert titulo_percentual in texto
    assert "80,0%" in texto
    referencia = "renda informada" if campo == "renda_mensal" else "faturamento informado"
    assert f"R$ 800,00 em receitas registradas de R$ 1.000,00 de {referencia}." in texto
    descricao = (
        "Acompanhe suas receitas registradas em relação à renda mensal informada "
        if campo == "renda_mensal" else
        "Acompanhe suas receitas registradas em relação ao faturamento mensal informado "
    ) + "e veja o resultado financeiro do mês."
    assert descricao in texto
    assert "recebidos de" not in texto
    assert "Resultado do mês" in texto
    assert "R$ 500,00" in texto
    assert "R$ 800,00 em receitas − R$ 300,00 em gastos" in texto
    assert "#2E7D32" in texto
    assert "Saldo acumulado" not in texto
    assert "5.000,00" not in texto
    assert not app.caption


def test_resumo_sem_referencia_explica_por_que_nao_ha_percentual():
    app = AppTest.from_string(r'''
import streamlit as st
from trixter.saldo import exibir_saldo
st.session_state.usuario_atual = {"id_usuario": "u", "renda_mensal": 0}
class Cursor:
    def execute(self, sql, *a): pass
    def fetchone(self): return (0, 0)
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def close(self): pass
exibir_saldo(Conn, "Pessoa F\u00edsica", "Gasto")
''').run()
    assert not app.exception
    texto = " ".join(bloco.value for bloco in app.markdown)
    assert "Sem referência" in texto
    assert "R$ 0,00" in texto
    assert "cadastrado" in app.caption[-1].value


def test_configuracoes_mostra_as_tres_preferencias():
    app = AppTest.from_string('''
import streamlit as st
from trixter.configuracoes import exibir_configuracoes
st.session_state.usuario_logado = True
st.session_state.usuario_atual = {"id_usuario": "u", "credencial_versao": 1}
class Cursor:
    def execute(self, sql, *a): self.sql = sql
    def fetchone(self): return (1, 5, 0, 1)
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def close(self): pass
    def commit(self): pass
exibir_configuracoes(Conn)
''').run()
    assert not app.exception
    rotulos = [item.label for item in app.checkbox]
    assert rotulos == [
        "Receber relatório mensal por e-mail",
        "Receber alertas por e-mail",
        "Receber resumo semanal por e-mail",
    ]
