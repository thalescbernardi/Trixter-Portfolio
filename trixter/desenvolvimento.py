"""Recursos de teste desativados por padrão."""


def cadastro_local_permitido(ativacao, endereco_servidor, email):
    """Exige ativação, servidor em loopback e destinatário fictício reservado."""
    return (
        ativacao == "1"
        and endereco_servidor in ("127.0.0.1", "::1")
        and email.strip().lower().endswith("@example.test")
    )
