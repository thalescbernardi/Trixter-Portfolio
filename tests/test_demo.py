from datetime import date

import pytest

from trixter.credencial import recurso_email
from trixter.demo import criar_demo_pj


class Conexao:
    def __init__(self, falhar=False, codigo=0):
        self.falhar = falhar
        self.codigo = codigo
        self.comandos = []
        self.confirmada = self.revertida = False
        self.fechamentos = 0

    def cursor(self): return self

    def execute(self, sql, *args):
        if self.falhar and "INSERT INTO dbo.usuarios" in sql:
            raise RuntimeError("Falha simulada")
        self.comandos.append((sql, args))

    def fetchone(self):
        sql = self.comandos[-1][0] if self.comandos else ""
        if "sp_getapplock" in sql:
            return (self.codigo,)
        return None

    def commit(self): self.confirmada = True
    def rollback(self): self.revertida = True
    def close(self): self.fechamentos += 1


def test_demo_pj_dados_isolados_e_mes_atual():
    conexao = Conexao()
    usuario = criar_demo_pj(lambda: conexao, date(2026, 12, 28))
    assert usuario["tipo_pessoa"] == "Pessoa Jurídica"
    assert usuario["conta_demo"] is True
    assert not usuario["receber_alertas"]
    assert not usuario["receber_relatorio_mensal"]
    assert usuario["objetivo_financeiro"] is None
    assert usuario["valor_objetivo"] == 0
    assert conexao.confirmada and not conexao.revertida
    assert conexao.fechamentos == 2
    textos = [sql for sql, _args in conexao.comandos]
    indice_trava = next(i for i, sql in enumerate(textos) if "sp_getapplock" in sql)
    indice_usuario = next(i for i, sql in enumerate(textos) if "INSERT INTO dbo.usuarios" in sql)
    assert indice_trava < indice_usuario
    trava_sql, trava_args = conexao.comandos[indice_trava]
    assert trava_args[0] == recurso_email(usuario["email"])
    assert trava_args[1] == 5000
    assert "Exclusive" in trava_sql and "LockOwner = 'Transaction'" in trava_sql
    for sql, args in conexao.comandos:
        assert sql.count("?") == len(args)
        if "sp_getapplock" in sql or "WHERE email = ?" in sql:
            continue
        assert usuario["id_usuario"] in args
        if "dbo.orcamentos" in sql:
            assert args[3:5] == (12, 2026)
        if "dbo.gastos" in sql or "dbo.receitas" in sql:
            assert date(2026, 9, 1) <= args[2] <= date(2026, 12, 28)
    outra = criar_demo_pj(Conexao, date(2026, 12, 28))
    assert outra["id_usuario"] != usuario["id_usuario"]


def test_falha_nao_deixa_demo_parcial():
    conexao = Conexao(falhar=True)
    with pytest.raises(RuntimeError):
        criar_demo_pj(lambda: conexao)
    assert conexao.revertida and not conexao.confirmada
    assert conexao.fechamentos == 2
    assert any("sp_getapplock" in sql for sql, _args in conexao.comandos)
    assert not any("dbo.categorias" in sql for sql, _args in conexao.comandos)


def test_trava_recusada_nao_grava_demo():
    conexao = Conexao(codigo=-1)
    with pytest.raises(RuntimeError):
        criar_demo_pj(lambda: conexao)
    assert conexao.revertida and not conexao.confirmada
    assert not any("INSERT INTO dbo.usuarios" in sql for sql, _args in conexao.comandos)


def test_demo_planejamento_cobre_categorias_do_mes():
    conexao = Conexao()
    hoje = date(2026, 9, 28)
    criar_demo_pj(lambda: conexao, hoje)
    planos = [args for sql, args in conexao.comandos if 'dbo.planejamentos ' in sql]
    despesas = {a[3]: a[5] for a in planos if a[2] == 'Despesa'}
    assert sum(despesas.values()) == 12000
    assert sum(a[5] for a in planos if a[2] == 'Receita') == 20000
    for sql, args in conexao.comandos:
        if 'dbo.gastos ' in sql and args[2].month == hoje.month:
            assert args[3] in despesas


@pytest.mark.parametrize("hoje", [date(2026, 1, 1), date(2026, 9, 28)])
def test_demo_tem_tres_meses_completos_para_simulador(hoje):
    from trixter.planejamento import deslocar_mes
    conexao = Conexao()
    criar_demo_pj(lambda: conexao, hoje)
    totais = {}
    for sql, args in conexao.comandos:
        for tabela in ("receitas", "gastos"):
            if f"dbo.{tabela} " in sql:
                assert args[2] <= hoje
                chave = (args[2].replace(day=1), tabela)
                totais[chave] = totais.get(chave, 0) + args[-1]
    for deslocamento in (-3, -2, -1, 0):
        mes = deslocar_mes(hoje, deslocamento)
        assert totais[(mes, "receitas")] == 20000
        assert totais[(mes, "gastos")] == 11150
