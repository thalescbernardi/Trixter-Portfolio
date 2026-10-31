"""Expurgo de demonstrações abandonadas, com banco fictício."""
import logging
from contextlib import nullcontext
from datetime import datetime, timedelta
from pathlib import Path

import pyodbc
import pytest

from trixter.demo_expurgo import (
    ID_CONTA_DEMO,
    LIMITE_POR_EXECUCAO,
    RETENCAO,
    TABELAS,
    conexao_utilizavel,
    excluir_demonstracao,
    expurgar_demonstracoes,
    padrao_email,
)

AGORA = datetime(2026, 10, 15, 12, 0, 0)
CORTE = AGORA - RETENCAO


def _email_ok(email, padrao):
    texto = (email or "").strip().lower()
    sufixo = padrao[2:]
    return texto.count("@") == 1 and len(texto) > len(sufixo) and texto.endswith(sufixo)


def _conta(identificador, **alteracoes):
    dados = {
        "id_usuario": identificador,
        "conta_demo": 1,
        "email": f"{identificador}@demo.trixter.local",
        "data_entrada": CORTE - timedelta(hours=1),
    }
    dados.update(alteracoes)
    return dados


class _Banco:
    def __init__(self, contas, falhar_id=None, morta=False):
        self.contas = {conta["id_usuario"]: dict(conta) for conta in contas}
        self.comandos = []
        self.commits = 0
        self.rollbacks = 0
        self.bloqueios = set()
        self.remocoes = []
        self.externos = set()
        self.falhar_id = falhar_id
        self.morta = morta
        self.revogar = set()
        self.vinculos = []

    def commit(self):
        for identificador in self.remocoes:
            self.contas.pop(identificador, None)
        self.remocoes.clear()
        self.commits += 1
        self.bloqueios.clear()

    def rollback(self):
        self.remocoes.clear()
        self.rollbacks += 1
        self.bloqueios.clear()


class _Conexao:
    def __init__(self, banco):
        self.banco = banco
        self.fechada = False

    def cursor(self):
        return _Cursor(self.banco)

    def commit(self):
        self.banco.commit()

    def rollback(self):
        self.banco.rollback()

    def close(self):
        self.fechada = True


class _Cursor:
    def __init__(self, banco):
        self.banco = banco
        self._linha = None
        self._linhas = []

    def execute(self, sql, *params):
        if len(params) == 1 and isinstance(params[0], (tuple, list)):
            params = tuple(params[0])
        texto = " ".join(sql.split())
        self.banco.comandos.append((texto, params))
        if self.banco.morta:
            raise pyodbc.OperationalError("08S01", "conexao encerrada pessoa@example.com")
        if "sp_getapplock" in texto:
            recurso = params[0]
            if recurso in self.banco.bloqueios or recurso in self.banco.externos:
                self._linha = (-1,)
                return
            self.banco.bloqueios.add(recurso)
            self._linha = (0,)
            return
        if texto.startswith("SELECT TOP"):
            self._linhas = self._candidatos(params)
            return
        if "UPDLOCK" in texto:
            self._linha = self._revalidar(texto, params)
            return
        if texto.startswith("DELETE"):
            identificador = params[0]
            tabela = texto.split()[2]
            if self.banco.falhar_id == identificador and "envios_automaticos" in texto:
                raise RuntimeError("falha ficticia pessoa@example.com segredo")
            if tabela == "dbo.recorrencias" and any(
                origem in ("dbo.gastos", "dbo.receitas")
                and usuario == identificador
                and referencia
                for origem, usuario, referencia in self.banco.vinculos
            ):
                raise pyodbc.IntegrityError("23000", "FK (547)")
            self.banco.vinculos = [
                item for item in self.banco.vinculos
                if not (item[0] == tabela and item[1] == identificador)
            ]
            if texto.endswith("dbo.usuarios WHERE id_usuario = ?"):
                self.banco.remocoes.append(identificador)
            return
        if texto == "SELECT 1":
            self._linha = (1,)
            return
        if "OBJECT_ID" in texto and "limites_acesso" in texto:
            self._linha = (None,)
            return
        raise AssertionError(texto)

    def fetchone(self):
        return self._linha

    def fetchall(self):
        return list(self._linhas)

    def close(self):
        return None

    def _candidatos(self, params):
        limite, modelo, corte, padrao = params
        elegiveis = [
            conta for conta in self.banco.contas.values()
            if conta.get("conta_demo") == 1
            and conta["id_usuario"] != modelo
            and conta.get("data_entrada") is not None
            and conta["data_entrada"] < corte
            and _email_ok(conta.get("email"), padrao)
        ]
        elegiveis.sort(key=lambda conta: conta["data_entrada"])
        return [(conta["id_usuario"],) for conta in elegiveis[: int(limite)]]

    def _revalidar(self, texto, params):
        identificador = params[0]
        conta = self.banco.contas.get(identificador)
        if conta is None or identificador in self.banco.revogar:
            return None
        if conta.get("conta_demo") != 1 or identificador == params[1]:
            return None
        if "data_entrada <" in texto:
            if conta.get("data_entrada") is None or not conta["data_entrada"] < params[2]:
                return None
            padrao = params[3]
        else:
            padrao = params[2]
        if not _email_ok(conta.get("email"), padrao):
            return None
        return (identificador,)


def _expurgar(contas, limite=LIMITE_POR_EXECUCAO, **banco_kwargs):
    banco = _Banco(contas, **banco_kwargs)
    resultado = expurgar_demonstracoes(_Conexao(banco), AGORA, limite)
    return banco, resultado


def test_so_entra_quem_cumpre_os_quatro_criterios():
    banco, resultado = _expurgar([
        _conta("antiga"),
        _conta("exata", data_entrada=CORTE),
        _conta("recente", data_entrada=AGORA - timedelta(hours=23)),
        _conta("real", conta_demo=0, email="pessoa@example.com"),
        _conta("real-com-dominio", conta_demo=0, email="real@demo.trixter.local"),
        _conta("outro-dominio", email="pessoa@example.com"),
        _conta("sufixo", email="pessoa@demo.trixter.local.evil"),
        _conta("dois-arrobas", email="a@b@demo.trixter.local"),
        _conta("modelo", id_usuario=ID_CONTA_DEMO),
        _conta("sem-data", data_entrada=None),
    ])
    assert resultado == {"excluidas": 1, "ignoradas": 0, "adiadas": 0, "falhas": 0}
    assert "antiga" not in banco.contas
    assert set(banco.contas) == {
        "exata", "recente", "real", "real-com-dominio", "outro-dominio",
        "sufixo", "dois-arrobas", ID_CONTA_DEMO, "sem-data",
    }
    selecao = next(sql for sql, _params in banco.comandos if sql.startswith("SELECT TOP"))
    assert "conta_demo = 1" in selecao
    assert "id_usuario <> ?" in selecao
    assert "data_entrada < ?" in selecao
    assert "LIKE ? ESCAPE" in selecao
    assert "LEN(REPLACE" in selecao or "REPLACE(LOWER" in selecao
    assert padrao_email() == "%_@demo.trixter.local"


def test_revalidacao_impede_a_exclusao_se_a_conta_deixou_de_ser_elegivel():
    banco = _Banco([_conta("antiga")])
    banco.revogar.add("antiga")
    resultado = expurgar_demonstracoes(_Conexao(banco), AGORA)
    assert resultado["excluidas"] == 0
    assert resultado["ignoradas"] == 1
    assert "antiga" in banco.contas
    assert not any(sql.startswith("DELETE") for sql, _params in banco.comandos)


def test_exclusao_completa_segue_a_ordem_e_uma_transacao_por_conta():
    banco, resultado = _expurgar([_conta("antiga")])
    assert resultado["excluidas"] == 1
    apagamentos = [sql for sql, _params in banco.comandos if sql.startswith("DELETE")]
    assert apagamentos == [f"DELETE FROM {tabela} WHERE id_usuario = ?" for tabela in TABELAS]
    assert banco.commits == 1


def test_gastos_e_receitas_saem_antes_das_recorrencias_vinculadas():
    assert TABELAS == (
        "dbo.planejamentos",
        "dbo.gastos",
        "dbo.receitas",
        "dbo.recorrencias",
        "dbo.orcamentos",
        "dbo.categorias",
        "dbo.envios_automaticos",
        "dbo.usuarios",
    )
    banco = _Banco([_conta("antiga")])
    banco.vinculos = [
        ("dbo.recorrencias", "antiga", "r1"),
        ("dbo.gastos", "antiga", "r1"),
        ("dbo.receitas", "antiga", "r1"),
    ]
    resultado = expurgar_demonstracoes(_Conexao(banco), AGORA)
    apagamentos = [sql for sql, _params in banco.comandos if sql.startswith("DELETE")]
    gastos = apagamentos.index("DELETE FROM dbo.gastos WHERE id_usuario = ?")
    receitas = apagamentos.index("DELETE FROM dbo.receitas WHERE id_usuario = ?")
    recorrencias = apagamentos.index("DELETE FROM dbo.recorrencias WHERE id_usuario = ?")
    assert gastos < recorrencias
    assert receitas < recorrencias
    assert resultado == {"excluidas": 1, "ignoradas": 0, "adiadas": 0, "falhas": 0}
    assert banco.vinculos == []
    assert "antiga" not in banco.contas


def test_falha_desfaz_a_conta_e_continua_a_proxima():
    banco, resultado = _expurgar(
        [_conta("falha", data_entrada=CORTE - timedelta(hours=2)), _conta("seguinte")],
        falhar_id="falha",
    )
    assert resultado["falhas"] == 1
    assert resultado["excluidas"] == 1
    assert "falha" in banco.contas
    assert "seguinte" not in banco.contas


def test_bloqueio_ocupado_adia_sem_apagar_e_a_segunda_passagem_e_idempotente():
    banco = _Banco([_conta("antiga")])
    banco.externos.add("trixter:demo:antiga")
    adiada = expurgar_demonstracoes(_Conexao(banco), AGORA)
    assert adiada["adiadas"] == 1
    assert "antiga" in banco.contas
    assert not any(sql.startswith("DELETE") for sql, _params in banco.comandos)
    banco.externos.clear()
    primeira = expurgar_demonstracoes(_Conexao(banco), AGORA)
    segunda = expurgar_demonstracoes(_Conexao(banco), AGORA)
    assert primeira["excluidas"] == 1
    assert segunda == {"excluidas": 0, "ignoradas": 0, "adiadas": 0, "falhas": 0}
    assert "antiga" not in banco.contas


def test_logout_remove_demonstracao_recente_e_recusa_conta_real():
    recente = _conta("recente", data_entrada=AGORA)
    banco = _Banco([recente, _conta("real", conta_demo=0, email="pessoa@example.com")])
    assert excluir_demonstracao(_Conexao(banco), "recente", AGORA) == "excluida"
    assert "recente" not in banco.contas
    assert not any("data_entrada" in sql for sql, _params in banco.comandos)
    assert excluir_demonstracao(_Conexao(banco), "real", AGORA) == "ignorada"
    assert "real" in banco.contas
    recursos = [
        params[0] for sql, params in banco.comandos if "sp_getapplock" in sql
    ]
    assert recursos[0] == "trixter:demo:recente"
    assert recursos[1] == "trixter:demo:real"
    ocupada = _Banco([_conta("ocupada", data_entrada=AGORA)])
    ocupada.externos.add("trixter:demo:ocupada")
    with pytest.raises(RuntimeError, match="bloqueio"):
        excluir_demonstracao(_Conexao(ocupada), "ocupada", AGORA)
    assert "ocupada" in ocupada.contas
    assert not any(sql.startswith("DELETE") for sql, _params in ocupada.comandos)


def test_limite_por_execucao_remove_as_mais_antigas():
    contas = [
        _conta(f"d{indice}", data_entrada=CORTE - timedelta(hours=indice + 1))
        for indice in range(5)
    ]
    banco, resultado = _expurgar(contas, limite=2)
    assert resultado["excluidas"] == 2
    assert "d4" not in banco.contas and "d3" not in banco.contas
    assert {"d0", "d1", "d2"} <= set(banco.contas)
    assert LIMITE_POR_EXECUCAO == 32


def test_lista_de_tabelas_nao_esta_duplicada_no_aplicativo():
    fonte = Path("Gerenciador de Gastos V2.py").read_text(encoding="utf-8")
    assert "DELETE FROM dbo.planejamentos" not in fonte
    assert TABELAS[-2:] == ("dbo.envios_automaticos", "dbo.usuarios")


def test_falha_do_expurgo_nao_registra_email_nem_credencial(caplog):
    banco = _Banco([_conta("falha")], falhar_id="falha")
    with caplog.at_level(logging.ERROR):
        resultado = expurgar_demonstracoes(_Conexao(banco), AGORA)
    assert resultado["falhas"] == 1
    assert "pessoa@example.com" not in caplog.text
    assert "segredo" not in caplog.text
    assert "RuntimeError" in caplog.text


def _cli(monkeypatch, conexao, executar):
    import executar_envios as cli
    monkeypatch.setattr(cli, "carregar_config", lambda *a: {"automacao": {}})
    monkeypatch.setattr(cli, "validar_config", lambda *a, **k: None)
    monkeypatch.setattr(cli, "conectar_banco", lambda *a: conexao)
    monkeypatch.setattr(cli.Historico, "exclusivo", lambda self: nullcontext())
    monkeypatch.setattr(cli.Historico, "expurgar", lambda self, agora: 0)
    monkeypatch.setattr(cli, "executar", executar)
    return cli


def test_simulacao_nao_altera_o_banco(monkeypatch):
    banco = _Banco([_conta("antiga")])
    conexao = _Conexao(banco)

    def executar(*_args, **_kwargs):
        return {"falhas": 0, "incertos": 0}

    cli = _cli(monkeypatch, conexao, executar)
    assert cli.main(["--simular"]) == 0
    assert banco.comandos == []
    assert banco.commits == 0 and banco.rollbacks == 0
    assert "antiga" in banco.contas


def test_falha_de_envio_ainda_expurga_e_falha_de_expurgo_nao_reenvia(monkeypatch):
    banco = _Banco([_conta("antiga")])
    envios = []

    def executar(*_args, **_kwargs):
        envios.append("envio")
        raise pyodbc.ProgrammingError("42S22", "Invalid column name 'x'. (207) pessoa@example.com")

    cli = _cli(monkeypatch, _Conexao(banco), executar)
    assert cli.main(["--enviar"]) == 1
    assert envios == ["envio"]
    assert "antiga" not in banco.contas

    banco = _Banco([_conta("antiga")])
    envios.clear()

    def sucesso(*_args, **_kwargs):
        envios.append("envio")
        return {"falhas": 0, "incertos": 0}

    def expurgo_quebrado(*_args, **_kwargs):
        raise RuntimeError("pessoa@example.com segredo")

    cli = _cli(monkeypatch, _Conexao(banco), sucesso)
    monkeypatch.setattr(cli, "expurgar_demonstracoes", expurgo_quebrado)
    assert cli.main(["--enviar"]) == 0
    assert envios == ["envio"]
    assert "antiga" in banco.contas


def test_falha_da_limpeza_nao_muda_envio_nem_expurgo(monkeypatch, caplog):
    ordem = []

    def executar(*_args, **_kwargs):
        ordem.append("envio")
        return {"falhas": 0, "incertos": 0}

    def expurgo(*_args, **_kwargs):
        ordem.append("expurgo")
        return {"excluidas": 0, "ignoradas": 0, "adiadas": 0, "falhas": 0}

    def limpar(*_args, **_kwargs):
        ordem.append("limpeza")
        raise RuntimeError("pessoa@example.com segredo")

    cli = _cli(monkeypatch, _Conexao(_Banco([])), executar)
    monkeypatch.setattr(cli, "expurgar_demonstracoes", expurgo)
    monkeypatch.setattr(cli, "limpar_expirados", limpar)
    with caplog.at_level(logging.ERROR):
        assert cli.main(["--enviar"]) == 0
    assert ordem == ["envio", "expurgo", "limpeza"]
    assert "Limpeza de limites de acesso interrompida" in caplog.text
    assert "pessoa@example.com" not in caplog.text
    assert "segredo" not in caplog.text

    ordem.clear()
    assert cli.main(["--simular"]) == 0
    assert ordem == ["envio"]

    ordem.clear()
    monkeypatch.setattr(cli.Historico, "inicializar", lambda self: ordem.append("historico"))
    assert cli.main(["--inicializar-historico"]) == 0
    assert ordem == ["historico"]


def test_conexao_inutilizavel_nao_chama_o_expurgo(monkeypatch):
    banco = _Banco([_conta("antiga")], morta=True)
    chamadas = []

    def executar(*_args, **_kwargs):
        return {"falhas": 1, "incertos": 0}

    cli = _cli(monkeypatch, _Conexao(banco), executar)
    monkeypatch.setattr(cli, "expurgar_demonstracoes", lambda *a, **k: chamadas.append(1))
    assert cli.main(["--enviar"]) == 1
    assert chamadas == []
    assert conexao_utilizavel(_Conexao(banco)) is False
