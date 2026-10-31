"""Regra e hash da senha de acesso."""
import bcrypt


def mensagem_senha(senha):
    """Devolve o aviso da primeira regra quebrada. Senha aceita devolve None."""
    if len(senha) < 8:
        return "A senha deve ter pelo menos 8 caracteres. Por favor, tente novamente."
    if not any(caractere.isdigit() for caractere in senha) or not any(caractere.isalpha() for caractere in senha):
        return "A senha deve conter pelo menos uma letra e um número. Por favor, tente novamente."
    if not any(caractere.isupper() for caractere in senha) or not any(caractere.islower() for caractere in senha):
        return "A senha deve conter pelo menos uma letra maiúscula e uma letra minúscula. Por favor, tente novamente."
    if not any(not caractere.isalnum() for caractere in senha):
        return "A senha deve conter pelo menos um caractere especial. Por favor, tente novamente."
    return None


def gerar_hash_senha(senha):
    senha_bytes = senha.encode("utf-8")
    hash_senha = bcrypt.hashpw(senha_bytes, bcrypt.gensalt())
    return hash_senha.decode("utf-8")


# Hash válido só para gastar o mesmo tempo quando a conta não existe.
_HASH_PREENCHIMENTO = "$2b$12$gPylYEhyYs2inuTlkIhqDeJ4MsrIkFN0b7Z5Y/ZXc1yGDzI4lZI1u"


def senha_confere(senha, hash_armazenado, verificar=None):
    """Confere a senha. Sem hash gravado, ainda mede um bcrypt."""
    verificar = verificar or bcrypt.checkpw
    material = hash_armazenado or _HASH_PREENCHIMENTO
    try:
        confere = verificar(senha.encode("utf-8"), str(material).encode("utf-8"))
    except ValueError:
        confere = False
    return bool(hash_armazenado) and bool(confere)
