import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_demo_esvazia_o_espaco_da_tela_aberta():
    fonte = Path("Gerenciador de Gastos V2.py").read_text(encoding="utf-8")
    assert 'tela_atual == "acompanhar_meta"' not in fonte
    arvore = ast.parse(fonte)
    assert any(isinstance(n, ast.FunctionDef) and n.name == "limpar_tela_aberta" for n in arvore.body)
    chamadas = [
        n for n in ast.walk(arvore)
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "limpar_tela_aberta"
    ]
    assert [ast.unparse(n) for n in chamadas] == [
        "limpar_tela_aberta(area_funcionalidade, area_botao_voltar)",
        "limpar_tela_aberta(area_funcionalidade, area_botao_voltar)",
    ]


def test_todas_rotas_sidebar_e_limpeza_em_todos_os_pares():
    from types import SimpleNamespace
    arvore = ast.parse(Path("Gerenciador de Gastos V2.py").read_text(encoding="utf-8"))
    callback = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == "abrir_tela_cadastro")
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                and ast.unparse(n.func) in ("st.sidebar.button", "st.button")
                and not any(k.arg == "key" and isinstance(k.value, ast.Constant) and k.value.value == "voltar_menu_principal" for k in n.keywords)
                and any(k.arg == "on_click" and ast.unparse(k.value) == "abrir_tela_cadastro" for k in n.keywords)]
    assert len(chamadas) == 15
    for chamada in chamadas:
        argumentos = next(k.value for k in chamada.keywords if k.arg == "args")
        assert len(argumentos.elts) == 2
        assert ast.unparse(argumentos.elts[1]) == "area_transicao"
    destinos = [next(k.value.elts[0].value for k in n.keywords if k.arg == "args") for n in chamadas]
    class Estado(dict):
        __getattr__ = dict.__getitem__
        __setattr__ = dict.__setitem__
    class Area:
        def __init__(self): self.limpezas = 0
        def empty(self): self.limpezas += 1
    estado = Estado()
    escopo = {"st": SimpleNamespace(session_state=estado)}
    exec(compile(ast.Module(body=[callback], type_ignores=[]), "callback", "exec"), escopo)
    for origem in destinos + ["configuracoes", "seguranca", "alertas", "menu"]:
        for destino in destinos + ["menu"]:
            estado.update(tela_atual=origem, menu_conta_aberto=True, menu_alertas_aberto=True,
                          relatorio_gerado=True, mes_relatorio=9, ano_relatorio=2026)
            conteudo, voltar = Area(), Area()
            escopo["abrir_tela_cadastro"](destino, conteudo, voltar)
            assert estado.tela_atual == destino
            assert conteudo.limpezas == voltar.limpezas == 1
            assert not estado.menu_conta_aberto and not estado.menu_alertas_aberto
            if "relatorio_mensal" in (origem, destino):
                assert not estado.relatorio_gerado and estado.mes_relatorio is None
    fonte = '''
import streamlit as st
termo_gasto = "Despesa"
st.session_state.setdefault("tela_atual", "menu")
area_transicao = st.empty()
with area_transicao.container():
    area_funcionalidade = st.empty()
    area_botao_voltar = st.empty()
'''
    fonte += ast.unparse(callback) + "\n" + "\n".join(ast.unparse(c).replace("st.button(", "st.sidebar.button(", 1) for c in chamadas)
    fonte += '\nwith area_funcionalidade.container():\n    st.title(st.session_state.tela_atual)\n'
    fonte += '''
if st.session_state.tela_atual != "menu":
    with area_botao_voltar.container():
        st.button("Voltar", key="teste_voltar", on_click=abrir_tela_cadastro, args=("menu", area_transicao))
'''
    app = AppTest.from_string(fonte).run()
    for chamada, destino in zip(chamadas, destinos):
        chave = next(k.value.value for k in chamada.keywords if k.arg == "key")
        app.sidebar.button(key=chave).click().run()
        assert not app.exception
        assert len(app.title) == 1 and app.title[0].value == destino
        assert len([b for b in app.button if b.key == "teste_voltar"]) == 1
    app.button(key="teste_voltar").click().run()
    assert not app.exception
    assert app.title[0].value == "menu"
    assert not [b for b in app.button if b.key == "teste_voltar"]


def test_troca_cadastro_define_destino_antes_de_renderizar():
    arvore = ast.parse(Path("Gerenciador de Gastos V2.py").read_text(encoding="utf-8"))
    callback = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == "abrir_tela_cadastro")
    botoes = [n for n in ast.walk(arvore) if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id in ("btn_cadastrar_gasto", "btn_cadastrar_receita", "btn_importar_pdf") for t in n.targets)]
    fonte = '''
import streamlit as st
termo_gasto = "Despesa"
st.session_state.setdefault("tela_atual", "cadastrar_gasto")
st.session_state.setdefault("menu_conta_aberto", True)
st.session_state.setdefault("menu_alertas_aberto", True)
area_transicao = st.empty()
with area_transicao.container():
    area_funcionalidade = st.empty()
    area_botao_voltar = st.empty()
'''
    fonte += ast.unparse(callback) + "\n" + "\n".join(ast.unparse(n).replace("st.button(", "st.sidebar.button(", 1) for n in botoes)
    fonte += '\nwith area_funcionalidade.container():\n    st.title(st.session_state.tela_atual)\n'
    app = AppTest.from_string(fonte).run()
    for destino in ("importar_pdf", "cadastrar_receita", "cadastrar_gasto", "cadastrar_receita"):
        app.sidebar.button(key=f"btn_{destino}").click().run()
        assert not app.exception
        assert len(app.title) == 1
        assert app.title[0].value == destino
        assert not app.session_state.menu_conta_aberto
        assert not app.session_state.menu_alertas_aberto
