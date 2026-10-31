import bcrypt

from trixter.senha import gerar_hash_senha, mensagem_senha, senha_confere


def test_senha_aceita_so_quando_cumpre_a_regra_do_cadastro():
    assert "8 caracteres" in mensagem_senha("Curta1!")
    assert "letra e um número" in mensagem_senha("Abcdefgh!")
    assert "maiúscula e uma letra minúscula" in mensagem_senha("abcdefg1!")
    assert "caractere especial" in mensagem_senha("Abcdefg1")
    assert mensagem_senha("Abcdefg1!") is None


def test_troca_na_conta_recusa_senha_fraca_sem_gravar():
    from streamlit.testing.v1 import AppTest

    fonte = '''
from trixter.seguranca import exibir_seguranca
from trixter.senha import gerar_hash_senha
import streamlit as st
st.session_state.usuario_logado = True
st.session_state.usuario_atual = {"id_usuario": "u1", "credencial_versao": 1}
st.session_state.gravou = False
hash_atual = gerar_hash_senha("Atual123!")
class Cursor:
    def execute(self, sql, *args):
        self.sql = sql
        if "UPDATE" in sql:
            st.session_state.gravou = True
    def fetchone(self):
        if "credencial_versao" in self.sql:
            return (1,)
        if "senha" in self.sql:
            return (hash_atual,)
        return None
    def close(self):
        pass
class Conexao:
    def cursor(self):
        return Cursor()
    def commit(self):
        pass
    def close(self):
        pass
def conectar_banco():
    return Conexao()
exibir_seguranca(conectar_banco)
'''
    app = AppTest.from_string(fonte, default_timeout=15).run()
    assert not app.exception
    app.text_input(key="seguranca_senha_atual").set_value("Atual123!")
    app.text_input(key="seguranca_nova_senha").set_value("Abcdefg1")
    app.text_input(key="seguranca_confirmar_senha").set_value("Abcdefg1")
    app.button(key="btn_alterar_senha").click().run()
    assert not app.exception
    assert any("caractere especial" in erro.value for erro in app.error)
    assert not app.session_state.gravou


def test_conta_ausente_nao_confere_mesmo_que_o_preenchimento_passe():
    assert senha_confere("Teste123!", None, lambda senha, hash_: True) is False
    assert senha_confere("Teste123!", "nao-e-hash") is False
    hash_senha = gerar_hash_senha("Teste123!")
    assert senha_confere("Teste123!", hash_senha) is True
    assert senha_confere("Outra123!", hash_senha) is False


def test_hash_confere_a_senha_e_nao_guarda_o_texto():
    hash_senha = gerar_hash_senha("Teste123!")
    assert hash_senha != "Teste123!"
    assert bcrypt.checkpw("Teste123!".encode("utf-8"), hash_senha.encode("utf-8"))
    assert not bcrypt.checkpw("outra".encode("utf-8"), hash_senha.encode("utf-8"))
    assert gerar_hash_senha("Teste123!") != hash_senha
