from trixter.sessao import garantir_acesso, garantir_navegacao


def test_acesso_so_preenche_chave_ausente():
    estado = {"entrar": True}
    garantir_acesso(estado)
    assert estado["entrar"] is True
    assert estado["criar_conta"] is False
    assert estado["usuario_logado"] is False
    assert estado["usuario_atual"] is None
    assert estado["recuperar_senha"] is False
    assert estado["menu_conta_aberto"] is False
    assert estado["menu_alertas_aberto"] is False


def test_navegacao_comeca_no_menu_e_preserva_a_tela_aberta():
    estado = {}
    garantir_navegacao(estado)
    assert estado["tela_atual"] == "menu"
    assert estado["alterar_recorrencia"] is False
    estado["tela_atual"] = "onboarding"
    garantir_navegacao(estado)
    assert estado["tela_atual"] == "onboarding"
