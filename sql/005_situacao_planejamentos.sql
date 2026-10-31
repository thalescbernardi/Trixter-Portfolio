-- Executar no banco do Trixter antes de usar contas a receber e a pagar.
-- NULL significa compromisso em aberto. A tela deriva Previsto ou Atrasado pela data.
-- Recebido e Pago são gravados quando o usuário baixa o compromisso.
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.planejamentos', N'situacao') IS NULL
    BEGIN
        ALTER TABLE dbo.planejamentos
            ADD situacao nvarchar(12) NULL;
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.planejamentos')
          AND name = N'CK_planejamentos_situacao'
    )
    BEGIN
        EXEC sp_executesql N'
            ALTER TABLE dbo.planejamentos WITH CHECK
            ADD CONSTRAINT CK_planejamentos_situacao
            CHECK (situacao IS NULL OR situacao IN (N''Recebido'', N''Pago''));
        ';
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
