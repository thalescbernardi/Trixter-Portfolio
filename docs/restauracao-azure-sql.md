# Restauração segura do Azure SQL — Trixter

Procedimento manual. Não executa restauração nem autoriza alterações em produção.

## 1. Pré-condições e responsável

- Thales Carvalho Bernardi coordena a recuperação e autoriza a reabertura; um operador por ele autorizado pode executar as etapas com as permissões necessárias.
- Registrar motivo, operador, horários UTC, ponto PITR escolhido, banco de origem, banco de destino e decisão final. Não registrar credenciais ou conteúdo financeiro no relato operacional.
- Configuração administrativa informada para `banco-exemplo`: PITR de sete dias, frequência indicada de 12 horas e nenhuma política LTR. Confirmar os pontos realmente disponíveis no incidente; a frequência indicada não representa os únicos horários restauráveis.
- Confirmar acesso administrativo, capacidade/custo do banco temporário e meios de isolamento antes de começar. Não presumir slots, Storage Account, diário externo ou outros recursos não verificados.

## 2. Suspender acesso e automações

1. Interromper o acesso público à aplicação e suspender todos os executores de e-mail identificados, incluindo agendamentos e execuções manuais do GitHub Actions.
2. Confirmar que não existem execuções em andamento; suspensão de novos agendamentos não cancela um SMTP já iniciado. Registrar resultados conhecidos ou incertos.
3. Impedir novas gravações no banco original durante a comparação. Não executar a aplicação ou o executor contra o banco restaurado para fazer a conferência.

## 3. Restaurar e preservar as evidências

1. Preservar o banco original, quando disponível, e as evidências de alterações e envios posteriores ao ponto escolhido. Não sobrescrever nem excluir a origem.
2. No Azure SQL, solicitar PITR para **outro banco**, com nome distinto. Manter o destino sem conexão da aplicação pública ou dos executores e com acesso restrito aos responsáveis.
3. Registrar a conclusão e o ponto efetivamente restaurado. Comparar com a origem congelada e com evidências independentes confiáveis; o próprio banco restaurado não comprova eventos posteriores ao seu ponto de recuperação.

## 4. Conciliar antes de reabrir

| Item | Ação obrigatória |
| --- | --- |
| Contas excluídas | Reaplicar a exclusão e conferir a ausência dos registros relacionados, usando identificadores internos. Ausência na origem exige verificar que ela está íntegra e representa o estado mais recente. |
| Movimentações excluídas ou corrigidas | Comparar identificadores de receitas e gastos por usuário e reaplicar exclusões/correções comprovadas. Não reconciliar somente por descrição, data ou valor. |
| Senhas, e-mails e sessões | Preservar alterações posteriores comprovadas e impedir autenticação com credenciais antigas. Invalidar sessões anteriores por procedimento verificado; reiniciar a aplicação, sozinho, não comprova essa invalidação. Não copiar senhas para relatórios. Se não for possível conciliar, manter o acesso bloqueado até existir procedimento seguro de recuperação e verificação de identidade. |
| Preferências de e-mail | Reaplicar as escolhas posteriores comprovadas. Sem evidência suficiente, manter as modalidades financeiras automáticas desativadas; não interpretar a preferência antiga como autorização atual. |
| Histórico de envios | Conciliar `dbo.envios_automaticos` com a origem e evidências do provedor disponíveis, por usuário, tipo e período. Preservar a prevenção de duplicidades e os resultados incertos. Ausência de registro não comprova ausência de envio. |

Não reenviar mensagens como teste. Não apagar nem converter `incerto` em `falha` para liberar tentativa. Estados interrompidos seguem a recuperação existente, sob o bloqueio exclusivo do executor, somente depois da conciliação e da autorização para retomada. O expurgo de 30 dias não substitui essa conferência.

## 5. Decidir a liberação

Liberar somente quando todos os critérios estiverem documentados:

- Exclusões e correções posteriores foram conciliadas para o conjunto de dados que será disponibilizado, sem divergências pendentes.
- Credenciais antigas e sessões anteriores não permitem acesso; preferências foram conciliadas ou mantidas desligadas.
- Isolamento entre usuários e integridade dos relacionamentos foram conferidos.
- Envios já processados ou incertos não serão repetidos. Manter os executores suspensos enquanto houver dúvida, mesmo que o acesso à aplicação possa ser liberado separadamente.
- Responsável aprovou explicitamente o destino e a retomada. Alterar a conexão somente nessa etapa autorizada, mantendo as demais cópias isoladas.

**Se o banco original estiver indisponível e não houver evidência suficiente para conciliar os dados, manter o banco restaurado isolado. Não reabrir automaticamente nem usar o decurso de sete dias como justificativa para liberar os dados.**

## 6. Descartar cópias temporárias

Inventariar bancos restaurados, exportações e arquivos de comparação, com responsável e data de revisão. Restringir acesso enquanto forem necessários; após validação e autorização, remover apenas as cópias identificadas e registrar o descarte. Não excluir a única evidência necessária à conciliação. Considerar que bancos temporários também podem gerar backups e custos.

O Trixter não elimina diretamente cópias administradas pelo Azure. Conferir o ciclo aplicável a cada banco/cópia; sete dias de PITR não significam eliminação absoluta de todas as cópias ao final desse prazo.

## 7. Limitações atuais

Não existe registro externo completo e confiável de exclusões e demais alterações críticas. O procedimento depende da integridade da origem ou de evidências independentes suficientes; anotações manuais incompletas não suprem essa lacuna. Se a conciliação não puder ser demonstrada, a consequência é indisponibilidade até resolução, e não restauração pública presumida como segura. Não há garantia de recuperação integral nem de prazo de retorno.
