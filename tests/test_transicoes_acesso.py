import ast
from pathlib import Path
from types import SimpleNamespace


def test_menu_conta_remove_resumo_antes_de_abrir_destino():
    from streamlit.testing.v1 import AppTest
    arvore = ast.parse(Path('Gerenciador de Gastos V2.py').read_text(encoding='utf-8'))
    callback = next(n for n in arvore.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'abrir_tela_menu_conta')
    for destino in ('configuracoes', 'seguranca'):
        setup = '''
import streamlit as st
st.session_state.setdefault('tela_atual', 'menu')
st.session_state.setdefault('menu_conta_aberto', True)
st.session_state.setdefault('menu_alertas_aberto', False)
area_aplicacao = st.empty()
'''
        tela = f'''
with area_aplicacao.container():
    if st.session_state.tela_atual == 'menu':
        slot_menu_conta = st.empty()
        with slot_menu_conta.container():
            st.button('Destino', key='destino', on_click=abrir_tela_menu_conta,
                      args=({destino!r}, slot_menu_conta, area_aplicacao))
        st.subheader('Seu resumo financeiro')
        st.metric('Saldo atual', 'R$ 50,00')
        st.button('Cadastrar gasto', key='atalho')
    else:
        st.title(st.session_state.tela_atual)
'''
        app = AppTest.from_string(setup + ast.unparse(callback) + '\n' + tela).run()
        assert len(app.metric) == 1
        app.button(key='destino').click().run()
        assert not app.exception
        assert app.title[0].value == destino
        assert not app.metric and not app.subheader and not app.button
        assert not app.session_state.menu_conta_aberto
        assert not app.session_state.menu_alertas_aberto


def test_callbacks_limpam_telas_antes_de_mudar_estado():
    arvore = ast.parse(Path('Gerenciador de Gastos V2.py').read_text(encoding='utf-8'))
    class Estado(dict):
        __getattr__ = dict.__getitem__
        __setattr__ = dict.__setitem__
    estado = Estado(usuario_logado=True, usuario_atual={'id_usuario': 'teste'})
    eventos = []
    class Area:
        def empty(self): eventos.append(estado.usuario_logado)
        def markdown(self, texto, **kwargs):
            assert 'stSidebar' in texto and 'display:none' in texto
            eventos.append(estado.usuario_logado)
    from trixter import estilo
    from trixter.sessao import encerrar_sessao_local
    escopo = {
        'st': SimpleNamespace(session_state=estado),
        'estilo': estilo,
        'encerrar_sessao_local': encerrar_sessao_local,
    }
    funcoes = [n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name in ('abrir_acesso', 'sair_conta')]
    exec(compile(ast.Module(body=funcoes, type_ignores=[]), 'acesso', 'exec'), escopo)
    for destino in ('entrar', 'criar_conta'):
        if destino == 'criar_conta':
            estado['declaracao_maioridade'] = True
        escopo['abrir_acesso'](destino, Area())
        assert estado.entrar == (destino == 'entrar')
        assert estado.criar_conta == (destino == 'criar_conta')
        if destino == 'criar_conta':
            assert 'declaracao_maioridade' not in estado
    eventos.clear()
    estado['declaracao_maioridade'] = True
    escopo['sair_conta'](Area(), Area())
    assert eventos == [True]
    assert not estado.usuario_logado and estado.usuario_atual is None
    assert not estado.menu_conta_aberto and not estado.menu_alertas_aberto
    assert not estado.entrar and not estado.criar_conta
    assert 'declaracao_maioridade' not in estado


def test_botoes_landing_dentro_da_area_limpa():
    arvore = ast.parse(Path('Gerenciador de Gastos V2.py').read_text(encoding='utf-8'))
    acesso = ast.parse(Path('trixter/acesso.py').read_text(encoding='utf-8'))
    area = next(n for n in ast.walk(arvore) if isinstance(n, ast.With)
                and ast.unparse(n.items[0].context_expr) == 'area_landing.container()')
    assert any(isinstance(n, ast.Call) and ast.unparse(n.func) == 'exibir_landing' for n in ast.walk(area))
    tela = next(n for n in acesso.body if isinstance(n, ast.FunctionDef) and n.name == 'exibir_landing')
    chaves = [k.value.value for n in ast.walk(tela) if isinstance(n, ast.Call)
              for k in n.keywords if k.arg == 'key' and isinstance(k.value, ast.Constant)]
    assert {'btn_entrar', 'btn_criar_conta'} <= set(chaves)


def test_sair_de_area_aninhada_reabre_landing():
    from streamlit.testing.v1 import AppTest
    arvore = ast.parse(Path('Gerenciador de Gastos V2.py').read_text(encoding='utf-8'))
    callback = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == 'sair_conta')
    fonte = '''
import streamlit as st
from trixter import estilo
from trixter.sessao import encerrar_sessao_local
st.session_state.setdefault('usuario_logado', True)
st.session_state.setdefault('usuario_atual', {'id_usuario': 'teste'})
'''
    fonte += ast.unparse(callback) + '\n'
    fonte += '''
if not st.session_state.usuario_logado:
    st.title('Landing')
    st.button('Entrar')
    st.button('Criar Conta')
area_aplicacao = st.empty()
if st.session_state.usuario_logado:
    st.sidebar.button('Funcionalidade da sidebar')
    with area_aplicacao.container():
        st.title('Funcionalidade')
        area_menu_conta = st.empty()
        with area_menu_conta.container():
            st.button('Sair', key='sair', on_click=sair_conta, args=(area_menu_conta, area_aplicacao))
'''
    app = AppTest.from_string(fonte).run()
    app.button(key='sair').click().run()
    assert not app.exception
    assert len(app.title) == 1 and app.title[0].value == 'Landing'
    assert [b.label for b in app.button] == ['Entrar', 'Criar Conta']
    assert not app.sidebar.button
    assert not app.session_state.usuario_logado


def test_voltar_login_remove_formulario_e_retorna_landing():
    from streamlit.testing.v1 import AppTest
    arvore = ast.parse(Path('Gerenciador de Gastos V2.py').read_text(encoding='utf-8'))
    acesso = ast.parse(Path('trixter/acesso.py').read_text(encoding='utf-8'))
    callback = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == 'voltar_para_inicio')
    botao = next(n for n in ast.walk(acesso) if isinstance(n, ast.Call)
                 and any(k.arg == 'key' and isinstance(k.value, ast.Constant) and k.value.value == 'voltar_entrar' for k in n.keywords))
    fonte = '''
import streamlit as st
from trixter import verificacao
st.session_state.setdefault('entrar', True)
'''
    fonte += ast.unparse(callback) + '\n'
    fonte += '''
if not st.session_state.entrar:
    st.title('Landing')
area_login = st.empty()
if st.session_state.entrar:
    with area_login.container():
        st.title('Login')
        st.text_input('Email')
'''
    fonte += '        ' + ast.unparse(botao) + '\n'
    app = AppTest.from_string(fonte).run()
    app.button(key='voltar_entrar').click().run()
    assert not app.exception
    assert len(app.title) == 1 and app.title[0].value == 'Landing'
    assert not app.text_input
    assert not app.session_state.entrar


def test_voltar_cadastro_limpa_area_e_codigo_pendente():
    from streamlit.testing.v1 import AppTest
    arvore = ast.parse(Path('Gerenciador de Gastos V2.py').read_text(encoding='utf-8'))
    acesso = ast.parse(Path('trixter/acesso.py').read_text(encoding='utf-8'))
    callback = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == 'voltar_para_inicio')
    for chave in ('btn_voltar_criar_conta', 'btn_voltar_codigo'):
        botao = next(n for n in ast.walk(acesso) if isinstance(n, ast.Call)
                     and any(k.arg == 'key' and isinstance(k.value, ast.Constant) and k.value.value == chave for k in n.keywords))
        fonte = '''
import streamlit as st
from trixter import verificacao
st.session_state.setdefault('criar_conta', True)
if st.session_state.criar_conta:
    st.session_state.setdefault('verificacao_cadastro', {'codigo': '123456'})
    st.session_state['codigo_digitado_cadastro'] = '123456'
    st.session_state['codigo_digitado_recuperacao'] = '654321'
    st.session_state['codigo_digitado_email'] = '111111'
    st.session_state.setdefault('novo_usuario_pendente', {'email': 'teste@example.test'})
    st.session_state['declaracao_maioridade'] = True
'''
        fonte += ast.unparse(callback) + '\n'
        fonte += '''
if not st.session_state.criar_conta:
    st.title('Landing')
area_cadastro = st.empty()
if st.session_state.criar_conta:
    with area_cadastro.container():
        st.title('Criar conta')
        st.text_input('Email')
        st.text_input('Codigo', key='codigo_digitado_cadastro')
'''
        fonte += '        ' + ast.unparse(botao) + '\n'
        app = AppTest.from_string(fonte).run()
        app.button(key=chave).click().run()
        assert not app.exception
        assert len(app.title) == 1 and app.title[0].value == 'Landing'
        assert not app.text_input
        assert app.session_state.novo_usuario_pendente is None
        assert 'verificacao_cadastro' not in app.session_state
        for chave in (
            'codigo_digitado_cadastro',
            'codigo_digitado_recuperacao',
            'codigo_digitado_email',
            'declaracao_maioridade',
        ):
            assert chave not in app.session_state


def test_voltar_recuperacao_limpa_formulario_e_autorizacao():
    from streamlit.testing.v1 import AppTest
    arvore = ast.parse(Path('Gerenciador de Gastos V2.py').read_text(encoding='utf-8'))
    acesso = ast.parse(Path('trixter/acesso.py').read_text(encoding='utf-8'))
    callback = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == 'voltar_para_inicio')
    botao = next(n for n in ast.walk(acesso) if isinstance(n, ast.Call)
                 and any(k.arg == 'key' and isinstance(k.value, ast.Constant) and k.value.value == 'voltar_recuperacao_senha' for k in n.keywords))
    fonte = '''
import streamlit as st
from trixter import verificacao
st.session_state.setdefault('recuperar_senha', True)
if st.session_state.recuperar_senha:
    st.session_state.verificacao_recuperacao = {'codigo': '123456'}
    st.session_state.autorizacao_recuperacao = {'email': 'teste@example.test'}
    st.session_state.aviso_recuperacao = 'Codigo enviado'
    st.session_state['codigo_digitado_cadastro'] = '123456'
    st.session_state['codigo_digitado_recuperacao'] = '654321'
    st.session_state['codigo_digitado_email'] = '111111'
'''
    fonte += ast.unparse(callback) + '\n'
    fonte += '''
if not st.session_state.recuperar_senha:
    st.title('Landing')
area_recuperacao = st.empty()
if st.session_state.recuperar_senha:
    with area_recuperacao.container():
        st.title('Recuperar senha')
        st.text_input('Email')
        st.text_input('Codigo', key='codigo_digitado_recuperacao')
'''
    fonte += '        ' + ast.unparse(botao) + '\n'
    app = AppTest.from_string(fonte).run()
    app.button(key='voltar_recuperacao_senha').click().run()
    assert not app.exception
    assert len(app.title) == 1 and app.title[0].value == 'Landing'
    assert not app.text_input
    for chave in (
        'verificacao_recuperacao', 'autorizacao_recuperacao', 'aviso_recuperacao',
        'codigo_digitado_cadastro', 'codigo_digitado_recuperacao', 'codigo_digitado_email',
    ):
        assert chave not in app.session_state
