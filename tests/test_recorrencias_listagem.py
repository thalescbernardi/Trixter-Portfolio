from datetime import date
from decimal import Decimal
from pathlib import Path

from trixter.recorrencias_tela import (
    resumir_recorrencias,
    texto_periodo,
    texto_proxima,
    texto_tipo,
    valor_mensal_previsto,
)


def _item(**alteracao):
    base = {
        "tipo": "Receita",
        "categoria": "Serviços",
        "valor": 100,
        "frequencia": "Mensal",
        "dia": 1,
        "mes": None,
        "dia_semana": None,
        "classificacao": "Fixo",
        "ativa": 1,
        "proxima_execucao": date(2026, 10, 15),
    }
    base.update(alteracao)
    return base


def test_dia_da_regra_nao_e_a_proxima_execucao():
    recorrencia = _item(dia=1, proxima_execucao=date(2026, 10, 15))
    assert texto_periodo(recorrencia) == "Todo dia 1"
    assert texto_proxima(recorrencia["proxima_execucao"]) == "15/10/2026"


def test_periodo_anual_mostra_dia_e_mes():
    assert texto_periodo(_item(frequencia="Anual", dia=1, mes=10)) == "Todo dia 01/10"


def test_tipo_de_gasto_vira_despesa_so_na_pj():
    gasto = _item(tipo="Gasto")
    assert texto_tipo(gasto, "Pessoa Jurídica") == "Despesa"
    assert texto_tipo(gasto, "Pessoa Física") == "Gasto"


def test_resumo_previsto_ignora_inativa_e_separa_receita_de_gasto():
    recorrencias = [
        _item(valor=100, tipo="Receita"),
        _item(valor=40, tipo="Gasto"),
        _item(valor=999, tipo="Receita", ativa=0),
        _item(valor=1200, tipo="Receita", frequencia="Anual", dia=1, mes=3),
        _item(valor=10, tipo="Gasto", frequencia="Semanal", dia_semana=1),
        _item(valor=1, tipo="Gasto", frequencia="Diária"),
    ]
    resumo = resumir_recorrencias(recorrencias)
    assert resumo["ativas"] == 5
    assert resumo["receitas"] == Decimal("200.00")
    assert valor_mensal_previsto(recorrencias[4]) == Decimal("43.33")
    assert valor_mensal_previsto(recorrencias[5]) == Decimal("30.00")
    assert resumo["gastos"] == Decimal("113.33")
    assert valor_mensal_previsto(recorrencias[2]) == Decimal("0.00")


def test_listagem_fica_num_fragmento_sem_rerun_da_pagina():
    fonte = Path(__file__).resolve().parents[1].joinpath("trixter", "recorrencias_tela.py").read_text(encoding="utf-8")
    assert "@st.fragment\ndef exibir_recorrencias" in fonte
    assert "st.rerun()" not in fonte
    assert 'st.rerun(scope="fragment")' in fonte
    assert "AND ativa = 1" not in fonte
    assert "INSERT INTO dbo.receitas" in fonte
    assert "INSERT INTO dbo.gastos" in fonte


def test_cartao_mostra_os_campos_e_o_resumo_previsto():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from datetime import date
from trixter.recorrencias_tela import exibir_resumo_e_cartoes
exibir_resumo_e_cartoes([
    {
        "id_recorrencia": "r1",
        "tipo": "Gasto",
        "categoria": "Aluguel",
        "descricao": "Sala",
        "valor": 200,
        "frequencia": "Mensal",
        "dia": 1,
        "mes": None,
        "dia_semana": None,
        "classificacao": None,
        "ativa": 1,
        "proxima_execucao": date(2026, 10, 15),
    }
], "Pessoa Jurídica", "Despesa", lambda: None)
''').run()
    assert not app.exception
    texto = " ".join(getattr(item, "value", "") for item in list(app.markdown) + list(app.caption) + list(app.metric))
    assert "Despesa" in texto
    assert "Aluguel" in texto
    assert "Todo dia 1" in texto
    assert "Não classificado" in texto
    assert "Ativa" in texto
    assert "15/10/2026" in texto
    assert "estimativas" in texto
    assert any(getattr(item, "label", "") == "Desativar" for item in app.button)
