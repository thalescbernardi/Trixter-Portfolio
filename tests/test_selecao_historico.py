"""Seleção do histórico por tipo e id_transacao, com dados fictícios."""
from datetime import datetime

from streamlit.testing.v1 import AppTest

from trixter.historico_tela import identidade_movimentacao, rotulos_movimentacao
from trixter.sessao import encerrar_sessao_local

_R1 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1"
_R2 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2"
_D1 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1"
_D2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2"
_MESMO = "cccccccc-cccc-cccc-cccc-ccccccccccc3"


def _script(linhas):
    texto = ",\n".join(repr(linha) for linha in linhas)
    return f"""
import datetime
import streamlit as st
from trixter.historico_tela import exibir_historico

def formatar_moeda(valor):
    return f"R$ {{valor:.2f}}"

st.session_state.setdefault("usuario_atual", {{"id_usuario": "usuario-teste"}})
st.session_state.setdefault("chamadas", [])
st.session_state.setdefault("commits", 0)

class Cursor:
    description = [(c,) for c in (
        "id_transacao", "id_usuario", "data", "descricao", "valor", "categoria", "tipo", "classificacao", "cliente"
    )]
    def execute(self, sql, *args):
        self.rowcount = 1
        st.session_state.chamadas.append((" ".join(sql.split()), args))
    def fetchall(self):
        return [
{texto}
        ]
    def close(self):
        pass

class Conexao:
    def cursor(self):
        return Cursor()
    def commit(self):
        st.session_state.commits += 1
    def close(self):
        pass

if st.session_state.pop("invalidar_selecao", False):
    st.session_state.historico_movimentacao_selecionada = "Receita|id-de-outra-conta"
    st.session_state.editando_movimentacao = ("outra-conta", "id-de-outra-conta", "Receita")

exibir_historico(lambda: Conexao(), "Pessoa Física", "Gasto", formatar_moeda)
"""


def _linha(ident, tipo, descricao="Sala", cliente=None):
    return (
        ident, "usuario-teste", datetime(2026, 10, 20), descricao, 50.0,
        "Aluguel", tipo, None, cliente,
    )


def _app(linhas):
    return AppTest.from_string(_script(linhas)).run()


def _escritas(app):
    return [
        (sql, args)
        for sql, args in app.session_state.chamadas
        if sql.startswith("DELETE") or sql.startswith("UPDATE")
    ]


def _botao(app, texto):
    return next(botao for botao in app.button if botao.label == texto)


def test_rotulos_iguais_recebem_a_identidade_completa():
    import pandas as pd
    linhas = pd.DataFrame(
        [_linha(_R1, "Receita"), _linha(_R2, "Receita", "Outra")],
        columns=["id_transacao", "id_usuario", "data", "descricao", "valor", "categoria", "tipo", "classificacao", "cliente"],
    )
    linhas.loc[1, "descricao"] = "Sala"
    rotulos = rotulos_movimentacao(linhas, lambda valor: f"R$ {valor:.2f}")
    assert rotulos[identidade_movimentacao("Receita", _R1)] != rotulos[identidade_movimentacao("Receita", _R2)]
    assert _R1 in rotulos[identidade_movimentacao("Receita", _R1)]
    assert _R2 in rotulos[identidade_movimentacao("Receita", _R2)]
    assert "Receita|" in rotulos[identidade_movimentacao("Receita", _R1)]


def test_duas_receitas_iguais_preservam_o_primeiro_e_o_segundo():
    app = _app([_linha(_R1, "Receita"), _linha(_R2, "Receita")])
    assert not app.exception
    caixa = app.selectbox(key="historico_movimentacao_selecionada")
    assert caixa.value == identidade_movimentacao("Receita", _R1)
    assert len(caixa.options) == 2
    app.run()
    assert not app.exception
    assert app.selectbox(key="historico_movimentacao_selecionada").value == identidade_movimentacao("Receita", _R1)
    _botao(app, "Excluir Movimentação Selecionada").click().run()
    assert not app.exception
    sql, args = _escritas(app)[-1]
    assert "DELETE FROM dbo.receitas" in sql
    assert args == (_R1, "usuario-teste")
    assert "id_usuario = ?" in sql

    app.selectbox(key="historico_movimentacao_selecionada").set_value(
        identidade_movimentacao("Receita", _R2)
    ).run()
    app.run()
    assert not app.exception
    assert app.selectbox(key="historico_movimentacao_selecionada").value == identidade_movimentacao("Receita", _R2)
    antes = len(_escritas(app))
    _botao(app, "Excluir Movimentação Selecionada").click().run()
    sql, args = _escritas(app)[-1]
    assert len(_escritas(app)) == antes + 1
    assert args == (_R2, "usuario-teste")
    assert app.session_state.commits >= 1


def test_duas_despesas_iguais_preservam_os_identificadores():
    app = _app([_linha(_D1, "Gasto"), _linha(_D2, "Gasto")])
    assert not app.exception
    assert app.selectbox(key="historico_movimentacao_selecionada").value == identidade_movimentacao("Gasto", _D1)
    app.run()
    assert app.selectbox(key="historico_movimentacao_selecionada").value == identidade_movimentacao("Gasto", _D1)
    app.button(key="btn_alterar_transacao").click().run()
    assert not app.exception
    _botao(app, "Salvar Alterações").click().run()
    sql, args = _escritas(app)[-1]
    assert "UPDATE dbo.gastos" in sql
    assert args[-2:] == (_D1, "usuario-teste")
    app._run()

    app.selectbox(key="historico_movimentacao_selecionada").set_value(
        identidade_movimentacao("Gasto", _D2)
    ).run()
    app.run()
    assert app.selectbox(key="historico_movimentacao_selecionada").value == identidade_movimentacao("Gasto", _D2)
    app.button(key="btn_alterar_transacao").click().run()
    _botao(app, "Salvar Alterações").click().run()
    sql, args = _escritas(app)[-1]
    assert "UPDATE dbo.gastos" in sql
    assert args[-2:] == (_D2, "usuario-teste")


def test_receita_e_gasto_com_o_mesmo_id_nao_se_confundem():
    app = _app([
        _linha(_MESMO, "Receita", "Da receita"),
        _linha(_MESMO, "Gasto", "Do gasto"),
    ])
    assert not app.exception
    assert app.selectbox(key="historico_movimentacao_selecionada").value == identidade_movimentacao("Receita", _MESMO)
    app.button(key="btn_alterar_transacao").click().run()
    assert not app.exception
    assert app.text_input(key="editar_descricao").value == "Da receita"
    _botao(app, "Salvar Alterações").click().run()
    sql, args = _escritas(app)[-1]
    assert "UPDATE dbo.receitas" in sql
    assert args[-2:] == (_MESMO, "usuario-teste")
    app._run()

    app.selectbox(key="historico_movimentacao_selecionada").set_value(
        identidade_movimentacao("Gasto", _MESMO)
    ).run()
    app.run()
    assert app.selectbox(key="historico_movimentacao_selecionada").value == identidade_movimentacao("Gasto", _MESMO)
    app.button(key="btn_alterar_transacao").click().run()
    assert app.text_input(key="editar_descricao").value == "Do gasto"
    _botao(app, "Excluir Movimentação Selecionada").click().run()
    sql, args = _escritas(app)[-1]
    assert "DELETE FROM dbo.gastos" in sql
    assert args == (_MESMO, "usuario-teste")


def test_troca_de_selecao_descarta_a_edicao_pendente():
    app = _app([_linha(_R1, "Receita", "Primeira"), _linha(_R2, "Receita", "Segunda")])
    app.button(key="btn_alterar_transacao").click().run()
    assert app.session_state.editando_movimentacao == ("usuario-teste", _R1, "Receita")
    app.selectbox(key="historico_movimentacao_selecionada").set_value(
        identidade_movimentacao("Receita", _R2)
    ).run()
    assert "editando_movimentacao" not in app.session_state
    assert _escritas(app) == []
    assert app.session_state.commits == 0


def test_selecao_invalida_nao_altera_nem_exclui():
    app = _app([_linha(_R1, "Receita"), _linha(_R2, "Receita")])
    app.session_state.invalidar_selecao = True
    _botao(app, "Excluir Movimentação Selecionada").click().run()
    assert not app.exception
    assert _escritas(app) == []
    assert app.session_state.commits == 0
    assert "editando_movimentacao" not in app.session_state
    assert app.selectbox(key="historico_movimentacao_selecionada").value in (
        identidade_movimentacao("Receita", _R1),
        identidade_movimentacao("Receita", _R2),
    )

    app.session_state.invalidar_selecao = True
    app.button(key="btn_alterar_transacao").click().run()
    assert not app.exception
    assert _escritas(app) == []
    assert app.session_state.commits == 0


def test_encerrar_sessao_apaga_a_selecao_do_historico():
    estado = {
        "usuario_logado": True,
        "usuario_atual": {"id_usuario": "usuario-teste"},
        "historico_movimentacao_selecionada": identidade_movimentacao("Receita", _R1),
        "editando_movimentacao": ("usuario-teste", _R1, "Receita"),
    }
    encerrar_sessao_local(estado)
    assert "historico_movimentacao_selecionada" not in estado
    assert "editando_movimentacao" not in estado
