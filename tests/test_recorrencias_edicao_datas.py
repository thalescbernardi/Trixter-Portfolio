from datetime import date

import pytest

from trixter.recorrencias_tela import proxima_apos_edicao
from trixter.sessao import garantir_navegacao


def registro(proxima, **campos):
    return dict(frequencia="Mensal", dia=15, mes=None, dia_semana=None,
                proxima_execucao=proxima, **campos)


@pytest.mark.parametrize("hoje,ponteiro,dia,esperada", [
    (date(2026, 10, 29), date(2026, 11, 15), 18, date(2026, 11, 18)),
    (date(2026, 10, 29), date(2026, 11, 15), 7, date(2026, 11, 7)),
    (date(2026, 11, 17), date(2026, 11, 18), 15, date(2026, 12, 15)),
    (date(2026, 11, 17), date(2026, 11, 18), 17, date(2026, 12, 17)),
    (date(2026, 1, 29), date(2026, 2, 15), 31, date(2026, 2, 28)),
    (date(2028, 1, 29), date(2028, 2, 15), 31, date(2028, 2, 29)),
    (date(2026, 12, 29), date(2027, 1, 15), 31, date(2027, 1, 31)),
])
def test_recalcula_calendario_sem_antecipar_inicio_futuro(hoje, ponteiro, dia, esperada):
    recorrencia = registro(ponteiro)
    recorrencia["dia"] = ponteiro.day
    assert proxima_apos_edicao(recorrencia, "Mensal", dia, None, None, hoje) == esperada


@pytest.mark.parametrize("ponteiro", [date(2026, 10, 15), date(2099, 11, 15), None])
def test_regra_inalterada_preserva_ponteiro_inclusive_pendente(ponteiro):
    assert proxima_apos_edicao(registro(ponteiro), "Mensal", 15, None, None, date(2026, 10, 29)) == ponteiro


def test_mudar_regra_nao_descarta_vencida_nao_processada():
    with pytest.raises(ValueError, match="vencidas"):
        proxima_apos_edicao(registro(date(2026, 10, 15)), "Mensal", 18, None, None, date(2026, 10, 29))


@pytest.mark.parametrize("freq,dia,mes,semana,hoje,esperada", [
    ("Diária", None, None, None, date(2026, 10, 29), date(2026, 11, 15)),
    ("Semanal", None, None, 7, date(2026, 10, 29), date(2026, 11, 15)),
    ("Anual", 29, 2, None, date(2026, 10, 29), date(2027, 2, 28)),
])
def test_mudanca_de_frequencia(freq, dia, mes, semana, hoje, esperada):
    assert proxima_apos_edicao(registro(date(2026, 11, 15)), freq, dia, mes, semana, hoje) == esperada


def test_limpa_edicao_em_qualquer_destino_e_preserva_durante_rerun_normal():
    estado = {"tela_atual": "gerenciar_recorrencias", "alterar_recorrencia": True,
              "_recorrencia_em_edicao": ("u", "r"), "novo_dia_recorrencia_r": 18}
    garantir_navegacao(estado)
    assert estado["alterar_recorrencia"] is True
    assert estado["novo_dia_recorrencia_r"] == 18
    estado["tela_atual"] = "seguranca"
    garantir_navegacao(estado)
    assert estado["alterar_recorrencia"] is False
    assert "_recorrencia_em_edicao" not in estado
    assert "novo_dia_recorrencia_r" not in estado
