-- Executar uma vez no banco do Trixter, pelo SSMS.
-- Conta tentativas de login, envio e código. Não altera dbo.usuarios.
-- Enquanto esta tabela não existir, o aplicativo segue só com o limite da sessão.
IF OBJECT_ID(N'dbo.limites_acesso', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.limites_acesso (
        fluxo varchar(24) NOT NULL,
        chave varchar(160) NOT NULL,
        tentativas int NOT NULL,
        janela_inicio datetime2 NOT NULL,
        bloqueado_ate datetime2 NULL,
        CONSTRAINT PK_limites_acesso PRIMARY KEY (fluxo, chave)
    );
END;
