"""Cenarios ficticios do Simulador, sem inserir dados em qualquer banco."""
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from trixter.planejamento import consultar_base_simulador, simular_reserva


SCRIPT = r'''
import streamlit as st
from unittest.mock import patch
from trixter import simulador as s
st.session_state.usuario_atual = {"id_usuario": "ficticio"}
st.session_state.setdefault("totais_base", (12000.0, 7500.0))
st.session_state.setdefault("historico", True)
st.session_state.valores_internos = []
class Cursor:
    def execute(self, sql, *args):
        assert sql.lstrip().startswith("SELECT")
        assert "WHERE id_usuario = ?" in sql
        assert args[0] == "ficticio"
        self.sql = sql
    def fetchone(self):
        if "COUNT(*)" in self.sql:
            indice = 0 if "dbo.receitas" in self.sql else 1
            return (st.session_state.totais_base[indice], 3 if st.session_state.historico else 0)
        if "classificacao" in self.sql: return (6000.0,)
        if "objetivo_financeiro" in self.sql: return None
        return (9000.0,) if "dbo.receitas" in self.sql else (6000.0,)
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def close(self): pass
formatar_original = s.formatar_moeda
def registrar(valor):
    st.session_state.valores_internos.append(float(valor))
    return formatar_original(valor)
with patch.object(s, "formatar_moeda", side_effect=registrar):
    s.exibir_simulador(Conn, "Pessoa F\u00edsica", "Gasto")
'''


@pytest.fixture
def app(monkeypatch):
    import pyodbc
    monkeypatch.setattr(pyodbc, "connect", Mock(side_effect=AssertionError("SQL real proibido")))
    tela = AppTest.from_string(SCRIPT).run()
    assert not tela.exception
    return tela


def cenario(app, reducao, aumento, meses):
    app.slider[0].set_value(reducao)
    app.slider[1].set_value(aumento)
    next(w for w in app.number_input if w.label == "Por quantos meses deseja simular ?").set_value(meses)
    app.run()
    assert not app.exception
    return {m.label: m.value for m in app.metric}


def test_cenario_principal_confere_interno_e_exibicao(app):
    valores = cenario(app, 20, 10, 12)
    assert valores["Receita mensal simulada"] == "R$ 4.400,00"
    assert valores["Gasto mensal simulado"] == "R$ 2.000,00"
    assert valores["Saldo médio mensal"] == "R$ 1.500,00"
    assert valores["Saldo mensal simulado"] == "R$ 2.400,00"
    assert valores["Acumulado no cenário atual"] == "R$ 18.000,00"
    assert valores["Acumulado no cenário simulado"] == "R$ 28.800,00"
    assert valores["Ganho adicional no período"] == "R$ 10.800,00"
    assert app.session_state.valores_internos == pytest.approx([
        4000, 2500, 1500, 4400, 2000, 2400, 900, 18000, 28800, 10800,
    ])
    # A reserva usa o saldo real completo (3000), nao o acumulado simulado.
    assert valores["Meses cobertos pelo saldo"] == "1.5"
    assert valores["Reserva desejada"] == "R$ 6.000,00"
    assert valores["Falta para a reserva"] == "R$ 3.000,00"


@pytest.mark.parametrize("reducao,aumento,meses,receita,gasto,acumulado", [
    (0, 0, 1, 4000, 2500, 1500),
    (100, 100, 120, 8000, 0, 960000),
    (100, 0, 6, 4000, 0, 24000),
    (0, 100, 24, 8000, 2500, 132000),
    (20, 10, 3, 4400, 2000, 7200),
])
def test_limites_e_periodos_diferentes(app, reducao, aumento, meses, receita, gasto, acumulado):
    cenario(app, reducao, aumento, meses)
    internos = app.session_state.valores_internos
    assert internos[3:6] == pytest.approx([receita, gasto, receita - gasto])
    assert internos[7] == pytest.approx(1500 * meses)
    assert internos[8] == pytest.approx(acumulado)
    assert internos[9] == pytest.approx(acumulado - 1500 * meses)
    for slider in app.slider:
        assert (slider.proto.min, slider.proto.max, slider.proto.step) == (0, 100, 5)
    periodo = next(w for w in app.number_input if w.label == "Por quantos meses deseja simular ?")
    assert (periodo.proto.min, periodo.proto.max) == (1, 120)


@pytest.mark.parametrize("totais,historico,esperado", [
    ((0.0, 0.0), False, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    ((3000.0, 6000.0), True, [1000, 2000, -1000, 1100, 1600, -500, 500, -12000, -6000, 6000]),
])
def test_sem_historico_e_saldo_negativo(app, totais, historico, esperado):
    app.session_state.totais_base = totais
    app.session_state.historico = historico
    valores = cenario(app, 20, 10, 12)
    assert app.session_state.valores_internos == pytest.approx(esperado)
    if not historico:
        assert any("Sem movimentações" in w.value for w in app.warning)
        assert valores["Acumulado no cenário simulado"] == "R$ 0,00"
    else:
        assert valores["Saldo mensal simulado"] == "-R$ 500,00"
        assert valores["Acumulado no cenário simulado"] == "-R$ 6.000,00"


def test_precisao_mantida_antes_da_formatacao_monetaria(app):
    app.session_state.totais_base = (12000.01, 7500.01)
    valores = cenario(app, 20, 10, 12)
    internos = app.session_state.valores_internos
    receita = Decimal("12000.01") / 3 * Decimal("1.10")
    gasto = Decimal("7500.01") / 3 * Decimal("0.80")
    assert internos[3] == pytest.approx(float(receita), abs=1e-8)
    assert internos[4] == pytest.approx(float(gasto), abs=1e-8)
    assert internos[8] == pytest.approx(float((receita - gasto) * 12), abs=1e-8)
    assert valores["Saldo mensal simulado"] == "R$ 2.400,00"
    assert valores["Acumulado no cenário simulado"] == "R$ 28.800,01"


def test_base_usa_tres_meses_completos_sem_banco():
    cursor = Mock()
    cursor.fetchone.side_effect = [(Decimal("12000"), 3), (Decimal("7500"), 3)]
    assert consultar_base_simulador(cursor, "ficticio", date(2026, 1, 28)) == (
        4000, 2500, True, date(2025, 10, 1), date(2026, 1, 1),
    )
    for chamada in cursor.execute.call_args_list:
        assert chamada.args[1:] == ("ficticio", date(2025, 10, 1), date(2026, 1, 1))
        assert "data >= ? AND data < ?" in chamada.args[0]


@pytest.mark.parametrize("saldo,fixo,meses,receita,cobertos,desejada,falta,falta_mensal", [
    (3000, 2000, 3, 4400, "1.5", 6000, 3000, 0),
    (10000, 2000, 3, 4400, "5", 6000, 0, 0),
    (-1000, 2000, 3, 1500, "0", 6000, 7000, 500),
    (0, 2000, 1, 0, "0", 2000, 2000, 2000),
    (0, 2000, 24, 2500, "0", 48000, 48000, 0),
])
def test_reserva_emergencia(saldo, fixo, meses, receita, cobertos, desejada, falta, falta_mensal):
    resultado = simular_reserva(saldo, fixo, meses, receita)
    assert resultado["meses_cobertos"] == Decimal(cobertos)
    assert resultado["reserva_desejada"] == desejada
    assert resultado["falta"] == falta
    assert resultado["falta_mensal"] == falta_mensal


def test_reserva_sem_custo_fixo_nao_inventa_cobertura():
    resultado = simular_reserva(3000, 0, 3, 4400)
    assert resultado["meses_cobertos"] is None
    assert resultado["reserva_desejada"] is None
