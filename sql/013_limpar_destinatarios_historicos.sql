-- Limpeza administrativa separada: aplicar SOMENTE apos 012 e atualizacao
-- validada do executor. Manter executores suspensos durante a limpeza.
-- O executor antigo voltaria a persistir enderecos.
-- Executar sem transacao externa: cada lote confirma separadamente.
-- Nao modifica estados, datas, tentativas ou identificadores. Idempotente.
SET XACT_ABORT ON;

IF @@TRANCOUNT <> 0
    THROW 50002, 'Executar a limpeza sem transacao externa.', 1;
SET IMPLICIT_TRANSACTIONS OFF;

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.envios_automaticos', N'U')
      AND name = N'destinatario' AND is_nullable = 1
      AND system_type_id = TYPE_ID(N'nvarchar')
      AND user_type_id = TYPE_ID(N'nvarchar') AND max_length = 640
)
    THROW 50003, 'Aplicar e validar a migracao de destinatario antes da limpeza.', 1;

DECLARE @afetados int = 1;
WHILE @afetados > 0
BEGIN
    BEGIN TRANSACTION;
    UPDATE TOP (500) dbo.envios_automaticos
       SET destinatario = NULL
     WHERE destinatario IS NOT NULL;
    SET @afetados = @@ROWCOUNT;
    COMMIT TRANSACTION;
END;
