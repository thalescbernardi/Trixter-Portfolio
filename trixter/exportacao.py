"""Exportação da conta autenticada. Não grava arquivo e não inclui credencial."""
from datetime import date, datetime, timezone
from decimal import Decimal
import json

from .credencial import SessaoIndisponivel, preparar_operacao
from .senha import senha_confere

_PROIBIDOS = {"senha", "message_id", "ultimo_erro", "token", "credencial_versao"}

CONTA = (
    "id_usuario",
    "tipo_pessoa",
    "data_entrada",
    "ultimo_acesso",
    "email",
    "nome",
    "cpf",
    "renda_mensal",
    "nome_empresa",
    "cnpj",
    "faturamento_mensal",
    "objetivo_financeiro",
    "valor_objetivo",
    "data_objetivo",
    "valor_acumulado_meta",
    "onboarding_concluido",
    "conta_demo",
    "aliquota_imposto",
    "dia_vencimento_imposto",
    "receber_relatorio_mensal",
    "dia_relatorio_mensal",
    "receber_alertas",
    "receber_resumo_semanal",
)
CATEGORIAS = ("id_usuario", "nome", "tipo")
RECEITAS = (
    "id_transacao",
    "id_usuario",
    "id_recorrencia",
    "data",
    "categoria",
    "descricao",
    "valor",
    "classificacao",
    "cliente",
)
GASTOS = (
    "id_transacao",
    "id_usuario",
    "id_recorrencia",
    "data",
    "categoria",
    "descricao",
    "valor",
    "classificacao",
)
ORCAMENTOS = ("id_orcamento", "id_usuario", "categoria", "mes", "ano", "valor_limite")
RECORRENCIAS = (
    "id_recorrencia",
    "id_usuario",
    "tipo",
    "categoria",
    "descricao",
    "valor",
    "frequencia",
    "proxima_execucao",
    "ativa",
    "dia_semana",
    "dia",
    "mes",
    "classificacao",
)
PLANEJAMENTOS = (
    "id_planejamento",
    "id_usuario",
    "tipo",
    "categoria",
    "descricao",
    "valor",
    "data",
    "cliente",
    "situacao",
)
ENVIOS = ("tipo", "periodo", "status", "tentativas", "criado_em", "enviado_em")

_ORDEM = {
    "dbo.categorias": "nome, tipo",
    "dbo.receitas": "id_transacao",
    "dbo.gastos": "id_transacao",
    "dbo.orcamentos": "id_orcamento",
    "dbo.recorrencias": "id_recorrencia",
    "dbo.planejamentos": "id_planejamento",
    "dbo.envios_automaticos": "criado_em, tipo, periodo",
}

_TABELAS = (
    ("categorias", "dbo.categorias", CATEGORIAS),
    ("receitas", "dbo.receitas", RECEITAS),
    ("gastos", "dbo.gastos", GASTOS),
    ("orcamentos", "dbo.orcamentos", ORCAMENTOS),
    ("recorrencias", "dbo.recorrencias", RECORRENCIAS),
    ("planejamentos", "dbo.planejamentos", PLANEJAMENTOS),
    ("envios_automaticos", "dbo.envios_automaticos", ENVIOS),
)


class ExportacaoIndisponivel(Exception):
    """A consulta falhou. Nenhum arquivo deve ser entregue."""


def sessao_autorizada(conectar_banco, estado):
    """A exportação só segue com a sessão ainda válida."""
    try:
        return preparar_operacao(conectar_banco, estado) == "ok"
    except SessaoIndisponivel:
        return False


def autorizar_exportacao(cursor, id_usuario, senha, sessao_demo):
    """'ok' libera. Conta real depende da senha. Demonstração depende do banco e da sessão."""
    cursor.execute(
        """
        SELECT senha, conta_demo
        FROM dbo.usuarios
        WHERE id_usuario = ?
        """,
        id_usuario,
    )
    linha = cursor.fetchone()
    if linha is None:
        return "ausente"
    armazenada, conta_demo = linha
    if bool(conta_demo) and sessao_demo:
        return "ok"
    if bool(conta_demo):
        return "recusada"
    if senha_confere(senha or "", armazenada):
        return "ok"
    return "senha"


def exportar_conta(cursor, id_usuario, agora=None):
    """Lê só a conta informada. Qualquer falha descarta o resultado inteiro."""
    try:
        conta = _uma(cursor, "dbo.usuarios", CONTA, id_usuario)
        if conta is None:
            raise ExportacaoIndisponivel("consulta indisponivel")
        documento = {"gerado_em": _iso_utc(agora), "conta": conta}
        for nome, tabela, colunas in _TABELAS:
            documento[nome] = _varias(cursor, tabela, colunas, id_usuario)
        _vetar(documento)
        return documento
    except ExportacaoIndisponivel:
        raise
    except Exception as erro:
        raise ExportacaoIndisponivel("consulta indisponivel") from erro


def concluir_exportacao(cursor, id_usuario, senha, sessao_demo, sessao_ok):
    """Devolve a situação e o JSON, ou None quando o arquivo não pode sair."""
    if not sessao_ok:
        return "sessao", None
    situacao = autorizar_exportacao(cursor, id_usuario, senha, sessao_demo)
    if situacao != "ok":
        return situacao, None
    try:
        return "ok", serializar(exportar_conta(cursor, id_usuario))
    except ExportacaoIndisponivel:
        return "falha", None


def serializar(documento):
    """JSON UTF-8. Data e Decimal já foram convertidos; tipo inesperado interrompe."""
    _vetar(documento)
    try:
        texto = json.dumps(documento, ensure_ascii=False, indent=2, default=_recusar)
    except ExportacaoIndisponivel:
        raise
    except Exception as erro:
        raise ExportacaoIndisponivel("consulta indisponivel") from erro
    return texto.encode("utf-8")


def _uma(cursor, tabela, colunas, id_usuario):
    cursor.execute(_consulta(tabela, colunas), id_usuario)
    linha = cursor.fetchone()
    if linha is None:
        return None
    return _linha(colunas, linha)


def _varias(cursor, tabela, colunas, id_usuario):
    cursor.execute(_consulta(tabela, colunas), id_usuario)
    return [_linha(colunas, linha) for linha in cursor.fetchall()]


def _consulta(tabela, colunas):
    lista = ", ".join(colunas)
    sql = f"SELECT {lista} FROM {tabela} WHERE id_usuario = ?"
    ordem = _ORDEM.get(tabela)
    if ordem:
        sql += f" ORDER BY {ordem}"
    return sql


def _linha(colunas, linha):
    return {coluna: _valor(valor) for coluna, valor in zip(colunas, linha)}


def _iso_utc(agora):
    momento = datetime.now(timezone.utc) if agora is None else agora()
    if getattr(momento, "tzinfo", None) is None or momento.utcoffset() is None:
        raise ExportacaoIndisponivel("consulta indisponivel")
    return momento.astimezone(timezone.utc).isoformat()


def _valor(valor):
    if isinstance(valor, bytes):
        raise ExportacaoIndisponivel("consulta indisponivel")
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, Decimal):
        return format(valor, "f")
    if isinstance(valor, datetime):
        return valor.isoformat(sep="T")
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


def _vetar(documento):
    def andar(no):
        if isinstance(no, dict):
            for chave, valor in no.items():
                if _proibido(chave):
                    raise ExportacaoIndisponivel("consulta indisponivel")
                andar(valor)
        elif isinstance(no, list):
            for item in no:
                andar(item)

    andar(documento)


def _proibido(chave):
    texto = str(chave).casefold()
    return texto in _PROIBIDOS or "senha" in texto


def _recusar(_valor):
    raise ExportacaoIndisponivel("consulta indisponivel")
