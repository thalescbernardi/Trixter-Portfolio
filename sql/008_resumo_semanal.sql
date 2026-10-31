-- Executar no banco do Trixter antes da próxima rodada do executor de e-mails.
-- 0 significa que o resumo semanal não será enviado. O padrão das contas já existentes é 0.
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.usuarios', N'receber_resumo_semanal') IS NULL
    BEGIN
        ALTER TABLE dbo.usuarios
            ADD receber_resumo_semanal bit NOT NULL
                CONSTRAINT DF_usuarios_receber_resumo_semanal DEFAULT 0;
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
