from datetime import date
from decimal import Decimal

import pytest
from streamlit.testing.v1 import AppTest

from trixter.inicio import comparar_faturamento, consultar_resumo


def test_resumo_isola_usuario_e_virada_de_ano():
    class Cursor:
        def __init__(self):
            self.chamadas = []
            self.valores = iter([(Decimal('100.10'), Decimal('20.10')), (Decimal('110.20'), Decimal('10.05'))])
            self.fechado = False
        def execute(self, sql, *args): self.chamadas.append((sql, args))
        def fetchone(self): return next(self.valores)
        def close(self): self.fechado = True
    c = Cursor()
    class Conn:
        def cursor(self): return c
    assert consultar_resumo(Conn(), 'usuario-a', date(2026, 12, 5)) == (
        Decimal('-10.10'), Decimal('20.10'), Decimal('10.05'))
    for sql, args in c.chamadas:
        assert 'WHERE id_usuario = ?' in sql
        assert args == (date(2026, 12, 1), date(2027, 1, 1), 'usuario-a')
    assert c.fechado


@pytest.mark.parametrize('termo', ['Gasto', 'Despesa'])
@pytest.mark.parametrize('destino', ['gasto', 'receita'])
def test_inicio_metricas_e_atalhos(termo, destino):
    setup = '''
import streamlit as st
from trixter.inicio import renderizar_resumo, aplicar_estilo
st.session_state.setdefault('tela_atual', 'menu')
st.session_state.setdefault('menu_conta_aberto', True)
st.session_state.setdefault('menu_alertas_aberto', False)
class Cursor:
    def execute(self, *args): pass
    def fetchone(self): return (0, 0)
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def close(self): pass
aplicar_estilo(st.session_state.tela_atual)
if st.session_state.tela_atual == 'menu':
    renderizar_resumo(Conn, {'id_usuario': 'teste'}, TERMO)
'''
    app = AppTest.from_string(setup.replace('TERMO', repr(termo))).run()
    assert not app.exception
    assert len(app.metric) == 3
    assert app.metric[2].label == f'{termo}s do mês'
    assert all(m.value == 'R$ 0,00' for m in app.metric)
    app.button(key=f'inicio_cadastrar_{destino}').click().run()
    assert not app.exception
    assert app.session_state.tela_atual == f'cadastrar_{destino}'
    assert not app.session_state.menu_conta_aberto
    assert not app.metric


def test_faturamento_real_contra_o_cadastrado():
    abaixo = comparar_faturamento(10000, Decimal("8000"))
    assert abaixo["diferenca"] == Decimal("-2000")
    assert abaixo["percentual"] == Decimal("0.8")
    assert "abaixo" in abaixo["texto"]
    assert "acima" in comparar_faturamento(1000, 1500)["texto"]
    igual = comparar_faturamento(1000, 1000)
    assert igual["diferenca"] == 0
    assert "igual" in igual["texto"]
    sem_base = comparar_faturamento(None, 500)
    assert sem_base["percentual"] is None
    assert "cadastrado" in sem_base["texto"]


def test_inicio_pj_mostra_faturamento_cadastrado_e_realizado():
    app = AppTest.from_string('''
import streamlit as st
from trixter.inicio import renderizar_resumo
class Cursor:
    def execute(self, *args): pass
    def fetchone(self): return (0, 8000)
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def close(self): pass
renderizar_resumo(Conn, {
    "id_usuario": "empresa",
    "tipo_pessoa": "Pessoa Jur\\u00eddica",
    "faturamento_mensal": 10000,
}, "Despesa")
''').run()
    assert not app.exception
    rotulos = [metrica.label for metrica in app.metric]
    assert "Faturamento cadastrado" in rotulos
    assert "Faturamento do mês" in rotulos
    assert "abaixo" in app.caption[-1].value


def test_inicio_pf_mostra_renda_cadastrada_e_do_mes():
    app = AppTest.from_string('''
import streamlit as st
from trixter.inicio import renderizar_resumo
class Cursor:
    def execute(self, *args): pass
    def fetchone(self): return (0, 8000)
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def close(self): pass
renderizar_resumo(Conn, {
    "id_usuario": "pessoa",
    "tipo_pessoa": "Pessoa F\\u00edsica",
    "renda_mensal": 10000,
}, "Gasto")
''').run()
    assert not app.exception
    rotulos = [metrica.label for metrica in app.metric]
    assert "Renda cadastrada" in rotulos
    assert "Renda do mês" in rotulos
    assert "A renda do mês" in app.caption[-1].value
    assert "abaixo" in app.caption[-1].value


def test_destaque_da_meta_usa_o_nome_da_tela():
    app = AppTest.from_string('''
import streamlit as st
from trixter.inicio import aplicar_estilo
aplicar_estilo("visualizar_meta")
''').run()
    assert not app.exception
    destaque = [
        bloco.proto.body for bloco in app.get("html")
        if "btn_acompanhar_meta" in bloco.proto.body and "EEE4D1" in bloco.proto.body
    ]
    assert destaque


def test_meta_mostra_se_o_saldo_cobre_o_objetivo():
    from trixter.inicio import comparar_meta_saldo
    cobre = comparar_meta_saldo(12000, 10000)
    assert cobre["folga"] == Decimal(2000)
    assert "sobra" in cobre["texto"]
    assert comparar_meta_saldo(10000, 10000)["texto"] == "O saldo atual cobre a meta."
    falta = comparar_meta_saldo(4000, 10000)
    assert falta["folga"] == Decimal(-6000)
    assert "faltam" in falta["texto"]
