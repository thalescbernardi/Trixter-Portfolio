from datetime import date

from trixter.resumo_semanal import consultar_resumo_semanal, semana_devida, texto_resumo


def test_a_semana_comeca_na_segunda_e_respeita_a_preferencia():
    assert semana_devida({"receber_resumo_semanal": True}, date(2026, 10, 5)) == date(2026, 10, 5)
    assert semana_devida({"receber_resumo_semanal": True}, date(2026, 10, 7)) == date(2026, 10, 5)
    assert semana_devida({"receber_resumo_semanal": True}, date(2026, 10, 4)) == date(2026, 9, 28)
    assert semana_devida({"receber_resumo_semanal": False}, date(2026, 10, 5)) is None
    assert semana_devida({"receber_resumo_semanal": True, "conta_demo": True}, date(2026, 10, 5)) is None


class Cursor:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.description = [
            ("id_planejamento",), ("tipo",), ("categoria",), ("descricao",),
            ("valor",), ("data",), ("situacao",), ("cliente",),
        ]
        self.consultas = []

    def execute(self, sql, *args):
        self.consultas.append((sql, args))

    def fetchone(self):
        return self.respostas.pop(0)

    def fetchall(self):
        return self.respostas.pop(0)


def test_resumo_reune_saldo_vencimento_estouro_e_atraso():
    hoje = date(2026, 10, 7)
    planos = [
        ("p1", "Despesa", "Aluguel", "Sala", 1000, date(2026, 10, 9), None, None),
        ("p2", "Receita", "Serviço", "Contrato", 200, date(2026, 10, 8), None, "Beta"),
        ("p3", "Receita", "Serviço", "Futuro", 500, date(2026, 10, 20), None, "Aurora"),
        ("p4", "Receita", "Serviço", "Atraso", 400, date(2026, 10, 1), None, "Aurora"),
        ("p5", "Receita", "Serviço", "Pago", 100, date(2026, 10, 2), "Recebido", "Aurora"),
    ]
    orcamentos = [("Folha", 1000, 1500), ("Marketing", 100, 80), ("Zero", 0, 10)]
    cursor = Cursor([(5000,), (3800,), planos, orcamentos])
    dados = consultar_resumo_semanal(cursor, "empresa", hoje)
    assert dados["saldo"] == 1200
    assert dados["semana"] == date(2026, 10, 5)
    assert dados["ate"] == date(2026, 10, 14)
    assert [item["categoria"] for item in dados["vencimentos"]] == ["Serviço", "Aluguel"]
    assert dados["estouradas"][0]["categoria"] == "Folha"
    assert [item["categoria"] for item in dados["estouradas"]] == ["Folha"]
    assert dados["atrasos"] == [{"cliente": "Aurora", "valor": dados["atrasos"][0]["valor"]}]
    assert dados["atrasos"][0]["valor"] == 400
    texto = texto_resumo(dados)
    assert "Saldo: R$ 1.200,00" in texto
    assert "08/10/2026 · A receber · Serviço · R$ 200,00" in texto
    assert "09/10/2026 · A pagar · Aluguel · R$ 1.000,00" in texto
    assert "Beta" not in texto
    assert "Aurora" not in texto
    assert "20/10/2026" not in texto
    assert "Folha já usou 150% do limite" in texto
    assert "Recebimento em atraso: R$ 400,00." in texto
    assert "Marketing" not in texto


def test_resumo_omite_nomes_e_preserva_a_contagem():
    hoje = date(2026, 10, 7)
    planos = [
        ("p1", "Receita", "Serviço", "Contrato Beta", 200, date(2026, 10, 8), None, "Beta"),
        ("p2", "Receita", "Serviço", "Atraso Aurora", 400, date(2026, 10, 1), None, "Aurora"),
        ("p3", "Receita", "Projeto", "Atraso Norte", 150, date(2026, 10, 2), None, "Norte"),
    ]
    dados = consultar_resumo_semanal(Cursor([(0,), (0,), planos, []]), "empresa", hoje)
    texto = texto_resumo(dados)
    assert "08/10/2026 · A receber · Serviço · R$ 200,00" in texto
    assert "Recebimento em atraso: R$ 400,00." in texto
    assert "Mais um cliente também está em atraso." in texto
    assert "Beta" not in texto and "Aurora" not in texto and "Norte" not in texto
    assert "Contrato Beta" not in texto
    assert {item["cliente"] for item in dados["atrasos"]} == {"Aurora", "Norte"}


def test_semana_quieta_ainda_tem_leitura():
    cursor = Cursor([(0,), (0,), [], []])
    texto = texto_resumo(consultar_resumo_semanal(cursor, "empresa", date(2026, 10, 5)))
    assert "Nada vence nos próximos 7 dias." in texto
    assert "Nenhuma categoria estourou o orçamento neste mês." in texto
    assert "Nenhum cliente em atraso." in texto


def test_envio_semanal_usa_a_segunda_e_nao_repete(monkeypatch):
    from test_envios import Memoria, releitura_de, usuario
    from trixter import automacao

    hist = Memoria()
    user = usuario(receber_relatorio_mensal=False, receber_resumo_semanal=True)
    monkeypatch.setattr(automacao, "buscar_usuarios", lambda conexao: [user])
    periodos = []

    def preparar(conexao, usuario, periodo):
        periodos.append(periodo)
        return {"destinatario": usuario["email"], "assunto": "s", "corpo": "c"}

    hoje = date(2026, 10, 7)
    primeiro = automacao.executar(
        releitura_de([user]), hist, {}, hoje, simular=False,
        preparar_semanal=preparar, enviar=lambda *a, **k: None,
    )
    assert primeiro["enviados"] == 1
    assert periodos == [date(2026, 10, 5)]
    assert hist.consultar("u1", date(2026, 10, 5), tipo="resumo_semanal") == ("enviado", 1)
    segundo = automacao.executar(
        releitura_de([user]), hist, {}, hoje, simular=False,
        preparar_semanal=preparar, enviar=lambda *a, **k: None,
    )
    assert segundo["enviados"] == 0
    assert segundo["ignorados"] == 1
