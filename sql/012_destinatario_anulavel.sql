-- Migracao administrativa explicita; nao executar pelo usuario operacional.
-- Conferir o banco de destino e suspender os executores antes de aplicar.
-- Apenas permite NULL. A limpeza de valores existentes pertence ao script 013.
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.envios_automaticos', N'U') IS NULL
    THROW 50001, 'Tabela de historico ausente ou sem visibilidade; revisar antes de continuar.', 1;

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.envios_automaticos', N'U')
      AND name = N'destinatario'
      AND system_type_id = TYPE_ID(N'nvarchar')
      AND user_type_id = TYPE_ID(N'nvarchar')
      AND max_length = 640
      AND is_computed = 0
)
    THROW 50001, 'Coluna destinatario ausente ou com definicao inesperada; revisar antes de continuar.', 1;

IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.envios_automaticos', N'U')
      AND name = N'destinatario' AND is_nullable = 0
)
    ALTER TABLE dbo.envios_automaticos ALTER COLUMN destinatario nvarchar(320) NULL;
