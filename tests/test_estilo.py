from pathlib import Path

from trixter import estilo

from trixter.estilo import (
    ESTILO_ALERTA,
    ESTILO_BASE,
    ESTILO_FUNDO,
    ESTILO_LOGADO,
    ESTILO_MENUS,
    ESTILO_OCULTAR_NAVEGACAO,
    ESTILO_SEGURANCA,
    folha,
)


def test_publicar_css_usa_html_e_preserva_conteudo_e_ordem(monkeypatch):
    publicados = []
    monkeypatch.setattr(estilo.st, "html", publicados.append)

    def markdown_indevido(*args, **kwargs):
        raise AssertionError("CSS não deve ocupar blocos de Markdown")

    monkeypatch.setattr(estilo.st, "markdown", markdown_indevido)
    folhas = (ESTILO_BASE, ESTILO_LOGADO, ESTILO_SEGURANCA)
    for css in folhas:
        estilo.publicar(css)
    assert publicados == [folha(css) for css in folhas]


def test_a_interface_nao_embute_folha_de_estilo():
    for caminho in ("Gerenciador de Gastos V2.py", "trixter/inicio.py"):
        assert "<style>" not in Path(caminho).read_text(encoding="utf-8")


def test_documentos_reutilizam_fundo_e_suavizacao_sem_afetar_outras_telas(monkeypatch):
    publicados = []
    monkeypatch.setattr(estilo, "publicar", publicados.append)
    monkeypatch.setattr(estilo.Path, "read_bytes", lambda _: b"imagem-ficticia")
    estilo.publicar_fundo_documentos()
    seletor = '[data-testid="stAppViewContainer"]:has(.st-key-documentos_legais)'
    assert publicados == [
        ESTILO_FUNDO.format(img_fundo="aW1hZ2VtLWZpY3RpY2lh").replace(
            '[data-testid="stAppViewContainer"]', seletor),
        estilo.ESTILO_CADASTRO.replace('[data-testid="stAppViewContainer"]', seletor),
    ]
    assert all(seletor in css for css in publicados)
    assert "background-size: cover" in publicados[0]
    assert "rgba(255, 255, 255, 0.72)" in publicados[1]
    assert "background-blend-mode: lighten" in publicados[1]
    assert not any("width:" in css or "font" in css for css in publicados)


def test_cores_autenticadas_saem_com_a_sessao():
    assert "[data-testid=\"stAppViewContainer\"]" in ESTILO_LOGADO
    assert "#F7F8FA" in ESTILO_LOGADO
    assert "#FAF7EE" in ESTILO_LOGADO
    texto = Path("Gerenciador de Gastos V2.py").read_text(encoding="utf-8")
    consulta = texto.index("numeros_resumo = consultar_resumo(")
    saudacao = texto.index("trixter-saudacao")
    assert consulta < saudacao


def test_seletores_principais_permanecem():
    assert ".st-key-btn_confirmar_entrada" in ESTILO_BASE
    assert ".frase-esquerda" in ESTILO_BASE
    assert ".titulo-seguranca" in ESTILO_SEGURANCA
    assert ".st-key-btn_alertas" in ESTILO_ALERTA
    menus = ESTILO_MENUS.format(
        menu_conta_visibilidade="hidden",
        menu_conta_interacao="none",
        menu_alertas_visibilidade="hidden",
        menu_alertas_interacao="none",
    )
    assert ".st-key-cabecalho_menu .st-key-menu_conta_box" in menus
    assert "visibility: hidden" in menus
    assert "{menu_conta_visibilidade}" not in menus
    fundo = ESTILO_FUNDO.format(img_fundo="abc")
    assert 'base64,abc' in fundo
    ocultar = folha(ESTILO_OCULTAR_NAVEGACAO)
    assert "stSidebarCollapsedControl" in ocultar
    assert "display:none" in ocultar
