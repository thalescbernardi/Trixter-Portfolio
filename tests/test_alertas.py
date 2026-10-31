from datetime import date, timedelta

import pytest

from trixter import alertas, automacao
from trixter.historico import Historico
from test_envios import Memoria, ConexaoSQL, releitura_de, usuario, preparar

HOJE = date(2026, 9, 6)


class Cursor:
    def __init__(self, linhas=(), meta=None):
        self.linhas = linhas
        self.meta = meta
        self.consultas = []
        self.fechado = False

    def execute(self, sql, *args):
        self.consultas.append((sql, args))

    def fetchall(self):
        return self.linhas

    def fetchone(self):
        return self.meta

    def close(self):
        self.fechado = True


def test_orcamentos_limites_e_data_explicita():
    cursor = Cursor([("A", 100, 79), ("B", 100, 80), ("C", 100, 100),
                     ("D", 0, 50), ("E", 100, 120)])
    resultado = alertas.gerar_alertas_orcamento(cursor, "u1", HOJE)
    assert [(a["categoria"], a["nivel"]) for a in resultado] == [
        ("B", "atencao"), ("C", "critico"), ("E", "critico")]
    assert cursor.consultas[0][1] == ("u1", 9, 2026)
    assert "GETDATE" not in cursor.consultas[0][0]


def test_alerta_de_orcamento_diz_se_o_custo_e_fixo_ou_variavel():
    cursor = Cursor([
        ("Folha", 100, 85, 85, 0),
        ("Marketing", 100, 100, 0, 100),
    ])
    resultado = alertas.gerar_alertas_orcamento(cursor, "u1", HOJE)
    assert "é fixo" in resultado[0]["mensagem"]
    assert "é variável" in resultado[1]["mensagem"]
    assert resultado[0]["nivel"] == "atencao"
    assert resultado[1]["nivel"] == "critico"


@pytest.mark.parametrize("dias,quantidade", [(-1, 0), (0, 1), (3, 1), (4, 0)])
def test_janela_recorrencias(dias, quantidade):
    cursor = Cursor([("Casa", "Gasto", "Aluguel", 100, HOJE + timedelta(days=dias))])
    resultado = alertas.gerar_alertas_recorrencias(cursor, "u1", HOJE)
    assert len(resultado) == quantidade
    assert cursor.consultas[0][1] == ("u1",)
    assert "ativa = 1" in cursor.consultas[0][0]


def test_email_de_recorrencia_omite_descricao_e_a_tela_conserva():
    cursor = Cursor([
        ("Serviço", "Receita", "Contrato da Oficina Lima", 200, HOJE + timedelta(days=2)),
        ("Serviço", "Gasto", "Mensalidade do João", 80, HOJE + timedelta(days=1)),
    ])
    resultado = alertas.gerar_alertas_recorrencias(cursor, "u1", HOJE)
    assert [alerta["categoria"] for alerta in resultado] == ["Serviço", "Serviço"]
    assert "Contrato da Oficina Lima" in resultado[0]["mensagem"]
    assert "Mensalidade do João" in resultado[1]["mensagem"]
    corpo = "\n".join(f"- {alertas.texto_para_email(alerta)}" for alerta in resultado)
    assert "Recorrência de receita em Serviço, no valor de R$ 200,00, possui próxima execução em 2 dia(s)." in corpo
    assert "Recorrência de gasto em Serviço, no valor de R$ 80,00, possui próxima execução em 1 dia(s)." in corpo
    assert "Contrato da Oficina Lima" not in corpo
    assert "João" not in corpo


def test_preparar_alertas_preserva_os_outros_tipos(monkeypatch):
    recorrencias = alertas.gerar_alertas_recorrencias(
        Cursor([("Serviço", "Receita", "Contrato da Oficina Lima", 200, HOJE)]),
        "u1", HOJE,
    )
    orcamento = {"tipo": "orcamento", "mensagem": "O orçamento da categoria Folha foi excedido."}

    class Conexao:
        def cursor(self):
            return Cursor()

    monkeypatch.setattr(automacao, "coletar_alertas", lambda *args: recorrencias + [orcamento])
    corpo = automacao.preparar_alertas(Conexao(), usuario(), HOJE)["corpo"]
    assert "Contrato da Oficina Lima" not in corpo
    assert "Recorrência de receita em Serviço" in corpo
    assert "O orçamento da categoria Folha foi excedido." in corpo
    assert "Contrato da Oficina Lima" in recorrencias[0]["mensagem"]


@pytest.mark.parametrize("dias,acumulado,quantidade", [
    (-1, 0, 0), (0, 0, 1), (30, 50, 1), (31, 0, 0), (10, 100, 0)])
def test_janela_meta(dias, acumulado, quantidade):
    cursor = Cursor(meta=("Reserva", 100, HOJE + timedelta(days=dias), acumulado))
    assert len(alertas.gerar_alertas_meta(cursor, "u1", HOJE)) == quantidade


@pytest.mark.parametrize("vazio", [True, False])
def test_mensagem_diaria_sem_pdf(monkeypatch, vazio):
    cursor = Cursor()
    class Conexao:
        def cursor(self): return cursor
    def coletar(c, uid, hoje):
        assert c is cursor and uid == "u1" and hoje == HOJE
        return [] if vazio else [{"mensagem": "Primeiro"}, {"mensagem": "Segundo"}]
    monkeypatch.setattr(automacao, "coletar_alertas", coletar)
    mensagem = automacao.preparar_alertas(Conexao(), usuario(), HOJE)
    assert cursor.fechado
    if vazio:
        assert mensagem is None
    else:
        assert "- Primeiro\n- Segundo" in mensagem["corpo"]
        assert mensagem["corpo"].startswith("Olá!")
        assert "anexo" not in mensagem


def executar(monkeypatch, hist, usuarios=None, hoje=HOJE, **kwargs):
    lista = usuarios or [usuario(receber_relatorio_mensal=False, receber_alertas=True)]
    monkeypatch.setattr(automacao, "buscar_usuarios", lambda c: lista)
    defaults = dict(simular=False, preparar=preparar, preparar_diarios=preparar,
                    enviar=lambda *a, **k: None)
    return automacao.executar(releitura_de(lista), hist, {}, hoje, **(defaults | kwargs))


def test_dedup_diaria_e_novo_dia(monkeypatch):
    hist = Memoria()
    chamadas = []
    enviar = lambda *a, **k: chamadas.append(k)
    assert executar(monkeypatch, hist, enviar=enviar)["enviados"] == 1
    assert executar(monkeypatch, hist, enviar=enviar)["ignorados"] == 1
    assert executar(monkeypatch, hist, hoje=HOJE + timedelta(days=1), enviar=enviar)["enviados"] == 1
    assert len(chamadas) == 2
    assert hist.consultar("u1", HOJE, tipo="alertas_diarios") == ("enviado", 1)


def test_sem_alertas_nao_consume_dia(monkeypatch):
    hist = Memoria()
    assert executar(monkeypatch, hist, preparar_diarios=lambda *a: None)["sem_alertas"] == 1
    assert not hist.registros
    assert executar(monkeypatch, hist)["enviados"] == 1


def test_simulacao_diaria_nao_grava(monkeypatch):
    hist = Memoria()
    def proibido(*a, **k): pytest.fail("SMTP em simulação")
    assert executar(monkeypatch, hist, simular=True, enviar=proibido)["simulados"] == 1
    assert not hist.registros and not hist.eventos


@pytest.mark.parametrize("alteracao", [{"receber_alertas": False}, {"conta_demo": True}])
def test_alertas_respeitam_preferencia_demo(monkeypatch, alteracao):
    hist = Memoria()
    user = usuario(receber_relatorio_mensal=False, receber_alertas=True) | alteracao
    def proibido(*a): pytest.fail("Não deve consultar os alertas")
    assert executar(monkeypatch, hist, [user], preparar_diarios=proibido)["ignorados"] == 1
    assert not hist.registros


def test_dois_tipos_independentes_no_mesmo_lote(monkeypatch):
    hist = Memoria()
    usuarios = [usuario(receber_alertas=True)]
    assert executar(monkeypatch, hist, usuarios)["enviados"] == 2
    assert executar(monkeypatch, hist, usuarios)["ignorados"] == 2
    assert len(hist.registros) == 2


def test_incerto_diario_nao_reenvia_no_dia(monkeypatch):
    hist = Memoria()
    chamadas = []
    def falhar(*a, **k):
        chamadas.append(1)
        raise TimeoutError()
    assert executar(monkeypatch, hist, enviar=falhar)["incertos"] == 1
    assert executar(monkeypatch, hist, enviar=falhar)["incertos"] == 1
    assert len(chamadas) == 1


def test_falha_preparacao_diaria_retry_limitado(monkeypatch):
    hist = Memoria()
    def falhar(*a): raise ValueError()
    for _ in range(4):
        executar(monkeypatch, hist, preparar_diarios=falhar)
    assert hist.consultar("u1", HOJE, tipo="alertas_diarios") == ("falha", 3)
    assert "enviando" not in hist.eventos


@pytest.mark.parametrize("estado,envios", [("preparando", 1), ("enviando", 0)])
def test_recuperacao_diaria(monkeypatch, estado, envios):
    hist = Memoria()
    hist.registros["u1", HOJE, "alertas_diarios"] = (estado, 1)
    assert executar(monkeypatch, hist)["enviados"] == envios


def test_sql_tipo_diario_em_todas_operacoes():
    conn = ConexaoSQL([(0,), None, (42,)])
    with Historico(conn).exclusivo() as hist:
        hist.recuperar_interrompidos()
        hist.reservar("u1", HOJE, "teste@example.com", tipo="alertas_diarios")
        hist.atualizar("u1", HOJE, "enviando", tipo="alertas_diarios")
    comandos = conn.comandos[1:-1]
    assert all("alertas_diarios" in params for sql, params in comandos)
    assert "relatorio_mensal" in comandos[0][1]


def test_sql_busca_usuarios_com_qualquer_preferencia():
    cursor = Cursor([(123, True)])
    cursor.description = [("id_usuario",), ("receber_alertas",)]
    class Conexao:
        def cursor(self): return cursor
    assert automacao.buscar_usuarios(Conexao()) == [{"id_usuario": 123, "receber_alertas": True}]
    sql = cursor.consultas[0][0]
    assert "receber_relatorio_mensal=1 OR receber_alertas=1" in sql
    assert "ISNULL(conta_demo,0)=0" in sql
    assert cursor.fechado


@pytest.mark.parametrize("nome", ["orcamento", "recorrencias", "meta"])
def test_interface_delega_e_fecha_conexao(nome):
    import ast
    from contextlib import closing
    from pathlib import Path
    from types import SimpleNamespace

    raiz = Path(__file__).resolve().parents[1]
    arvore = ast.parse((raiz / "Gerenciador de Gastos V2.py").read_text(encoding="utf-8"))
    funcao = next(n for n in arvore.body if isinstance(n, ast.FunctionDef)
                  and n.name == f"gerar_alertas_{nome}")
    cursor = Cursor()
    class Conexao:
        fechada = False
        def cursor(self): return cursor
        def close(self): self.fechada = True
    conexao = Conexao()
    def regra(c, uid, hoje):
        assert c is cursor and uid == "u1" and hoje == date.today()
        return [{"mensagem": "Mesmo alerta"}]
    contexto = dict(closing=closing, conectar_banco=lambda: conexao, date=date,
                    regras_alertas=SimpleNamespace(**{funcao.name: regra}))
    exec(compile(ast.Module(body=[funcao], type_ignores=[]), "interface", "exec"), contexto)
    assert contexto[funcao.name]("u1") == [{"mensagem": "Mesmo alerta"}]
    assert cursor.fechado and conexao.fechada


def test_relatorio_incerto_nao_bloqueia_alertas(monkeypatch):
    hist = Memoria()
    hist.registros["u1", date(2026, 8, 1)] = ("incerto", 1)
    resumo = executar(monkeypatch, hist, [usuario(receber_alertas=True)])
    assert resumo["incertos"] == 1 and resumo["enviados"] == 1
    assert hist.consultar("u1", HOJE, tipo="alertas_diarios") == ("enviado", 1)
