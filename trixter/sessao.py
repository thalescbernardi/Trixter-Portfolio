"""Estado inicial da sessão. Não abre banco e não escolhe a tela."""


def _definir(estado, chave, valor):
    if chave not in estado:
        estado[chave] = valor


def garantir_acesso(estado):
    """Garante as chaves da entrada, antes de qualquer tela."""
    _definir(estado, "criar_conta", False)
    _definir(estado, "entrar", False)
    _definir(estado, "usuario_logado", False)
    _definir(estado, "usuario_atual", None)
    _definir(estado, "recuperar_senha", False)
    _definir(estado, "menu_conta_aberto", False)
    _definir(estado, "menu_alertas_aberto", False)


def garantir_navegacao(estado):
    """Garante a tela inicial e o modo de edição de recorrência."""
    _definir(estado, "tela_atual", "menu")
    _definir(estado, "alterar_recorrencia", False)
    if estado["tela_atual"] != "gerenciar_recorrencias":
        encerrar_edicao_recorrencia(estado)


def encerrar_edicao_recorrencia(estado):
    """Fecha o editor, sem alterar a selecao nem os dados financeiros."""
    estado["alterar_recorrencia"] = False
    estado.pop("_recorrencia_em_edicao", None)
    prefixos = (
        "novo_valor_recorrencia_", "nova_descricao_recorrencia_",
        "nova_categoria_recorrencia_", "nova_classificacao_recorrencia_",
        "nova_frequencia_recorrencia_", "novo_dia_semana_recorrencia_",
        "novo_dia_recorrencia_", "novo_dia_anual_recorrencia_", "novo_mes_anual_recorrencia_",
    )
    for chave in list(estado):
        if chave.startswith(prefixos):
            estado.pop(chave, None)


_CHAVES_SENSIVEIS = (
    "declaracao_maioridade",
    "novo_usuario_pendente",
    "codigo_cadastro_enviado",
    "aviso_codigo_cadastro",
    "reenvio_cadastro",
    "reenvio_recuperacao",
    "aviso_recuperacao",
    "aviso_conta_existente",
    "senha",
    "nova_senha",
    "confirmar_senha",
    "nova_senha_recuperacao",
    "confirmar_nova_senha_recuperacao",
    "codigo_digitado_cadastro",
    "codigo_digitado_recuperacao",
    "seguranca_senha_atual",
    "seguranca_nova_senha",
    "seguranca_confirmar_senha",
    "senha_email_seguranca",
    "codigo_digitado_email",
    "reenvio_email",
    "aviso_email",
    "senha_exclusao",
    "senha_exportacao",
    "_limpar_senha_exportacao",
    "exportacao_conta_json",
    "exportacao_conta_aviso",
    "usuario_original",
    "pdf_texto_sessao",
    "arquivo_pdf",
    "novo_nome",
    "novo_cpf",
    "novo_cnpj",
    "novo_nome_empresa",
    "novo_email",
    "renda_mensal",
    "faturamento_mensal",
    "email_entrada",
    "email_recuperacao",
    "novo_email_seguranca",
    "confirmar_email_seguranca",
    "politica_origem",
    "politica_campos",
    "editando_movimentacao",
    "historico_movimentacao_selecionada",
    "historico_cliente",
    "historico_cliente_id",
    "historico_cliente_sucesso",
    "historico_cliente_aviso",
    "movimentacao_excluida_aviso",
    "movimentacao_alterada_aviso",
    "movimentacao_excluida_sucesso",
    "movimentacao_alterada_sucesso",
    "editar_data",
    "editar_categoria",
    "editar_valor",
    "editar_descricao",
    "editar_classificacao",
    "planejamento_exclusao_pendente",
    "planejamento_excluido_sucesso",
    "planejamento_exclusao_aviso",
    "planejamento_mensal_selecionado",
    "planejamento_mensal_descricao",
    "planejamento_mensal_cliente",
    "planejamento_mensal_campos_id",
    "planejamento_texto_sucesso",
    "planejamento_texto_aviso",
)


def _remover(estado, chave):
    """Apaga a chave. Não atribui valor: o Streamlit recusa alteração depois do widget."""
    estado.pop(chave, None)


def descartar_exportacao(estado):
    """Remove o JSON e o aviso. Não altera o usuário da sessão."""
    _remover(estado, "exportacao_conta_json")
    _remover(estado, "exportacao_conta_aviso")


def guardar_exportacao(estado, id_usuario, arquivo):
    """Guarda só o identificador de quem autorizou e os bytes do arquivo."""
    estado["exportacao_conta_json"] = {
        "id_usuario": str(id_usuario),
        "arquivo": arquivo,
    }


def arquivo_autorizado(estado, id_usuario):
    """Devolve os bytes se o proprietário é a sessão atual. Divergência apaga o arquivo."""
    guardado = estado.get("exportacao_conta_json")
    if not isinstance(guardado, dict):
        if guardado is not None:
            descartar_exportacao(estado)
        return None
    arquivo = guardado.get("arquivo")
    if guardado.get("id_usuario") != str(id_usuario) or not isinstance(arquivo, bytes) or not arquivo:
        descartar_exportacao(estado)
        return None
    return arquivo


def limpar_pdf_da_conta(estado, id_usuario):
    """Remove o texto e o arquivo de PDF só quando pertencem à conta informada."""
    guardado = estado.get("pdf_texto_sessao")
    if not isinstance(guardado, dict):
        return
    if str(guardado.get("usuario")) != str(id_usuario):
        return
    _remover(estado, "pdf_texto_sessao")
    _remover(estado, "arquivo_pdf")


def encerrar_sessao_local(estado):
    """Encerra a aba e apaga credenciais, códigos e dados da conta."""
    for chave in list(estado.keys()):
        if chave.startswith("verificacao_") or chave.startswith("autorizacao_"):
            _remover(estado, chave)
    for chave in _CHAVES_SENSIVEIS:
        _remover(estado, chave)
    estado["usuario_logado"] = False
    estado["usuario_atual"] = None
    estado["menu_conta_aberto"] = False
    estado["menu_alertas_aberto"] = False
    estado["recuperar_senha"] = False
    estado["criar_conta"] = False
    estado["entrar"] = False
    estado["tela_atual"] = "menu"
