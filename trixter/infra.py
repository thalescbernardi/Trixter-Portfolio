"""Banco e SMTP sem dependência do Streamlit."""
from contextlib import closing, contextmanager
from contextvars import ContextVar
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
import os
import re
import smtplib
import ssl
import time
import tomllib


RAIZ = Path(__file__).resolve().parent.parent

_operacao_sql = ContextVar("operacao_sql", default="executor")
_falha_sql = ContextVar("falha_sql", default="")
_COLUNA = re.compile(r"(?:Invalid column name|Nome de coluna) '([^']+)'", re.IGNORECASE)
_OBJETO = re.compile(r"(?:Invalid object name|Nome de objeto) '([^']+)'", re.IGNORECASE)
_NUMERO = re.compile(r"\((\d+)\)")


@contextmanager
def operacao_sql(nome):
    """Marca a operação SQL corrente. A primeira falha permanece após o bloco."""
    token = _operacao_sql.set(nome)
    try:
        yield
    except Exception:
        if not _falha_sql.get():
            _falha_sql.set(nome)
        raise
    finally:
        _operacao_sql.reset(token)


def limpar_falha_sql():
    _falha_sql.set("")


def operacao_que_falhou():
    return _falha_sql.get() or _operacao_sql.get()


def descrever_erro_sql(erro):
    """SQLSTATE, operação e número do erro, sem senha, e-mail ou texto livre."""
    estado = str(erro.args[0]) if getattr(erro, "args", None) else ""
    texto = str(erro.args[1]) if len(getattr(erro, "args", ())) > 1 else ""
    partes = [f"sqlstate={estado}", f"operacao={operacao_que_falhou()}"]
    numero = _NUMERO.search(texto)
    if numero:
        partes.append(f"erro_sql={numero.group(1)}")
    coluna = _COLUNA.search(texto)
    objeto = _OBJETO.search(texto)
    if coluna:
        partes.append(f"coluna={coluna.group(1)}")
    elif objeto:
        partes.append(f"objeto={objeto.group(1)}")
    return " ".join(partes)

# TRIXTER_CONFIG continua sendo só o caminho de um TOML. Estas variáveis são a configuração em si.
VARIAVEIS_CONFIG = {
    "TRIXTER_DATABASE_DRIVER": ("database", "driver"),
    "TRIXTER_DATABASE_SERVER": ("database", "server"),
    "TRIXTER_DATABASE_NAME": ("database", "database"),
    "TRIXTER_DATABASE_TRUSTED_CONNECTION": ("database", "trusted_connection"),
    "TRIXTER_DATABASE_USUARIO": ("database", "usuario"),
    "TRIXTER_DATABASE_SENHA": ("database", "senha"),
    "TRIXTER_DATABASE_ENCRYPT": ("database", "encrypt"),
    "TRIXTER_DATABASE_TRUST_SERVER_CERTIFICATE": ("database", "trust_server_certificate"),
    "TRIXTER_EMAIL_REMETENTE": ("email", "remetente"),
    "TRIXTER_EMAIL_SERVIDOR": ("email", "servidor"),
    "TRIXTER_EMAIL_PORTA": ("email", "porta"),
    "TRIXTER_EMAIL_USUARIO": ("email", "usuario"),
    "TRIXTER_EMAIL_SENHA": ("email", "senha"),
    "TRIXTER_AUTOMACAO_FUSO_HORARIO": ("automacao", "fuso_horario"),
    "TRIXTER_AUTOMACAO_MAX_TENTATIVAS": ("automacao", "max_tentativas"),
}
_VARIAVEIS_INTEIRAS = {"TRIXTER_EMAIL_PORTA": (1, 65535), "TRIXTER_AUTOMACAO_MAX_TENTATIVAS": (1, None)}


def _inteiro_de_ambiente(nome, valor):
    minimo, maximo = _VARIAVEIS_INTEIRAS[nome]
    if not valor.isdigit():
        raise ValueError(f"{nome} inválida.")
    numero = int(valor)
    if numero < minimo or (maximo is not None and numero > maximo):
        raise ValueError(f"{nome} inválida.")
    return numero


def _variaveis_presentes(ambiente):
    return [nome for nome in VARIAVEIS_CONFIG if nome in ambiente]


def _config_por_ambiente(ambiente):
    presentes = _variaveis_presentes(ambiente)
    if not presentes:
        return None
    config = {}
    for nome in presentes:
        secao, campo = VARIAVEIS_CONFIG[nome]
        valor = str(ambiente[nome]).strip()
        if nome in _VARIAVEIS_INTEIRAS:
            valor = _inteiro_de_ambiente(nome, valor)
        config.setdefault(secao, {})[campo] = valor
    return config


def _arquivo_toml(caminho, ambiente):
    escolhido = caminho or ambiente.get("TRIXTER_CONFIG")
    candidatos = ([Path(escolhido).expanduser()] if escolhido else [
        RAIZ / ".streamlit" / "secrets.toml",
        Path.home() / ".streamlit" / "secrets.toml",
    ])
    for arquivo in candidatos:
        if arquivo.is_file():
            return arquivo
    return None


def carregar_config(caminho=None):
    """Lê uma única fonte: variáveis TRIXTER_* ou um TOML, nunca os dois mesclados."""
    arquivo = _arquivo_toml(caminho, os.environ)
    if _variaveis_presentes(os.environ) and arquivo is not None:
        raise ValueError(
            "Configuração definida ao mesmo tempo por variáveis TRIXTER_* e por arquivo TOML. "
            "Use apenas uma das fontes."
        )
    por_ambiente = _config_por_ambiente(os.environ)
    if por_ambiente is not None:
        return por_ambiente
    if arquivo is not None:
        with arquivo.open("rb") as entrada:
            return tomllib.load(entrada)
    raise ValueError("Configuração não encontrada. Use --config CAMINHO ou TRIXTER_CONFIG.")


def validar_config(config, smtp=True):
    obrigatorios = {"database": ("driver", "server", "database", "trusted_connection")}
    if smtp:
        obrigatorios["email"] = ("remetente", "servidor", "porta", "usuario", "senha")
    for secao, campos in obrigatorios.items():
         for campo in campos:
            if config.get(secao, {}).get(campo) in (None, ""):
                raise ValueError(f"Configuração ausente: [{secao}] {campo}")
    if smtp and int(config["email"]["porta"]) not in range(1, 65536):
        raise ValueError("Porta SMTP inválida.")
    banco = config["database"]
    if str(banco["trusted_connection"]).lower() not in ("yes", "true", "1"):
        if not banco.get("usuario") or not banco.get("senha"):
            raise ValueError("Autenticação SQL requer database.usuario e database.senha.")


def conectar_banco(config):
    import pyodbc

    banco = config["database"]
    def escapar(valor):
         return "{" + str(valor).replace("}", "}}") + "}"

    partes = [f"DRIVER={escapar(banco['driver'])}",
              f"SERVER={escapar(banco['server'])}",
              f"DATABASE={escapar(banco['database'])}"]
    integrado = str(banco.get("trusted_connection", "yes")).lower() in ("yes", "true", "1")
    if integrado:
        partes.append("Trusted_Connection=yes")
    else:
        partes.extend([f"UID={escapar(banco['usuario'])}", f"PWD={escapar(banco['senha'])}"])
    for chave, atributo in (("encrypt", "Encrypt"), ("trust_server_certificate", "TrustServerCertificate")):
        if chave in banco:
            partes.append(f"{atributo}={escapar(banco[chave])}")
    cadeia = ";".join(partes) + ";"

    def abrir():
        return pyodbc.connect(cadeia, timeout=15)

    conexao = abrir_com_retomada(abrir)
    conexao.timeout = 60
    return conexao


def enviar_email(config, destinatario, assunto, corpo, anexo=None, message_id=None):
    email = config["email"]
    mensagem = EmailMessage()
    mensagem["From"] = email["remetente"]
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem["Date"] = formatdate(localtime=False)
    mensagem["Message-ID"] = message_id or make_msgid()
    mensagem.set_content(corpo)
    if anexo:
        mensagem.add_attachment(anexo["conteudo"], maintype="application",
                               subtype="pdf", filename=anexo["nome"])
    contexto = ssl.create_default_context()
    porta = int(email["porta"])
    # closing evita tratar falha no QUIT como falha de um envio já aceito.
    if porta == 465:
        smtp = smtplib.SMTP_SSL(email["servidor"], porta, timeout=30, context=contexto)
    else:
        smtp = smtplib.SMTP(email["servidor"], porta, timeout=30)
    with closing(smtp) as servidor:
        if porta != 465:
            servidor.starttls(context=contexto)
        servidor.login(email["usuario"], email["senha"])
        recusados = servidor.send_message(mensagem)
        if recusados:
            raise smtplib.SMTPRecipientsRefused(recusados)
    return mensagem["Message-ID"]


# Códigos que o Azure SQL serverless devolve enquanto sai da pausa.
CODIGOS_BANCO_RETOMANDO = (
    "40613", "40197", "40501", "4060", "10928", "10929",
    "49918", "49919", "49920", "42108", "42109",
    "10060", "HYT00", "HYT01", "08001", "08S01",
)


def erro_de_retomada(erro):
    texto = " ".join(str(parte) for parte in getattr(erro, "args", ()))
    return any(codigo in texto for codigo in CODIGOS_BANCO_RETOMANDO)


def abrir_com_retomada(abrir, dormir=time.sleep, relogio=time.monotonic, limite=90):
    """Repete a conexão enquanto o banco pausado está voltando."""
    espera = 5.0
    prazo = relogio() + limite
    while True:
        try:
            return abrir()
        except Exception as erro:
            agora = relogio()
            if not erro_de_retomada(erro) or agora >= prazo:
                raise
            pausa = min(espera, prazo - agora)
            if pausa <= 0:
                raise
            dormir(pausa)
            espera = min(espera * 2, 15.0)
