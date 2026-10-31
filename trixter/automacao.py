"""Execução de relatórios mensais, alertas diários e resumo semanal, independente do Streamlit."""
from contextlib import closing
from datetime import date
import logging

from .alertas import coletar_alertas, texto_para_email
from .infra import enviar_email, operacao_sql
from .relatorios import calcular_relatorio_mensal, gerar_pdf_relatorio, mes_anterior
from .resumo_semanal import consultar_resumo_semanal, semana_devida, texto_resumo

log = logging.getLogger(__name__)


def periodo_devido(usuario, hoje):
    """Envia o mês anterior a partir do dia escolhido, inclusive após dias perdidos."""
    if not usuario.get("receber_relatorio_mensal") or usuario.get("conta_demo"):
        return None
    dia = usuario.get("dia_relatorio_mensal")
    if dia is None or not 1 <= int(dia) <= 28 or hoje.day < int(dia):
        return None
    return date(*mes_anterior(hoje.year, hoje.month), 1)


def buscar_usuarios(conexao):
    with operacao_sql("buscar_usuarios"):
        return _buscar_usuarios(conexao)


def _buscar_usuarios(conexao):
    with closing(conexao.cursor()) as cursor:
        cursor.execute("""
            SELECT id_usuario, email, tipo_pessoa, receber_relatorio_mensal,
                   dia_relatorio_mensal, conta_demo, receber_alertas, receber_resumo_semanal
            FROM dbo.usuarios
            WHERE (receber_relatorio_mensal=1 OR receber_alertas=1 OR receber_resumo_semanal=1)
              AND ISNULL(conta_demo,0)=0
        """)
        colunas = [coluna[0] for coluna in cursor.description]
        return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def preparar_relatorio(conexao, usuario, periodo):
    with closing(conexao.cursor()) as cursor:
        dados = calcular_relatorio_mensal(cursor, usuario["id_usuario"], periodo.year, periodo.month)
    dados["termo_gasto"] = "Despesa" if usuario["tipo_pessoa"] == "Pessoa Jurídica" else "Gasto"
    pdf = gerar_pdf_relatorio(**dados)
    competencia = f"{dados['mes_selecionado']}/{periodo.year}"
    return {
        "destinatario": usuario["email"].strip(),
        "assunto": f"Relatório mensal - {competencia}",
        "corpo": ("Olá!\n\nSegue em anexo o seu relatório mensal referente a "
                  f"{competencia}.\n\nAtenciosamente,\nTrixter"),
        "anexo": {"conteudo": pdf.getvalue(),
                  "nome": f"relatorio_{periodo.year}_{periodo.month:02d}.pdf"},
    }


def preparar_alertas(conexao, usuario, periodo):
    with closing(conexao.cursor()) as cursor:
        alertas = coletar_alertas(cursor, usuario["id_usuario"], periodo)
    if not alertas:
        return None
    return {
        "destinatario": usuario["email"].strip(),
        "assunto": "Seus alertas financeiros - Trixter",
        "corpo": ("Olá!\n\nEstes são os seus alertas financeiros atuais:\n\n"
                  + "\n".join(f"- {texto_para_email(alerta)}" for alerta in alertas)
                  + "\n\nAtenciosamente,\nTrixter"),
    }


_COLUNAS_PREFERENCIA = (
    "receber_relatorio_mensal",
    "dia_relatorio_mensal",
    "conta_demo",
    "receber_alertas",
    "receber_resumo_semanal",
)


def ler_preferencia_atual(conexao, id_usuario):
    """Relê dbo.usuarios. None se a conta não existe. Não reutiliza o lote inicial."""
    with closing(conexao.cursor()) as cursor:
        cursor.execute(
            """
            SELECT receber_relatorio_mensal,
                   dia_relatorio_mensal,
                   conta_demo,
                   receber_alertas,
                   receber_resumo_semanal
            FROM dbo.usuarios
            WHERE id_usuario = ?
            """,
            id_usuario,
        )
        linha = cursor.fetchone()
    if linha is None:
        return None
    return dict(zip(_COLUNAS_PREFERENCIA, linha))


def preferencia_autoriza_envio(atual, tipo, hoje, periodo):
    """False para 0, NULL, conta ausente, demonstração ou período inelegível."""
    if not atual or atual.get("conta_demo"):
        return False
    if tipo == "relatorio_mensal":
        return periodo_devido(atual, hoje) == periodo
    if tipo == "alertas_diarios":
        return bool(atual.get("receber_alertas")) and periodo == hoje
    if tipo == "resumo_semanal":
        return semana_devida(atual, hoje) == periodo
    return False


def preparar_resumo(conexao, usuario, hoje):
    with closing(conexao.cursor()) as cursor:
        dados = consultar_resumo_semanal(cursor, usuario["id_usuario"], hoje)
    return {
        "destinatario": usuario["email"].strip(),
        "assunto": f"Resumo semanal - {dados['semana']:%d/%m/%Y}",
        "corpo": texto_resumo(dados),
    }


def trabalhos_devidos(usuarios, hoje, preparar, preparar_diarios, preparar_semanal=None):
    for usuario in usuarios:
        trabalhos = []
        periodo = periodo_devido(usuario, hoje)
        if periodo is not None:
            trabalhos.append(("relatorio_mensal", periodo, preparar))
        if usuario.get("receber_alertas") and not usuario.get("conta_demo"):
            trabalhos.append(("alertas_diarios", hoje, preparar_diarios))
        semana = semana_devida(usuario, hoje)
        if semana is not None:
            preparador = preparar_semanal or (
                lambda conexao, usuario, periodo, hoje=hoje: preparar_resumo(conexao, usuario, hoje)
            )
            trabalhos.append(("resumo_semanal", semana, preparador))
        # Um usuário sem envio elegível conta uma vez como ignorado.
        for tipo, periodo, preparador in trabalhos or [(None, None, None)]:
            yield usuario, tipo, periodo, preparador


def executar(conexao, historico, config, hoje, simular=True,
             preparar=preparar_relatorio, enviar=enviar_email,
             preparar_diarios=preparar_alertas, preparar_semanal=None):
    """Retorna contagens. Falha no histórico interrompe o lote, nunca libera reenvio."""
    resumo = dict(enviados=0, simulados=0, ignorados=0, falhas=0, incertos=0, sem_alertas=0)
    max_tentativas = int(config.get("automacao", {}).get("max_tentativas", 3))
    if max_tentativas < 1:
        raise ValueError("max_tentativas deve ser pelo menos 1.")
    tem_historico = historico.existe()
    if not simular and not tem_historico:
        raise ValueError("Histórico ausente. Execute --inicializar-historico primeiro.")
    if not tem_historico:
        log.warning("Simulação sem histórico: ainda não é possível verificar envios anteriores.")
    if not simular:
        historico.recuperar_interrompidos()
    trabalhos = trabalhos_devidos(
        buscar_usuarios(conexao), hoje, preparar, preparar_diarios, preparar_semanal
    )
    for usuario, tipo, periodo, preparador in trabalhos:
        if periodo is None:
            resumo["ignorados"] += 1
            continue
        uid = usuario["id_usuario"]
        email = (usuario.get("email") or "").strip()
        if "@" not in email or any(c in email for c in "\r\n"):
            log.error("Usuário %s: destinatário ausente ou inválido.", uid)
            resumo["falhas"] += 1
            continue
        registro = historico.consultar(uid, periodo, tipo=tipo) if tem_historico else None
        if registro and (registro[0] != "falha" or registro[1] >= max_tentativas):
            log.info("Usuário %s, tipo %s, período %s: ignorado (%s).", uid, tipo, periodo, registro[0])
            resumo["ignorados"] += 1
            if registro[0] == "incerto":
                resumo["incertos"] += 1
            elif registro[0] == "falha":
                resumo["falhas"] += 1
            continue
        # Gera antes de reservar: ausência de alertas não consome a cota do dia.
        # O bloqueio exclusivo do executor continua cobrindo todo este fluxo.
        try:
            mensagem = preparador(conexao, usuario, periodo)
        except Exception as erro:
            detalhe = f"Falha antes do SMTP ({type(erro).__name__})."
            if not simular:
                reserva = historico.reservar(uid, periodo, email, max_tentativas, tipo=tipo)
                if reserva is not None:
                    historico.atualizar(uid, periodo, "falha", detalhe, tipo=tipo)
            log.error("Usuário %s, tipo %s: %s", uid, tipo, detalhe)
            resumo["falhas"] += 1
            continue
        if mensagem is None:
            log.info("Usuário %s, tipo %s: sem alertas; nenhum envio reservado.", uid, tipo)
            resumo["sem_alertas"] += 1
            continue
        if simular:
            log.info("SIMULAÇÃO usuário %s, tipo %s, período %s: mensagem preparada; nenhum envio.",
                     uid, tipo, periodo)
            resumo["simulados"] += 1
            continue
        # A releitura reduz a janela, mas não a fecha: o SMTP ainda ocorre depois.
        try:
            atual = ler_preferencia_atual(conexao, uid)
            autorizado = preferencia_autoriza_envio(atual, tipo, hoje, periodo)
        except Exception as erro:
            log.error(
                "Usuário %s, tipo %s: preferência não confirmada (%s).",
                uid, tipo, type(erro).__name__,
            )
            resumo["falhas"] += 1
            continue
        if not autorizado:
            log.info(
                "Usuário %s, tipo %s, período %s: preferência atual não autoriza o envio.",
                uid, tipo, periodo,
            )
            resumo["ignorados"] += 1
            continue
        message_id = historico.reservar(uid, periodo, email, max_tentativas, tipo=tipo)
        if message_id is None:
            resumo["ignorados"] += 1
            continue
        # Commit antes de chamar SMTP: crash/timeout não autoriza novo envio.
        historico.atualizar(uid, periodo, "enviando", tipo=tipo)
        try:
            enviar(config, **mensagem, message_id=message_id)
        except Exception as erro:
            detalhe = f"Resultado SMTP não confirmado ({type(erro).__name__}); conferir no Brevo."
            historico.atualizar(uid, periodo, "incerto", detalhe, tipo=tipo)
            log.error("Usuário %s: %s", uid, detalhe)
            resumo["incertos"] += 1
            continue
        historico.atualizar(uid, periodo, "enviado", tipo=tipo)
        log.info("Usuário %s, tipo %s, período %s: aceito pelo servidor SMTP.", uid, tipo, periodo)
        resumo["enviados"] += 1
    return resumo
