"""Instrumentacao inerte por padrao; ativacao apenas pelo lancador local protegido."""
from contextlib import contextmanager
import re


_destino = None
_ETAPAS = {
    "conexao_1", "cursor_1", "consulta_usuario", "conexao_2", "cursor_2",
    "registrar_tentativa", "verificar_limites", "liberar_controles",
    "atualizar_ultimo_acesso", "commit_login", "rollback_login",
}
_CLASSES = {
    "Error", "Warning", "InterfaceError", "DatabaseError", "DataError",
    "OperationalError", "IntegrityError", "InternalError", "ProgrammingError",
    "NotSupportedError", "ErroLimite", "BloqueioLocal", "ValueError", "TypeError",
}
_NATIVO = re.compile(r"\((-?\d{1,10})\)(?=\s*(?:\([A-Za-z][A-Za-z0-9_]*\))?\s*$)")


def _informar(etapa, erro):
    if _destino is None or etapa not in _ETAPAS:
        return
    try:
        import pyodbc
        atual = erro
        vistos = set()
        estado = "indisponivel"
        numero = "indisponivel"
        while atual is not None and id(atual) not in vistos:
            vistos.add(id(atual))
            if isinstance(atual, pyodbc.Error):
                args = atual.args
                if args and isinstance(args[0], str) and re.fullmatch(r"[A-Z0-9]{5}", args[0]):
                    estado = args[0]
                if len(args) > 1 and isinstance(args[1], str):
                    encontrado = _NATIVO.search(args[1])
                    if encontrado:
                        numero = str(int(encontrado.group(1)))
                break
            atual = atual.__cause__
        classe = type(erro).__name__
        if classe not in _CLASSES:
            classe = "Exception"
        _destino(f"etapa={etapa} classe={classe} sqlstate={estado} nativo={numero}")
    except Exception:
        # Falha no diagnostico nunca substitui a excecao original.
        pass


@contextmanager
def etapa(nome):
    try:
        yield
    except Exception as erro:
        _informar(nome, erro)
        raise


def executar(nome, funcao, *args, **kwargs):
    with etapa(nome):
        return funcao(*args, **kwargs)
