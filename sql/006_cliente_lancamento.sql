-- Executar no banco do Trixter antes de informar cliente na receita.
-- NULL significa lançamento sem cliente. Não cria cadastro de tomador.
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.receitas', N'cliente') IS NULL
    BEGIN
        ALTER TABLE dbo.receitas
            ADD cliente nvarchar(80) NULL;
    END;

    IF COL_LENGTH(N'dbo.planejamentos', N'cliente') IS NULL
    BEGIN
        ALTER TABLE dbo.planejamentos
            ADD cliente nvarchar(80) NULL;
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
