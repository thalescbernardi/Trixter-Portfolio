import ast
import hashlib
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pyodbc
import pytest
from streamlit.testing.v1 import AppTest

from trixter.credencial import (
    endereco_email,
    preparar_operacao,
    recurso_email,
    reservar_email,
    segurar_email,
)
from trixter.seguranca import (
    ASSUNTO_AVISO_EMAIL,
    ASSUNTO_CODIGO_EMAIL,
    concluir_alteracao_email,
    confirmar_troca_email,
    pedir_confirmacao_email,
)
from trixter.senha import gerar_hash_senha
from trixter.sessao import encerrar_sessao_local

AGORA = datetime(2026, 10, 12, 15, 0, 0)
IP = "203.0.113.9"
SENHA = "Senha123!"
PROIBIDOS = ("R$", "saldo", "categoria", "cliente", "faturamento", "receita", "despesa")


class Banco:
    def __init__(self):
        self.usuarios = {}
        self.limites = {}
        self.guard = threading.Lock()
        self.travas = {}
        self.alteracoes = []
        self.sincronizar = None
        self.recusar_trava = False
        self.falhar_update = False
        self.falhar_trava = False
        self.falhar_insercao = False
        self.codigo_trava = None
        self.recursos = []

    def conta(self, id_usuario, email, senha, versao=1):
        self.usuarios[id_usuario] = {"email": email, "senha": senha, "versao": versao}

    def conectar(self):
        return _Conexao(self)

    def trava(self, nome):
        with self.guard:
            if nome not in self.travas:
                self.travas[nome] = threading.Lock()
            return self.travas[nome]


class _Conexao:
    def __init__(self, banco):
        self.banco = banco
        self.limites_antes = deepcopy(banco.limites)
        self.desfazer = None
        self.inserido = None
        self.travas = []

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        if self.desfazer is not None:
            self.banco.alteracoes.append(self.desfazer[0])
            self.desfazer = None
        if self.inserido is not None:
            self.banco.alteracoes.append(self.inserido)
            self.inserido = None
        self.limites_antes = deepcopy(self.banco.limites)
        self._soltar()

    def rollback(self):
        self.banco.limites = self.limites_antes
        if self.inserido is not None:
            self.banco.usuarios.pop(self.inserido, None)
            self.inserido = None
        if self.desfazer is not None:
            id_usuario, email, versao = self.desfazer
            self.banco.usuarios[id_usuario]["email"] = email
            self.banco.usuarios[id_usuario]["versao"] = versao
            self.desfazer = None
        self._soltar()

    def close(self):
        if self.desfazer is not None or self.inserido is not None:
            self.rollback()
        else:
            self._soltar()

    def _soltar(self):
        while self.travas:
            self.travas.pop().release()


class _Cursor:
    def __init__(self, conexao):
        self.conexao = conexao
        self.banco = conexao.banco
        self._linha = None
        self.rowcount = -1
        self.sql = ""

    def execute(self, sql, *params):
        texto = " ".join(sql.split())
        self.sql = texto
        if "sp_getapplock" in texto:
            self._applock(params[0])
            return
        if "limites_acesso" in texto or "janela_inicio" in texto:
            self._limite(texto, params)
            return
        if "UPDLOCK" in texto:
            self._ler_conta(params[0], travar=True)
            return
        if texto.startswith("UPDATE") and "SET email" in texto:
            self._gravar_email(params)
            return
        if texto.startswith("SELECT") and "credencial_versao" in texto:
            usuario = self.banco.usuarios.get(params[0])
            self._linha = None if usuario is None else (usuario["versao"],)
            return
        if texto.startswith("SELECT") and "senha" in texto:
            usuario = self.banco.usuarios.get(params[0])
            self._linha = None if usuario is None else (usuario["senha"], usuario["email"])
            return
        if texto.startswith("INSERT") and "dbo.usuarios" in texto:
            self._inserir_usuario(params)
            return
        if texto.startswith("SELECT") and "WHERE email" in texto:
            encontrado = next(
                (
                    uid for uid, dados in self.banco.usuarios.items()
                    if str(dados["email"]).strip().lower() == str(params[0]).strip().lower()
                ),
                None,
            )
            self._linha = None if encontrado is None else (encontrado,)
            return
        if "data_entrada" in texto:
            self._linha = None
            return
        raise AssertionError(texto)

    def fetchone(self):
        return self._linha

    def nextset(self):
        return False

    def close(self):
        return None

    def _applock(self, recurso):
        self.banco.recursos.append(str(recurso))
        if self.banco.falhar_trava:
            raise pyodbc.Error("HY000", "trava")
        if not str(recurso).startswith("trixter.email|"):
            self._linha = (0,)
            return
        if self.banco.codigo_trava is not None:
            self._linha = (int(self.banco.codigo_trava),)
            return
        if self.banco.recusar_trava:
            self._linha = (-1,)
            return
        trava = self.banco.trava(str(recurso))
        if not trava.acquire(timeout=5):
            self._linha = (-1,)
            return
        self.conexao.travas.append(trava)
        self._linha = (0,)

    def _ler_conta(self, id_usuario, travar):
        if travar and self.banco.sincronizar is not None:
            self.banco.sincronizar.wait(timeout=5)
        if travar:
            trava = self.banco.trava(f"usuario|{id_usuario}")
            if not trava.acquire(timeout=5):
                self._linha = None
                return
            self.conexao.travas.append(trava)
        usuario = self.banco.usuarios.get(id_usuario)
        self._linha = None if usuario is None else (usuario["email"],)

    def _gravar_email(self, params):
        if self.banco.falhar_update:
            raise pyodbc.Error("HY000", "falha")
        email_novo, id_usuario, email_atual, _repetido, _usuario = params
        usuario = self.banco.usuarios.get(id_usuario)
        if usuario is None or usuario["email"] != email_atual:
            self._linha = None
            return
        ocupado = any(
            uid != id_usuario and str(dados["email"]).strip().lower() == str(email_novo).strip().lower()
            for uid, dados in self.banco.usuarios.items()
        )
        if ocupado:
            self._linha = None
            return
        self.conexao.desfazer = (id_usuario, usuario["email"], usuario["versao"])
        usuario["email"] = email_novo
        usuario["versao"] += 1
        self._linha = (usuario["versao"],)
        self.rowcount = 1

    def _inserir_usuario(self, params):
        if self.banco.falhar_insercao:
            raise pyodbc.Error("HY000", "falha")
        id_usuario = params[0]
        email = params[1] if len(params) == 2 else params[5]
        ocupado = any(
            uid != id_usuario and str(dados["email"]).strip().lower() == str(email).strip().lower()
            for uid, dados in self.banco.usuarios.items()
        )
        if ocupado or id_usuario in self.banco.usuarios:
            self._linha = None
            return
        self.banco.usuarios[id_usuario] = {"email": email, "senha": "hash", "versao": 1}
        self.conexao.inserido = id_usuario
        self._linha = (1,)
        self.rowcount = 1

    def _limite(self, texto, params):
        if texto.startswith("DELETE") and "janela_inicio" in texto:
            limite_data = params[0]
            self.banco.limites = {
                chave: valor for chave, valor in self.banco.limites.items() if valor[1] >= limite_data
            }
            self.rowcount = 1
            return
        if texto.startswith("DELETE"):
            self.banco.limites.pop((params[0], params[1]), None)
            self.rowcount = 1
            return
        if texto.startswith("SELECT"):
            self._linha = self.banco.limites.get((params[0], params[1]))
            return
        if texto.startswith("UPDATE"):
            tentativas, inicio, ate, fluxo, chave = params
            self.banco.limites[(fluxo, chave)] = (tentativas, inicio, ate)
            self.rowcount = 1
            return
        if texto.startswith("INSERT"):
            fluxo, chave, tentativas, inicio, ate = params
            self.banco.limites[(fluxo, chave)] = (tentativas, inicio, ate)
            self.rowcount = 1
            return
        raise AssertionError(texto)


class _Envios:
    def __init__(self):
        self.itens = []
        self.falhar_codigo = False
        self.falhar_aviso = False

    def enviar(self, **kwargs):
        registro = {
            "destinatario": kwargs["destinatario"],
            "assunto": kwargs["assunto"],
            "corpo": kwargs["corpo"],
        }
        self.itens.append(registro)
        if self.falhar_codigo and kwargs["assunto"] == ASSUNTO_CODIGO_EMAIL:
            raise RuntimeError("smtp")
        if self.falhar_aviso and kwargs["assunto"] == ASSUNTO_AVISO_EMAIL:
            raise RuntimeError("smtp")

    def codigo(self):
        return re.search(r"\b(\d{6})\b", self.itens[-1]["corpo"]).group(1)


def _estado():
    return {}


def _pedir(banco, envios, estado, novo=" Novo@Example.com ", confirmar=None, senha=SENHA, agora=AGORA, usuario="u1"):
    return pedir_confirmacao_email(
        estado, banco.conectar, usuario, novo, confirmar or novo, senha, envios.enviar, IP, agora,
    )


def _concluir(banco, envios, estado, codigo, agora=AGORA, usuario="u1"):
    return concluir_alteracao_email(
        estado, banco.conectar, usuario, codigo, envios.enviar, IP, agora,
    )


def _preparar():
    banco = Banco()
    banco.conta("u1", "antigo@example.com", gerar_hash_senha(SENHA))
    return banco, _Envios(), _estado()


def _textos_sem_financeiro(envios):
    for item in envios.itens:
        texto = f"{item['assunto']}\n{item['corpo']}".lower()
        assert all(palavra.lower() not in texto for palavra in PROIBIDOS)


def test_senha_errada_nao_envia_nem_grava():
    banco, envios, estado = _preparar()
    assert _pedir(banco, envios, estado, senha="Errada123!") == "senha"
    assert envios.itens == []
    assert "verificacao_email" not in estado
    assert banco.usuarios["u1"]["email"] == "antigo@example.com"
    assert banco.alteracoes == []


def test_falha_do_brevo_nao_deixa_codigo_utilizavel():
    banco, envios, estado = _preparar()
    envios.falhar_codigo = True
    assert _pedir(banco, envios, estado) == "envio"
    assert "verificacao_email" not in estado
    assert banco.alteracoes == []
    codigo = envios.codigo()
    assert _concluir(banco, envios, estado, codigo)[0] == "ausente"
    assert banco.usuarios["u1"]["email"] == "antigo@example.com"


def test_codigo_certo_troca_email_e_versao_num_commit():
    banco, envios, estado = _preparar()
    assert _pedir(banco, envios, estado) == "enviado"
    assert banco.alteracoes == []
    desafio = estado["verificacao_email"]
    codigo = envios.codigo()
    assert "codigo" not in desafio
    assert desafio["codigo_hash"] != codigo
    assert codigo not in desafio.values()
    assert desafio["email"] == "novo@example.com"
    assert desafio["usuario_id"] == "u1"
    assert desafio["finalidade"] == "email"
    assert desafio["email_anterior"] == "antigo@example.com"
    situacao, versao, email = _concluir(banco, envios, estado, codigo)
    assert situacao == "alterado"
    assert versao == 2
    assert email == "novo@example.com"
    assert banco.usuarios["u1"]["email"] == "novo@example.com"
    assert banco.usuarios["u1"]["versao"] == 2
    assert banco.alteracoes == ["u1"]
    assert envios.itens[-1]["assunto"] == ASSUNTO_AVISO_EMAIL
    assert envios.itens[-1]["destinatario"] == "antigo@example.com"
    assert codigo not in envios.itens[-1]["corpo"]
    assert "novo@example.com" not in envios.itens[-1]["corpo"]
    _textos_sem_financeiro(envios)
    assert "verificacao_email" not in estado


def test_codigo_expirado_repetido_e_sexta_tentativa_nao_gravam():
    banco, envios, estado = _preparar()
    assert _pedir(banco, envios, estado) == "enviado"
    codigo = envios.codigo()
    assert _concluir(banco, envios, estado, codigo, AGORA + timedelta(minutes=10))[0] == "expirado"
    assert banco.alteracoes == []

    assert _pedir(banco, envios, estado, agora=AGORA + timedelta(minutes=2)) == "enviado"
    codigo = envios.codigo()
    assert _concluir(banco, envios, estado, codigo)[0] == "alterado"
    assert _concluir(banco, envios, estado, codigo)[0] == "ausente"
    assert banco.usuarios["u1"]["versao"] == 2

    banco.usuarios["u1"]["email"] = "antigo@example.com"
    banco.usuarios["u1"]["versao"] = 1
    banco.alteracoes.clear()
    assert _pedir(banco, envios, estado, agora=AGORA + timedelta(minutes=4)) == "enviado"
    codigo = envios.codigo()
    for _ in range(4):
        assert _concluir(banco, envios, estado, "000000", AGORA + timedelta(minutes=4))[0] == "invalido"
    assert _concluir(banco, envios, estado, "000000", AGORA + timedelta(minutes=4))[0] == "limite"
    assert _concluir(banco, envios, estado, codigo, AGORA + timedelta(minutes=4))[0] == "ausente"
    assert banco.alteracoes == []


def test_codigo_nao_confirma_outro_endereco_usuario_ou_finalidade():
    banco, envios, estado = _preparar()
    assert _pedir(banco, envios, estado) == "enviado"
    codigo = envios.codigo()
    estado["verificacao_email"]["email"] = "outro@example.com"
    assert _concluir(banco, envios, estado, codigo)[0] == "invalido"
    assert banco.alteracoes == []

    estado.clear()
    assert _pedir(banco, envios, estado, agora=AGORA + timedelta(minutes=2)) == "enviado"
    codigo = envios.codigo()
    estado["verificacao_email"]["usuario_id"] = "u2"
    assert _concluir(banco, envios, estado, codigo, AGORA + timedelta(minutes=2))[0] == "invalido"

    from trixter import verificacao
    estado.pop("verificacao_email", None)
    estado.pop("autorizacao_email", None)
    verificacao.registrar(estado, "recuperacao", codigo, "novo@example.com", "u1", AGORA)
    assert _concluir(banco, envios, estado, codigo, AGORA + timedelta(minutes=2))[0] == "ausente"
    assert banco.usuarios["u1"]["email"] == "antigo@example.com"


def test_outra_sessao_e_revogada_e_esta_adota_a_versao():
    banco, envios, estado = _preparar()
    assert _pedir(banco, envios, estado) == "enviado"
    codigo = envios.codigo()
    situacao, versao, email = _concluir(banco, envios, estado, codigo)
    assert situacao == "alterado"
    atual = {
        "usuario_logado": True,
        "usuario_atual": {"id_usuario": "u1", "email": "antigo@example.com", "credencial_versao": 1},
    }
    from trixter.credencial import adotar_versao
    adotar_versao(atual, versao)
    atual["usuario_atual"]["email"] = email
    assert preparar_operacao(banco.conectar, atual) == "ok"
    outra = {
        "usuario_logado": True,
        "usuario_atual": {"id_usuario": "u1", "email": "antigo@example.com", "credencial_versao": 1},
    }
    assert preparar_operacao(banco.conectar, outra) == "revogada"
    assert outra["usuario_logado"] is False


def test_falha_do_aviso_preserva_a_troca():
    banco, envios, estado = _preparar()
    assert _pedir(banco, envios, estado) == "enviado"
    codigo = envios.codigo()
    envios.falhar_aviso = True
    situacao, versao, email = _concluir(banco, envios, estado, codigo)
    assert situacao == "aviso_falhou"
    assert versao == 2
    assert email == "novo@example.com"
    assert banco.usuarios["u1"]["email"] == "novo@example.com"
    assert _concluir(banco, envios, estado, codigo)[0] == "ausente"


def test_pedido_novo_invalida_o_codigo_anterior():
    banco, envios, estado = _preparar()
    assert _pedir(banco, envios, estado) == "enviado"
    primeiro = envios.codigo()
    assert _pedir(banco, envios, estado, agora=AGORA + timedelta(seconds=61)) == "enviado"
    segundo = envios.codigo()
    assert primeiro != segundo
    assert _concluir(banco, envios, estado, primeiro, AGORA + timedelta(seconds=61))[0] == "invalido"
    assert banco.alteracoes == []
    assert _concluir(banco, envios, estado, segundo, AGORA + timedelta(seconds=61))[0] == "alterado"
    assert banco.usuarios["u1"]["email"] == "novo@example.com"


def test_reenvio_cedo_preserva_o_codigo_e_a_cota_bloqueia_o_quarto():
    banco, envios, estado = _preparar()
    assert _pedir(banco, envios, estado) == "enviado"
    codigo = envios.codigo()
    assert _pedir(banco, envios, estado, agora=AGORA + timedelta(seconds=30)) == "espera"
    assert len([item for item in envios.itens if item["assunto"] == ASSUNTO_CODIGO_EMAIL]) == 1
    momento = AGORA + timedelta(seconds=61)
    for passo in range(2):
        assert _pedir(banco, envios, estado, agora=momento) == "enviado"
        momento += timedelta(seconds=61)
    assert _pedir(banco, envios, estado, agora=momento) == "limite"
    assert _concluir(banco, envios, estado, envios.codigo(), momento)[0] == "alterado"


def test_email_ocupado_e_invalido_nao_gravam():
    banco, envios, estado = _preparar()
    banco.conta("u2", "novo@example.com", "hash")
    assert _pedir(banco, envios, estado, "novo@example.com") == "ocupado"
    assert envios.itens == []
    assert _pedir(banco, envios, estado, "sem-arroba") == "invalido"
    assert _pedir(banco, envios, estado, "novo@example.com", "outro@example.com") == "diferente"
    assert banco.usuarios["u1"]["email"] == "antigo@example.com"


def test_falha_sql_desfaz_e_nao_avisa():
    banco, envios, estado = _preparar()
    assert _pedir(banco, envios, estado) == "enviado"
    codigo = envios.codigo()
    banco.falhar_update = True
    assert _concluir(banco, envios, estado, codigo)[0] == "nao_alterou"
    assert banco.usuarios["u1"]["email"] == "antigo@example.com"
    assert banco.usuarios["u1"]["versao"] == 1
    assert all(item["assunto"] != ASSUNTO_AVISO_EMAIL for item in envios.itens)
    assert _concluir(banco, envios, estado, codigo)[0] == "ausente"


def test_trava_recusada_nao_grava():
    banco, envios, estado = _preparar()
    assert _pedir(banco, envios, estado) == "enviado"
    codigo = envios.codigo()
    banco.recusar_trava = True
    assert _concluir(banco, envios, estado, codigo)[0] == "nao_alterou"
    assert banco.alteracoes == []
    assert _concluir(banco, envios, estado, codigo)[0] == "ausente"


def test_duas_confirmacoes_simultaneas_alteram_a_conta_uma_vez():
    banco = Banco()
    banco.conta("u1", "antigo@example.com", "hash")
    banco.sincronizar = threading.Barrier(2)

    def tentar(destino):
        conexao = banco.conectar()
        try:
            cursor = conexao.cursor()
            versao = confirmar_troca_email(cursor, "u1", "antigo@example.com", destino)
            if versao is None:
                conexao.rollback()
                return None
            conexao.commit()
            return versao
        finally:
            conexao.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(tentar, ["um@example.com", "dois@example.com"]))
    assert sum(item is not None for item in resultados) == 1
    assert banco.usuarios["u1"]["versao"] == 2
    assert banco.usuarios["u1"]["email"] in {"um@example.com", "dois@example.com"}
    assert len(banco.alteracoes) == 1


def test_dois_usuarios_nao_ficam_com_o_mesmo_email():
    banco = Banco()
    banco.conta("u1", "a@example.com", "hash")
    banco.conta("u2", "b@example.com", "hash")

    def tentar(usuario, anterior):
        conexao = banco.conectar()
        try:
            cursor = conexao.cursor()
            versao = confirmar_troca_email(cursor, usuario, anterior, "mesmo@example.com")
            if versao is None:
                conexao.rollback()
                return None
            conexao.commit()
            return versao
        finally:
            conexao.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(
            lambda item: tentar(*item),
            [("u1", "a@example.com"), ("u2", "b@example.com")],
        ))
    assert sum(item is not None for item in resultados) == 1
    emails = [banco.usuarios["u1"]["email"], banco.usuarios["u2"]["email"]]
    assert emails.count("mesmo@example.com") == 1


def test_logout_apaga_o_codigo_e_o_aviso():
    _banco, _envios, estado = _preparar()
    estado["verificacao_email"] = {"codigo_hash": "abc", "sal": "sal"}
    estado["codigo_digitado_email"] = "123456"
    estado["aviso_email"] = ("sucesso", "ok")
    estado["reenvio_email"] = AGORA
    encerrar_sessao_local(estado)
    assert "verificacao_email" not in estado
    assert "codigo_digitado_email" not in estado
    assert "aviso_email" not in estado
    assert "reenvio_email" not in estado


def test_tela_so_grava_depois_do_codigo():
    from trixter import seguranca

    banco, envios, _estado = _preparar()
    seguranca._banco_teste = banco
    seguranca._envios_teste = envios

    def tela():
        import streamlit as st
        from trixter import seguranca as tela_seguranca
        from trixter.seguranca import exibir_seguranca
        st.session_state.setdefault("usuario_logado", True)
        st.session_state.setdefault("usuario_atual", {
            "id_usuario": "u1", "email": "antigo@example.com", "credencial_versao": 1,
        })
        exibir_seguranca(tela_seguranca._banco_teste.conectar, tela_seguranca._envios_teste.enviar)

    try:
        app = AppTest.from_function(tela, default_timeout=30).run()
        assert not app.exception
        app.text_input(key="novo_email_seguranca").set_value(" Novo@Example.com ")
        app.text_input(key="confirmar_email_seguranca").set_value("novo@example.com")
        app.text_input(key="senha_email_seguranca").set_value(SENHA)
        app.button(key="btn_alterar_email").click().run()
        assert not app.exception
        assert banco.usuarios["u1"]["email"] == "antigo@example.com"
        codigo = envios.codigo()
        assert "codigo" not in app.session_state.verificacao_email
        assert codigo not in app.session_state.verificacao_email.values()
        app.text_input(key="codigo_digitado_email").set_value(codigo)
        app.button(key="btn_confirmar_email").click().run()
        assert not app.exception
        assert banco.usuarios["u1"]["email"] == "novo@example.com"
        assert app.session_state.usuario_atual["credencial_versao"] == 2
        assert app.session_state.usuario_atual["email"] == "novo@example.com"
        assert "verificacao_email" not in app.session_state
        assert "codigo_digitado_email" not in app.session_state
        assert any("alterado com sucesso" in item.value for item in app.success)
    finally:
        del seguranca._banco_teste
        del seguranca._envios_teste


def test_tela_recusa_senha_errada_e_sessao_anonima():
    from trixter import seguranca

    banco, envios, _estado = _preparar()
    seguranca._banco_teste = banco
    seguranca._envios_teste = envios

    def tela():
        import streamlit as st
        from trixter import seguranca as tela_seguranca
        from trixter.seguranca import exibir_seguranca
        st.session_state.setdefault("usuario_logado", True)
        st.session_state.setdefault("usuario_atual", {
            "id_usuario": "u1", "email": "antigo@example.com", "credencial_versao": 1,
        })
        exibir_seguranca(tela_seguranca._banco_teste.conectar, tela_seguranca._envios_teste.enviar)

    try:
        app = AppTest.from_function(tela, default_timeout=30).run()
        assert not app.exception
        app.text_input(key="novo_email_seguranca").set_value("novo@example.com")
        app.text_input(key="confirmar_email_seguranca").set_value("novo@example.com")
        app.text_input(key="senha_email_seguranca").set_value("Errada123!")
        app.button(key="btn_alterar_email").click().run()
        assert not app.exception
        assert any("incorreta" in item.value for item in app.error)
        assert envios.itens == []
        assert banco.alteracoes == []

        def anonima():
            from trixter import seguranca as tela_seguranca
            from trixter.seguranca import exibir_seguranca
            exibir_seguranca(tela_seguranca._banco_teste.conectar, tela_seguranca._envios_teste.enviar)

        vazia = AppTest.from_function(anonima, default_timeout=30).run()
        assert not vazia.exception
        assert vazia.button == []
    finally:
        del seguranca._banco_teste
        del seguranca._envios_teste


def test_troca_de_email_continua_com_hash_e_rejeita_reuso():
    banco, envios, estado = _preparar()
    assert _pedir(banco, envios, estado) == "enviado"
    desafio = estado["verificacao_email"]
    codigo = envios.codigo()
    assert "codigo" not in desafio
    assert desafio["sal"]
    assert desafio["codigo_hash"] != codigo
    assert codigo not in desafio.values()
    assert _concluir(banco, envios, estado, codigo)[0] == "alterado"
    assert _concluir(banco, envios, estado, codigo)[0] == "ausente"
    assert banco.usuarios["u1"]["email"] == "novo@example.com"


def _fontes_de_producao():
    raiz = Path(__file__).resolve().parents[1]
    return [*sorted((raiz / "trixter").glob("*.py")), raiz / "Gerenciador de Gastos V2.py"]


def _trecho(arquivo, nome):
    fonte = arquivo.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    funcao = next(
        no for no in ast.walk(arvore)
        if isinstance(no, ast.FunctionDef) and no.name == nome
    )
    return ast.get_source_segment(fonte, funcao)


def _cadastrar(banco, id_usuario, email):
    conexao = banco.conectar()
    try:
        cursor = conexao.cursor()
        try:
            if not reservar_email(cursor, email, id_usuario):
                conexao.rollback()
                return False
            cursor.execute(
                "INSERT INTO dbo.usuarios (id_usuario, email) VALUES (?, ?)",
                id_usuario,
                endereco_email(email),
            )
            if cursor.fetchone() is None:
                conexao.rollback()
                return False
            conexao.commit()
            return True
        except pyodbc.Error:
            conexao.rollback()
            return False
    finally:
        conexao.close()


class _CursorTrava:
    def __init__(self, linha):
        self.linha = linha
        self.chamadas = []
        self.conjuntos = 0

    def execute(self, sql, *args):
        self.chamadas.append((sql, args))

    def fetchone(self):
        return self.linha

    def nextset(self):
        self.conjuntos += 1
        return False


def test_recurso_ignora_caixa_e_espacos():
    assert recurso_email(" Mesmo@Example.com ") == recurso_email("mesmo@example.com")
    assert recurso_email("mesmo@example.com") == (
        "trixter.email|" + hashlib.sha256(b"mesmo@example.com").hexdigest()
    )


@pytest.mark.parametrize("linha, esperado", [
    ((0,), True),
    ((1,), True),
    ((-1,), False),
    ((-2,), False),
    ((-3,), False),
    ((-999,), False),
    (None, False),
    (("x",), False),
])
def test_retorno_da_trava_de_email(linha, esperado):
    cursor = _CursorTrava(linha)
    assert segurar_email(cursor, " A@Example.com ") is esperado
    sql, args = cursor.chamadas[0]
    assert args == (recurso_email("a@example.com"), 5000)
    assert "LockMode = 'Exclusive'" in sql
    assert "LockOwner = 'Transaction'" in sql
    assert cursor.conjuntos == 1


def test_erro_no_conjunto_seguinte_nao_e_engolido():
    class Cursor(_CursorTrava):
        def nextset(self):
            raise pyodbc.Error("HY000", "conjunto")

    with pytest.raises(pyodbc.Error):
        segurar_email(Cursor((0,)), "a@example.com")


def test_todos_os_caminhos_reservam_o_email():
    gravacoes = []
    for arquivo in _fontes_de_producao():
        fonte = arquivo.read_text(encoding="utf-8")
        if "trixter.email|" in fonte:
            assert arquivo.name == "credencial.py"
        for no in ast.walk(ast.parse(fonte)):
            if not isinstance(no, ast.FunctionDef):
                continue
            trecho = ast.get_source_segment(fonte, no)
            if not trecho:
                continue
            if "INSERT INTO dbo.usuarios" not in trecho and "SET email =" not in trecho:
                continue
            gravacoes.append((arquivo.name, no.name))
            if no.name == "gravar_email":
                continue
            marca = "INSERT INTO dbo.usuarios" if "INSERT INTO dbo.usuarios" in trecho else "SET email ="
            assert "reservar_email" in trecho
            assert trecho.index("reservar_email") < trecho.index(marca)
    assert ("credencial.py", "gravar_email") in gravacoes
    assert ("acesso.py", "exibir_cadastro") in gravacoes
    assert ("demo.py", "criar_demo_pj") in gravacoes
    assert ("Gerenciador de Gastos V2.py", "_preencher_demo_temporaria") in gravacoes
    confirmar = _trecho(Path(__file__).resolve().parents[1] / "trixter" / "seguranca.py", "confirmar_troca_email")
    assert confirmar.index("reservar_email") < confirmar.index("gravar_email(")


def test_cadastro_recusa_email_que_ja_existe():
    banco = Banco()
    banco.conta("u1", "mesmo@example.com", "hash")
    assert _cadastrar(banco, "u2", " Mesmo@Example.com ") is False
    assert "u2" not in banco.usuarios
    assert banco.usuarios["u1"]["email"] == "mesmo@example.com"


def test_dois_cadastros_do_mesmo_email_gravam_um():
    banco = Banco()
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(
            lambda uid: _cadastrar(banco, uid, "mesmo@example.com"),
            ["u1", "u2"],
        ))
    assert resultados.count(True) == 1
    assert [dados["email"] for dados in banco.usuarios.values()].count("mesmo@example.com") == 1
    assert set(banco.recursos) == {recurso_email("mesmo@example.com")}


def test_cadastros_com_caixa_diferente_disputam_o_mesmo_endereco():
    banco = Banco()
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(
            lambda item: _cadastrar(banco, *item),
            [("u1", " Mesmo@Example.com "), ("u2", "mesmo@example.com")],
        ))
    assert resultados.count(True) == 1
    assert [dados["email"] for dados in banco.usuarios.values()] == ["mesmo@example.com"]


def test_cadastro_simultaneo_nao_divide_o_email_com_a_alteracao():
    banco = Banco()
    banco.conta("u1", "antigo@example.com", "hash")

    def alterar():
        conexao = banco.conectar()
        try:
            cursor = conexao.cursor()
            versao = confirmar_troca_email(
                cursor, "u1", "antigo@example.com", "mesmo@example.com",
            )
            if versao is None:
                conexao.rollback()
                return False
            conexao.commit()
            return True
        finally:
            conexao.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(
            lambda funcao: funcao(),
            [alterar, lambda: _cadastrar(banco, "u2", " Mesmo@Example.com ")],
        ))
    assert resultados.count(True) == 1
    assert [dados["email"] for dados in banco.usuarios.values()].count("mesmo@example.com") == 1
    assert set(banco.recursos) == {recurso_email("mesmo@example.com")}


@pytest.mark.parametrize("codigo", [-1, -2, -3, -999])
def test_trava_negativa_nao_grava_cadastro(codigo):
    banco = Banco()
    banco.codigo_trava = codigo
    assert _cadastrar(banco, "u1", "mesmo@example.com") is False
    assert banco.usuarios == {}


def test_erro_sql_na_trava_nao_grava_cadastro():
    banco = Banco()
    banco.falhar_trava = True
    assert _cadastrar(banco, "u1", "mesmo@example.com") is False
    assert banco.usuarios == {}


def test_erro_sql_no_cadastro_desfaz_e_libera_o_endereco():
    banco = Banco()
    banco.falhar_insercao = True
    assert _cadastrar(banco, "u1", "mesmo@example.com") is False
    assert banco.usuarios == {}
    banco.falhar_insercao = False
    assert _cadastrar(banco, "u1", "mesmo@example.com") is True
    assert banco.usuarios["u1"]["email"] == "mesmo@example.com"


def test_fechar_sem_commit_nao_mantem_o_cadastro():
    banco = Banco()
    conexao = banco.conectar()
    cursor = conexao.cursor()
    assert reservar_email(cursor, "mesmo@example.com", "u1") is True
    cursor.execute(
        "INSERT INTO dbo.usuarios (id_usuario, email) VALUES (?, ?)",
        "u1",
        "mesmo@example.com",
    )
    conexao.close()
    assert "u1" not in banco.usuarios
    assert _cadastrar(banco, "u2", "mesmo@example.com") is True
