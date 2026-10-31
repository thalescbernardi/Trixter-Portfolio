"""Política de Privacidade: texto, acesso e preservação dos campos."""
import pytest

from trixter.acesso import abrir_sessao
from trixter.privacidade import VERSAO_POLITICA, _SECOES, descartar_politica_fora_de_seguranca
from trixter.sessao import encerrar_sessao_local
from tests.test_enumeracao import _codigo_do_email, _validar_cadastro, app_cadastro


def _texto_completo():
    return "\n".join(
        paragrafo
        for _titulo, paragrafos in _SECOES
        for paragrafo in paragrafos
    )


def _secao(titulo):
    return "\n".join(next(paragrafos for nome, paragrafos in _SECOES if nome == titulo))


def test_versao_inicial_e_minuta_sem_data_publica():
    assert VERSAO_POLITICA == "minuta"
    texto = _texto_completo()
    assert "17 de outubro" not in texto
    assert "em conformidade" not in texto.lower()


def test_texto_cobre_demonstracao_pdf_e_prestadores():
    demonstracao = _secao("Demonstração temporária")
    assert "tenta remover a demonstração" in demonstracao
    assert "Contas temporárias de demonstração tornam-se elegíveis para expurgo após 24 horas de sua criação" in demonstracao
    assert "exatamente" not in demonstracao

    pdf = _secao("Importação de PDF")
    assert "sessão do aplicativo" in pdf
    assert "não comprova eliminação imediata" in pdf
    assert "não é gravado no banco" in pdf

    prestadores = _secao("Prestadores e tratamento fora do Brasil")
    assert "Brazil South" in prestadores
    assert "Azure App Service" in prestadores
    assert "Azure SQL Database" in prestadores
    assert "Streamlit Community Cloud" not in prestadores
    assert "Brevo" in prestadores
    assert "GitHub Actions" in prestadores
    assert "pode ocorrer fora do Brasil" in prestadores
    assert "não declara mecanismos contratuais ainda não confirmados" in prestadores
    assert "contato@trixter.app.br" in _texto_completo()


@pytest.mark.parametrize("maioridade", [False, True])
def test_cadastro_abre_e_fecha_sem_apagar_campos_nem_registrar_aceite(maioridade):
    app = app_cadastro()
    app.text_input(key="novo_nome").set_value("Ana Fictícia")
    app.text_input(key="novo_email").set_value("ana@example.com")
    app.text_input(key="nova_senha").set_value("Teste123!")
    app.text_input(key="confirmar_senha").set_value("Teste123!")
    app.number_input(key="renda_mensal").set_value(2500.0)
    app.checkbox(key="declaracao_maioridade").set_value(maioridade)
    app.button(key="btn_politica_cadastro").click().run()

    assert not app.exception
    assert app.header[0].value == "Política de Privacidade"
    assert any(item.value == "Versão: minuta" for item in app.caption)
    assert not app.checkbox
    assert not app.text_input
    assert app.session_state.politica_origem == "cadastro"
    assert "aceite" not in app.session_state
    guardados = app.session_state.politica_campos
    assert guardados["novo_nome"] == "Ana Fictícia"
    assert guardados["novo_email"] == "ana@example.com"
    assert guardados["nova_senha"] == "Teste123!"
    assert guardados["confirmar_senha"] == "Teste123!"
    assert guardados["renda_mensal"] == 2500.0
    assert guardados["declaracao_maioridade"] is maioridade

    app.button(key="btn_fechar_politica").click().run()
    assert not app.exception
    assert not app.header
    assert app.session_state.politica_origem is None
    assert app.text_input(key="novo_nome").value == "Ana Fictícia"
    assert app.text_input(key="novo_email").value == "ana@example.com"
    assert app.text_input(key="nova_senha").value == "Teste123!"
    assert app.text_input(key="confirmar_senha").value == "Teste123!"
    assert app.number_input(key="renda_mensal").value == 2500.0
    assert app.checkbox(key="declaracao_maioridade").value is maioridade
    assert "politica_campos" not in app.session_state
    assert not any("aceito" in item.label.lower() for item in app.checkbox)

    app.button(key="btn_salvar_nova_conta").click().run()
    assert not app.exception
    assert app.session_state.inserts == 0
    if maioridade:
        assert len(app.session_state.envios) == 1
        assert app.session_state.novo_usuario_pendente["declaracao_maioridade"] is True
    else:
        assert any("18 anos" in erro.value for erro in app.error)
        assert app.session_state.envios == []
        assert "consultas" not in app.session_state
        assert "codigo_cadastro_enviado" not in app.session_state or not app.session_state.codigo_cadastro_enviado


def test_codigo_de_cadastro_continua_visivel_e_preservado():
    app = app_cadastro()
    app.text_input(key="novo_nome").set_value("Ana")
    app.text_input(key="novo_email").set_value("ana@example.com")
    app.text_input(key="nova_senha").set_value("Teste123!")
    app.text_input(key="confirmar_senha").set_value("Teste123!")
    app.checkbox(key="declaracao_maioridade").set_value(True)
    next(botao for botao in app.button if botao.label == "Criar Conta").click().run()
    assert app.session_state.codigo_cadastro_enviado is True
    assert any(botao.key == "btn_politica_cadastro" for botao in app.button)
    app.text_input(key="codigo_digitado_cadastro").set_value("123456")
    app.button(key="btn_politica_cadastro").click().run()
    assert app.session_state.politica_campos["codigo_digitado_cadastro"] == "123456"
    assert app.session_state.politica_campos["novo_email"] == "ana@example.com"
    assert app.session_state.politica_campos["declaracao_maioridade"] is True
    assert app.session_state.codigo_cadastro_enviado is True
    app.button(key="btn_fechar_politica").click().run()
    assert app.text_input(key="codigo_digitado_cadastro").value == "123456"
    assert app.text_input(key="novo_email").value == "ana@example.com"
    assert app.checkbox(key="declaracao_maioridade").value is True
    assert "politica_campos" not in app.session_state
    _validar_cadastro(app, _codigo_do_email(app))
    assert not app.exception
    assert app.session_state.inserts == 1
    for chave in (
        "declaracao_maioridade", "politica_campos", "politica_origem",
        "nova_senha", "confirmar_senha", "novo_usuario_pendente",
        "codigo_digitado_cadastro", "verificacao_cadastro", "autorizacao_cadastro",
    ):
        assert chave not in app.session_state
    assert "senha" not in app.session_state.usuario_atual
    assert "declaracao_maioridade" not in app.session_state.usuario_atual


def test_politica_nao_cria_declaracao_ausente(monkeypatch):
    from types import SimpleNamespace
    from trixter import privacidade

    class Estado(dict):
        __setattr__ = dict.__setitem__

    estado = Estado()
    monkeypatch.setattr(privacidade, "st", SimpleNamespace(session_state=estado))
    privacidade.abrir_politica("cadastro")
    assert "declaracao_maioridade" not in estado["politica_campos"]
    privacidade.fechar_politica()
    assert "declaracao_maioridade" not in estado
    assert "politica_campos" not in estado


@pytest.mark.parametrize("declaracao_pendente", [None, False])
def test_codigo_apos_politica_nao_insere_sem_declaracao_pendente(declaracao_pendente):
    from tests.test_enumeracao import _criar

    app = _criar(app_cadastro())
    app.button(key="btn_politica_cadastro").click().run()
    app.button(key="btn_fechar_politica").click().run()
    assert not app.exception
    assert app.checkbox(key="declaracao_maioridade").value is True
    pendente = app.session_state.novo_usuario_pendente
    if declaracao_pendente is None:
        pendente.pop("declaracao_maioridade")
    else:
        pendente["declaracao_maioridade"] = declaracao_pendente
    _validar_cadastro(app, _codigo_do_email(app))
    assert not app.exception
    assert app.session_state.inserts == 0
    assert any("18 anos" in erro.value for erro in app.error)
    assert "usuario_logado" not in app.session_state or not app.session_state.usuario_logado
    assert "verificacao_cadastro" not in app.session_state
    assert "autorizacao_cadastro" not in app.session_state


def test_login_abre_politica_e_devolve_o_email():
    app = app_cadastro()
    app.session_state.criar_conta = False
    app.session_state.entrar = True
    app.run()
    app.text_input(key="email_entrada").set_value("ana@example.com")
    app.text_input(key="senha").set_value("Teste123!")
    app.button(key="btn_politica_login").click().run()
    assert not app.exception
    assert app.header[0].value == "Política de Privacidade"
    assert not app.checkbox
    assert app.session_state.politica_campos["email_entrada"] == "ana@example.com"
    assert app.session_state.politica_campos["senha"] == "Teste123!"
    app.button(key="btn_fechar_politica").click().run()
    assert app.text_input(key="email_entrada").value == "ana@example.com"
    assert app.text_input(key="senha").value == "Teste123!"
    assert any(botao.key == "btn_confirmar_entrada" for botao in app.button)


def _app_seguranca(demo=False, com_retorno_menu=False):
    from streamlit.testing.v1 import AppTest

    rodape = ""
    if com_retorno_menu:
        import ast
        from pathlib import Path
        fonte = (Path(__file__).resolve().parents[1] / "Gerenciador de Gastos V2.py").read_text(encoding="utf-8")
        arvore = ast.parse(fonte)
        botao = next(n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                     and any(k.arg == "key" and isinstance(k.value, ast.Constant)
                             and k.value.value == "voltar_menu_principal" for k in n.keywords))
        condicoes = [n for n in ast.walk(arvore) if isinstance(n, ast.If)
                     and botao in list(ast.walk(n))]
        condicao = min(condicoes, key=lambda n: len(list(ast.walk(n))))
        rodape = '''
st.session_state.setdefault("tela_atual", "seguranca")
area_botao_voltar = st.empty()
area_transicao = None
def abrir_tela_cadastro(*args): pass
''' + ast.unparse(condicao)
    conta = "True" if demo else "False"
    return AppTest.from_string(
        f"""
import streamlit as st
from trixter.privacidade import descartar_politica_fora_de_seguranca
from trixter.seguranca import exibir_seguranca
st.session_state.usuario_logado = True
st.session_state.usuario_atual = {{
    "id_usuario": "u1",
    "email": "ana@example.com",
    "credencial_versao": 1,
    "conta_demo": {conta},
}}
if st.session_state.get("aplicar_saida"):
    descartar_politica_fora_de_seguranca(st.session_state)
class Cursor:
    def execute(self, sql, *args):
        self.sql = " ".join(sql.split())
    def fetchone(self):
        if "credencial_versao" in getattr(self, "sql", ""):
            return (1,)
        return None
    def close(self):
        pass
class Conexao:
    def cursor(self):
        return Cursor()
    def commit(self):
        pass
    def rollback(self):
        pass
    def close(self):
        pass
exibir_seguranca(lambda: Conexao())
""" + rodape,
        default_timeout=30,
    ).run()


@pytest.mark.parametrize("demo", [False, True])
def test_documentos_tem_um_unico_retorno_com_rodape_real(demo):
    app = _app_seguranca(demo, com_retorno_menu=True)
    assert any(b.key == "voltar_menu_principal" for b in app.button)
    for _ in range(2):
        app.button(key="btn_politica_seguranca").click().run()
        assert app.session_state.politica_origem == "seguranca"
        # Estabiliza a arvore do AppTest apos a interrupcao por rerun explicito.
        # A necessidade do rerun em escopo app e verificada no teste abaixo.
        app.run()
        assert not app.exception
        assert [b.key for b in app.button] == ["btn_fechar_politica"]
        assert len(app.tabs) == 2
        app.button(key="btn_fechar_politica").click().run()
        assert app.session_state.politica_origem is None
        app.run()
        assert not app.exception
        assert not app.tabs
        assert any(b.key == "voltar_menu_principal" for b in app.button)


def test_transicoes_do_fragmento_pedem_rerun_app_apos_mudar_estado(monkeypatch):
    """Modela callbacks ANTES do fragmento; nao usa rerun completo implicito do AppTest."""
    import ast
    import inspect
    from unittest.mock import Mock
    from trixter import seguranca

    # Corpo real sem o decorador: SQL e renderizadores sao substituidos por mocks.
    arvore = ast.parse(inspect.getsource(seguranca.exibir_seguranca))
    funcao = arvore.body[0]
    funcao.decorator_list = []
    ambiente = dict(vars(seguranca))
    exec(compile(ast.fix_missing_locations(arvore), "<fragmento_seguranca>", "exec"), ambiente)
    fragmento = ambiente["exibir_seguranca"]
    estado = {"usuario_atual": {"conta_demo": True}}
    callbacks = {}
    clique = [None]
    eventos = []

    class RerunApp(BaseException):
        pass

    def botao(*args, key, **kwargs):
        callbacks[key] = (kwargs.get("on_click"), kwargs.get("args", ()))
        return clique[0] == key

    def abrir(origem):
        estado["politica_origem"] = origem
        eventos.append("abrir")

    def fechar():
        estado["politica_origem"] = None
        eventos.append("fechar")

    def rerun(*, scope):
        assert scope == "app"
        eventos.append("rerun_app")
        raise RerunApp

    st_mock = Mock(session_state=estado, button=botao, rerun=rerun)
    monkeypatch.setattr(seguranca, "st", st_mock)
    monkeypatch.setattr(seguranca, "abrir_politica", abrir)
    monkeypatch.setattr(seguranca, "fechar_politica", fechar)
    ambiente.update(st=st_mock, exigir_operacao=lambda _: True,
                    politica_aberta=lambda origem: estado.get("politica_origem") == origem,
                    abrir_politica=abrir, fechar_politica=fechar,
                    exibir_politica=Mock(), _exibir_exportacao=Mock())
    monkeypatch.setattr(seguranca.estilo, "publicar", Mock())
    fragmento(Mock())
    for key, acao in [("btn_politica_seguranca", "abrir"),
                      ("btn_fechar_politica", "fechar"),
                      ("btn_politica_seguranca", "abrir")]:
        callback, argumentos = callbacks[key]
        if callback:
            callback(*argumentos)  # Ordem do Streamlit: callback antes da renderizacao.
        clique[0] = key
        with pytest.raises(RerunApp):
            fragmento(Mock())
        assert eventos[-2:] == [acao, "rerun_app"]
        assert callback is None
        clique[0] = None
        fragmento(Mock())


def test_seguranca_e_demonstracao_abrem_a_mesma_politica():
    for demo in (False, True):
        app = _app_seguranca(demo)
        assert not app.exception
        assert any(botao.key == "btn_politica_seguranca" for botao in app.button)
        if not demo:
            app.text_input(key="seguranca_senha_atual").set_value("Teste123!")
        app.button(key="btn_politica_seguranca").click().run()
        if not demo:
            assert app.session_state.politica_campos["seguranca_senha_atual"] == "Teste123!"
        assert not app.exception
        assert app.header[0].value == "Política de Privacidade"
        assert not app.checkbox
        assert "aceite" not in app.session_state
        app.button(key="btn_fechar_politica").click().run()
        assert not app.header
        assert any(botao.key == "btn_politica_seguranca" for botao in app.button)
        if not demo:
            assert app.text_input(key="seguranca_senha_atual").value == "Teste123!"


def test_navegar_para_fora_de_seguranca_fecha_a_politica_sem_devolver_a_senha():
    app = _app_seguranca(False)
    app.text_input(key="seguranca_senha_atual").set_value("Teste123!")
    app.button(key="btn_politica_seguranca").click().run()
    assert app.header[0].value == "Política de Privacidade"
    app.session_state.tela_atual = "configuracoes"
    app.session_state.aplicar_saida = True
    app.run()
    assert not app.exception
    assert not app.header
    assert "politica_campos" not in app.session_state
    assert "politica_origem" not in app.session_state
    assert app.text_input(key="seguranca_senha_atual").value == ""
    app.session_state.aplicar_saida = False
    app.session_state.tela_atual = "seguranca"
    app.run()
    assert not app.header
    assert any(botao.key == "btn_politica_seguranca" for botao in app.button)


def test_politica_de_cadastro_nao_fecha_ao_sair_de_seguranca():
    estado = {
        "politica_origem": "cadastro",
        "politica_campos": {"novo_nome": "Ana"},
        "tela_atual": "menu",
    }
    descartar_politica_fora_de_seguranca(estado)
    assert estado["politica_origem"] == "cadastro"
    assert estado["politica_campos"]["novo_nome"] == "Ana"


def test_politica_aberta_em_seguranca_permanece_ate_o_voltar():
    estado = {
        "politica_origem": "seguranca",
        "politica_campos": {"senha_exclusao": "Teste123!"},
        "tela_atual": "seguranca",
    }
    descartar_politica_fora_de_seguranca(estado)
    assert estado["politica_campos"]["senha_exclusao"] == "Teste123!"


def test_fim_da_sessao_apaga_a_copia_sem_gravar():
    import inspect
    from trixter import privacidade

    fonte = inspect.getsource(privacidade)
    assert "cursor.execute" not in fonte
    assert "logging" not in fonte
    assert "open(" not in fonte

    estado = {
        "usuario_logado": True,
        "declaracao_maioridade": True,
        "usuario_atual": {"id_usuario": "u1"},
        "politica_origem": "seguranca",
        "politica_campos": {
            "declaracao_maioridade": True,
            "senha_exclusao": "Teste123!",
            "codigo_digitado_email": "123456",
        },
    }
    encerrar_sessao_local(estado)
    assert "politica_campos" not in estado
    assert "politica_origem" not in estado
    assert "declaracao_maioridade" not in estado

    entrada = {
        "politica_origem": "login",
        "politica_campos": {"senha": "Teste123!", "email_entrada": "ana@example.com"},
    }
    abrir_sessao(
        {"id_usuario": "u1", "email": "ana@example.com", "credencial_versao": 1},
        "menu",
        entrada,
    )
    assert "politica_campos" not in entrada
    assert "politica_origem" not in entrada
    assert entrada["usuario_atual"]["email"] == "ana@example.com"


def test_cancelar_o_cadastro_apaga_a_copia_da_politica():
    import ast
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    arvore = ast.parse(Path("Gerenciador de Gastos V2.py").read_text(encoding="utf-8"))
    callback = next(
        no for no in arvore.body
        if isinstance(no, ast.FunctionDef) and no.name == "voltar_para_inicio"
    )
    fonte = """
import streamlit as st
from trixter import verificacao
st.session_state.politica_origem = "cadastro"
st.session_state.politica_campos = {
    "declaracao_maioridade": True,
    "nova_senha": "Teste123!",
    "codigo_digitado_cadastro": "123456",
    "novo_email": "ana@example.com",
}
st.session_state.criar_conta = True
st.session_state.declaracao_maioridade = True
"""
    fonte += ast.unparse(callback) + "\nvoltar_para_inicio()\n"
    app = AppTest.from_string(fonte).run()
    assert not app.exception
    assert "politica_campos" not in app.session_state
    assert "politica_origem" not in app.session_state
    assert "declaracao_maioridade" not in app.session_state
    assert app.session_state.criar_conta is False



def test_retencao_historico_descreve_expurgo_e_limites():
    texto = _secao("Retenção e cópias de segurança")
    assert "30 dias contados da data mais recente" in texto
    assert "atualização e o encerramento da janela" in texto
    assert "sob bloqueio exclusivo" in texto
    assert "ausência de execução podem postergá-la" in texto
    assert "não autorizam reenvio automático" in texto
    assert VERSAO_POLITICA == "minuta"


def test_minutas_completas_identificam_propostas_e_limites():
    from trixter.termos import VERSAO_TERMOS, _SECOES as secoes_termos

    assert VERSAO_POLITICA == VERSAO_TERMOS == "minuta"
    politica = _texto_completo()
    termos = "\n".join(p for _, paragrafos in secoes_termos for p in paragrafos)
    assert len(_SECOES) == 15
    assert len(secoes_termos) == 16
    for texto in (politica, termos):
        assert "Thales Carvalho Bernardi" in texto
        assert "contato@trixter.app.br" in texto
        assert "portfólio" in texto
        assert "18 anos" in texto
        assert "envio manual de relatórios por e-mail está bloqueado" in texto.lower()
        assert "visualização e download" in texto
        assert "?" not in texto
        assert "\ufffd" not in texto
    for texto in (politica, termos):
        assert "minuta para revisão jurídica, sem aprovação ou vigência definitiva" in texto
        assert "validação jurídica concluída" not in texto
    assert "Os enquadramentos adotados não representam garantia de conformidade integral" in politica
    assert "art. 7º" in politica and "art. 11" in politica
    assert "pode atuar como operador" in politica
    assert "O repositório desabilita explicitamente as estatísticas de uso do Streamlit" in politica
    assert "gatherUsageStats = false em .streamlit/config.toml" in politica
    assert "A versão integrada ainda não foi publicada no Azure" in politica
    assert "não comprova sua aplicação na versão atualmente em produção" in politica
    assert "dependem de confirmação administrativa" in politica
    assert "não comprova a existência de valores históricos" in politica
    assert "não institui aceite obrigatório" in termos
    assert "não afirma a existência de ferramenta administrativa de suspensão" in termos
    assert "não é exclusão geral de responsabilidade" in termos.lower()


def test_documentos_delimitam_dados_de_terceiros_e_papeis_por_tratamento():
    from trixter.termos import _SECOES as secoes_termos

    terceiros = _secao("Dados de usuários e informações de terceiros")
    pdf = _secao("Importação de PDF")
    termos = "\n".join(next(
        paragrafos for titulo, paragrafos in secoes_termos
        if titulo == "Informações de clientes e uso profissional"
    ))
    for texto in (terceiros, termos):
        assert "Cliente é opcional" in texto
        assert "identificação mínima suficiente" in texto
        assert "documentos de identificação" in texto
        assert "credenciais" in texto
        assert "sensíveis ou excessivos" in texto or "sensíveis ou conteúdo excessivo" in texto
        assert "obrigações próprias do Trixter" in texto or "deveres próprios do Trixter" in texto
    assert "pode atuar como controlador" in terceiros
    assert "o Trixter pode atuar como operador" in terceiros
    assert "sem atribuir um único papel a todas as operações" in terceiros
    assert "instruções legítimas" in terceiros
    assert "autenticação" in terceiros
    assert "cooperar no atendimento" in terceiros
    assert "não recolhem arquivos baixados nem mensagens já entregues" in terceiros
    assert "análises por cliente e exportações" in terceiros
    assert "relatórios e comunicações" in terceiros
    assert "antes da seleção das movimentações" in pdf
    assert "descrições desses movimentos podem integrar os registros da conta" in pdf
    assert "antes de importar, exportar ou compartilhar" in termos
    assert "não autoriza o Trixter a explorar dados de clientes para publicidade" in termos


@pytest.mark.parametrize("origem", ["cadastro", "login", "seguranca", "demo"])
def test_termos_acessiveis_com_retorno_pelo_mesmo_fluxo(origem, monkeypatch):
    from unittest.mock import Mock
    from trixter import estilo
    fundo = Mock(wraps=estilo.publicar_fundo_documentos)
    monkeypatch.setattr(estilo, "publicar_fundo_documentos", fundo)
    if origem in ("seguranca", "demo"):
        app = _app_seguranca(demo=origem == "demo")
        botao = "btn_politica_seguranca"
        campo = None if origem == "demo" else "seguranca_senha_atual"
    else:
        app = app_cadastro()
        if origem == "login":
            app.session_state.criar_conta = False
            app.session_state.entrar = True
            app.run()
        botao = "btn_politica_" + origem
        campo = "nova_senha" if origem == "cadastro" else "senha"
    if campo:
        app.text_input(key=campo).set_value("Teste123!")
    assert "Termos de Uso" in app.button(key=botao).label
    app.button(key=botao).click().run()
    assert not app.exception
    assert fundo.called
    assert [tab.label for tab in app.tabs] == ["Política de Privacidade", "Termos de Uso"]
    assert app.tabs[0].header[0].value == "Política de Privacidade"
    assert app.tabs[1].header[0].value == "Termos de Uso"
    for tab in app.tabs:
        assert any(item.value == "Versão: minuta" for item in tab.caption)
        assert any("não aprovada para publicação" in item.value for item in tab.caption)
    assert not app.checkbox
    assert not app.text_input
    assert "aceite" not in app.session_state
    assert "consentimento" not in app.session_state
    if campo:
        assert app.session_state.politica_campos[campo] == "Teste123!"
    app.button(key="btn_fechar_politica").click().run()
    assert not app.exception
    assert not app.tabs
    assert "politica_campos" not in app.session_state
    assert app.session_state.politica_origem is None
    if campo:
        assert app.text_input(key=campo).value == "Teste123!"
