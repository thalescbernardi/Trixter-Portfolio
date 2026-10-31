"""Repetição do contêiner só quando a abertura da conexão falha."""
import re
from pathlib import Path

WORKFLOW = Path("docs/workflows/envios.yml")


def _script():
    return WORKFLOW.read_text(encoding="utf-8")


def _padrao():
    script = _script()
    encontrado = re.search(r"grep -Eq '([^']+)' envio\.log", script)
    assert encontrado, "o workflow não declara o filtro da conexão inicial"
    return encontrado.group(1)


def _falha_inicial(log):
    padrao = _padrao()
    return any(re.search(padrao, linha) for linha in log.splitlines())


def _execucoes(logs):
    """Espelha o laço: no máximo três execuções; espera 60s e depois 120s."""
    esperas = []
    for tentativa, log in enumerate(logs, start=1):
        if tentativa == 3 or not _falha_inicial(log):
            return tentativa, esperas
        esperas.append(60 if tentativa == 1 else 120)
    raise AssertionError("o laço passou de três execuções")


def _linha(sqlstate, operacao, erro_sql, frase="Executor interrompido"):
    return (
        f"ERROR {frase} (OperationalError sqlstate={sqlstate} "
        f"operacao={operacao} erro_sql={erro_sql})."
    )


def test_workflow_repete_so_a_abertura_e_limita_tres_execucoes():
    script = _script()
    assert 'while [ "$tentativa" -le 3 ]' in script
    assert '[ "$tentativa" -eq 3 ]' in script
    assert script.index("sleep 60") < script.index("sleep 120")
    assert 'grep -q "erro_sql=40615"' not in script
    assert _falha_inicial(_linha("HYT00", "conectar", "0"))
    assert _falha_inicial(_linha("HYT01", "conectar", "0"))
    assert _falha_inicial(_linha("42000", "conectar", "40615"))
    assert _execucoes([_linha("HYT00", "conectar", "0")] * 5) == (3, [60, 120])
    assert _execucoes([
        _linha("HYT01", "conectar", "0"),
        _linha("42000", "conectar", "40615"),
        _linha("HYT00", "conectar", "0"),
    ]) == (3, [60, 120])


def test_workflow_nao_repete_login_incorreto_nem_falha_de_negocio():
    assert not _falha_inicial(_linha("28000", "conectar", "18456"))
    assert not _falha_inicial(_linha("HYT00", "buscar_usuarios", "0"))
    assert not _falha_inicial(_linha("HYT01", "historico.reservar", "0"))
    assert not _falha_inicial(_linha("HYT00", "historico.atualizar", "0"))
    expurgo = (
        "ERROR Expurgo de demonstração falhou "
        "(sqlstate=HYT00 operacao=executor erro_sql=0)."
    )
    assert not _falha_inicial(expurgo)
    assert not _falha_inicial(
        "ERROR Expurgo de demonstrações interrompido (OperationalError)."
    )
    negocio = "\n".join([
        "INFO Resultado: {'enviados': 1, 'falhas': 1}",
        _linha("HYT00", "historico.atualizar", "0"),
        expurgo,
    ])
    assert _execucoes([negocio, negocio]) == (1, [])
    assert _execucoes([
        _linha("HYT00", "conectar", "0"),
        _linha("28000", "conectar", "18456"),
    ]) == (2, [60])
