-- Executar no banco do Trixter, pelo SSMS, fora do horário do envio automático.
-- Cria um índice único não filtrado só em dbo.usuarios.email.
-- Não altera linhas, não muda nulidade e não remove nenhum índice já existente.
--
-- Operação offline: não usa ONLINE nem RESUMABLE. O CREATE INDEX obtém
-- bloqueio de modificação de esquema (Sch-M) em dbo.usuarios. Sch-M é
-- incompatível com os demais bloqueios, então leitura e gravação de outras
-- sessões nessa tabela esperam desde a construção até o COMMIT deste script.
-- O próprio script confirma a transação. Com dezenas de linhas a espera é
-- curta, mas login, cadastro, alteração de e-mail e o executor ficam parados
-- durante esse intervalo. Execute fora da agenda do envio automático.
--
-- As pré-condições são lidas na mesma transação, imediatamente antes do
-- CREATE, e não gravam nada. Se a construção encontrar duplicata, o CATCH
-- desfaz a transação e o índice não permanece.
--
-- Rodar de novo não cria outro índice quando já existe uma chave única de
-- linha, agrupada ou não agrupada, habilitada, sem IGNORE_DUP_KEY, não
-- filtrada e formada somente pela coluna email, qualquer que seja o nome.
-- Índice filtrado, composto, desabilitado, hipotético, columnstore, não único
-- ou com IGNORE_DUP_KEY não é equivalente e não autoriza pular a criação.
-- Se o nome UX_usuarios_email já existir com outra forma, o script para.
--
-- Reversão, em uma execução separada, somente se este script criou o índice:
-- DROP INDEX UX_usuarios_email ON dbo.usuarios;
-- Não apague a chave primária de id_usuario nem outro índice de outro nome.
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.usuarios', N'U') IS NULL
        THROW 51100, N'dbo.usuarios não existe.', 1;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.columns AS coluna
        WHERE coluna.object_id = OBJECT_ID(N'dbo.usuarios')
          AND coluna.name = N'email'
          AND TYPE_NAME(coluna.user_type_id) = N'varchar'
          AND coluna.max_length = 255
    )
        THROW 51101, N'dbo.usuarios.email não é varchar(255). O índice não foi criado.', 1;

    IF EXISTS (
        SELECT 1
        FROM sys.indexes AS indice
        WHERE indice.object_id = OBJECT_ID(N'dbo.usuarios')
          AND indice.type IN (1, 2)
          AND indice.is_hypothetical = 0
          AND indice.is_disabled = 0
          AND indice.is_unique = 1
          AND indice.ignore_dup_key = 0
          AND indice.has_filter = 0
          AND NOT EXISTS (
              SELECT 1
              FROM sys.index_columns AS incluida
              WHERE incluida.object_id = indice.object_id
                AND incluida.index_id = indice.index_id
                AND incluida.is_included_column = 1
          )
          AND (
              SELECT COUNT(*)
              FROM sys.index_columns AS chave
              WHERE chave.object_id = indice.object_id
                AND chave.index_id = indice.index_id
                AND chave.is_included_column = 0
                AND chave.key_ordinal > 0
          ) = 1
          AND EXISTS (
              SELECT 1
              FROM sys.index_columns AS chave
              INNER JOIN sys.columns AS coluna
                  ON coluna.object_id = chave.object_id
                 AND coluna.column_id = chave.column_id
              WHERE chave.object_id = indice.object_id
                AND chave.index_id = indice.index_id
                AND chave.is_included_column = 0
                AND chave.key_ordinal = 1
                AND coluna.name = N'email'
          )
    )
        PRINT N'Índice único equivalente já existe. Nenhuma alteração foi feita.';
    ELSE
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM sys.indexes
            WHERE object_id = OBJECT_ID(N'dbo.usuarios')
              AND name = N'UX_usuarios_email'
        )
            THROW 51102, N'UX_usuarios_email existe, mas não é uma chave única só de email.', 1;

        IF EXISTS (
            SELECT email
            FROM dbo.usuarios
            GROUP BY email
            HAVING COUNT(*) > 1
        )
        OR EXISTS (
            SELECT LOWER(LTRIM(RTRIM(email)))
            FROM dbo.usuarios
            WHERE email IS NOT NULL
            GROUP BY LOWER(LTRIM(RTRIM(email)))
            HAVING COUNT(*) > 1
        )
            THROW 51103, N'Há e-mails duplicados. O índice não foi criado.', 1;

        IF EXISTS (
            SELECT 1
            FROM dbo.usuarios
            WHERE email IS NULL
        )
            THROW 51104, N'Há e-mail nulo. O índice não foi criado.', 1;

        IF EXISTS (
            SELECT 1
            FROM dbo.usuarios
            WHERE email IS NOT NULL
              AND LTRIM(RTRIM(email)) = N''
        )
            THROW 51105, N'Há e-mail vazio. O índice não foi criado.', 1;

        CREATE UNIQUE NONCLUSTERED INDEX UX_usuarios_email
            ON dbo.usuarios (email);

        PRINT N'Índice UX_usuarios_email criado.';
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
