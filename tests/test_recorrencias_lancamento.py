from datetime import date

import pytest

from trixter.recorrencias_tela import avancar_execucao, processar_pendencias


def _recorrencia(**alteracao):
    base = {
        "id_usuario": "u1",
        "id_recorrencia": "r1",
        "tipo": "Receita",
        "categoria": "Rendimentos",
        "descricao": "Investimento",
        "valor": 200,
        "frequencia": "Mensal",
        "dia": 1,
        "mes": None,
        "dia_semana": None,
        "classificacao": "Variável",
        "ativa": 1,
        "proxima_execucao": date(2026, 10, 1),
    }
    base.update(alteracao)
    return base


def _banco(existentes=None, falhar=None, ponteiro=None):
    existentes = set(existentes or [])
    estado = {
        "inserts": [],
        "updates": [],
        "commits": 0,
        "rollbacks": 0,
        "fechadas": 0,
        "cursores": 0,
        "ponteiro": ponteiro,
    }

    def conectar():
        pendente = {}

        class Cursor:
            def execute(self, sql, *args):
                if "UPDLOCK" in sql:
                    self.kind = "ponteiro"
                elif "COUNT" in sql:
                    self.kind = "count"
                    self.count = 1 if args[2] in existentes else 0
                elif "INSERT" in sql:
                    if falhar == "insert" or falhar == len(estado["inserts"]) + 1:
                        raise RuntimeError("falha no insert")
                    estado["inserts"].append((sql, args))
                    pendente["data"] = args[5]
                elif "UPDATE" in sql:
                    if falhar == "update":
                        raise RuntimeError("falha no update")
                    estado["updates"].append(args[0])
                    estado["ponteiro"] = args[0]
            def fetchone(self):
                if getattr(self, "kind", None) == "ponteiro":
                    return (estado["ponteiro"],)
                return (getattr(self, "count", 0),)
            def close(self):
                estado["cursores"] += 1

        class Conexao:
            def cursor(self):
                return Cursor()
            def commit(self):
                if "data" in pendente:
                    existentes.add(pendente.pop("data"))
                estado["commits"] += 1
            def rollback(self):
                pendente.pop("data", None)
                estado["rollbacks"] += 1
            def close(self):
                estado["fechadas"] += 1

        return Conexao()

    return conectar, estado, existentes


def test_mensal_ainda_nao_lancada_avanca_para_o_dia_escolhido():
    recorrencia = _recorrencia(proxima_execucao=date(2026, 10, 15), dia=1)
    assert avancar_execucao(date(2026, 10, 15), recorrencia) == date(2026, 11, 1)
    conectar, estado, _ = _banco()
    proxima = processar_pendencias(conectar, recorrencia, date(2026, 10, 12))
    assert proxima == date(2026, 10, 15)
    assert estado["inserts"] == []
    assert estado["commits"] == 0


def test_lancamento_que_ja_existe_nao_duplica_e_avanca():
    recorrencia = _recorrencia()
    conectar, estado, _ = _banco({date(2026, 10, 1)}, ponteiro=date(2026, 10, 1))
    proxima = processar_pendencias(conectar, recorrencia, date(2026, 10, 12))
    assert estado["inserts"] == []
    assert estado["updates"] == [date(2026, 11, 1)]
    assert proxima == date(2026, 11, 1)
    assert estado["commits"] == 1
    assert estado["rollbacks"] == 0
    assert estado["cursores"] == 1
    assert estado["fechadas"] == 1


def test_execucao_repetida_nao_gera_outro_lancamento():
    recorrencia = _recorrencia()
    conectar, estado, _ = _banco(ponteiro=date(2026, 10, 1))
    primeira = processar_pendencias(conectar, recorrencia, date(2026, 10, 12))
    recorrencia["proxima_execucao"] = primeira
    segunda = processar_pendencias(conectar, recorrencia, date(2026, 10, 12))
    assert primeira == segunda == date(2026, 11, 1)
    assert len(estado["inserts"]) == 1
    assert "dbo.receitas" in estado["inserts"][0][0]
    assert estado["inserts"][0][1][-1] == "Variável"
    assert estado["commits"] == 1


def test_atrasadas_mensais_lancam_cada_mes_no_dia_cadastrado():
    recorrencia = _recorrencia(proxima_execucao=date(2026, 8, 1))
    conectar, estado, _ = _banco(ponteiro=date(2026, 8, 1))
    proxima = processar_pendencias(conectar, recorrencia, date(2026, 10, 12))
    datas = [item[1][5] for item in estado["inserts"]]
    assert datas == [date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)]
    assert proxima == date(2026, 11, 1)
    assert estado["commits"] == 3
    assert estado["rollbacks"] == 0


def test_diaria_semanal_e_anual_seguem_a_regra_de_geracao():
    assert avancar_execucao(date(2026, 10, 12), _recorrencia(frequencia="Diária")) == date(2026, 10, 13)
    assert avancar_execucao(date(2026, 10, 5), _recorrencia(frequencia="Semanal")) == date(2026, 10, 12)
    anual = _recorrencia(frequencia="Anual", dia=10, mes=3, proxima_execucao=date(2026, 10, 15))
    assert avancar_execucao(date(2026, 10, 15), anual) == date(2027, 10, 10)
    conectar, estado, _ = _banco(ponteiro=date(2026, 10, 11))
    proxima = processar_pendencias(
        conectar,
        _recorrencia(frequencia="Diária", proxima_execucao=date(2026, 10, 11), tipo="Gasto"),
        date(2026, 10, 12),
    )
    assert [item[1][5] for item in estado["inserts"]] == [date(2026, 10, 11), date(2026, 10, 12)]
    assert all("dbo.gastos" in item[0] for item in estado["inserts"])
    assert proxima == date(2026, 10, 13)


def test_frequencia_desconhecida_nao_entra_em_loop():
    recorrencia = _recorrencia(frequencia="Quinzenal")
    assert avancar_execucao(date(2026, 10, 1), recorrencia) is None
    conectar, estado, _ = _banco()
    proxima = processar_pendencias(conectar, recorrencia, date(2026, 10, 12))
    assert proxima == date(2026, 10, 1)
    assert estado["inserts"] == []
    assert estado["fechadas"] == 0


def test_falha_no_insert_desfaz_a_transacao_e_para():
    recorrencia = _recorrencia(proxima_execucao=date(2026, 8, 1))
    conectar, estado, _ = _banco(falhar=1, ponteiro=date(2026, 8, 1))
    with pytest.raises(RuntimeError, match="falha no insert"):
        processar_pendencias(conectar, recorrencia, date(2026, 10, 12))
    assert estado["inserts"] == []
    assert estado["updates"] == []
    assert estado["commits"] == 0
    assert estado["rollbacks"] == 1
    assert estado["cursores"] == 1
    assert estado["fechadas"] == 1


def test_falha_no_update_desfaz_o_insert_da_mesma_transacao():
    conectar, estado, existentes = _banco(falhar="update", ponteiro=date(2026, 10, 1))
    with pytest.raises(RuntimeError, match="falha no update"):
        processar_pendencias(conectar, _recorrencia(), date(2026, 10, 12))
    assert len(estado["inserts"]) == 1
    assert estado["updates"] == []
    assert estado["commits"] == 0
    assert estado["rollbacks"] == 1
    assert date(2026, 10, 1) not in existentes
    assert estado["cursores"] == 1
    assert estado["fechadas"] == 1


def test_falha_no_meio_de_uma_serie_atrasada_preserva_o_que_ja_commitou():
    conectar, estado, _ = _banco(falhar=2, ponteiro=date(2026, 8, 1))
    with pytest.raises(RuntimeError, match="falha no insert"):
        processar_pendencias(
            conectar,
            _recorrencia(proxima_execucao=date(2026, 8, 1)),
            date(2026, 10, 12),
        )
    assert [item[1][5] for item in estado["inserts"]] == [date(2026, 8, 1)]
    assert estado["updates"] == [date(2026, 9, 1)]
    assert estado["commits"] == 1
    assert estado["rollbacks"] == 1
    assert estado["fechadas"] == 2


def _banco_concorrente(ponteiros, falhar_primeira=False):
    """Simula a trava da linha. Não é o SQL Server."""
    import threading

    travas = {}
    guarda = threading.Lock()
    barreira = {"pronta": False, "espera": threading.Barrier(2)}
    estado = {"inserts": [], "erros": []}

    def conectar():
        class Cursor:
            def __init__(self):
                self.kind = None
                self.count = 0
                self.trava = None
                self.passou_barreira = False

            def execute(self, sql, *args):
                if "UPDLOCK" in sql:
                    if not self.passou_barreira and not barreira["pronta"]:
                        barreira["espera"].wait(timeout=3)
                        self.passou_barreira = True
                    chave = (args[0], args[1])
                    with guarda:
                        self.trava = travas.setdefault(chave, threading.Lock())
                    if not self.trava.acquire(timeout=3):
                        raise TimeoutError("trava")
                    self.kind = "ponteiro"
                    self.lido = ponteiros[chave]
                elif "COUNT" in sql:
                    self.kind = "count"
                    self.count = 1 if any(
                        item[2] == args[1] and item[1] == args[0] and item[5] == args[2]
                        for item in estado["inserts"]
                    ) else 0
                elif "INSERT" in sql:
                    if falhar_primeira and not estado["erros"]:
                        estado["erros"].append("insert")
                        raise RuntimeError("falha no insert")
                    estado["inserts"].append(args)
                elif "UPDATE" in sql:
                    ponteiros[(args[1], args[2])] = args[0]

            def fetchone(self):
                if self.kind == "ponteiro":
                    return (self.lido,)
                return (self.count,)

            def close(self):
                if self.trava is not None and self.trava.locked():
                    self.trava.release()
                    self.trava = None

        class Conexao:
            def cursor(self):
                return Cursor()
            def commit(self):
                pass
            def rollback(self):
                pass
            def close(self):
                pass

        return Conexao()

    return conectar, estado


def _rodar_em_paralelo(recorrencias, hoje, falhar_primeira=False):
    import threading

    ponteiros = {
        (item["id_recorrencia"], item["id_usuario"]): item["proxima_execucao"]
        for item in recorrencias
    }
    conectar, estado = _banco_concorrente(ponteiros, falhar_primeira)
    erros = []

    def trabalho(item):
        try:
            processar_pendencias(conectar, item, hoje)
        except Exception as erro:
            erros.append(erro)

    if len(recorrencias) == 1:
        tarefas = [
            threading.Thread(target=trabalho, args=(recorrencias[0],)),
            threading.Thread(target=trabalho, args=(recorrencias[0],)),
        ]
    else:
        tarefas = [threading.Thread(target=trabalho, args=(item,)) for item in recorrencias]
    for tarefa in tarefas:
        tarefa.start()
    for tarefa in tarefas:
        tarefa.join(timeout=5)
        assert not tarefa.is_alive()
    return estado, erros, ponteiros


def test_duas_sessoes_da_mesma_recorrencia_inserem_uma_vez():
    estado, erros, ponteiros = _rodar_em_paralelo([_recorrencia()], date(2026, 10, 12))
    assert erros == []
    assert len(estado["inserts"]) == 1
    assert estado["inserts"][0][5] == date(2026, 10, 1)
    assert ponteiros[("r1", "u1")] == date(2026, 11, 1)


def test_repetir_depois_do_lancamento_nao_insere_de_novo():
    recorrencia = _recorrencia()
    estado, erros, ponteiros = _rodar_em_paralelo([recorrencia], date(2026, 10, 12))
    assert erros == []
    recorrencia["proxima_execucao"] = ponteiros[("r1", "u1")]
    estado_2, erros_2, _ = _rodar_em_paralelo([recorrencia], date(2026, 10, 12))
    assert erros_2 == []
    assert len(estado["inserts"]) == 1
    assert estado_2["inserts"] == []


def test_falha_da_primeira_sessao_libera_a_trava_para_a_segunda():
    estado, erros, ponteiros = _rodar_em_paralelo(
        [_recorrencia()], date(2026, 10, 12), falhar_primeira=True,
    )
    assert len(erros) == 1
    assert len(estado["inserts"]) == 1
    assert ponteiros[("r1", "u1")] == date(2026, 11, 1)


def test_recorrencias_distintas_e_usuarios_distintos_nao_se_bloqueiam():
    uma = _recorrencia(id_recorrencia="r1", proxima_execucao=date(2026, 10, 1))
    outra = _recorrencia(id_recorrencia="r2", id_usuario="u2", proxima_execucao=date(2026, 10, 1))
    estado, erros, ponteiros = _rodar_em_paralelo([uma, outra], date(2026, 10, 12))
    assert erros == []
    assert len(estado["inserts"]) == 2
    assert ponteiros[("r1", "u1")] == date(2026, 11, 1)
    assert ponteiros[("r2", "u2")] == date(2026, 11, 1)
