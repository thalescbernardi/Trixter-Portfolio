import pytest

from trixter.desenvolvimento import cadastro_local_permitido


@pytest.mark.parametrize("flag,host,email,permitido", [
    ("1", "127.0.0.1", "empresa@example.test", True),
    ("1", "::1", "empresa@example.test", True),
    (None, "127.0.0.1", "empresa@example.test", False),
    ("1", "0.0.0.0", "empresa@example.test", False),
    ("1", None, "empresa@example.test", False),
    ("1", "127.0.0.1", "pessoa@gmail.com", False),
    ("1", "127.0.0.1", "empresa@example.test.com", False),
])
def test_cadastro_local(flag, host, email, permitido):
    assert cadastro_local_permitido(flag, host, email) is permitido
