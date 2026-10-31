-- Executar no banco utilizado pelo Trixter, antes de habilitar o campo na tela.
-- NULL significa "Não classificado"; nenhum lançamento antigo é reclassificado.
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.gastos', N'classificacao') IS NULL
    BEGIN
        ALTER TABLE dbo.gastos
            ADD classificacao nvarchar(8) NULL;
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.gastos')
          AND name = N'CK_gastos_classificacao'
    )
    BEGIN
        -- SQL dinâmico permite validar a coluna adicionada neste mesmo lote.
        EXEC sp_executesql N'
            ALTER TABLE dbo.gastos WITH CHECK
            ADD CONSTRAINT CK_gastos_classificacao
            CHECK (classificacao IS NULL OR classificacao IN (N''Fixo'', N''Variável''));
        ';
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
