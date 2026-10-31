"""Ciclo dos códigos de e-mail, independente da interface e do SMTP.

O intervalo é por sessão/fluxo; não substitui limites persistentes por conta/IP.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta


def limpar(estado, fluxo):
    estado.pop(f"verificacao_{fluxo}", None)
    estado.pop(f"autorizacao_{fluxo}", None)


def iniciar_solicitacao(estado, fluxo, agora=None):
    """Revoga a autorização anterior inclusive quando o reenvio é bloqueado."""
    agora = agora or datetime.now()
    limpar(estado, fluxo)
    chave = f"reenvio_{fluxo}"
    limite = estado.get(chave)
    if limite and agora < limite:
        return max(1, int((limite - agora).total_seconds()) + 1)
    estado[chave] = agora + timedelta(seconds=60)
    return 0


def _resumo_codigo(sal, fluxo, usuario_id, email, codigo):
    material = f"{sal}:{fluxo}:{usuario_id}:{email}:{codigo.strip()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def registrar(estado, fluxo, codigo, email, usuario_id=None, agora=None, *, proteger=False, email_anterior=None):
    agora = agora or datetime.now()
    limpar(estado, fluxo)
    endereco = email.strip().lower()
    desafio = dict(
        email=endereco, usuario_id=usuario_id,
        finalidade=fluxo, expira=agora + timedelta(minutes=10), tentativas=0,
    )
    if email_anterior is not None:
        desafio["email_anterior"] = str(email_anterior).strip().lower()
    if proteger:
        sal = secrets.token_hex(16)
        desafio["sal"] = sal
        desafio["codigo_hash"] = _resumo_codigo(sal, fluxo, usuario_id, endereco, codigo)
    else:
        desafio["codigo"] = codigo
    estado[f"verificacao_{fluxo}"] = desafio


def _codigo_confere(desafio, digitado, fluxo):
    informado = (digitado or "").strip()
    if "codigo_hash" not in desafio:
        return informado == desafio.get("codigo")
    try:
        resumo = _resumo_codigo(
            desafio.get("sal") or "",
            desafio.get("finalidade", fluxo),
            desafio.get("usuario_id"),
            desafio.get("email") or "",
            informado,
        )
        return hmac.compare_digest(resumo, desafio["codigo_hash"])
    except (TypeError, ValueError):
        return False


def validar(estado, fluxo, digitado, agora=None):
    agora = agora or datetime.now()
    desafio = estado.get(f"verificacao_{fluxo}")
    if not desafio:
        return "ausente"
    if agora >= desafio["expira"]:
        limpar(estado, fluxo)
        return "expirado"
    if desafio["tentativas"] >= 5:
        limpar(estado, fluxo)
        return "limite"
    if desafio.get("finalidade", fluxo) != fluxo:
        limpar(estado, fluxo)
        return "ausente"
    if not _codigo_confere(desafio, digitado, fluxo):
        desafio["tentativas"] += 1
        if desafio["tentativas"] >= 5:
            limpar(estado, fluxo)
            return "limite"
        return "invalido"
    # Consome o código e vincula uma autorização curta ao mesmo fluxo.
    autorizacao = dict(
        email=desafio["email"], usuario_id=desafio["usuario_id"],
        finalidade=desafio.get("finalidade", fluxo),
        expira=agora + timedelta(minutes=10),
    )
    if desafio.get("email_anterior"):
        autorizacao["email_anterior"] = desafio["email_anterior"]
    estado[f"autorizacao_{fluxo}"] = autorizacao
    estado.pop(f"verificacao_{fluxo}")
    return "sucesso"


def autorizacao(estado, fluxo, agora=None):
    agora = agora or datetime.now()
    dados = estado.get(f"autorizacao_{fluxo}")
    if not dados or agora >= dados["expira"]:
        estado.pop(f"autorizacao_{fluxo}", None)
        return None
    return dados.copy()


def mensagem(estado, fluxo, resultado):
    if resultado == "invalido":
        restantes = 5 - estado[f"verificacao_{fluxo}"]["tentativas"]
        return f"Código inválido. Tentativas restantes: {restantes}"
    return {
        "expirado": "O código expirou. Solicite um novo código.",
        "limite": "Limite de tentativas excedido. Solicite um novo código.",
        "ausente": "Solicite um novo código antes de validar.",
    }[resultado]
