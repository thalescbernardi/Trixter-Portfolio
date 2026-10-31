"""Cadastro sem CPF e sem CNPJ, com dados fictícios."""
import pytest

from tests.test_enumeracao import _codigo_do_email, _validar_cadastro, app_cadastro

SENHA = "Teste123!"
# Ordem do INSERT em dbo.usuarios: cpf é o 8º valor e cnpj é o 11º.
CPF = 7
CNPJ = 10


def _preencher_acesso(app, email="pessoa@example.com", senha=SENHA):
    app.text_input(key="novo_email").set_value(email)
    app.text_input(key="nova_senha").set_value(senha)
    app.text_input(key="confirmar_senha").set_value(senha)


def _criar(app, declarar=True):
    if declarar:
        app.checkbox(key="declaracao_maioridade").set_value(True)
    next(botao for botao in app.button if botao.label == "Criar Conta").click().run()
    return app


def _pessoa_juridica(app):
    app.selectbox(key="tipo_pessoa").select("Pessoa Jurídica").run()
    return app


def _rotulos(app):
    return [campo.label for campo in app.text_input]


def test_formulario_nao_pede_cpf_nem_cnpj():
    app = app_cadastro()
    assert not any("CPF" in rotulo or "CNPJ" in rotulo for rotulo in _rotulos(app))
    app = _pessoa_juridica(app_cadastro())
    assert not any("CPF" in rotulo or "CNPJ" in rotulo for rotulo in _rotulos(app))


def test_pessoa_fisica_grava_documentos_nulos():
    app = app_cadastro()
    app.text_input(key="novo_nome").set_value("Ana")
    _preencher_acesso(app)
    _criar(app)
    assert not app.exception
    assert not app.error
    assert app.session_state.codigo_cadastro_enviado is True
    pendente = app.session_state.novo_usuario_pendente
    assert pendente["declaracao_maioridade"] is True
    assert pendente["tipo_pessoa"] == "Pessoa Física"
    assert pendente["cpf"] is None
    assert pendente["cnpj"] is None
    _validar_cadastro(app, _codigo_do_email(app))
    assert app.session_state.inserts == 1
    gravado = app.session_state.ultimo_insert
    assert gravado[CPF] is None
    assert gravado[CNPJ] is None
    assert "declaracao_maioridade" not in app.session_state.usuario_atual
    assert "declaracao_maioridade" not in app.session_state


def test_pessoa_juridica_grava_documentos_nulos():
    app = _pessoa_juridica(app_cadastro())
    app.text_input(key="novo_nome_empresa").set_value("Oficina Fictícia")
    _preencher_acesso(app, email="oficina@example.com")
    _criar(app)
    assert not app.exception
    assert not app.error
    pendente = app.session_state.novo_usuario_pendente
    assert pendente["tipo_pessoa"] == "Pessoa Jurídica"
    assert pendente["cpf"] is None
    assert pendente["cnpj"] is None
    assert pendente["nome_empresa"] == "Oficina Fictícia"
    _validar_cadastro(app, _codigo_do_email(app))
    assert app.session_state.inserts == 1
    gravado = app.session_state.ultimo_insert
    assert gravado[CPF] is None
    assert gravado[CNPJ] is None


@pytest.mark.parametrize("pessoa", ["Pessoa Física", "Pessoa Jurídica"])
def test_nova_conta_comeca_com_emails_financeiros_desligados(pessoa):
    app = app_cadastro()
    if pessoa == "Pessoa Jurídica":
        _pessoa_juridica(app)
        app.text_input(key="novo_nome_empresa").set_value("Oficina Fictícia")
    else:
        app.text_input(key="novo_nome").set_value("Pessoa Fictícia")
    _preencher_acesso(app)
    _criar(app)
    assert not app.exception
    assert app.session_state.inserts == 0
    assert len(app.session_state.envios) == 1
    _validar_cadastro(app, _codigo_do_email(app))
    assert not app.exception
    assert not app.error
    assert app.session_state.inserts == 1
    sql = app.session_state.ultimo_insert_sql
    colunas = [coluna.strip() for coluna in sql.split("(", 1)[1].split(")", 1)[0].split(",")]
    valores = app.session_state.ultimo_insert
    assert sql.count("?") == len(colunas) == len(valores) == 15
    gravado = dict(zip(colunas, valores, strict=True))
    assert gravado["tipo_pessoa"] == pessoa
    for preferencia in (
        "receber_relatorio_mensal", "receber_alertas", "receber_resumo_semanal",
    ):
        assert gravado[preferencia] == 0


def test_senha_curta_continua_bloqueando():
    app = app_cadastro()
    _preencher_acesso(app, senha="curta")
    _criar(app)
    assert not app.exception
    assert any("8 caracteres" in erro.value for erro in app.error)
    assert app.session_state.envios == []
    assert app.checkbox(key="declaracao_maioridade").value is True


def test_declaracao_comeca_desmarcada_e_bloqueia_antes_do_email():
    app = app_cadastro()
    caixa = app.checkbox(key="declaracao_maioridade")
    assert caixa.label == "Declaro que tenho 18 anos completos ou mais."
    assert caixa.value is False
    _preencher_acesso(app)
    _criar(app, declarar=False)
    assert not app.exception
    assert any("18 anos" in erro.value for erro in app.error)
    assert app.session_state.envios == []
    assert "consultas" not in app.session_state
    assert "codigo_cadastro_enviado" not in app.session_state or app.session_state.codigo_cadastro_enviado is not True
    assert "novo_usuario_pendente" not in app.session_state or not app.session_state.novo_usuario_pendente


def test_login_e_recuperacao_nao_pedem_declaracao_de_maioridade():
    app = app_cadastro()
    app.session_state.criar_conta = False
    app.session_state.entrar = True
    app.run()
    assert not app.exception
    assert not any("18 anos" in item.label for item in app.checkbox)
    app.session_state.entrar = False
    app.session_state.recuperar_senha = True
    app.run()
    assert not app.exception
    assert not any("18 anos" in item.label for item in app.checkbox)


def test_email_invalido_continua_bloqueando():
    app = _pessoa_juridica(app_cadastro())
    _preencher_acesso(app, email="sem-arroba")
    _criar(app)
    assert not app.exception
    assert any("endereço válido" in erro.value for erro in app.error)
    assert app.session_state.envios == []
