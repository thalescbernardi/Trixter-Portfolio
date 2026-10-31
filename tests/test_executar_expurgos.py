"""Manutencao sem banco, SMTP ou Docker reais."""
import ast
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pyodbc
import pytest

import executar_expurgos as cli

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def ambiente(monkeypatch):
    eventos = []
    conexao = Mock()
    config = {"database": {"driver": "ODBC Driver 18 for SQL Server", "server": "ficticio",
              "database": "ficticio", "trusted_connection": "no", "usuario": "ficticio", "senha": "ficticia"}}
    monkeypatch.setattr(cli, "carregar_config", Mock(return_value=config))
    monkeypatch.setattr(cli, "validar_config", Mock(wraps=cli.validar_config))
    monkeypatch.setattr(cli, "conectar_banco", Mock(return_value=conexao))
    hist = Mock()
    hist.existe.return_value = True
    hist.expurgar.return_value = 4
    bloqueado = [False]

    @contextmanager
    def exclusivo():
        eventos.append("bloquear")
        bloqueado[0] = True
        try:
            yield
        finally:
            bloqueado[0] = False
            eventos.append("liberar")

    hist.exclusivo.side_effect = exclusivo
    def recuperar():
        assert bloqueado[0]
        eventos.append("recuperar")
    hist.recuperar_interrompidos.side_effect = recuperar
    def historico(agora):
        assert bloqueado[0] and agora.tzinfo is not None
        eventos.append("historico")
        return 4
    hist.expurgar.side_effect = historico
    def demos(conn, agora):
        assert conn is conexao and bloqueado[0] and agora.tzinfo is None
        eventos.append("demos")
        return {"excluidas": 2, "ignoradas": 0, "adiadas": 0, "falhas": 0}
    def limites(conn, agora):
        assert conn is conexao and bloqueado[0] and agora.tzinfo is None
        eventos.append("limites")
        return {"apagadas": 3, "incompleta": False}
    monkeypatch.setattr(cli, "Historico", Mock(return_value=hist))
    monkeypatch.setattr(cli, "expurgar_demonstracoes", Mock(side_effect=demos))
    monkeypatch.setattr(cli, "limpar_expirados", Mock(side_effect=limites))
    # Qualquer chamada real ao SQL ou SMTP torna o teste imediatamente invalido.
    monkeypatch.setattr(pyodbc, "connect", Mock(side_effect=AssertionError("SQL real proibido")))
    import smtplib
    for nome in ("SMTP", "SMTP_SSL"):
        monkeypatch.setattr(smtplib, nome, Mock(side_effect=AssertionError("SMTP proibido")))
    return config, conexao, hist, eventos


def test_fluxo_exclusivo_e_referencia_consistente(ambiente):
    config, conexao, hist, eventos = ambiente
    assert cli.main([]) == 0
    assert eventos == ["bloquear", "recuperar", "historico", "demos", "limites", "liberar"]
    cli.validar_config.assert_called_once_with(config, smtp=False)
    referencia = hist.expurgar.call_args.args[0]
    assert cli.expurgar_demonstracoes.call_args.args[1] == referencia.replace(tzinfo=None)
    assert cli.limpar_expirados.call_args.args[1] == referencia.replace(tzinfo=None)
    hist.inicializar.assert_not_called()
    hist.reservar.assert_not_called()
    conexao.close.assert_called_once_with()


def test_historico_ausente_nao_cria_tabelas(ambiente):
    _, conexao, hist, eventos = ambiente
    hist.existe.return_value = False
    assert cli.main([]) == 1
    hist.inicializar.assert_not_called()
    hist.recuperar_interrompidos.assert_not_called()
    hist.expurgar.assert_not_called()
    cli.expurgar_demonstracoes.assert_not_called()
    assert eventos == ["bloquear", "liberar"]
    conexao.close.assert_called_once_with()


@pytest.mark.parametrize("alvo", ["conectar_banco", "exclusivo", "recuperar_interrompidos", "expurgar", "expurgar_demonstracoes", "limpar_expirados"])
def test_excecoes_propagam_falha_sem_expor_mensagem(ambiente, caplog, alvo):
    _, conexao, hist, _ = ambiente
    funcao = getattr(hist, alvo) if alvo in ("exclusivo", "recuperar_interrompidos", "expurgar") else getattr(cli, alvo)
    funcao.side_effect = ValueError("PWD=segredo pessoa@example.com C:/privado")
    assert cli.main([]) == 1
    assert "segredo" not in caplog.text and "pessoa@example.com" not in caplog.text
    assert "C:/privado" not in caplog.text
    if alvo != "conectar_banco":
        conexao.close.assert_called_once_with()


@pytest.mark.parametrize("resultado", [
    {"excluidas": 0, "adiadas": 0, "falhas": 1},
    {"excluidas": 0, "adiadas": 1, "falhas": 0},
])
def test_falha_retornada_pelas_demonstracoes(ambiente, resultado):
    cli.expurgar_demonstracoes.side_effect = None
    cli.expurgar_demonstracoes.return_value = resultado
    assert cli.main([]) == 1
    cli.limpar_expirados.assert_not_called()


def test_limpeza_incompleta_nao_informa_sucesso(ambiente):
    cli.limpar_expirados.side_effect = None
    cli.limpar_expirados.return_value = {"apagadas": 1024, "incompleta": True}
    assert cli.main([]) == 1


def test_recusa_configuracao_smtp_antes_de_conectar(ambiente):
    config, _, _, _ = ambiente
    config["email"] = {"senha": "ficticia"}
    assert cli.main([]) == 1
    cli.conectar_banco.assert_not_called()


def test_sem_imports_financeiros_ou_chamadas_de_envio():
    fonte = (RAIZ / "executar_expurgos.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    assert not any(isinstance(n, ast.ImportFrom) and n.module == "trixter.automacao" for n in ast.walk(arvore))
    for proibido in ("enviar_email", "SMTP", "buscar_usuarios", "trabalhos_devidos", ".inicializar(", ".reservar("):
        assert proibido not in fonte


def test_workflow_digest_mount_entrypoint_secrets_e_firewall():
    fonte = (RAIZ / "docs/workflows/expurgos.yml").read_text(encoding="utf-8")
    assert 'schedule:' in fonte and 'workflow_dispatch:' in fonte
    assert '  push:' not in fonte and 'workflow_run:' not in fonte
    assert 'permissions:\n  contents: read\n  packages: read\n  id-token: write' in fonte
    assert 'IMAGE: ghcr.io/usuario-exemplo/trixter-envios@sha256:876bf7472c4e4e5e00e97645acaa6b739280f459b4043e561c7835956c4d2197' in fonte
    passo = fonte.split('- name: Executar somente expurgos', 1)[1].split('- name: Fechar o firewall', 1)[0]
    assert '--entrypoint python' in passo
    assert 'target=/app/executar_expurgos.py,readonly' in passo
    assert '"$IMAGE" -B /app/executar_expurgos.py' in passo
    assert 'source=$GITHUB_WORKSPACE/executar_expurgos.py' in passo
    assert "TRIXTER_EMAIL" not in fonte and ":latest" not in fonte
    assert "docker push" not in fonte and "docker build" not in fonte
    fechar = fonte.split('- name: Fechar o firewall', 1)[1]
    assert "always()" in fechar
    assert "steps.azure.outcome" in fechar  # Cobre criacao parcialmente falha.
    assert "starts_with" not in fonte  # Nao apaga regras de outros executores.
    assert 'WORKDIR /app' in (RAIZ / "Dockerfile").read_text(encoding="utf-8")
    assert 'USER trixter' in (RAIZ / "Dockerfile").read_text(encoding="utf-8")


def test_validacao_manual_isolada_nao_pode_disparar_limpeza():
    fonte = (RAIZ / "docs/workflows/expurgos.yml").read_text(encoding="utf-8")
    validar, limpar = fonte.split('  validar:', 1)[1].split('  limpar:', 1)
    assert "default: Validar" in fonte
    assert "github.event_name == 'workflow_dispatch' && inputs.operacao == 'Validar'" in validar
    assert "inputs.operacao == 'Expurgar'" in limpar
    assert "github.event_name == 'schedule'" in limpar
    assert '--network none --read-only --entrypoint python' in validar
    assert 'target=/app/executar_expurgos.py,readonly' in validar
    assert '"$IMAGE" -B -' in validar
    assert 'TRIXTER_DATABASE' not in validar and 'TRIXTER_EMAIL' not in validar
    assert 'azure/login' not in validar and 'id-token:' not in validar
    assert 'secrets.TRIXTER' not in validar
    inicio = validar.index("from pathlib import Path")
    fim = validar.index('\n          PY', inicio)
    codigo = '\n'.join(linha[10:] for linha in validar[inicio:fim].splitlines()[1:])
    codigo = 'from pathlib import Path\n' + codigo
    arvore = ast.parse(codigo)
    assert "run_name='validacao_expurgos'" in codigo
    assert "validacao_inicializacao=aprovada main_nao_executado" in codigo
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
            assert no.func.id not in ('main', 'conectar_banco', 'exec', 'eval')
