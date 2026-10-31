"""Falhas de login ficticias: apenas metadados seguros sao registrados."""
import ast
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pyodbc
import pytest

from trixter import diagnostico_login as diag


class Estado(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


@pytest.mark.parametrize("falha", [
    "conexao_1", "cursor_1", "consulta_usuario", "conexao_2", "cursor_2",
    "verificar_limites", "liberar_controles", "atualizar_ultimo_acesso", "commit_login",
    "registrar_tentativa", "sem_falha",
])
def test_identifica_etapa_sem_registrar_conteudo_sensivel(falha, monkeypatch):
    monkeypatch.setattr(pyodbc, "connect", Mock(side_effect=AssertionError("SQL real proibido")))
    saida = Mock()
    monkeypatch.setattr(diag, "_destino", saida)
    erro = pyodbc.OperationalError("42000", "senha-ficticia; pessoa@example.invalid; SERVER=remoto; (229) (SQLExecDirectW)")
    def verificar(nome):
        if nome == falha: raise erro
    estado = Estado(email_entrada="pessoa@example.invalid", senha="senha-ficticia")
    st = SimpleNamespace(session_state=estado)
    cursor1 = Mock()
    cursor1.description = [(nome,) for nome in ("senha", "id_usuario", "onboarding_concluido")]
    cursor1.execute.side_effect = lambda *a: verificar("consulta_usuario")
    cursor1.fetchone.return_value = ("hash-ficticio", "usuario-ficticio", 1)
    cursor2 = Mock()
    cursor2.execute.side_effect = lambda *a: verificar("atualizar_ultimo_acesso")
    conexoes = [Mock(), Mock()]
    for i, conexao in enumerate(conexoes, 1):
        def obter_cursor(i=i):
            verificar(f"cursor_{i}")
            return cursor1 if i == 1 else cursor2
        conexao.cursor.side_effect = obter_cursor
    conexoes[1].commit.side_effect = lambda: verificar("commit_login")
    contador = 0
    def conectar():
        nonlocal contador
        contador += 1
        verificar(f"conexao_{contador}")
        return conexoes[contador - 1]
    class ErroLimite(Exception): pass
    def confirmar(*args, **kwargs):
        verificar("registrar_tentativa" if kwargs["registrar"] else "verificar_limites")
        return True
    limite = SimpleNamespace(ErroLimite=ErroLimite, confirmar_reserva=confirmar,
        liberar_par=lambda *a: verificar("liberar_controles"))
    abrir = Mock()
    contexto = dict(st=st, closing=closing, pyodbc=pyodbc, diagnostico_login=diag,
        conectar_banco=conectar, ip_cliente=lambda: "127.0.0.1",
        senha_confere=lambda *a: falha != "registrar_tentativa",
        limite_acesso=limite, abrir_sessao=abrir)
    raiz = Path(__file__).resolve().parents[1]
    arvore = ast.parse((raiz / "Gerenciador de Gastos V2.py").read_text(encoding="utf-8"))
    funcao = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == "confirmar_entrada")
    exec(compile(ast.Module(body=[funcao], type_ignores=[]), "login_ficticio", "exec"), contexto)
    contexto["confirmar_entrada"](Mock())
    if falha == "sem_falha":
        saida.assert_not_called()
        abrir.assert_called_once()
        conexoes[1].commit.assert_called_once()
        assert "aviso_banco" not in estado
        return
    saida.assert_called_once_with(f"etapa={falha} classe=OperationalError sqlstate=42000 nativo=229")
    assert "pausado" in estado.aviso_banco
    abrir.assert_not_called()
    if falha in {"consulta_usuario", "verificar_limites", "liberar_controles", "atualizar_ultimo_acesso", "commit_login", "registrar_tentativa"}:
        conexoes[0 if falha == "consulta_usuario" else 1].rollback.assert_called_once()


def test_desativado_por_padrao_e_excecao_original_preservada(capsys):
    assert diag._destino is None
    erro = pyodbc.OperationalError("08001", "segredo-ficticio (53)")
    with pytest.raises(pyodbc.OperationalError) as capturado:
        with diag.etapa("conexao_1"):
            raise erro
    assert capturado.value is erro
    assert capsys.readouterr() == ("", "")


def test_causa_encadeada_ausencia_de_codigo_e_falha_do_destino(monkeypatch):
    saida = Mock()
    monkeypatch.setattr(diag, "_destino", saida)
    class ErroLimite(Exception): pass
    try:
        try: raise pyodbc.ProgrammingError("42S02", "dados-ficticios (208) (SQLExecDirectW)")
        except pyodbc.Error as causa: raise ErroLimite("nao imprimir") from causa
    except ErroLimite as erro:
        diag._informar("verificar_limites", erro)
    saida.assert_called_once_with("etapa=verificar_limites classe=ErroLimite sqlstate=42S02 nativo=208")
    saida.reset_mock()
    diag._informar("conexao_1", pyodbc.Error("senha-ficticia", "email-ficticio"))
    saida.assert_called_once_with("etapa=conexao_1 classe=Error sqlstate=indisponivel nativo=indisponivel")
    saida.side_effect = RuntimeError("falha-ficticia")
    erro = ValueError("nao imprimir")
    with pytest.raises(ValueError) as capturado:
        with diag.etapa("conexao_1"): raise erro
    assert capturado.value is erro
