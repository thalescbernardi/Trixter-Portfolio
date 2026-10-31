-- Executar no banco utilizado pelo Trixter, antes de habilitar o campo na tela.
-- NULL significa "Não classificado"; as receitas antigas permanecem assim.
-- Os valores internos seguem o mesmo padrão da classificação de gastos.
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.receitas', N'classificacao') IS NULL
    BEGIN
        ALTER TABLE dbo.receitas
            ADD classificacao nvarchar(8) NULL;
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.receitas')
          AND name = N'CK_receitas_classificacao'
    )
    BEGIN
        -- Compila a restrição depois de criar a coluna neste mesmo lote.
        EXEC sp_executesql N'
            ALTER TABLE dbo.receitas WITH CHECK
            ADD CONSTRAINT CK_receitas_classificacao
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
