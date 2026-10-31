"""Limites da importação de PDF. Os arquivos são sintéticos."""
import hashlib
from io import BytesIO
from types import SimpleNamespace

import pypdf
import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.errors import EmptyFileError, FileNotDecryptedError
from reportlab.pdfgen import canvas
from streamlit.testing.v1 import AppTest

from trixter.importacao import (
    LIMITE_BYTES,
    LIMITE_CARACTERES,
    MSG_INVALIDO,
    MSG_LEITURA,
    MSG_MOVIMENTACOES,
    MSG_PAGINAS,
    MSG_SENHA,
    MSG_TAMANHO,
    MSG_TEMPO,
    MSG_TEXTO,
    MSG_VAZIO,
    PdfRecusado,
    extrair_texto_pdf,
    texto_pdf_da_sessao,
)


def test_pypdf_na_versao_validada():
    assert pypdf.__version__ == "6.20.1"


class _Pagina:
    def __init__(self, texto, chamadas):
        self.texto = texto
        self.chamadas = chamadas

    def extract_text(self):
        self.chamadas.append(self.texto)
        return self.texto


def _fabrica(textos):
    chamadas = []
    paginas = [_Pagina(texto, chamadas) for texto in textos]

    def criar(dados):
        criar.leituras += 1
        return SimpleNamespace(pages=paginas, close=lambda: None)

    criar.leituras = 0
    criar.chamadas = chamadas
    return criar


def _pdf_texto(texto, paginas=1):
    buffer = BytesIO()
    desenho = canvas.Canvas(buffer)
    for _ in range(paginas):
        desenho.drawString(72, 720, texto)
        desenho.showPage()
    desenho.save()
    return buffer.getvalue()


def _pdf_em_branco(paginas):
    escritor = PdfWriter()
    for _ in range(paginas):
        escritor.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


def _pdf_com_senha(texto, senha_usuario, senha_dono=None):
    escritor = PdfWriter()
    escritor.append(PdfReader(BytesIO(_pdf_texto(texto))))
    escritor.encrypt(senha_usuario, senha_dono)
    buffer = BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


def _relogio(instantes):
    marcas = iter(instantes)

    def agora():
        return next(marcas)

    return agora


def test_tamanho_acima_de_2_mib_nao_abre_o_pdf():
    class Grande:
        size = LIMITE_BYTES + 1

        def seek(self, *args):
            pass

        def read(self, n=-1):
            raise AssertionError("o arquivo grande nao deve ser lido")

    with pytest.raises(PdfRecusado, match=MSG_TAMANHO):
        texto_pdf_da_sessao(Grande(), "usuario", _fabrica(["texto"]), sessao={})


def test_arquivo_vazio_e_sem_assinatura():
    with pytest.raises(PdfRecusado, match=MSG_VAZIO):
        texto_pdf_da_sessao(b"", "usuario", _fabrica(["texto"]), sessao={})
    fabrica = _fabrica(["texto"])
    with pytest.raises(PdfRecusado, match=MSG_INVALIDO):
        texto_pdf_da_sessao(b"nao e um pdf", "usuario", fabrica, sessao={})
    assert fabrica.leituras == 0
    tardia = b"x" * 1024 + b"%PDF-1.4"
    with pytest.raises(PdfRecusado, match=MSG_INVALIDO):
        texto_pdf_da_sessao(tardia, "usuario", fabrica, sessao={})
    assert fabrica.leituras == 0


def test_assinatura_nos_primeiros_1024_bytes_e_aceita():
    fabrica = _fabrica(["texto sintetico"])
    dados = b"\x00" * 8 + b"%PDF-1.4\nresto sintetico"
    sessao = {}
    assert texto_pdf_da_sessao(dados, "usuario", fabrica, sessao=sessao) == "texto sintetico"
    assert fabrica.leituras == 1


def test_paginas_demais_nao_extrai_texto():
    fabrica = _fabrica(["pagina"] * 16)
    with pytest.raises(PdfRecusado, match=MSG_PAGINAS):
        extrair_texto_pdf(b"%PDF-sintetico", fabrica)
    assert fabrica.chamadas == []
    assert extrair_texto_pdf(b"%PDF-sintetico", _fabrica([""] * 15)) == "\n" * 14


def test_pdf_sintetico_com_16_paginas_e_recusado():
    with pytest.raises(PdfRecusado, match=MSG_PAGINAS):
        extrair_texto_pdf(_pdf_em_branco(16), PdfReader)
    texto = extrair_texto_pdf(_pdf_em_branco(15), PdfReader)
    assert isinstance(texto, str)
    assert len(texto) < 1000


def test_limite_de_caracteres_usa_o_texto_acumulado():
    aceito = "a" * LIMITE_CARACTERES
    assert extrair_texto_pdf(b"%PDF-sintetico", _fabrica([aceito])) == aceito
    with pytest.raises(PdfRecusado, match=MSG_TEXTO):
        extrair_texto_pdf(b"%PDF-sintetico", _fabrica(["b" * (LIMITE_CARACTERES + 1)]))
    primeira = "c" * 100_000
    segunda = "d" * 100_000
    with pytest.raises(PdfRecusado, match=MSG_TEXTO):
        extrair_texto_pdf(b"%PDF-sintetico", _fabrica([primeira, segunda]))


def test_prazo_entre_paginas_nao_interrompe_extract_text():
    uma = _fabrica(["pagina unica"])
    assert extrair_texto_pdf(b"%PDF-sintetico", uma, agora=_relogio([0.0, 0.0, 99.0])) == "pagina unica"
    assert uma.chamadas == ["pagina unica"]

    duas = _fabrica(["primeira", "segunda"])
    with pytest.raises(PdfRecusado, match=MSG_TEMPO):
        extrair_texto_pdf(b"%PDF-sintetico", duas, agora=_relogio([0.0, 0.0, 3.1]))
    assert duas.chamadas == ["primeira"]


def _leitor_que_falha(erro):
    def criar(dados):
        raise erro

    return criar


def test_pdf_vazio_invalido_ou_corrompido_tem_mensagem_amigavel():
    with pytest.raises(PdfRecusado, match=MSG_VAZIO):
        extrair_texto_pdf(b"%PDF-1.4", _leitor_que_falha(EmptyFileError("vazio")))
    with pytest.raises(PdfRecusado, match=MSG_LEITURA):
        extrair_texto_pdf(b"%PDF-1.4\nquebrado\n%%EOF", PdfReader)


def test_senha_recusada_e_senha_vazia_preservada():
    protegido = _pdf_com_senha("Linha sintetica", "segredo")
    with pytest.raises(PdfRecusado, match=MSG_SENHA):
        extrair_texto_pdf(protegido, PdfReader)

    aberto = _pdf_com_senha("Linha sintetica", "", "dono-sintetico")
    assert "Linha sintetica" in extrair_texto_pdf(aberto, PdfReader)

    with pytest.raises(PdfRecusado, match=MSG_SENHA):
        extrair_texto_pdf(b"%PDF-sintetico", _leitor_que_falha(FileNotDecryptedError("protegido")))


def test_cache_da_sessao_segue_usuario_e_conteudo():
    fabrica = _fabrica(["texto sintetico"])
    sessao = {}
    primeiro = texto_pdf_da_sessao(b"%PDF-arquivo-a", "ana", fabrica, sessao=sessao)
    segundo = texto_pdf_da_sessao(b"%PDF-arquivo-a", "ana", fabrica, sessao=sessao)
    assert primeiro == segundo == "texto sintetico"
    assert fabrica.leituras == 1

    texto_pdf_da_sessao(b"%PDF-arquivo-b", "ana", fabrica, sessao=sessao)
    assert fabrica.leituras == 2
    assert sessao["pdf_texto_sessao"]["conteudo"] != hashlib.sha256(b"%PDF-arquivo-a").hexdigest()

    texto_pdf_da_sessao(b"%PDF-arquivo-b", "bruno", fabrica, sessao=sessao)
    assert fabrica.leituras == 3
    assert sessao["pdf_texto_sessao"]["usuario"] == "bruno"
    assert sessao["pdf_texto_sessao"]["texto"] == "texto sintetico"


def test_rerun_reusa_o_texto_extraido():
    app = AppTest.from_string(
        """
import streamlit as st
from trixter.importacao import texto_pdf_da_sessao
st.session_state.setdefault("chamadas", 0)
class Pagina:
    def extract_text(self):
        return "texto sintetico"
class Leitor:
    def __init__(self, dados):
        st.session_state.chamadas += 1
        self.pages = [Pagina()]
    def close(self):
        pass
texto_pdf_da_sessao(b"%PDF-1.4 sintetico", "u1", Leitor)
""",
        default_timeout=15,
    ).run()
    assert not app.exception
    assert app.session_state.chamadas == 1
    app.run()
    assert not app.exception
    assert app.session_state.chamadas == 1


def _app_extrato(linhas):
    return f'''
from trixter.importacao import exibir_importacao_pdf
import streamlit as st
from types import SimpleNamespace
st.session_state.setdefault("usuario_atual", {{"id_usuario": "u1"}})
st.session_state.setdefault("gravacoes", [])
st.session_state.setdefault("commits", 0)
st.file_uploader = lambda *a, **k: b"%PDF-1.4 sintetico"
class Cursor:
    def execute(self, sql, *args):
        if "INSERT INTO" in sql:
            st.session_state.gravacoes.append(sql)
    def fetchone(self):
        return None
    def close(self):
        pass
class Conexao:
    def cursor(self):
        return Cursor()
    def commit(self):
        st.session_state.commits += 1
    def close(self):
        pass
def conectar_banco():
    return Conexao()
def listar_categorias(*args):
    return ["Teste"]
def formatar_moeda(valor):
    return str(valor)
PdfReader = lambda arquivo: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: {linhas!r}, )], close=lambda: None)
exibir_importacao_pdf(conectar_banco, listar_categorias, formatar_moeda, PdfReader, "Pessoa Fisica", "Gasto")
'''


def test_arquivo_invalido_bloqueia_comprovante_e_extrato():
    app = AppTest.from_string(
        _app_extrato("01/01/2026 Sintetico 10,00").replace(
            'b"%PDF-1.4 sintetico"',
            'b"nao e pdf"',
        ),
        default_timeout=15,
    ).run()
    assert not app.exception
    assert app.error[0].value == MSG_INVALIDO
    assert not app.selectbox


def test_extrato_acima_de_300_nao_abre_editor_nem_grava():
    linhas = "\n".join(f"01/01/2026 Sintetico {indice:03d} 10,00" for indice in range(301))
    app = AppTest.from_string(_app_extrato(linhas), default_timeout=20).run()
    assert not app.exception
    app.selectbox(key="tipo_pdf_importacao").select("Extrato bancário").run()
    assert not app.exception
    assert app.error[0].value == MSG_MOVIMENTACOES
    assert not app.button
    assert app.session_state.gravacoes == []
    assert app.session_state.commits == 0


def test_pdf_sintetico_de_uma_pagina_entrega_o_texto():
    dados = _pdf_texto("Linha sintetica")
    assert dados.startswith(b"%PDF-")
    assert len(dados) <= LIMITE_BYTES
    assert "Linha sintetica" in extrair_texto_pdf(dados, PdfReader)
