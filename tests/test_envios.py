from datetime import date
from io import BytesIO
import logging
from types import SimpleNamespace

import pyodbc
import pytest
from pypdf import PdfReader

from trixter import automacao, infra
from trixter.historico import Historico
from trixter.relatorios import calcular_relatorio_mensal, gerar_pdf_relatorio


def usuario(**alteracoes):
    dados = dict(id_usuario="u1", email="teste@example.com", tipo_pessoa="Pessoa Jurídica",
                 receber_relatorio_mensal=True, dia_relatorio_mensal=5, conta_demo=False)
    return dados | alteracoes


@pytest.mark.parametrize("hoje,alteracoes,esperado", [
    (date(2026, 9, 4), {}, None),
    (date(2026, 9, 5), {}, date(2026, 8, 1)),
    (date(2026, 9, 30), {}, date(2026, 8, 1)),
    (date(2027, 1, 5), {}, date(2026, 12, 1)),
    (date(2028, 3, 5), {}, date(2028, 2, 1)),
    (date(2026, 9, 5), {"receber_relatorio_mensal": False}, None),
    (date(2026, 9, 5), {"conta_demo": True}, None),
    (date(2026, 9, 5), {"dia_relatorio_mensal": None}, None),
    (date(2026, 9, 30), {"dia_relatorio_mensal": 31}, None),
])
def test_periodo(hoje, alteracoes, esperado):
    assert automacao.periodo_devido(usuario(**alteracoes), hoje) == esperado


class CursorFinanceiro:
    def __init__(self, totais=(1000, 400, 500, 200), categorias=(("Moradia", 300), ("Outros", 100))):
        self.totais = iter(totais)
        self.categorias = categorias
        self.consultas = []

    def execute(self, sql, *args):
        self.consultas.append((sql, args))

    def fetchone(self):
        return (next(self.totais),)

    def fetchall(self):
        return self.categorias


def test_calculos_periodos_e_pdf():
    cursor = CursorFinanceiro()
    dados = calcular_relatorio_mensal(cursor, "u1", 2027, 1)
    assert dados["saldo_relatorio"] == 600
    assert dados["taxa_poupanca_relatorio"] == 60
    assert dados["percentual_por_categoria"]["Moradia"] == 75
    assert dados["variacao_receitas"] == dados["variacao_gastos"] == 100
    assert dados["principal_categoria"] == "Moradia"
    assert cursor.consultas[0][1] == ("u1", date(2027, 1, 1), date(2027, 2, 1))
    assert cursor.consultas[2][1] == ("u1", date(2026, 12, 1), date(2027, 1, 1))
    dados["termo_gasto"] = "Despesa"
    pdf = gerar_pdf_relatorio(**dados)
    assert pdf.getvalue().startswith(b"%PDF")
    texto = "\n".join(p.extract_text() for p in PdfReader(pdf).pages)
    assert "Janeiro" in texto and "2027" in texto
    assert "Moradia" in texto


def test_relatorio_sem_movimentacoes():
    dados = calcular_relatorio_mensal(CursorFinanceiro((0, 0, 0, 0), ()), "u1", 2026, 12)
    assert dados["taxa_poupanca_relatorio"] == 0
    assert dados["variacao_receitas"] is None
    assert dados["principal_categoria"] is None
    dados["termo_gasto"] = "Gasto"
    assert gerar_pdf_relatorio(**dados).getvalue().startswith(b"%PDF")


class Memoria:
    def __init__(self):
        self.registros = {}
        self.eventos = []

    def existe(self):
        return True

    def recuperar_interrompidos(self):
        for k, (status, tentativas) in list(self.registros.items()):
            if status in ("preparando", "enviando"):
                self.registros[k] = ("falha" if status == "preparando" else "incerto", tentativas)

    def chave(self, uid, periodo, tipo):
        return (uid, periodo) if tipo == "relatorio_mensal" else (uid, periodo, tipo)

    def consultar(self, uid, periodo, tipo="relatorio_mensal"):
        return self.registros.get(self.chave(uid, periodo, tipo))

    def reservar(self, uid, periodo, email, max_tentativas, tipo="relatorio_mensal"):
        anterior = self.consultar(uid, periodo, tipo=tipo)
        if anterior and (anterior[0] != "falha" or anterior[1] >= max_tentativas):
            return None
        self.registros[self.chave(uid, periodo, tipo)] = ("preparando", (anterior[1] if anterior else 0) + 1)
        self.eventos.append("preparando")
        return "<teste@trixter.local>"

    def atualizar(self, uid, periodo, status, erro=None, tipo="relatorio_mensal"):
        self.eventos.append(status)
        self.registros[self.chave(uid, periodo, tipo)] = (status, self.registros[self.chave(uid, periodo, tipo)][1])


@pytest.fixture
def ambiente(monkeypatch):
    usuarios = [usuario()]
    monkeypatch.setattr(automacao, "buscar_usuarios", lambda conn: usuarios)
    return usuarios, Memoria()


def preparar(*args):
    return dict(destinatario="teste@example.com", assunto="Relatório", corpo="Corpo",
                anexo={"conteudo": b"pdf", "nome": "relatorio.pdf"})


class Releitura:
    """Segunda consulta fictícia. A chave ausente ou None imita conta excluída."""

    def __init__(self, contas):
        self.contas = contas
        self.consultas = []

    def cursor(self):
        return self

    def execute(self, sql, *params):
        self.consultas.append((sql, params))
        self._id = params[0]

    def fetchone(self):
        conta = self.contas.get(self._id)
        if conta is None:
            return None
        return tuple(conta.get(coluna) for coluna in automacao._COLUNAS_PREFERENCIA)

    def close(self):
        pass


def releitura_de(usuarios):
    return Releitura({usuario_["id_usuario"]: usuario_ for usuario_ in usuarios})


def rodar(hist, **kwargs):
    conexao = kwargs.pop("conexao", None)
    if conexao is None:
        conexao = releitura_de(automacao.buscar_usuarios(None))
    return automacao.executar(conexao, hist, {}, date(2026, 9, 6), preparar=preparar, **kwargs)


def test_simulacao_nao_envia_nem_grava(ambiente):
    _, hist = ambiente
    def proibido(*a, **k):
        pytest.fail("Simulação não pode enviar.")
    assert rodar(hist, enviar=proibido)["simulados"] == 1
    assert hist.registros == {} and hist.eventos == []


def test_segunda_execucao_nao_duplica(ambiente):
    _, hist = ambiente
    enviados = []
    def enviar(*a, **k):
        assert hist.eventos[-1] == "enviando"
        enviados.append(k)
    assert rodar(hist, simular=False, enviar=enviar)["enviados"] == 1
    assert rodar(hist, simular=False, enviar=enviar)["ignorados"] == 1
    assert len(enviados) == 1
    assert hist.eventos == ["preparando", "enviando", "enviado"]


def test_smtp_incerto_nao_reenvia(ambiente):
    _, hist = ambiente
    chamadas = []
    def enviar(*a, **k):
        chamadas.append(1)
        raise TimeoutError("resposta perdida")
    assert rodar(hist, simular=False, enviar=enviar)["incertos"] == 1
    rodar(hist, simular=False, enviar=enviar)
    assert len(chamadas) == 1


def test_falha_pdf_retry_limitado(ambiente):
    _, hist = ambiente
    def falhar(*a):
        raise ValueError("PDF inválido")
    for _ in range(4):
        automacao.executar(None, hist, {}, date(2026, 9, 6), simular=False, preparar=falhar)
    assert hist.registros["u1", date(2026, 8, 1)] == ("falha", 3)
    assert "enviando" not in hist.eventos


@pytest.mark.parametrize("estado,envios", [("preparando", 1), ("enviando", 0), ("enviado", 0)])
def test_recuperacao_interrupcao(ambiente, estado, envios):
    _, hist = ambiente
    hist.registros["u1", date(2026, 8, 1)] = (estado, 1)
    chamadas = []
    rodar(hist, simular=False, enviar=lambda *a, **k: chamadas.append(1))
    assert len(chamadas) == envios


def test_falha_apos_smtp_nao_libera_reenvio(ambiente, monkeypatch):
    _, hist = ambiente
    atualizar = hist.atualizar
    def quebrar(uid, periodo, status, erro=None, tipo="relatorio_mensal"):
        if status == "enviado":
            raise ConnectionError("Banco desconectou")
        atualizar(uid, periodo, status, erro, tipo=tipo)
    monkeypatch.setattr(hist, "atualizar", quebrar)
    chamadas = []
    with pytest.raises(ConnectionError):
        rodar(hist, simular=False, enviar=lambda *a, **k: chamadas.append(1))
    rodar(hist, simular=False, enviar=lambda *a, **k: chamadas.append(1))
    assert len(chamadas) == 1
    assert hist.consultar("u1", date(2026, 8, 1))[0] == "incerto"


def test_falha_antes_smtp_nao_chama_provedor(ambiente, monkeypatch):
    _, hist = ambiente
    monkeypatch.setattr(hist, "atualizar", lambda *a, **k: (_ for _ in ()).throw(ConnectionError()))
    with pytest.raises(ConnectionError):
        rodar(hist, simular=False, enviar=lambda *a, **k: pytest.fail("Não pode enviar sem persistir estado."))


def test_optout_e_demo_excluidos(ambiente):
    usuarios, hist = ambiente
    usuarios[:] = [usuario(receber_relatorio_mensal=False), usuario(conta_demo=True)]
    assert rodar(hist, simular=False)["ignorados"] == 2
    assert not hist.registros


def _lote(monkeypatch, atual, hoje=date(2026, 10, 7)):
    base = usuario(
        receber_relatorio_mensal=True,
        receber_alertas=True,
        receber_resumo_semanal=True,
        dia_relatorio_mensal=5,
    )
    monkeypatch.setattr(automacao, "buscar_usuarios", lambda conn: [base])
    hist = Memoria()
    enviados = []
    resumo = automacao.executar(
        Releitura({"u1": atual}),
        hist,
        {},
        hoje,
        simular=False,
        preparar=preparar,
        preparar_diarios=preparar,
        preparar_semanal=preparar,
        enviar=lambda *a, **k: enviados.append(1),
    )
    return resumo, hist, enviados


def test_preferencia_desligada_depois_da_leitura_nao_envia(monkeypatch):
    resumo, hist, enviados = _lote(monkeypatch, usuario(
        receber_relatorio_mensal=False,
        receber_alertas=False,
        receber_resumo_semanal=False,
        dia_relatorio_mensal=5,
    ))
    assert resumo["enviados"] == 0 and resumo["ignorados"] == 3
    assert enviados == [] and hist.registros == {} and hist.eventos == []


def test_preferencia_que_permanece_ligada_reserva_e_envia(monkeypatch):
    atual = usuario(
        receber_relatorio_mensal=True,
        receber_alertas=True,
        receber_resumo_semanal=True,
        dia_relatorio_mensal=5,
    )
    conexao = Releitura({"u1": atual})
    monkeypatch.setattr(automacao, "buscar_usuarios", lambda conn: [atual])
    hist = Memoria()
    resumo = automacao.executar(
        conexao, hist, {}, date(2026, 10, 7), simular=False,
        preparar=preparar, preparar_diarios=preparar, preparar_semanal=preparar,
        enviar=lambda *a, **k: None,
    )
    assert resumo["enviados"] == 3
    assert hist.eventos == ["preparando", "enviando", "enviado"] * 3
    sql, params = conexao.consultas[0]
    assert "FROM dbo.usuarios" in sql and "WHERE id_usuario = ?" in sql
    assert params == ("u1",)
    for coluna in ("receber_relatorio_mensal", "receber_alertas", "receber_resumo_semanal", "dia_relatorio_mensal"):
        assert coluna in sql


def test_preferencia_nula_nao_envia(monkeypatch):
    resumo, hist, enviados = _lote(monkeypatch, usuario(
        receber_relatorio_mensal=None,
        receber_alertas=None,
        receber_resumo_semanal=None,
        dia_relatorio_mensal=5,
    ))
    assert enviados == [] and hist.registros == {}
    assert resumo["enviados"] == 0 and resumo["ignorados"] == 3


@pytest.mark.parametrize("atual", [None, usuario(conta_demo=True)])
def test_conta_excluida_ou_demonstracao_nao_envia(monkeypatch, atual):
    resumo, hist, enviados = _lote(monkeypatch, atual)
    assert enviados == [] and hist.registros == {}
    assert resumo["enviados"] == 0 and resumo["ignorados"] == 3


@pytest.mark.parametrize("bits,tipo,periodo", [
    (
        dict(receber_relatorio_mensal=True, receber_alertas=False, receber_resumo_semanal=False),
        "relatorio_mensal",
        date(2026, 9, 1),
    ),
    (
        dict(receber_relatorio_mensal=False, receber_alertas=True, receber_resumo_semanal=False),
        "alertas_diarios",
        date(2026, 10, 7),
    ),
    (
        dict(receber_relatorio_mensal=False, receber_alertas=False, receber_resumo_semanal=True),
        "resumo_semanal",
        date(2026, 10, 5),
    ),
])
def test_releitura_autoriza_somente_o_proprio_tipo(monkeypatch, bits, tipo, periodo):
    atual = usuario(dia_relatorio_mensal=5, conta_demo=False) | bits
    resumo, hist, enviados = _lote(monkeypatch, atual)
    assert resumo["enviados"] == 1 and len(enviados) == 1
    assert len(hist.registros) == 1
    assert hist.consultar("u1", periodo, tipo=tipo) == ("enviado", 1)


@pytest.mark.parametrize("dia", [None, 0, 31])
def test_relatorio_com_dia_invalido_ou_nulo_nao_envia(monkeypatch, dia):
    atual = usuario(
        receber_relatorio_mensal=True,
        receber_alertas=False,
        receber_resumo_semanal=False,
        dia_relatorio_mensal=dia,
    )
    resumo, hist, enviados = _lote(monkeypatch, atual)
    assert enviados == [] and hist.registros == {}
    assert resumo["enviados"] == 0
    assert ("u1", date(2026, 9, 1)) not in hist.registros


def test_falha_na_releitura_nao_envia_nem_reserva(monkeypatch):
    class Quebra:
        def cursor(self):
            return self

        def execute(self, *args):
            raise RuntimeError("banco indisponível")

        def close(self):
            pass

    monkeypatch.setattr(automacao, "buscar_usuarios", lambda conn: [usuario()])
    hist = Memoria()
    enviados = []
    resumo = automacao.executar(
        Quebra(), hist, {}, date(2026, 9, 6), simular=False,
        preparar=preparar, enviar=lambda *a, **k: enviados.append(1),
    )
    assert resumo["falhas"] == 1 and resumo["enviados"] == 0
    assert enviados == [] and hist.registros == {} and hist.eventos == []


def test_desligamento_nao_reabre_falha_anterior(monkeypatch):
    hist = Memoria()
    hist.registros["u1", date(2026, 8, 1)] = ("falha", 1)
    monkeypatch.setattr(automacao, "buscar_usuarios", lambda conn: [usuario()])
    conexao = Releitura({"u1": usuario(receber_relatorio_mensal=False)})
    enviados = []
    automacao.executar(
        conexao, hist, {}, date(2026, 9, 6), simular=False,
        preparar=preparar, enviar=lambda *a, **k: enviados.append(1),
    )
    assert enviados == []
    assert hist.registros["u1", date(2026, 8, 1)] == ("falha", 1)


def test_releitura_nao_entra_em_envio_manual_nem_transacional():
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[1]
    for relativo in (
        "trixter/alertas_tela.py",
        "trixter/relatorio_mensal.py",
        "trixter/acesso.py",
        "trixter/seguranca.py",
        "Gerenciador de Gastos V2.py",
    ):
        texto = (raiz / relativo).read_text(encoding="utf-8")
        assert "ler_preferencia_atual" not in texto
        assert "preferencia_autoriza_envio" not in texto


def test_smtp_anexo_e_message_id(monkeypatch):
    eventos = []
    class SMTP:
        def __init__(self, *a, **k): eventos.append("conectar")
        def starttls(self, **k): eventos.append("tls")
        def login(self, *a): eventos.append("login")
        def send_message(self, msg):
            eventos.append(msg)
            return {}
        def close(self): eventos.append("fechar")
    monkeypatch.setattr(infra.smtplib, "SMTP", SMTP)
    config = {"email": dict(servidor="smtp.example.com", porta=587,
                           usuario="u", senha="s", remetente="teste@example.com")}
    infra.enviar_email(config, **preparar(), message_id="<teste@trixter.local>")
    assert eventos[:3] == ["conectar", "tls", "login"]
    msg = eventos[3]
    assert msg["Message-ID"] == "<teste@trixter.local>"
    assert next(msg.iter_attachments()).get_payload(decode=True) == b"pdf"
    assert eventos[-1] == "fechar"


def test_historico_exige_bloqueio():
    with pytest.raises(RuntimeError, match="bloqueio"):
        Historico(None).reservar("u", date(2026, 1, 1), "u@example.com")


def test_cli_data_nao_permite_envio_real():
    from executar_envios import main
    with pytest.raises(SystemExit) as erro:
        main(["--enviar", "--data", "2026-09-06"])
    assert erro.value.code == 2


class CursorSQL:
    def __init__(self, conexao):
        self.conexao = conexao
        self.rowcount = -1  # SQL Server com SET NOCOUNT ON.

    def execute(self, sql, *args):
        self.conexao.comandos.append((sql, args))

    def fetchone(self):
        return self.conexao.respostas.pop(0)

    def close(self):
        pass


class ConexaoSQL:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.comandos = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return CursorSQL(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_lock_e_persistencia_com_nocount():
    conexao = ConexaoSQL([(0,), None, (42,)])
    hist = Historico(conexao)
    with hist.exclusivo():
        assert hist.reservar("u1", date(2026, 8, 1), "teste@example.com")
        hist.atualizar("u1", date(2026, 8, 1), "enviando")
        assert conexao.commits == 3  # lock, reserva, estado antes do SMTP
    assert not hist.bloqueado
    assert "sp_releaseapplock" in conexao.comandos[-1][0]
    assert conexao.commits == 4
    assert any("OUTPUT INSERTED.id_envio" in sql for sql, _ in conexao.comandos)


def test_lock_negado_nao_reserva():
    conexao = ConexaoSQL([(-1,)])
    hist = Historico(conexao)
    with pytest.raises(RuntimeError, match="Outro executor"):
        with hist.exclusivo():
            pytest.fail("Não pode executar com lock negado.")
    assert not hist.bloqueado
    assert len(conexao.comandos) == 1


def test_lock_liberado_apos_excecao():
    conexao = ConexaoSQL([(0,)])
    with pytest.raises(ValueError):
        with Historico(conexao).exclusivo():
            raise ValueError("falha")
    assert "sp_releaseapplock" in conexao.comandos[-1][0]


def test_reserva_enviado_nao_altera_registro():
    conexao = ConexaoSQL([(0,), ("enviado", 1)])
    with Historico(conexao).exclusivo() as hist:
        assert hist.reservar("u", date(2026, 8, 1), "u@example.com") is None
    assert not any("INSERT INTO" in sql or "UPDATE dbo" in sql for sql, _ in conexao.comandos)


def test_erro_usuario_nao_interrompe_outros(ambiente):
    usuarios, hist = ambiente
    usuarios.append(usuario(id_usuario="u2"))
    def preparar_um(conn, user, periodo):
        if user["id_usuario"] == "u1":
            raise ValueError("erro")
        return preparar()
    enviados = []
    resumo = automacao.executar(releitura_de(usuarios), hist, {}, date(2026, 9, 6), simular=False,
                               preparar=preparar_um, enviar=lambda *a, **k: enviados.append(1))
    assert resumo["falhas"] == resumo["enviados"] == 1
    assert len(enviados) == 1


@pytest.fixture
def sem_variaveis_de_config(monkeypatch):
    for nome in infra.VARIAVEIS_CONFIG:
        monkeypatch.delenv(nome, raising=False)


def test_config_independente_do_diretorio(tmp_path, monkeypatch, sem_variaveis_de_config):
    caminho = tmp_path / "privado.toml"
    caminho.write_text('[database]\nserver="teste"\n', encoding="utf-8")
    monkeypatch.setenv("TRIXTER_CONFIG", str(caminho))
    monkeypatch.chdir(tmp_path.parent)
    assert infra.carregar_config()["database"]["server"] == "teste"


def test_caminho_explicito_vence_trixter_config(tmp_path, monkeypatch, sem_variaveis_de_config):
    escolhido = tmp_path / "escolhido.toml"
    outro = tmp_path / "outro.toml"
    escolhido.write_text('[database]\nserver="escolhido"\n', encoding="utf-8")
    outro.write_text('[database]\nserver="outro"\n', encoding="utf-8")
    monkeypatch.setenv("TRIXTER_CONFIG", str(outro))
    assert infra.carregar_config(escolhido)["database"]["server"] == "escolhido"


def test_toml_padrao_na_raiz_quando_nao_ha_caminho(tmp_path, monkeypatch, sem_variaveis_de_config):
    monkeypatch.delenv("TRIXTER_CONFIG", raising=False)
    monkeypatch.setattr(infra, "RAIZ", tmp_path)
    pasta = tmp_path / ".streamlit"
    pasta.mkdir()
    (pasta / "secrets.toml").write_text('[database]\nserver="raiz"\n', encoding="utf-8")
    assert infra.carregar_config()["database"]["server"] == "raiz"


def test_caminho_ausente_nao_cai_no_arquivo_padrao(tmp_path, monkeypatch, sem_variaveis_de_config):
    monkeypatch.setattr(infra, "RAIZ", tmp_path)
    pasta = tmp_path / ".streamlit"
    pasta.mkdir()
    (pasta / "secrets.toml").write_text('[database]\nserver="raiz"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Configuração não encontrada"):
        infra.carregar_config(tmp_path / "nao-existe.toml")


def _ambiente_completo():
    return {
        "TRIXTER_DATABASE_DRIVER": "ODBC Driver 18 for SQL Server",
        "TRIXTER_DATABASE_SERVER": "srv.database.windows.net",
        "TRIXTER_DATABASE_NAME": "trixter",
        "TRIXTER_DATABASE_TRUSTED_CONNECTION": "no",
        "TRIXTER_DATABASE_USUARIO": "usuario-sql",
        "TRIXTER_DATABASE_SENHA": "segredo-banco",
        "TRIXTER_DATABASE_ENCRYPT": "yes",
        "TRIXTER_DATABASE_TRUST_SERVER_CERTIFICATE": "no",
        "TRIXTER_EMAIL_REMETENTE": "remetente@example.com",
        "TRIXTER_EMAIL_SERVIDOR": "smtp-relay.brevo.com",
        "TRIXTER_EMAIL_PORTA": "587",
        "TRIXTER_EMAIL_USUARIO": "login-smtp",
        "TRIXTER_EMAIL_SENHA": "segredo-smtp",
        "TRIXTER_AUTOMACAO_FUSO_HORARIO": "America/Sao_Paulo",
        "TRIXTER_AUTOMACAO_MAX_TENTATIVAS": "3",
    }


def test_config_por_variaveis_de_ambiente(tmp_path, monkeypatch, sem_variaveis_de_config):
    for nome, valor in _ambiente_completo().items():
        monkeypatch.setenv(nome, valor)
    config = infra.carregar_config(tmp_path / "ausente.toml")
    assert config["database"]["database"] == "trixter"
    assert config["database"]["trusted_connection"] == "no"
    assert config["email"]["porta"] == 587
    assert config["automacao"]["max_tentativas"] == 3
    infra.validar_config(config, smtp=True)


def test_ambiente_incompleto_nao_completa_com_toml(tmp_path, monkeypatch, sem_variaveis_de_config):
    arquivo = tmp_path / "completo.toml"
    arquivo.write_text(
        '[database]\ndriver="ODBC Driver 18 for SQL Server"\nserver="do-arquivo"\n'
        'database="banco"\ntrusted_connection="no"\nusuario="u"\nsenha="s"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("TRIXTER_DATABASE_SERVER", "do-ambiente")
    with pytest.raises(ValueError, match="apenas uma das fontes"):
        infra.carregar_config(arquivo)


def test_ambiente_incompleto_falha_na_validacao(tmp_path, monkeypatch, sem_variaveis_de_config):
    monkeypatch.setenv("TRIXTER_DATABASE_SERVER", "srv.database.windows.net")
    config = infra.carregar_config(tmp_path / "ausente.toml")
    assert config == {"database": {"server": "srv.database.windows.net"}}
    with pytest.raises(ValueError, match=r"\[database\] driver"):
        infra.validar_config(config, smtp=True)


def test_porta_de_ambiente_invalida_nao_e_aceita(tmp_path, monkeypatch, sem_variaveis_de_config):
    monkeypatch.setenv("TRIXTER_EMAIL_PORTA", "abc")
    with pytest.raises(ValueError, match="TRIXTER_EMAIL_PORTA"):
        infra.carregar_config(tmp_path / "ausente.toml")


def test_descricao_de_coluna_ausente_nao_leva_senha():
    from trixter.infra import descrever_erro_sql, limpar_falha_sql, operacao_sql
    limpar_falha_sql()
    try:
        with operacao_sql("buscar_usuarios"):
            raise pyodbc.ProgrammingError(
                "42S22",
                "[42S22] [SQL Server]Nome de coluna 'receber_resumo_semanal' inválido. (207) PWD=segredo",
            )
    except pyodbc.ProgrammingError as erro:
        texto = descrever_erro_sql(erro)
    with operacao_sql("liberar_bloqueio"):
        pass
    assert texto == "sqlstate=42S22 operacao=buscar_usuarios erro_sql=207 coluna=receber_resumo_semanal"
    assert "segredo" not in texto


def test_cli_registra_sqlstate_sem_vazar_senha(monkeypatch, caplog):
    import executar_envios as cli
    monkeypatch.setattr(cli, "carregar_config", lambda *a: {"automacao": {}})
    monkeypatch.setattr(cli, "validar_config", lambda *a, **k: None)

    def conectar(_config):
        raise pyodbc.ProgrammingError(
            "42S22",
            "Invalid column name 'receber_resumo_semanal'. (207) PWD=segredo",
        )

    monkeypatch.setattr(cli, "conectar_banco", conectar)
    with caplog.at_level(logging.ERROR):
        assert cli.main(["--enviar"]) == 1
    assert "sqlstate=42S22" in caplog.text
    assert "operacao=conectar" in caplog.text
    assert "erro_sql=207" in caplog.text
    assert "coluna=receber_resumo_semanal" in caplog.text
    assert "segredo" not in caplog.text


def test_cli_padrao_simula(monkeypatch):
    import executar_envios as cli
    class Conexao:
        def close(self): pass
    monkeypatch.setattr(cli, "carregar_config", lambda *a: {})
    monkeypatch.setattr(cli, "validar_config", lambda *a, **k: None)
    monkeypatch.setattr(cli, "conectar_banco", lambda *a: Conexao())
    chamadas = []
    def executar_fake(*a, **k):
        chamadas.append(k)
        return {"falhas": 0, "incertos": 0}
    monkeypatch.setattr(cli, "executar", executar_fake)
    assert cli.main([]) == 0
    assert chamadas == [{"simular": True}]


@pytest.mark.parametrize("tipo,termo", [("Pessoa Física", "Gasto"), ("Pessoa Jurídica", "Despesa")])
@pytest.mark.parametrize("demo,forcar_clique", [(False, False), (True, False), (True, True)])
def test_tela_relatorio_periodo_e_envio_manual(tipo, termo, demo, forcar_clique, monkeypatch):
    """Executa a tela real extraída por AST, substituindo apenas SQL e SMTP."""
    import ast
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    source = Path(__file__).resolve().parents[1].joinpath("Gerenciador de Gastos V2.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    bloco = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                 and ast.unparse(n.test) == "st.session_state.tela_atual == 'relatorio_mensal'")
    setup = '''
import streamlit as st
from contextlib import closing
from datetime import date
from trixter.relatorios import calcular_relatorio_mensal, formatar_moeda
from trixter.relatorios import gerar_pdf_relatorio as gerar_pdf_real
from trixter.relatorio_mensal import exibir_relatorio_mensal
st.session_state.setdefault("tela_atual", "relatorio_mensal")
st.session_state.setdefault("usuario_atual", {"id_usuario": "teste", "email": "teste@example.com"})
st.session_state.setdefault("envios", 0)
area_relatorio_mensal = st.empty()
class Cursor:
    def execute(self, sql, *args): self.sql = sql
    def fetchone(self): return (1000 if "dbo.receitas" in self.sql else 400,)
    def fetchall(self):
        return [(2026,), (2025,)] if "YEAR(data) AS ano" in self.sql else [("Moradia", 400)]
    def close(self): pass
class Conexao:
    def cursor(self): return Cursor()
    def close(self): pass
def conectar_banco(): return Conexao()
def gerar_pdf_relatorio(*args):
    st.session_state.periodo_pdf = args[:2]
    return gerar_pdf_real(*args)
def enviar_email(**kwargs): st.session_state.envios += 1
'''
    app = AppTest.from_string(
        setup + f"\nst.session_state.usuario_atual['conta_demo'] = {demo!r}\n"
        + f"termo_gasto = {termo!r}\n" + ast.unparse(bloco)
    ).run()
    assert not app.exception
    next(b for b in app.button if b.label == "Gerar Relatório").click().run()
    assert not app.exception
    assert app.session_state.periodo_pdf == ("Janeiro", 2026)
    app.selectbox[0].select("Fevereiro").run()
    assert not app.exception
    assert app.session_state.periodo_pdf == ("Janeiro", 2026)
    botao = next(b for b in app.button if b.label == "Enviar relatório por e-mail")
    assert botao.disabled is demo
    assert len(app.get("download_button")) == 1
    if demo:
        assert any("não está disponível na demonstração" in msg.value for msg in app.caption)
        assert app.session_state.envios == 0
        if not forcar_clique:
            return
        # Simula um clique mesmo sem o bloqueio visual: a execução deve negar o envio.
        import streamlit as st
        button_real = st.button

        def button_sem_bloqueio(label, *args, **kwargs):
            if label == "Enviar relatório por e-mail":
                kwargs["disabled"] = False
            return button_real(label, *args, **kwargs)

        monkeypatch.setattr(st, "button", button_sem_bloqueio)
        app.run()
    next(b for b in app.button if b.label == "Enviar relatório por e-mail").click().run()
    assert not app.exception
    assert app.session_state.envios == (0 if demo else 1)
    assert any("Relatório enviado" in msg.value for msg in app.success) is not demo
