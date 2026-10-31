"""Semantica mensal com consultas simuladas, sem conexoes reais."""
import pytest
from streamlit.testing.v1 import AppTest


SCRIPT = r'''
import streamlit as st
from unittest.mock import patch
from trixter import inteligencia as i
st.session_state.usuario_atual = {"id_usuario": "ficticio"}
st.session_state.setdefault("base", {
    "receitas_atual": (650, 1), "gastos_atual": (250, 1),
    "receitas_anterior": (0, 0), "gastos_anterior": (0, 0),
})
st.session_state.setdefault("categorias_atual", {"Alimentacao": 250})
st.session_state.setdefault("categorias_anterior", {})
class Cursor:
    def execute(self, sql, *args):
        assert sql.lstrip().startswith("SELECT")
        assert "id_usuario = ?" in sql
        assert args[0] == "ficticio"
        self.sql = sql
    def fetchone(self):
        if "dbo.orcamentos" in self.sql: return (700,)
        if "TOP 1" in self.sql:
            itens = st.session_state.categorias_atual
            return max(itens.items(), key=lambda x:x[1]) if itens else None
        assert "COUNT(*)" in self.sql
        tabela = "receitas" if "dbo.receitas" in self.sql else "gastos"
        periodo = "anterior" if "DATEADD" in self.sql else "atual"
        return st.session_state.base[tabela + "_" + periodo]
    def fetchall(self):
        return list((st.session_state.categorias_anterior if "DATEADD" in self.sql
                     else st.session_state.categorias_atual).items())
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def close(self): pass
with patch.object(i, "consultar_custos_mes", return_value={}), patch.object(i, "exibir_custos_mes"), \
     patch.object(i, "consultar_margem_mes"), patch.object(i, "exibir_margem"), \
     patch.object(i, "exibir_reserva_tributos"), patch.object(i, "consultar_concentracao_mes"), \
     patch.object(i, "exibir_concentracao"):
    i.exibir_inteligencia(Conn, st.session_state.get("tipo", "Pessoa F\u00edsica"), "Gasto")
'''


@pytest.fixture
def app(monkeypatch):
    import pyodbc
    from unittest.mock import Mock
    monkeypatch.setattr(pyodbc, "connect", Mock(side_effect=AssertionError("SQL real proibido")))
    tela = AppTest.from_string(SCRIPT).run()
    assert not tela.exception
    return tela


def textos(app):
    return " ".join(w.value for w in [*app.info, *app.success])


def anterior(app, receita, gasto, categorias):
    app.session_state.base["receitas_anterior"] = receita
    app.session_state.base["gastos_anterior"] = gasto
    app.session_state.categorias_anterior = categorias
    app.run()
    assert not app.exception
    return textos(app)


@pytest.mark.parametrize("tipo", ["Pessoa Física", "Pessoa Jurídica"])
def test_sem_mes_anterior_nao_conclui_melhora_ou_aumento(tipo, app):
    app.session_state.tipo = tipo
    app.run()
    assert not app.exception
    texto = textos(app)
    assert "Não há movimentações registradas no mês anterior" in texto
    assert "saldo registrado neste mês é R$ 400,00" in texto
    assert "Seu saldo mensal melhorou" not in texto
    assert "Seu saldo mensal piorou" not in texto
    assert "A categoria que mais aumentou" not in texto
    assert "Não há gastos registrados nos dois meses" in texto
    assert "não há base para concluir melhora ou piora" in app.success[0].value
    valores = {m.label: m.value for m in app.metric}
    assert valores == {"Receitas do mês": "R$ 650,00", "Gastos do mês": "R$ 250,00", "Taxa de poupança": "61.5%"}
    assert "consumiu 35.7% do orçamento" in texto
    prioridade = next(w.value for w in app.info if w.value.startswith("Prioridade do mês:"))
    assert "representa 100.0%" in prioridade
    assert "aumentaram" not in prioridade


def test_dois_meses_com_registros_preservam_comparacoes_e_prioridade(app):
    texto = anterior(app, (600, 1), (200, 1), {"Alimentacao": 200})
    assert "gastos aumentaram 25.0%" in texto
    assert "saldo mensal permaneceu igual" in texto
    assert "aumento de R$ 50,00" in texto
    assert "Prioridade do mês: seus Gastos aumentaram 25.0%" in texto
    assert "base para concluir" not in texto


@pytest.mark.parametrize("receita,gasto,categorias,saldo,ressalva", [
    ((500, 1), (0, 0), {}, "piorou em R$ 100,00", "apenas receitas, sem gastos registrados"),
    ((0, 0), (100, 1), {"Alimentacao": 100}, "melhorou em R$ 500,00", "apenas gastos, sem receitas registradas"),
])
def test_mes_anterior_parcial_explica_referencia_sem_eliminar_saldo_valido(app, receita, gasto, categorias, saldo, ressalva):
    texto = anterior(app, receita, gasto, categorias)
    assert saldo in texto
    assert ressalva in texto
    assert ressalva in app.success[0].value
    assert "comparar completamente" in texto


def test_registros_anteriores_somando_zero_nao_sao_ausencia(app):
    texto = anterior(app, (0, 1), (0, 1), {"Alimentacao": 0})
    assert "somam R$ 0,00" in texto
    assert "base zero" in texto
    assert "saldo mensal melhorou em R$ 400,00" in texto
    assert "aumento de R$ 250,00" in texto
    assert "Não há movimentações registradas no mês anterior" not in texto


def test_categoria_nova_com_base_anterior_valida_explica_zero(app):
    texto = anterior(app, (600, 1), (200, 1), {"Transporte": 200})
    assert "aumento de R$ 250,00" in texto
    assert "Essa categoria não teve gastos registrados" in texto
    assert "usa R$ 0,00 como referência" in texto


def test_mes_atual_sem_registros_nao_afirma_queda_ou_piora(app):
    app.session_state.base.update(receitas_atual=(0, 0), gastos_atual=(0, 0))
    app.session_state.categorias_atual = {}
    texto = anterior(app, (650, 1), (250, 1), {"Alimentacao": 250})
    assert "Não há movimentações registradas no mês atual para comparar o saldo" in texto
    assert "diminuíram" not in texto
    assert "Seu saldo mensal piorou" not in texto
    assert "Nenhuma categoria apresentou aumento" not in texto


def test_gastos_atuais_registrados_com_zero_permitam_queda_percentual(app):
    app.session_state.base["gastos_atual"] = (0, 1)
    app.session_state.categorias_atual = {"Alimentacao": 0}
    texto = anterior(app, (650, 1), (250, 1), {"Alimentacao": 250})
    assert "diminuíram 100.0%" in texto
    assert "Nenhuma categoria apresentou aumento" in texto


@pytest.mark.parametrize("receita,gasto,esperado_gastos,esperado_saldo", [
    ((1000, 1), (500, 1), "diminuíram 50.0%", "piorou em R$ 100,00"),
    ((300, 1), (100, 1), "aumentaram 150.0%", "melhorou em R$ 200,00"),
])
def test_melhora_e_piora_validas_continuam_no_resumo(app, receita, gasto, esperado_gastos, esperado_saldo):
    texto = anterior(app, receita, gasto, {"Alimentacao": gasto[0]})
    assert esperado_gastos in texto
    assert esperado_saldo in texto
    assert esperado_saldo in app.success[0].value
