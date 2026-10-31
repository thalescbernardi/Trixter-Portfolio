"""Sobe a interface Streamlit. Segredos entram só na execução, nunca na imagem."""
import os
from pathlib import Path


APP = Path(__file__).resolve().parent
SEGREDOS = APP / ".streamlit" / "secrets.toml"
ENTRADA = "Gerenciador de Gastos V2.py"
PORTA_PADRAO = "8501"

CAMPOS = {
    "database": (
        ("TRIXTER_WEB_DATABASE_DRIVER", "driver"),
        ("TRIXTER_WEB_DATABASE_SERVER", "server"),
        ("TRIXTER_WEB_DATABASE_NAME", "database"),
        ("TRIXTER_WEB_DATABASE_USERNAME", "username"),
        ("TRIXTER_WEB_DATABASE_PASSWORD", "password"),
    ),
    "email": (
        ("TRIXTER_WEB_EMAIL_REMETENTE", "remetente"),
        ("TRIXTER_WEB_EMAIL_SERVIDOR", "servidor"),
        ("TRIXTER_WEB_EMAIL_PORTA", "porta"),
        ("TRIXTER_WEB_EMAIL_USUARIO", "usuario"),
        ("TRIXTER_WEB_EMAIL_SENHA", "senha"),
    ),
}


def _nomes():
    return [nome for campos in CAMPOS.values() for nome, _campo in campos]


def _preenchidos(ambiente):
    return [
        nome for nome in _nomes()
        if str(ambiente.get(nome, "")).strip()
    ]


def _toml_basico(valor):
    texto = (
        str(valor)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{texto}"'


def porta_de_escuta(ambiente):
    """A porta interna segue WEBSITES_PORT, com 8501 quando a variável falta."""
    bruto = str(ambiente.get("WEBSITES_PORT", PORTA_PADRAO)).strip()
    if not bruto.isdigit() or not 1 <= int(bruto) <= 65535:
        raise ValueError("WEBSITES_PORT inválida.")
    return bruto


def preparar_segredos(ambiente, destino):
    """Grava o TOML do Streamlit só com o conjunto completo. Não devolve valores."""
    preenchidos = _preenchidos(ambiente)
    if not preenchidos:
        return "arquivo" if Path(destino).is_file() else "ausente"
    faltantes = [nome for nome in _nomes() if nome not in preenchidos]
    if faltantes:
        raise ValueError(
            "Segredos da interface incompletos: " + ", ".join(faltantes)
        )
    linhas = []
    for secao, campos in CAMPOS.items():
        linhas.append(f"[{secao}]")
        for nome, campo in campos:
            valor = ambiente[nome]
            if campo == "porta":
                valor = str(valor).strip()
                if not valor.isdigit() or not 1 <= int(valor) <= 65535:
                    raise ValueError("TRIXTER_WEB_EMAIL_PORTA inválida.")
                linhas.append(f"{campo} = {int(valor)}")
            else:
                linhas.append(f"{campo} = {_toml_basico(valor)}")
        linhas.append("")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".tmp")
    temporario.write_text("\n".join(linhas), encoding="utf-8")
    os.chmod(temporario, 0o600)
    temporario.replace(destino)
    os.chmod(destino, 0o600)
    return "variaveis"


def comando_streamlit(porta):
    return [
        "streamlit", "run", ENTRADA,
        "--server.headless", "true",
        "--server.address", "0.0.0.0",
        "--server.port", porta,
    ]


def main():
    try:
        porta = porta_de_escuta(os.environ)
        preparar_segredos(os.environ, SEGREDOS)
    except ValueError as erro:
        raise SystemExit(str(erro)) from None
    os.execvp("streamlit", comando_streamlit(porta))


if __name__ == "__main__":
    main()
