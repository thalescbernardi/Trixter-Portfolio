"""Selecao por ID, com registros homonimos e conexao inteiramente simulada."""
import pytest
from streamlit.testing.v1 import AppTest


SCRIPT = r'''
import streamlit as st
from datetime import date
from unittest.mock import patch
from trixter import recorrencias_tela as r
from trixter.sessao import garantir_navegacao
usuario = st.selectbox("Usuario ficticio", ["u1", "u2"], key="usuario_teste")
modulo = st.radio("Modulo ficticio", ["gerenciar_recorrencias", "outro"], key="modulo_teste")
st.session_state.tela_atual = modulo
garantir_navegacao(st.session_state)
st.session_state.usuario_atual = {"id_usuario": usuario}
st.session_state.setdefault("alterar_recorrencia", False)
st.session_state.setdefault("consultas", [])
st.session_state.setdefault("historico", False)
if "registros" not in st.session_state:
    st.session_state.registros = [
        {"id_recorrencia": ident, "id_usuario": dono, "tipo": "Receita", "categoria": "Igual",
         "descricao": "Mesmo texto", "valor": valor, "frequencia": "Mensal", "dia": 1,
         "mes": None, "dia_semana": None, "classificacao": None, "ativa": 0,
         "proxima_execucao": date(2099, 1, 1)}
        for ident, dono, valor in [("r1", "u1", 100.0), ("r2", "u1", 200.0), ("r3", "u2", 300.0)]
    ]
class Cursor:
    def execute(self, sql, *args):
        self.sql = " ".join(sql.split())
        self.args = args
        st.session_state.consultas.append((self.sql, args))
        if self.sql.startswith("UPDATE dbo.recorrencias SET valor"):
            assert "WHERE id_recorrencia = ? AND id_usuario = ?" in self.sql
            for row in st.session_state.registros:
                if (row["id_recorrencia"], row["id_usuario"]) == args[-2:]:
                    row["valor"], row["descricao"], row["categoria"] = args[:3]
                    row["frequencia"], row["dia"], row["mes"], row["dia_semana"], row["classificacao"] = args[3:8]
                    row["proxima_execucao"] = args[8]
        elif self.sql.startswith("DELETE"):
            assert "WHERE id_recorrencia = ? AND id_usuario = ?" in self.sql
            st.session_state.registros = [row for row in st.session_state.registros
                if (row["id_recorrencia"], row["id_usuario"]) != args]
        elif self.sql.startswith("UPDATE dbo.recorrencias SET ativa"):
            assert "WHERE id_recorrencia = ? AND id_usuario = ?" in self.sql
            for row in st.session_state.registros:
                if (row["id_recorrencia"], row["id_usuario"]) == args: row["ativa"] = 0
        return self
    def fetchall(self):
        assert "WHERE id_usuario = ?" in self.sql
        rows = [row for row in st.session_state.registros if row["id_usuario"] == self.args[0]]
        nomes = list(st.session_state.registros[0])
        self.description = [(nome,) for nome in nomes]
        return [tuple(row[nome] for nome in nomes) for row in rows]
    def fetchone(self):
        assert self.sql.count("AND id_usuario = ?") == 2
        assert self.args == (st.session_state.recorrencia_selecionada, usuario) * 2
        return (1 if st.session_state.historico else 0,)
    def close(self): pass
class Conn:
    def cursor(self): return Cursor()
    def commit(self): pass
    def close(self): pass
# AppTest executa scripts completos. Simula a passagem ao proximo ciclo apos
# o rerun do fragmento, sem alterar o escopo usado pelo codigo de producao.
rerun_original = st.rerun
def proximo_ciclo(**kwargs):
    assert kwargs == {"scope": "fragment"}
    rerun_original()
with patch.object(r, "listar_categorias", return_value=["Igual"]), \
     patch.object(r, "exibir_resumo_e_cartoes"), \
     patch.object(st, "rerun", side_effect=proximo_ciclo):
    if modulo == "gerenciar_recorrencias":
        r.exibir_recorrencias(Conn, "Pessoa F\u00edsica", "Gasto")
'''


@pytest.fixture
def app(monkeypatch):
    import pyodbc
    from unittest.mock import Mock
    monkeypatch.setattr(pyodbc, "connect", Mock(side_effect=AssertionError("SQL real proibido")))
    tela = AppTest.from_string(SCRIPT).run()
    assert not tela.exception
    return tela


def escritas(app):
    return [(sql, args) for sql, args in app.session_state.consultas
            if sql.startswith(("UPDATE", "DELETE", "INSERT"))]


def test_homonimos_tem_ids_e_rotulos_distintos(app):
    seletor = app.selectbox(key="recorrencia_selecionada")
    assert len(seletor.options) == 2
    assert len(set(seletor.options)) == 2
    assert all("Igual - Mesmo texto" in rotulo for rotulo in seletor.options)
    assert all(ident not in rotulo for ident in ("r1", "r2") for rotulo in seletor.options)
    assert seletor.options == ["Igual - Mesmo texto (opção 1)", "Igual - Mesmo texto (opção 2)"]
    for ident in ("r1", "r2"):
        app.selectbox(key="recorrencia_selecionada").select(ident).run()
        assert not app.exception
        assert app.session_state.recorrencia_selecionada == ident
    assert not escritas(app)


@pytest.mark.parametrize("ident,valor", [("r1", 100.0), ("r2", 200.0)])
def test_editar_altera_somente_id_e_usuario_selecionados(app, ident, valor):
    app.selectbox(key="recorrencia_selecionada").select(ident).run()
    app.button(key="btn_alterar_recorrencia").click().run()
    assert not app.exception
    assert app.number_input(key=f"novo_valor_recorrencia_{ident}").value == valor
    app.number_input(key=f"novo_valor_recorrencia_{ident}").set_value(450.0).run()
    next(b for b in app.button if b.label == "Salvar Altera\u00e7\u00f5es").click().run()
    assert not app.exception
    assert len(escritas(app)) == 1
    assert escritas(app)[0][1][-2:] == (ident, "u1")
    assert {row["id_recorrencia"]: row["valor"] for row in app.session_state.registros} == {
        "r1": 450.0 if ident == "r1" else 100.0,
        "r2": 450.0 if ident == "r2" else 200.0,
        "r3": 300.0,
    }


@pytest.mark.parametrize("ident", ["r1", "r2"])
def test_excluir_remove_somente_id_selecionado_e_limpa_editor(app, ident):
    app.selectbox(key="recorrencia_selecionada").select(ident).run()
    app.button(key="btn_alterar_recorrencia").click().run()
    app.button(key="btn_excluir_recorrencia").click().run()
    assert not app.exception
    assert escritas(app)[0][0].startswith("DELETE")
    assert escritas(app)[0][1] == (ident, "u1")
    assert all(row["id_recorrencia"] != ident for row in app.session_state.registros)
    assert app.session_state.recorrencia_selecionada != ident
    assert app.session_state.alterar_recorrencia is False
    assert "_recorrencia_em_edicao" not in app.session_state


def test_com_historico_preserva_desativacao_em_vez_de_exclusao(app):
    app.session_state.historico = True
    for row in app.session_state.registros:
        if row["id_recorrencia"] == "r2":
            row["ativa"] = 1
    app.run()
    app.selectbox(key="recorrencia_selecionada").select("r2").run()
    app.button(key="btn_excluir_recorrencia").click().run()
    assert not app.exception
    assert len(app.session_state.registros) == 3
    assert len(escritas(app)) == 1
    assert escritas(app)[0][0].startswith("UPDATE dbo.recorrencias SET ativa = 0")
    assert escritas(app)[0][1] == ("r2", "u1")
    assert next(row for row in app.session_state.registros if row["id_recorrencia"] == "r2")["ativa"] == 0


def test_troca_usuario_invalida_identidade_e_edicao(app):
    app.selectbox(key="recorrencia_selecionada").select("r2").run()
    app.button(key="btn_alterar_recorrencia").click().run()
    app.selectbox(key="usuario_teste").select("u2").run()
    assert not app.exception
    assert app.session_state.recorrencia_selecionada == "r3"
    assert app.session_state.alterar_recorrencia is False
    assert "_recorrencia_em_edicao" not in app.session_state
    assert not escritas(app)


def test_troca_selecao_fecha_editor_anterior(app):
    app.button(key="btn_alterar_recorrencia").click().run()
    app.selectbox(key="recorrencia_selecionada").select("r2").run()
    assert not app.exception
    assert app.session_state.alterar_recorrencia is False
    assert not any(w.key == "novo_valor_recorrencia_r1" for w in app.number_input)
    assert not escritas(app)


def test_selecao_obsoleta_nao_exclui_outro_registro(app):
    app.selectbox(key="recorrencia_selecionada").select("r2").run()
    app.session_state.registros = [r for r in app.session_state.registros if r["id_recorrencia"] != "r2"]
    app.button(key="btn_excluir_recorrencia").click().run()
    assert not app.exception
    assert app.session_state.recorrencia_selecionada == "r1"
    assert not escritas(app)


def test_edicao_mensal_carrega_dias_7_e_15_e_preserva_digitacao(app):
    for row in app.session_state.registros:
        if row["id_recorrencia"] == "r1": row.update(dia=7, valor=1700.0)
        if row["id_recorrencia"] == "r2": row.update(dia=15, valor=1200.0)
    app.run()
    for ident, dia, valor in [("r1", 7, 1700.0), ("r2", 15, 1200.0), ("r1", 7, 1700.0)]:
        app.selectbox(key="recorrencia_selecionada").select(ident).run()
        app.button(key="btn_alterar_recorrencia").click().run()
        assert not app.exception
        assert app.number_input(key=f"novo_dia_recorrencia_{ident}").value == dia
        assert app.number_input(key=f"novo_valor_recorrencia_{ident}").value == valor
        app.number_input(key=f"novo_dia_recorrencia_{ident}").set_value(20).run()
        app.text_input(key=f"nova_descricao_recorrencia_{ident}").set_value("Edicao ficticia").run()
        assert app.number_input(key=f"novo_dia_recorrencia_{ident}").value == 20
    assert not escritas(app)
    assert [row["dia"] for row in app.session_state.registros[:2]] == [7, 15]


@pytest.mark.parametrize("frequencia,dia,mes,semana", [
    ("Mensal", 15, None, None), ("Anual", 23, 11, None),
    ("Semanal", None, None, 5), ("Semanal", None, None, 7),
])
def test_salvar_sem_alterar_regra_preserva_valores_do_registro(app, frequencia, dia, mes, semana):
    for row in app.session_state.registros:
        if row["id_recorrencia"] == "r2":
            row.update(frequencia=frequencia, dia=dia, mes=mes, dia_semana=semana, classificacao="Fixo")
    app.run()
    app.selectbox(key="recorrencia_selecionada").select("r2").run()
    app.button(key="btn_alterar_recorrencia").click().run()
    assert not app.exception
    if frequencia == "Mensal":
        assert app.number_input(key="novo_dia_recorrencia_r2").value == dia
    elif frequencia == "Anual":
        assert app.number_input(key="novo_dia_anual_recorrencia_r2").value == dia
        assert app.number_input(key="novo_mes_anual_recorrencia_r2").value == mes
    else:
        esperado = "Sexta-feira" if semana == 5 else "Domingo"
        assert app.selectbox(key="novo_dia_semana_recorrencia_r2").value == esperado
    assert app.selectbox(key="nova_classificacao_recorrencia_r2").value == "Fixo"
    assert app.selectbox(key="nova_categoria_recorrencia_r2").value == "Igual"
    next(b for b in app.button if b.label == "Salvar Altera\u00e7\u00f5es").click().run()
    assert not app.exception
    args = escritas(app)[0][1]
    assert args[3:8] == (frequencia, dia, mes, semana, "Fixo")
    assert args[-2:] == ("r2", "u1")


def test_reabrir_editor_descarta_dia_antigo_da_sessao(app):
    app.session_state.registros[0]["dia"] = 7
    app.session_state["novo_dia_recorrencia_r1"] = 1
    app.button(key="btn_alterar_recorrencia").click().run()
    assert not app.exception
    assert app.number_input(key="novo_dia_recorrencia_r1").value == 7


def test_salvar_dia_grava_proxima_execucao_e_fecha_editor(app):
    from datetime import date
    app.session_state.registros[0].update(dia=15, valor=1200.0, proxima_execucao=date(2099, 11, 15))
    app.run()
    app.button(key="btn_alterar_recorrencia").click().run()
    app.number_input(key="novo_dia_recorrencia_r1").set_value(18).run()
    next(b for b in app.button if b.label == "Salvar Altera\u00e7\u00f5es").click().run()
    assert not app.exception
    sql, args = escritas(app)[0]
    assert "proxima_execucao = ?" in sql
    assert args[4] == 18
    assert args[8] == date(2099, 11, 18)
    assert app.session_state.registros[0]["proxima_execucao"] == date(2099, 11, 18)
    assert app.session_state.alterar_recorrencia is False
    assert "_recorrencia_em_edicao" not in app.session_state
    assert any("alterada com sucesso" in aviso.value for aviso in app.success)
    # AppTest pode acumular deltas anteriores ao rerun; reconstruir a arvore
    # sem serializar widgets cujo estado ja foi removido (como no Historico).
    app._run()
    assert not app.exception
    assert not any(w.key == "novo_dia_recorrencia_r1" for w in app.number_input)


def test_sair_e_retornar_fecha_editor_e_reabrir_carrega_banco(app):
    app.session_state.registros[0]["dia"] = 7
    app.button(key="btn_alterar_recorrencia").click().run()
    app.number_input(key="novo_dia_recorrencia_r1").set_value(18).run()
    app.run()
    assert app.number_input(key="novo_dia_recorrencia_r1").value == 18
    app.radio(key="modulo_teste").set_value("outro").run()
    assert not app.exception
    assert app.session_state.alterar_recorrencia is False
    assert "_recorrencia_em_edicao" not in app.session_state
    app.radio(key="modulo_teste").set_value("gerenciar_recorrencias").run()
    assert not app.exception
    assert not any(w.key == "novo_dia_recorrencia_r1" for w in app.number_input)
    app.button(key="btn_alterar_recorrencia").click().run()
    assert app.number_input(key="novo_dia_recorrencia_r1").value == 7
    assert not escritas(app)
