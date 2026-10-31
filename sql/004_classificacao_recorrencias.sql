-- Executar no banco do Trixter antes de habilitar a classificação na tela.
-- NULL mantém as recorrências antigas sem classificação.
-- Não modifica receitas ou gastos já gerados.
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.recorrencias', N'classificacao') IS NULL
    BEGIN
        ALTER TABLE dbo.recorrencias
            ADD classificacao nvarchar(8) NULL;
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.recorrencias')
          AND name = N'CK_recorrencias_classificacao'
    )
    BEGIN
        -- Compila a restrição após a criação da coluna neste mesmo lote.
        EXEC sp_executesql N'
            ALTER TABLE dbo.recorrencias WITH CHECK
            ADD CONSTRAINT CK_recorrencias_classificacao
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
