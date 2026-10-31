from datetime import date
from decimal import Decimal

from trixter.provisao import (
    aliquota_de, calcular_provisao, consultar_provisao_mes, gerar_alertas_provisao,
    periodo_que_vence,
)


def test_percentual_simples_sobre_a_receita():
    assert calcular_provisao(10000, 6) == Decimal("600.00")
    assert calcular_provisao("10000", "4,5") == Decimal("450.00")
    assert calcular_provisao(10000, 15.5) == Decimal("1550.00")
    assert calcular_provisao(10000, 8) == Decimal("800.00")
    assert calcular_provisao(10000, Decimal("12.5")) == Decimal("1250.00")
    assert calcular_provisao(10000, 0) == Decimal("0.00")
    assert calcular_provisao(0, 8) == Decimal("0.00")
    assert calcular_provisao(10000, None) is None
    assert aliquota_de(101) is None
    assert aliquota_de(-1) is None
    assert aliquota_de(0) == Decimal("0.00")


def test_o_dia_deste_mes_fecha_o_mes_anterior():
    setembro = periodo_que_vence(date(2026, 10, 15), 20)
    assert setembro["vencimento"] == date(2026, 10, 20)
    assert setembro["inicio"] == date(2026, 9, 1)
    assert setembro["fim"] == date(2026, 10, 1)
    assert setembro["dias"] == 5

    outubro = periodo_que_vence(date(2026, 10, 21), 20)
    assert outubro["vencimento"] == date(2026, 11, 20)
    assert outubro["inicio"] == date(2026, 10, 1)
    assert outubro["dias"] == 30

    virada = periodo_que_vence(date(2026, 1, 10), 20)
    assert virada["vencimento"] == date(2026, 1, 20)
    assert virada["inicio"] == date(2025, 12, 1)
    assert virada["fim"] == date(2026, 1, 1)

    fim_de_ano = periodo_que_vence(date(2026, 12, 21), 20)
    assert fim_de_ano["vencimento"] == date(2027, 1, 20)
    assert fim_de_ano["inicio"] == date(2026, 12, 1)
    assert periodo_que_vence(date(2026, 10, 15), None) is None
    assert periodo_que_vence(date(2026, 10, 15), 31) is None


class Cursor:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.consultas = []

    def execute(self, sql, *args):
        self.consultas.append((sql, args))

    def fetchone(self):
        return self.respostas.pop(0)


def test_alerta_entra_na_semana_do_vencimento():
    dentro = Cursor([(Decimal("6.00"), 20), (10000,)])
    alertas = gerar_alertas_provisao(dentro, "empresa", date(2026, 10, 15))
    assert len(alertas) == 1
    assert alertas[0]["nivel"] == "atencao"
    assert "setembro" in alertas[0]["mensagem"]
    assert "R$ 600,00" in alertas[0]["mensagem"]
    assert "não é o DAS" in alertas[0]["mensagem"]
    assert dentro.consultas[1][1] == ("empresa", date(2026, 9, 1), date(2026, 10, 1))

    longe = Cursor([(Decimal("6.00"), 20)])
    assert gerar_alertas_provisao(longe, "empresa", date(2026, 10, 12)) == []
    assert len(longe.consultas) == 1

    sem_receita = Cursor([(Decimal("6.00"), 20), (0,)])
    assert gerar_alertas_provisao(sem_receita, "empresa", date(2026, 10, 20)) == []

    sem_dia = Cursor([(Decimal("6.00"), None)])
    assert gerar_alertas_provisao(sem_dia, "empresa", date(2026, 10, 20)) == []


def test_consulta_do_mes_aceita_zero_e_percentual_antigo():
    cursor = Cursor([(0,)])
    vazio = consultar_provisao_mes(cursor, "empresa", date(2026, 10, 5), None)
    assert vazio["receita"] == Decimal("0.00")
    assert vazio["provisao"] == Decimal("0.00")
    assert len(cursor.consultas) == 1

    cursor = Cursor([(10000,)])
    resumo = consultar_provisao_mes(cursor, "empresa", date(2026, 12, 5), 6)
    assert cursor.consultas[0][1] == ("empresa", date(2026, 12, 1), date(2027, 1, 1))
    assert resumo["provisao"] == Decimal("600.00")

    cursor = Cursor([(10000,)])
    assert consultar_provisao_mes(cursor, "empresa", date(2026, 12, 5), 8)["provisao"] == Decimal("800.00")
    cursor = Cursor([(10000,)])
    assert consultar_provisao_mes(cursor, "empresa", date(2026, 12, 5), Decimal("12.5"))["provisao"] == Decimal("1250.00")
    cursor = Cursor([(10000,)])
    assert consultar_provisao_mes(cursor, "empresa", date(2026, 12, 5), 0)["provisao"] == Decimal("0.00")


def test_tela_provisao_mostra_a_estimativa():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from decimal import Decimal
from datetime import date
from trixter.provisao import exibir_provisao
exibir_provisao({
    "receita": Decimal("10000"),
    "aliquota": Decimal("6.00"),
    "provisao": Decimal("600.00"),
    "inicio": date(2026, 10, 1),
})
''').run()
    assert not app.exception
    assert app.subheader[0].value == "Reserva estimada para tributos"
    assert app.metric[0].label == "Reserva estimada do mês"
    assert app.metric[0].value == "R$ 600,00"
    assert any("não calcula impostos" in getattr(item, "value", "") for item in app.info)
    assert any("6%" in getattr(item, "value", "") for item in app.markdown)


def test_tela_reserva_sem_receita_mostra_zero():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from decimal import Decimal
from datetime import date
from trixter.provisao import exibir_provisao
exibir_provisao({
    "receita": Decimal("0.00"),
    "aliquota": Decimal("8.00"),
    "provisao": Decimal("0.00"),
    "inicio": date(2026, 10, 1),
})
''').run()
    assert not app.exception
    assert app.metric[0].value == "R$ 0,00"
    assert any("Não há receitas registradas" in getattr(item, "value", "") for item in app.info)


def test_formulario_comeca_em_zero_e_grava_o_percentual_informado():
    from decimal import Decimal
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from trixter.provisao import formulario_provisao
st.session_state.escolha = formulario_provisao(None, None)
''').run()
    assert not app.exception
    assert len(app.selectbox) == 0
    assert app.number_input[0].label == "Percentual a reservar (%)"
    assert app.number_input[0].value == 0.0
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state.escolha["aliquota"] is None
    assert app.session_state.escolha["dia"] is None

    app.number_input[0].set_value(8.0)
    app.button[0].click().run()
    assert app.session_state.escolha["aliquota"] == Decimal("8.00")

    app.number_input[0].set_value(12.5)
    app.button[0].click().run()
    assert app.session_state.escolha["aliquota"] == Decimal("12.50")


def test_formulario_reabre_percentual_antigo_sem_atividade():
    from decimal import Decimal
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from decimal import Decimal
from trixter.provisao import formulario_provisao
st.session_state.escolha = formulario_provisao(Decimal("4.50"), 20)
''').run()
    assert not app.exception
    assert len(app.selectbox) == 0
    assert app.number_input[0].value == 4.5
    assert app.checkbox[0].value is True
    assert app.number_input[1].value == 20
    app.button[0].click().run()
    assert app.session_state.escolha["aliquota"] == Decimal("4.50")
    assert app.session_state.escolha["dia"] == 20


def test_margem_e_reserva_continuam_somente_na_conta_pj():
    import ast
    from pathlib import Path
    fonte = Path(__file__).resolve().parents[1].joinpath("trixter", "inteligencia.py").read_text(encoding="utf-8")
    funcao = next(
        nodo for nodo in ast.parse(fonte).body
        if isinstance(nodo, ast.FunctionDef) and nodo.name == "exibir_inteligencia"
    )
    bloco = next(
        nodo for nodo in ast.walk(funcao)
        if isinstance(nodo, ast.If) and ast.unparse(nodo.test) == "tipo_pessoa == 'Pessoa Jurídica'"
    )
    texto_funcao = ast.unparse(funcao)
    texto_pj = ast.unparse(bloco)
    for nome in ("exibir_margem", "exibir_reserva_tributos"):
        assert nome in texto_pj
        assert texto_funcao.count(nome) == texto_pj.count(nome)
    assert "st.rerun" not in texto_funcao
    raiz = Path(__file__).resolve().parents[1]
    tela = raiz.joinpath("trixter", "inteligencia.py").read_text(encoding="utf-8")
    assert "@st.fragment\ndef exibir_reserva_tributos" in tela
    assert 'st.rerun(scope="fragment")' in tela
    provisao = raiz.joinpath("trixter", "provisao.py").read_text(encoding="utf-8")
    assert not any(
        linha.startswith("import streamlit") or linha.startswith("from streamlit")
        for linha in provisao.splitlines()
    )


def test_automacao_importa_provisao_sem_streamlit():
    import subprocess
    import sys
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[1]
    comando = """
import sys
from decimal import Decimal
from datetime import date

class Bloqueio:
    def find_spec(self, nome, path, target=None):
        if nome == "streamlit" or nome.startswith("streamlit."):
            raise ModuleNotFoundError("No module named 'streamlit'")
        return None

sys.meta_path.insert(0, Bloqueio())
sys.argv = ["executar_envios.py", "--help"]
import executar_envios
from trixter.alertas import coletar_alertas
from trixter.provisao import calcular_provisao, gerar_alertas_provisao

assert calcular_provisao(10000, 8) == Decimal("800.00")

class Cursor:
    def __init__(self):
        self.respostas = [(Decimal("8.00"), 20), (10000,)]
        self.consultas = []
    def execute(self, sql, *args):
        self.consultas.append(sql)
    def fetchone(self):
        return self.respostas.pop(0)

alertas = gerar_alertas_provisao(Cursor(), "empresa", date(2026, 10, 15))
assert len(alertas) == 1
assert alertas[0]["tipo"] == "provisao"
assert "R$ 800,00" in alertas[0]["mensagem"]
try:
    executar_envios.main(["--help"])
except SystemExit as saida:
    assert saida.code in (0, None)
else:
    raise AssertionError("a ajuda deveria encerrar o processo")
"""
    resultado = subprocess.run(
        [sys.executable, "-c", comando],
        cwd=raiz,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
