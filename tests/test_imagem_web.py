"""Imagem da interface, sem credenciais reais e sem o executor de e-mails."""
import os
from pathlib import Path
import shutil
import subprocess
import time
import tomllib
import urllib.request

import pytest

from iniciar_web import CAMPOS, comando_streamlit, porta_de_escuta, preparar_segredos


RAIZ = Path(__file__).resolve().parents[1]
IMAGEM = "trixter-web:teste"
SENHA_FICTICIA = "senha-ficticia-de-teste"


def test_configuracao_desativa_estatisticas_e_preserva_limite_de_upload():
    config = tomllib.loads((RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["browser"]["gatherUsageStats"] is False
    assert config["server"]["maxUploadSize"] == 2


def _ambiente_completo():
    return {
        "TRIXTER_WEB_DATABASE_DRIVER": "ODBC Driver 18 for SQL Server",
        "TRIXTER_WEB_DATABASE_SERVER": "servidor.exemplo",
        "TRIXTER_WEB_DATABASE_NAME": "banco_ficticio",
        "TRIXTER_WEB_DATABASE_USERNAME": "usuario_ficticio",
        "TRIXTER_WEB_DATABASE_PASSWORD": "senha-banco-ficticia",
        "TRIXTER_WEB_EMAIL_REMETENTE": "web@exemplo.teste",
        "TRIXTER_WEB_EMAIL_SERVIDOR": "smtp.exemplo.teste",
        "TRIXTER_WEB_EMAIL_PORTA": "587",
        "TRIXTER_WEB_EMAIL_USUARIO": "smtp-ficticio",
        "TRIXTER_WEB_EMAIL_SENHA": SENHA_FICTICIA,
    }


def test_sem_variaveis_nao_cria_arquivo_de_segredos(tmp_path):
    destino = tmp_path / ".streamlit" / "secrets.toml"
    assert preparar_segredos({}, destino) == "ausente"
    assert not destino.exists()


def test_arquivo_existente_permanece_quando_nao_ha_variaveis(tmp_path):
    destino = tmp_path / "secrets.toml"
    destino.write_text("conteudo-montado", encoding="utf-8")
    assert preparar_segredos({}, destino) == "arquivo"
    assert destino.read_text(encoding="utf-8") == "conteudo-montado"


def test_conjunto_incompleto_cita_o_nome_e_preserva_o_valor(tmp_path):
    destino = tmp_path / "secrets.toml"
    ambiente = {"TRIXTER_WEB_DATABASE_PASSWORD": SENHA_FICTICIA}
    with pytest.raises(ValueError) as erro:
        preparar_segredos(ambiente, destino)
    mensagem = str(erro.value)
    assert "TRIXTER_WEB_DATABASE_DRIVER" in mensagem
    assert SENHA_FICTICIA not in mensagem
    assert not destino.exists()


def test_variaveis_geram_o_toml_que_o_streamlit_le(tmp_path):
    destino = tmp_path / ".streamlit" / "secrets.toml"
    ambiente = _ambiente_completo()
    ambiente["TRIXTER_WEB_DATABASE_PASSWORD"] = 'segredo "com" \\barra\n'
    assert preparar_segredos(ambiente, destino) == "variaveis"
    carregado = tomllib.loads(destino.read_text(encoding="utf-8"))
    assert carregado["database"]["username"] == "usuario_ficticio"
    assert carregado["database"]["password"] == 'segredo "com" \\barra\n'
    assert carregado["email"]["porta"] == 587
    assert carregado["email"]["senha"] == SENHA_FICTICIA
    assert "usuario" not in carregado["database"]
    if os.name != "nt":
        assert destino.stat().st_mode & 0o777 == 0o600


def test_porta_padrao_e_a_variavel_do_app_service():
    assert porta_de_escuta({}) == "8501"
    assert porta_de_escuta({"WEBSITES_PORT": "8501"}) == "8501"
    with pytest.raises(ValueError):
        porta_de_escuta({"WEBSITES_PORT": "0"})


def test_comando_sobe_headless_na_porta_recebida():
    assert comando_streamlit("8501") == [
        "streamlit", "run", "Gerenciador de Gastos V2.py",
        "--server.headless", "true",
        "--server.address", "0.0.0.0",
        "--server.port", "8501",
    ]


def test_validacao_da_imagem_web_nao_publica_nem_recebe_secrets():
    texto = (RAIZ / "docs" / "workflows" / "validacao-imagem-web.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in texto
    assert "schedule:" not in texto
    assert "push:" not in texto
    assert "pull_request:" not in texto
    assert "${{ secrets" not in texto
    assert "ghcr.io" not in texto
    assert "docker push" not in texto
    assert "Dockerfile.web" in texto
    assert "/_stcore/health" in texto
    assert "8501:8501" in texto
    assert "secrets.toml" in texto


def test_imagem_web_nao_altera_o_contrato_do_executor():
    executor = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
    web = (RAIZ / "Dockerfile.web").read_text(encoding="utf-8")
    ignore = (RAIZ / ".dockerignore").read_text(encoding="utf-8")
    workflow = (RAIZ / "docs" / "workflows" / "imagem-envios.yml").read_text(encoding="utf-8")
    assert 'ENTRYPOINT ["python", "executar_envios.py"]' in executor
    assert 'CMD ["--enviar"]' in executor
    assert "Dockerfile.web" not in workflow
    assert "docker build --tag" in workflow
    assert "msodbcsql18" in web
    assert "requirements.txt" in web
    assert "requirements-envios.txt" not in web
    assert "executar_envios.py" not in web
    assert "--enviar" not in web
    assert "secrets.toml" not in web
    assert all(nome not in web for _secao, campos in CAMPOS.items() for nome, _campo in campos)
    assert ".streamlit\n" not in ignore
    assert "**/secrets.toml" in ignore


def test_publicacao_da_imagem_web_e_manual_e_separada_do_executor():
    texto = (RAIZ / "docs" / "workflows" / "imagem-web.yml").read_text(encoding="utf-8")
    envios = (RAIZ / "docs" / "workflows" / "imagem-envios.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in texto
    assert "schedule:" not in texto
    assert "push:" not in texto
    assert "pull_request:" not in texto
    assert "contents: read" in texto
    assert "packages: write" in texto
    assert "id-token:" not in texto
    assert "${{ secrets.GITHUB_TOKEN }}" in texto
    assert texto.count("${{ secrets.") == 1
    assert "ghcr.io/usuario-exemplo/trixter-web:${{ github.sha }}" in texto
    assert ":latest" not in texto
    assert "trixter-envios" not in texto
    assert "Dockerfile.web" in texto
    assert "docker push" in texto
    assert "password-stdin" in texto
    assert "org.opencontainers.image.source" in texto
    assert "persist-credentials: false" in texto
    assert "executar_envios.py" not in texto
    assert "--enviar" not in texto
    assert "TRIXTER_WEB_" not in texto
    assert "imagem-web.yml" not in envios
    assert "trixter-web" not in envios


def _rodar(comando, **kwargs):
    return subprocess.run(comando, cwd=RAIZ, check=True, text=True, **kwargs)


@pytest.mark.skipif(
    os.environ.get("TRIXTER_TESTAR_IMAGEM_WEB") != "1",
    reason="defina TRIXTER_TESTAR_IMAGEM_WEB=1 para construir e subir a imagem",
)
def test_imagem_sobe_sem_credenciais_e_grava_segredos_ficticios():
    if shutil.which("docker") is None:
        pytest.fail("Docker não está no PATH. O build da imagem web não foi executado.")
    _rodar(["docker", "build", "-f", "Dockerfile.web", "--tag", IMAGEM, "."])
    _rodar([
        "docker", "run", "--rm", "--entrypoint", "python", IMAGEM, "-c",
        "import pyodbc; from pathlib import Path; "
        "assert 'ODBC Driver 18 for SQL Server' in pyodbc.drivers(); "
        "assert not Path('/app/.streamlit/secrets.toml').exists(); "
        "assert Path('/app/assets/trixter_background.png').is_file()",
    ])
    nome = "trixter-web-teste"
    subprocess.run(["docker", "rm", "-f", nome], cwd=RAIZ, check=False)
    try:
        _rodar([
            "docker", "run", "-d", "--name", nome,
            "--publish", "127.0.0.1:18501:8501",
            "--env", "WEBSITES_PORT=8501",
            IMAGEM,
        ])
        _aguardar_saude("http://127.0.0.1:18501/_stcore/health")
        logs = _rodar(["docker", "logs", nome], capture_output=True).stdout
        assert SENHA_FICTICIA not in logs
    finally:
        subprocess.run(["docker", "rm", "-f", nome], cwd=RAIZ, check=False)

    nome_segredos = "trixter-web-segredos"
    subprocess.run(["docker", "rm", "-f", nome_segredos], cwd=RAIZ, check=False)
    try:
        ambiente = _ambiente_completo()
        comando = ["docker", "run", "-d", "--name", nome_segredos, "--publish", "127.0.0.1:18502:8501"]
        for chave, valor in ambiente.items():
            comando.extend(["--env", f"{chave}={valor}"])
        comando.append(IMAGEM)
        _rodar(comando)
        _aguardar_saude("http://127.0.0.1:18502/_stcore/health")
        verificacao = (
            "import os, stat, tomllib; from pathlib import Path; "
            "arquivo = Path('/app/.streamlit/secrets.toml'); "
            "dados = tomllib.loads(arquivo.read_text(encoding='utf-8')); "
            "assert dados['database']['username'] == os.environ['TRIXTER_WEB_DATABASE_USERNAME']; "
            "assert dados['email']['senha'] == os.environ['TRIXTER_WEB_EMAIL_SENHA']; "
            "assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600"
        )
        _rodar(["docker", "exec", nome_segredos, "python", "-c", verificacao])
        logs = _rodar(["docker", "logs", nome_segredos], capture_output=True)
        texto = logs.stdout + logs.stderr
        assert SENHA_FICTICIA not in texto
        assert "senha-banco-ficticia" not in texto
    finally:
        subprocess.run(["docker", "rm", "-f", nome_segredos], cwd=RAIZ, check=False)


def _aguardar_saude(url):
    prazo = time.monotonic() + 180
    ultimo = ""
    while time.monotonic() < prazo:
        try:
            with urllib.request.urlopen(url, timeout=3) as resposta:
                if resposta.status == 200:
                    return
        except Exception as erro:
            ultimo = str(erro)
        time.sleep(2)
    raise AssertionError(f"a interface não respondeu em {url}: {ultimo}")
