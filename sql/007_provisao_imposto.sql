-- Executar no banco do Trixter antes de salvar a provisão de imposto.
-- aliquota_imposto é o percentual escolhido pelo usuário (6 significa 6%).
-- dia_vencimento_imposto é o dia em que essa pessoa costuma pagar, de 1 a 28.
-- NULL significa que a conta ainda não foi configurada. Não apura DAS nem gera guia.
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.usuarios', N'aliquota_imposto') IS NULL
    BEGIN
        ALTER TABLE dbo.usuarios
            ADD aliquota_imposto decimal(5, 2) NULL;
    END;

    IF COL_LENGTH(N'dbo.usuarios', N'dia_vencimento_imposto') IS NULL
    BEGIN
        ALTER TABLE dbo.usuarios
            ADD dia_vencimento_imposto tinyint NULL;
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.usuarios')
          AND name = N'CK_usuarios_aliquota_imposto'
    )
    BEGIN
        EXEC sp_executesql N'
            ALTER TABLE dbo.usuarios WITH CHECK
            ADD CONSTRAINT CK_usuarios_aliquota_imposto
            CHECK (aliquota_imposto IS NULL OR (aliquota_imposto > 0 AND aliquota_imposto <= 100));
        ';
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.usuarios')
          AND name = N'CK_usuarios_dia_vencimento_imposto'
    )
    BEGIN
        EXEC sp_executesql N'
            ALTER TABLE dbo.usuarios WITH CHECK
            ADD CONSTRAINT CK_usuarios_dia_vencimento_imposto
            CHECK (dia_vencimento_imposto IS NULL OR dia_vencimento_imposto BETWEEN 1 AND 28);
        ';
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
