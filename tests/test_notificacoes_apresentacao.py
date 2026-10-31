"""Renderizacao do sininho sem banco ou execucao do aplicativo principal."""
import ast
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from trixter.alertas import gerar_alertas_orcamento
from trixter.estilo import ESTILO_BASE


def bloco_alertas():
    fonte = Path('Gerenciador de Gastos V2.py').read_text(encoding='utf-8')
    return next(n for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.For) and ast.unparse(n.iter) == 'alertas_sininho')


def test_valores_e_classificacoes_preservados_sem_delimitadores_matematicos():
    cursor = Mock()
    cursor.fetchall.return_value = [('Alimentacao', 700, 650, 300, 200)]
    alertas = gerar_alertas_orcamento(cursor, 'ficticio', date(2026, 10, 29))
    mensagem_original = alertas[0]['mensagem']
    assert '92.9%' in mensagem_original
    assert 'R$ 300,00' in mensagem_original
    assert 'R$ 200,00' in mensagem_original
    assert 'R$ 150,00' in mensagem_original
    st = Mock()
    exec(compile(ast.Module(body=[bloco_alertas()], type_ignores=[]), 'sininho_ficticio', 'exec'),
         {'st': st, 'alertas_sininho': alertas})
    st.warning.assert_called_once_with(mensagem_original.replace('$', r'\$'))
    assert alertas[0]['mensagem'] == mensagem_original
    assert st.warning.call_args.args[0].replace(r'\$', '$') == mensagem_original
    st.error.assert_not_called()


def test_ambos_renderizadores_escapam_cifroes_sem_mudar_regras_de_nivel():
    chamadas = [n for n in ast.walk(bloco_alertas()) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr in ('warning', 'error')]
    assert len(chamadas) == 2
    for chamada in chamadas:
        st = Mock()
        exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.Expr(chamada)], type_ignores=[])),
                     'alerta_ficticio', 'exec'),
             {'st': st, 'alerta': {'mensagem': 'R$ 300,00 fixo e R$ 350,00 variavel.'}})
        getattr(st, chamada.func.attr).assert_called_once_with(r'R\$ 300,00 fixo e R\$ 350,00 variavel.')


@pytest.mark.parametrize('mensagem', [
    'CategoriaSemEspacos' * 20,
    'Texto com varias palavras e classificacoes de gastos, sem valores monetarios.',
])
def test_texto_longo_sem_cifroes_permanece_igual(mensagem):
    st = Mock()
    exec(compile(ast.Module(body=[bloco_alertas()], type_ignores=[]), 'sininho_ficticio', 'exec'),
         {'st': st, 'alertas_sininho': [{'nivel': 'atencao', 'mensagem': mensagem}]})
    st.warning.assert_called_once_with(mensagem)


def test_quebra_de_linha_css_escopada_sem_alterar_ancora_ou_link():
    seletor = '.st-key-menu_alertas_box [data-testid="stAlert"] [data-testid="stMarkdownContainer"]'
    bloco = ESTILO_BASE.split(seletor + ' {', 1)[1].split('}', 1)[0]
    for regra in ('min-width: 0', 'max-width: 100%', 'white-space: normal',
                  'overflow-wrap: anywhere', 'word-break: normal'):
        assert regra in bloco
    paragrafo = ESTILO_BASE.split(seletor + ' p {', 1)[1].split('}', 1)[0]
    assert 'line-height: 1.5' in paragrafo
    assert '.st-key-menu_alertas_box::before' in ESTILO_BASE
    assert '.st-key-btn_ver_todos_alertas button' in ESTILO_BASE
    assert 'max-width: 195px' in ESTILO_BASE
    fonte = Path('Gerenciador de Gastos V2.py').read_text(encoding='utf-8')
    assert 'key="btn_alertas"' in fonte
    assert '"Ver todos os alertas"' in fonte
    assert 'on_click=abrir_tela_alertas' in fonte
