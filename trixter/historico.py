"""Histórico SQL Server e exclusão mútua entre executores."""
from contextlib import contextmanager, closing
from email.utils import make_msgid
from datetime import timedelta, timezone
from pathlib import Path

from .infra import operacao_sql

TIPO = "relatorio_mensal"
TIPOS_RECUPERAVEIS = ("relatorio_mensal", "alertas_diarios", "resumo_semanal")
# Mantém o mesmo lock da etapa 1, agora compartilhado pelos tipos de envio.
RECURSO = "trixter:envios:relatorio_mensal:v1"


class Historico:
    def __init__(self, conexao):
        self.conexao = conexao
        self.bloqueado = False

    @contextmanager
    def exclusivo(self):
        with operacao_sql("bloqueio"):
            with closing(self.conexao.cursor()) as cursor:
                cursor.execute("""
                    SET NOCOUNT ON;
                    DECLARE @resultado int;
                    EXEC @resultado = sys.sp_getapplock
                        @Resource = ?, @LockMode = 'Exclusive',
                        @LockOwner = 'Session', @LockTimeout = 0;
                    SELECT @resultado;
                """, RECURSO)
                resultado = cursor.fetchone()[0]
            self.conexao.commit()
        if resultado < 0:
            raise RuntimeError("Outro executor está ativo ou não foi possível obter o bloqueio SQL.")
        self.bloqueado = True
        try:
            yield self
        finally:
            self.bloqueado = False
            with operacao_sql("liberar_bloqueio"):
                self.conexao.rollback()
                with closing(self.conexao.cursor()) as cursor:
                    cursor.execute("EXEC sys.sp_releaseapplock @Resource=?, @LockOwner='Session'", RECURSO)
                self.conexao.commit()

    def existe(self):
        with operacao_sql("historico.existe"):
            with closing(self.conexao.cursor()) as cursor:
                cursor.execute("SELECT OBJECT_ID(N'dbo.envios_automaticos', N'U')")
                return cursor.fetchone()[0] is not None

    def inicializar(self):
        self._exigir_bloqueio()
        arquivo = Path(__file__).resolve().parent.parent / "sql" / "001_envios_automaticos.sql"
        with operacao_sql("historico.inicializar"):
            with closing(self.conexao.cursor()) as cursor:
                cursor.execute(arquivo.read_text(encoding="utf-8"))
            self.conexao.commit()

    def recuperar_interrompidos(self):
        self._exigir_bloqueio()
        with operacao_sql("historico.recuperar"):
            with closing(self.conexao.cursor()) as cursor:
                cursor.execute(f"""
                    UPDATE dbo.envios_automaticos
                    SET status = CASE WHEN status='enviando' THEN 'incerto' ELSE 'falha' END,
                        ultimo_erro = CASE WHEN status='enviando'
                            THEN N'Execução interrompida durante SMTP; conferir no provedor antes de qualquer reenvio.'
                            ELSE N'Execução interrompida antes do SMTP; nova tentativa permitida.' END,
                        atualizado_em=SYSUTCDATETIME()
                    WHERE tipo IN ({", ".join("?" * len(TIPOS_RECUPERAVEIS))}) AND status IN ('preparando','enviando')
                """, *TIPOS_RECUPERAVEIS)
            self.conexao.commit()

    def expurgar(self, agora, tamanho_lote=500):
        """Retém 30 dias após atualização e fim da elegibilidade, sob o lock do executor.

        A referência inclui fuso: períodos usam o fuso do executor; atualizado_em, UTC.
        Tipos desconhecidos e estados ativos são preservados.
        """
        self._exigir_bloqueio()
        if agora.tzinfo is None or agora.utcoffset() is None:
            raise ValueError("A referência do expurgo deve incluir fuso horário.")
        if not isinstance(tamanho_lote, int) or tamanho_lote < 1:
            raise ValueError("O tamanho do lote deve ser positivo.")
        # Trinta dias completos; converte o mesmo instante para ambos os relógios.
        limite_utc = agora.astimezone(timezone.utc) - timedelta(days=30)
        limite_local = limite_utc.astimezone(agora.tzinfo).replace(tzinfo=None)
        limite_utc = limite_utc.replace(tzinfo=None)
        total = 0
        while True:
            with operacao_sql("historico.expurgar"):
                with closing(self.conexao.cursor()) as cursor:
                    cursor.execute("""
                        ;WITH candidatos AS (
                            SELECT TOP (?) * FROM dbo.envios_automaticos
                            WHERE status IN ('enviado', 'falha', 'incerto')
                              AND atualizado_em <= ?
                              AND CASE tipo
                                  WHEN 'relatorio_mensal' THEN DATEADD(day, 1, EOMONTH(periodo, 1))
                                  WHEN 'resumo_semanal' THEN DATEADD(day, 7, periodo)
                                  WHEN 'alertas_diarios' THEN DATEADD(day, 1, periodo)
                              END <= ?
                            ORDER BY id_envio
                        )
                        DELETE FROM candidatos OUTPUT DELETED.id_envio;
                    """, tamanho_lote, limite_utc, limite_local)
                    quantidade = len(cursor.fetchall())
                self.conexao.commit()
            total += quantidade
            if quantidade < tamanho_lote:
                return total

    def consultar(self, usuario, periodo, tipo=TIPO):
        with operacao_sql("historico.consultar"):
            return self._consultar(usuario, periodo, tipo)

    def _consultar(self, usuario, periodo, tipo):
        with closing(self.conexao.cursor()) as cursor:
            cursor.execute("""
                SELECT status, tentativas FROM dbo.envios_automaticos
                WHERE id_usuario=? AND tipo=? AND periodo=?
            """, str(usuario), tipo, periodo)
            row = cursor.fetchone()
        return (row[0], row[1]) if row else None

    def reservar(self, usuario, periodo, destinatario, max_tentativas=3, tipo=TIPO):
        self._exigir_bloqueio()
        registro = self.consultar(usuario, periodo, tipo=tipo)
        if registro and (registro[0] != "falha" or registro[1] >= max_tentativas):
            return None
        message_id = make_msgid(domain="trixter.local")
        with operacao_sql("historico.reservar"):
            self._gravar_reserva(registro, message_id, usuario, periodo, destinatario, tipo)
        self.conexao.commit()
        return message_id

    def _gravar_reserva(self, registro, message_id, usuario, periodo, destinatario, tipo):
        with closing(self.conexao.cursor()) as cursor:
            if registro:
                cursor.execute("""
                    UPDATE dbo.envios_automaticos SET status='preparando',
                        tentativas=tentativas+1, destinatario=NULL, message_id=?,
                        ultimo_erro=NULL, atualizado_em=SYSUTCDATETIME()
                    WHERE id_usuario=? AND tipo=? AND periodo=? AND status='falha'
                """, message_id, str(usuario), tipo, periodo)
            else:
                cursor.execute("""
                    INSERT INTO dbo.envios_automaticos
                        (id_usuario,tipo,periodo,destinatario,status,message_id)
                    VALUES (?,?,?,NULL,'preparando',?)
                """, str(usuario), tipo, periodo, message_id)

    def atualizar(self, usuario, periodo, status, erro=None, tipo=TIPO):
        self._exigir_bloqueio()
        if status not in {"enviando", "enviado", "falha", "incerto"}:
            raise ValueError("Estado de envio inválido.")
        with operacao_sql("historico.atualizar"):
            self._gravar_estado(usuario, periodo, status, erro, tipo)

    def _gravar_estado(self, usuario, periodo, status, erro, tipo):
        with closing(self.conexao.cursor()) as cursor:
            cursor.execute("""
                UPDATE dbo.envios_automaticos SET status=?, ultimo_erro=?,
                    atualizado_em=SYSUTCDATETIME(),
                    enviado_em=CASE WHEN ?='enviado' THEN SYSUTCDATETIME() ELSE enviado_em END
                OUTPUT INSERTED.id_envio
                WHERE id_usuario=? AND tipo=? AND periodo=?
            """, status, erro, status, str(usuario), tipo, periodo)
            if cursor.fetchone() is None:
                raise RuntimeError("Registro de envio não encontrado; execução interrompida.")
        self.conexao.commit()

    def _exigir_bloqueio(self):
        if not self.bloqueado:
            raise RuntimeError("É necessário obter o bloqueio exclusivo antes de alterar o histórico.")
