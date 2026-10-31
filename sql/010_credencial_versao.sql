-- Executar no banco do Trixter antes de publicar o código que confere a sessão.
-- Contas já existentes recebem a versão 1. Troca e recuperação de senha incrementam o valor.
-- Rodar de novo não altera uma coluna que já existe.
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.usuarios', N'credencial_versao') IS NULL
    BEGIN
        ALTER TABLE dbo.usuarios
            ADD credencial_versao int NOT NULL
                CONSTRAINT DF_usuarios_credencial_versao DEFAULT 1;
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
