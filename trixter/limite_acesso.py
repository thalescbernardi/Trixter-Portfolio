"""Contadores de login, envio e código no SQL Server.

A sessão continua valendo o código. Estes contadores sobrevivem a outra aba
e a outro navegador. A decisão de permitir a operação e o consumo da cota
acontecem na mesma transação. Quem chama confirma ou desfaz antes de
bcrypt ou SMTP.

A leitura com UPDLOCK e HOLDLOCK não serializa uma chave que ainda não
existe: as duas sessões recebem RangeS-U, as travas são compatíveis e o
INSERT seguinte entra em deadlock. Por isso a tentativa trava cada chave
com sp_getapplock, em ordem alfabética, antes de tocar na tabela.
"""
import hashlib
import logging
from datetime import datetime, timedelta


log = logging.getLogger(__name__)

MENSAGEM_LOGIN = "E-mail ou senha incorretos."
MENSAGEM_RECUPERACAO = "Se o e-mail estiver cadastrado, você receberá um código de recuperação."

# A limpeza agendada repete o lote já usado no login. Não esvazia a tabela
# numa execução: ao encher 32 lotes, registros expirados podem permanecer.
_LOTE_LIMPEZA = 32
_MAX_LOTES_LIMPEZA = 32
_RETENCAO_LIMPEZA = timedelta(hours=24)

# Quanto a sessão espera a trava da chave, em milissegundos. Não é a cota.
_ESPERA_TRAVA_MS = 5000

# limite de eventos e duração da janela, em minutos.
_POLITICA = {
    "login": {"par": (8, 15), "ip": (30, 15)},
    "recuperacao_envio": {"par": (3, 30), "ip": (10, 30), "email": (5, 60)},
    "cadastro_envio": {"par": (3, 30), "ip": (10, 30), "email": (5, 60)},
    "recuperacao_codigo": {"par": (5, 15), "ip": (20, 15)},
    "cadastro_codigo": {"par": (5, 15), "ip": (20, 15)},
    "alteracao_email_envio": {"par": (3, 30), "ip": (10, 30), "email": (5, 60)},
    "alteracao_email_codigo": {"par": (5, 15), "ip": (20, 15)},
}


def normalizar_ip(ip):
    texto = (ip or "").strip()
    if not texto:
        return "local"
    return texto[:45]


def objeto_ausente(erro):
    texto = " ".join(str(parte) for parte in getattr(erro, "args", ()))
    texto = f"{texto} {erro}"
    return "limites_acesso" in texto and (
        "208" in texto
        or "42S02" in texto
        or "Invalid object name" in texto
        or "Nome de objeto" in texto
    )


class ErroLimite(Exception):
    """O limite não pôde ser decidido. A operação não fica autorizada."""


def _concorrencia(erro):
    texto = " ".join(str(parte) for parte in getattr(erro, "args", ()))
    texto = f"{texto} {erro}".lower()
    return any(marca in texto for marca in (
        "1205", "1222", "2627", "2601",
        "deadlock", "lock request time out",
        "duplicate key", "chave duplicada",
    ))


def bloqueado(cursor, fluxo, email, ip, agora=None):
    try:
        return _bloqueado(cursor, fluxo, email, ip, agora or datetime.now())
    except Exception as erro:
        if objeto_ausente(erro):
            _desfazer(cursor)
            return False
        raise


def consumir(cursor, fluxo, email, ip, agora=None):
    """Gasta uma unidade do par, do IP e, no envio, do e-mail."""
    agora = agora or datetime.now()
    try:
        _preparar(cursor, fluxo, email, ip, agora)
        _consumir(cursor, fluxo, email, ip, agora)
    except ErroLimite:
        _desfazer(cursor)
        raise
    except Exception as erro:
        _desfazer(cursor)
        if objeto_ausente(erro):
            return
        raise


def liberar_par(cursor, fluxo, email, ip):
    """Zera só o par e-mail+IP. O contador do IP permanece."""
    try:
        _travar_recursos(cursor, [_recurso(fluxo, _montar_chave("par", email, ip))])
        cursor.execute(
            """
            DELETE FROM dbo.limites_acesso
            WHERE fluxo = ? AND chave = ?
            """,
            fluxo,
            _montar_chave("par", email, ip),
        )
    except ErroLimite:
        _desfazer(cursor)
        raise
    except Exception as erro:
        _desfazer(cursor)
        if objeto_ausente(erro):
            return
        raise


def _bloqueado(cursor, fluxo, email, ip, agora):
    for chave, limite, minutos in _chaves(fluxo, email, ip):
        vigente = _vigente(_ler(cursor, fluxo, chave), agora, minutos)
        if not vigente:
            continue
        tentativas, _inicio, ate = vigente
        if (ate is not None and ate > agora) or tentativas >= limite:
            return True
    return False


def reservar(cursor, fluxo, email, ip, agora=None, registrar=True):
    """Trava a cota e, se registrar for verdadeiro, grava a tentativa.

    Devolve True quando a operação pode seguir. Não confirma a transação.
    Qualquer falha desfaz o que esta chamada gravou e não autoriza.
    """
    agora = agora or datetime.now()
    try:
        _preparar(cursor, fluxo, email, ip, agora)
        if _bloqueado(cursor, fluxo, email, ip, agora):
            return False
        if registrar:
            _consumir(cursor, fluxo, email, ip, agora)
        return True
    except ErroLimite:
        _desfazer(cursor)
        raise
    except Exception as erro:
        _desfazer(cursor)
        raise ErroLimite("limite indisponivel") from erro


def confirmar_reserva(conexao, cursor, fluxo, email, ip, registrar=True, agora=None):
    """Reserva e confirma, ou desfaz, antes de trabalho lento."""
    try:
        permitido = reservar(
            cursor, fluxo, email, ip, agora=agora, registrar=registrar,
        )
    except ErroLimite:
        _desfazer(cursor)
        raise
    if permitido:
        conexao.commit()
    else:
        conexao.rollback()
    return permitido


def _recurso(fluxo, chave):
    return f"trixter.limite|{fluxo}|{chave}"


def _preparar(cursor, fluxo, email, ip, agora):
    """Trava as chaves e só então limpa registro antigo.

    A limpeza fica depois da trava para não segurar uma linha enquanto
    espera outra sessão. Se a limpeza entrar em deadlock, a transação
    inteira já foi desfeita e as travas são pedidas de novo.
    """
    _travar_chaves(cursor, fluxo, email, ip)
    try:
        _limpar_antigos(cursor, agora)
    except Exception as erro:
        _desfazer(cursor)
        if objeto_ausente(erro) or not _concorrencia(erro):
            raise
        _travar_chaves(cursor, fluxo, email, ip)


def _travar_chaves(cursor, fluxo, email, ip):
    _travar_recursos(
        cursor,
        [_recurso(fluxo, chave) for chave, _limite, _minutos in _chaves(fluxo, email, ip)],
    )


def _travar_recursos(cursor, recursos):
    for recurso in sorted(set(recursos)):
        cursor.execute(
            """
            SET NOCOUNT ON;
            DECLARE @resultado int;
            EXEC @resultado = sp_getapplock
                @Resource = ?,
                @LockMode = 'Exclusive',
                @LockOwner = 'Transaction',
                @LockTimeout = ?;
            SELECT @resultado;
            SET NOCOUNT OFF;
            """,
            recurso,
            _ESPERA_TRAVA_MS,
        )
        linha = cursor.fetchone()
        proximo = getattr(cursor, "nextset", None)
        if proximo is not None:
            while proximo():
                pass
        codigo = int(linha[0]) if linha else -999
        if codigo < 0:
            _desfazer(cursor)
            raise ErroLimite("limite indisponivel") from RuntimeError(f"applock {codigo}")


def _resumo_email(email):
    return hashlib.sha256((email or "").strip().lower().encode("utf-8")).hexdigest()


def _curinga_par(resumo):
    """Prefixo do par deste hash, com % e _ escapados."""
    escapado = resumo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"par:{escapado}|%"


def _reiniciar(conexao):
    desfazer = getattr(conexao, "rollback", None)
    if desfazer is None:
        return
    desfazer()


def _tabela_limites(cursor):
    """False quando a tabela ainda não foi criada. Outro erro segue adiante."""
    try:
        cursor.execute("SELECT OBJECT_ID(N'dbo.limites_acesso', N'U')")
    except Exception as erro:
        if objeto_ausente(erro):
            return False
        raise
    linha = cursor.fetchone()
    return bool(linha and linha[0] is not None)


def limpar_expirados(conexao, agora=None):
    """Apaga janelas com mais de 24 horas, em transação própria.

    Cada lote tem no máximo 32 linhas e usa ROWLOCK, READPAST. A execução
    para no trigésimo segundo lote cheio: registros expirados podem
    permanecer, e a execução seguinte continua do que restar. Esta função
    não promete esvaziar a tabela de uma vez. Linha com bloqueado_ate no
    futuro permanece, mesmo que janela_inicio seja antigo. Tabela ausente
    não é erro.
    """
    agora = agora or datetime.now()
    corte = agora - _RETENCAO_LIMPEZA
    _reiniciar(conexao)
    cursor = conexao.cursor()
    apagadas = 0
    incompleta = False
    try:
        if not _tabela_limites(cursor):
            return {"apagadas": 0, "incompleta": False}
        for _lote in range(_MAX_LOTES_LIMPEZA):
            cursor.execute(
                f"""
                DELETE TOP ({_LOTE_LIMPEZA}) FROM dbo.limites_acesso WITH (ROWLOCK, READPAST)
                WHERE janela_inicio < ?
                  AND (bloqueado_ate IS NULL OR bloqueado_ate <= ?)
                """,
                corte,
                agora,
            )
            quantidade = cursor.rowcount
            conexao.commit()
            if quantidade is None or quantidade < 0:
                incompleta = True
                break
            apagadas += quantidade
            if quantidade < _LOTE_LIMPEZA:
                break
        else:
            incompleta = True
        if incompleta and apagadas >= _LOTE_LIMPEZA * _MAX_LOTES_LIMPEZA:
            log.info(
                "Limpeza de limites atingiu o teto de %s lotes; "
                "registros expirados podem permanecer. apagadas=%s",
                _MAX_LOTES_LIMPEZA,
                apagadas,
            )
        elif incompleta:
            log.info(
                "Limpeza de limites interrompida; "
                "registros expirados podem permanecer. apagadas=%s",
                apagadas,
            )
        else:
            log.info("Limpeza de limites: apagadas=%s", apagadas)
        return {"apagadas": apagadas, "incompleta": incompleta}
    except Exception as erro:
        _reiniciar(conexao)
        if objeto_ausente(erro):
            return {"apagadas": apagadas, "incompleta": False}
        raise
    finally:
        fechar = getattr(cursor, "close", None)
        if callable(fechar):
            fechar()


def apagar_chaves_do_email(cursor, email):
    """Remove as chaves deste e-mail. Não confirma a transação.

    Apaga email:{hash} e par:{hash}|ip. Conserva ip: e qualquer outro
    e-mail. O hash usa a mesma normalização das chaves de bloqueio.
    E-mail ausente ou em branco não apaga nada. Tabela ausente não é erro.
    """
    if email is None:
        return
    endereco = str(email).strip().lower()
    if not endereco:
        return
    if not _tabela_limites(cursor):
        return
    resumo = _resumo_email(endereco)
    cursor.execute(
        """
        DELETE FROM dbo.limites_acesso
        WHERE chave = ? OR chave LIKE ? ESCAPE '\\'
        """,
        f"email:{resumo}",
        _curinga_par(resumo),
    )


def _limpar_antigos(cursor, agora):
    """Apaga um lote antigo sem esperar linha travada por outra sessão."""
    cursor.execute(
        """
        DELETE TOP (32) FROM dbo.limites_acesso WITH (ROWLOCK, READPAST)
        WHERE janela_inicio < ?
        """,
        agora - timedelta(hours=24),
    )


def _consumir(cursor, fluxo, email, ip, agora):
    for chave, limite, minutos in _chaves(fluxo, email, ip):
        linha = _ler(cursor, fluxo, chave)
        vigente = _vigente(linha, agora, minutos)
        if vigente is None:
            tentativas, inicio, ate = 1, agora, None
        else:
            tentativas, inicio, ate = vigente
            tentativas += 1
        if tentativas >= limite:
            ate = inicio + timedelta(minutes=minutos)
        _gravar(cursor, fluxo, chave, tentativas, inicio, ate, existia=linha is not None)


def _exigir_uma_linha(cursor):
    if getattr(cursor, "rowcount", -1) != 1:
        raise RuntimeError("gravacao incompleta")


def _chaves(fluxo, email, ip):
    ip = normalizar_ip(ip)
    resumo = _resumo_email(email)
    nomes = {
        "par": f"par:{resumo}|{ip}",
        "ip": f"ip:{ip}",
        "email": f"email:{resumo}",
    }
    return [
        (nomes[nome], limite, minutos)
        for nome, (limite, minutos) in _POLITICA[fluxo].items()
    ]


def _montar_chave(nome, email, ip):
    return next(chave for chave, _limite, _minutos in _chaves("login", email, ip) if chave.startswith(nome + ":"))


def _vigente(linha, agora, minutos):
    if not linha:
        return None
    tentativas, inicio, ate = linha[0], linha[1], linha[2]
    if inicio is None or inicio <= agora - timedelta(minutes=minutos):
        return None
    return tentativas, inicio, ate


def _ler(cursor, fluxo, chave):
    cursor.execute(
        """
        SELECT tentativas, janela_inicio, bloqueado_ate
        FROM dbo.limites_acesso WITH (UPDLOCK, HOLDLOCK)
        WHERE fluxo = ? AND chave = ?
        """,
        fluxo,
        chave,
    )
    return cursor.fetchone()


def _gravar(cursor, fluxo, chave, tentativas, inicio, ate, existia):
    if existia:
        cursor.execute(
            """
            UPDATE dbo.limites_acesso
            SET tentativas = ?, janela_inicio = ?, bloqueado_ate = ?
            WHERE fluxo = ? AND chave = ?
            """,
            tentativas,
            inicio,
            ate,
            fluxo,
            chave,
        )
        _exigir_uma_linha(cursor)
        return
    cursor.execute(
        """
        INSERT INTO dbo.limites_acesso
            (fluxo, chave, tentativas, janela_inicio, bloqueado_ate)
        VALUES (?, ?, ?, ?, ?)
        """,
        fluxo,
        chave,
        tentativas,
        inicio,
        ate,
    )
    _exigir_uma_linha(cursor)


def _desfazer(cursor):
    conexao = getattr(cursor, "connection", None)
    desfazer = getattr(conexao, "rollback", None)
    if desfazer is None:
        return
    try:
        desfazer()
    except Exception:
        return
