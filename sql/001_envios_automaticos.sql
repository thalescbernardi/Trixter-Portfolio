-- Executar uma vez pelo executor --inicializar-historico ou pelo SSMS.
-- Não altera tabelas existentes do aplicativo.
IF OBJECT_ID(N'dbo.envios_automaticos', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.envios_automaticos (
        id_envio bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
        id_usuario nvarchar(128) NOT NULL,
        tipo varchar(40) NOT NULL,
        periodo date NOT NULL,
        destinatario nvarchar(320) NULL,
        status varchar(20) NOT NULL,
        tentativas int NOT NULL DEFAULT 1,
        message_id nvarchar(255) NOT NULL,
        criado_em datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
        atualizado_em datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
        enviado_em datetime2 NULL,
        ultimo_erro nvarchar(1000) NULL,
        CONSTRAINT UQ_envios_automaticos_periodo UNIQUE (id_usuario, tipo, periodo),
        CONSTRAINT CK_envios_automaticos_status CHECK
            (status IN ('preparando', 'enviando', 'enviado', 'falha', 'incerto'))
    );
END;
