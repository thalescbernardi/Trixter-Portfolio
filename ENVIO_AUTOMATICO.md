> Documento da capacidade implementada. Nesta copia de portfolio, os workflows em `docs/workflows/` sao exemplos inativos, sem credenciais ou agendamento.

# Relatórios mensais e alertas diários automáticos

O executor funciona sem navegador, sessão de usuário ou processo Streamlit. O
computador/servidor que executa a tarefa precisa estar ligado, com acesso ao SQL
Server e ao SMTP. A mesma execução processa relatórios mensais, alertas diários e o resumo semanal.

## Estrutura

- `executar_envios.py`: entrada de linha de comando.
- `trixter/infra.py`: configuração, SQL Server e SMTP/Brevo.
- `trixter/relatorios.py`: cálculos e PDF compartilhados com a interface.
- `trixter/alertas.py`: regras de orçamento, recorrências e metas compartilhadas com a interface.
- `trixter/automacao.py`: seleção dos usuários e fluxo de envio.
- `trixter/historico.py`: persistência e bloqueio entre execuções.
- `sql/001_envios_automaticos.sql`: criação idempotente da tabela de histórico.

## Regras implementadas

- Somente `receber_relatorio_mensal=1`, conta não demo e dia entre 1 e 28.
- Envia o **mês anterior**, a partir do dia escolhido, considerando
  `America/Sao_Paulo` (configurável). Exemplo: em 10/09, com dia 5, envia agosto.
- Se o computador estiver desligado no dia escolhido, a próxima execução ainda
  naquele mês recupera o envio. Não há envio retroativo de vários meses perdidos.
- Janeiro envia dezembro do ano anterior. Contas sem movimentos recebem PDF
  com totais zerados, como no relatório manual.
- A preferência é consultada novamente em cada execução. Um lote usa o retrato
  das preferências lido no início; mudanças durante o lote valem para o próximo.
- Alertas: somente `receber_alertas=1` e conta não demo. Envia um único e-mail
  reunindo os alertas do usuário, no máximo uma vez por dia no fuso configurado.
- Mantém as regras da interface: orçamento do mês com consumo a partir de 80%
  (crítico a partir de 100%); recorrências ativas com vencimento de hoje até 3
  dias; metas não atingidas com prazo de hoje até 30 dias. Limites de orçamento
  não positivos são ignorados para evitar divisão por zero.
- Sem alertas, não envia e não reserva histórico. Se surgirem alertas depois,
  uma nova execução no mesmo dia poderá enviá-los. Depois de um envio aceito,
  novos alertas aguardam o dia seguinte. Um alerta ainda ativo pode aparecer
  novamente no resumo do próximo dia.
- Dias perdidos não geram resumos retroativos: os alertas usam a data da execução.
  O executor apenas consulta recorrências; não lança nem avança suas execuções.
- Resumo semanal: somente `receber_resumo_semanal=1` e conta não demo. A preferência
  fica em Configurações, depois de executar `sql/008_resumo_semanal.sql`. O período
  gravado é a segunda-feira da semana corrente. Se a máquina estiver desligada na
  segunda, a próxima execução até o domingo ainda envia essa semana. A semana
  anterior não é recuperada. O texto traz saldo, o que vence em 7 dias a partir
  da data da execução, a categoria que passou de 100% do orçamento e o cliente
  com recebimento atrasado. A leitura sai mesmo quando esses itens estão vazios.

- Os envios manuais continuam explícitos e independentes do histórico automático.

## Preparação

Use Python 3.11 ou superior e instale o driver ODBC correspondente ao SQL Server.
No ambiente Python escolhido:

```powershell
python -m pip install -r requirements-envios.txt
```

O ambiente Anaconda já utilizado pelo projeto pode ser reaproveitado. Escolha
sempre o executável absoluto ao configurar a tarefa.

Use o mesmo TOML privado do aplicativo ou copie `config.envios.exemplo.toml` para
`.streamlit/secrets.toml` e preencha-o. O executor usa uma única fonte.
Variáveis de ambiente e arquivo TOML não são mesclados: se os dois existirem ao
mesmo tempo, a execução para.

Se existir qualquer variável `TRIXTER_DATABASE_`, `TRIXTER_EMAIL_` ou
`TRIXTER_AUTOMACAO_`, a configuração vem só dessas variáveis. `TRIXTER_CONFIG`
não entra nesse grupo: ela continua sendo apenas o caminho de um arquivo.

Se nenhuma dessas variáveis existir, o executor lê o primeiro arquivo encontrado:

1. `--config CAMINHO`, quando informado;
2. variável `TRIXTER_CONFIG`;
3. `.streamlit/secrets.toml` na raiz do projeto;
4. `.streamlit/secrets.toml` na pasta pessoal do usuário da tarefa.

Arquivos não são mesclados entre si. Um caminho explícito que não exista não
cai no arquivo padrão. Se usar outro nome/local, mantenha-o fora do Git.
A senha de e-mail é a **chave SMTP do Brevo**, não a chave de API.
Porta 587 usa STARTTLS; porta 465 usa TLS direto.

Com `Trusted_Connection=yes`, a conta Windows da tarefa deve ter acesso ao banco.
A criação da tabela exige permissão DDL; execuções normais precisam SELECT nas
tabelas financeiras/usuários e SELECT, INSERT e UPDATE em `envios_automaticos`.
O executor também usa `sys.sp_getapplock`/`sp_releaseapplock` no banco configurado.

## Primeiro uso

Na pasta do projeto (substitua os caminhos pelo ambiente escolhido):

```powershell
# Cria somente o histórico; não envia e-mails.
python executar_envios.py --config "C:\caminho\secrets.toml" --inicializar-historico

# Prepara relatórios e alertas em memória, sem SMTP e sem gravar histórico.
python executar_envios.py --config "C:\caminho\secrets.toml" --simular

# Permite testar a elegibilidade em outra data, somente na simulação.
python executar_envios.py --config "C:\caminho\secrets.toml" --simular --data 2026-10-05

# Envio real. Repetir não reenvia um período já registrado como enviado.
python executar_envios.py --config "C:\caminho\secrets.toml" --enviar
```

Sem opção de ação, o comportamento é **simular**. A simulação pode ser usada antes
da criação da tabela, mas nesse caso avisa que não verificou envios anteriores.
Ela acessa o banco, mas não grava arquivos PDF, não chama SMTP e não reserva envios.
As contagens aparecem no terminal, incluindo `sem_alertas`. Um usuário pode
gerar dois ou três envios no mesmo lote: relatório mensal, resumo diário de alertas
e resumo semanal.
Erros retornam código de saída 1; sucesso, 0.

## Agendador de Tarefas do Windows

Crie uma tarefa diária, por exemplo às 08:00:

- Programa: caminho absoluto do `python.exe` do ambiente preparado.
- Argumentos: `"C:\caminho\Trixter\executar_envios.py" --config "C:\caminho\secrets.toml" --enviar`
- Iniciar em: `C:\caminho\Trixter`.
- Se necessário, escolha executar mesmo sem o usuário conectado, com a conta
  autorizada no SQL Server e com acesso ao arquivo de configuração.
- Habilite executar quando possível após um início agendado perdido.
- Em instâncias simultâneas, escolha não iniciar nova instância.
- Habilite o histórico da tarefa para acompanhar falhas; o comando manual também
  permite inspecionar as contagens e os logs. O registro detalhado fica no banco.

Nenhuma tarefa é instalada automaticamente por este código. Não execute o
agendador dentro do Streamlit: um rerun ou várias sessões poderiam multiplicá-lo.

## Azure Container Apps Jobs

O contêiner não leva arquivo de credenciais. A configuração entra só por
variáveis de ambiente, sem `TRIXTER_CONFIG` e sem TOML montado. O comando
continua `python executar_envios.py --enviar`.

Valores comuns, definidos como variável normal do job:

| Variável | Equivale no TOML | Exemplo |
|---|---|---|
| `TRIXTER_DATABASE_DRIVER` | `database.driver` | `ODBC Driver 18 for SQL Server` |
| `TRIXTER_DATABASE_SERVER` | `database.server` | `seu-servidor.database.windows.net` |
| `TRIXTER_DATABASE_NAME` | `database.database` | nome do banco |
| `TRIXTER_DATABASE_TRUSTED_CONNECTION` | `database.trusted_connection` | `no` |
| `TRIXTER_DATABASE_ENCRYPT` | `database.encrypt` | `yes` |
| `TRIXTER_DATABASE_TRUST_SERVER_CERTIFICATE` | `database.trust_server_certificate` | `no` |
| `TRIXTER_EMAIL_REMETENTE` | `email.remetente` | remetente verificado no Brevo |
| `TRIXTER_EMAIL_SERVIDOR` | `email.servidor` | `smtp-relay.brevo.com` |
| `TRIXTER_EMAIL_PORTA` | `email.porta` | `587` |
| `TRIXTER_AUTOMACAO_FUSO_HORARIO` | `automacao.fuso_horario` | `America/Sao_Paulo` |
| `TRIXTER_AUTOMACAO_MAX_TENTATIVAS` | `automacao.max_tentativas` | `3` |

Segredos, gravados como secret do Container App e referenciados pelo job:

| Variável | Equivale no TOML |
|---|---|
| `TRIXTER_DATABASE_USUARIO` | `database.usuario` |
| `TRIXTER_DATABASE_SENHA` | `database.senha` |
| `TRIXTER_EMAIL_USUARIO` | `email.usuario` |
| `TRIXTER_EMAIL_SENHA` | `email.senha` |

`TRIXTER_DATABASE_ENCRYPT` e `TRIXTER_DATABASE_TRUST_SERVER_CERTIFICATE` são
opcionais. Sem elas, a conexão não acrescenta esses atributos, como num TOML
que não tem as chaves. Fuso e máximo de tentativas também são opcionais: o
padrão continua `America/Sao_Paulo` e 3. As demais variáveis da tabela de
valores comuns e os quatro segredos são necessários para o envio real, com
`TRIXTER_DATABASE_TRUSTED_CONNECTION=no`. Uma variável preenchida pela metade
não completa o restante com arquivo.

## Histórico e duplicidade

A chave única é `(id_usuario, tipo, periodo)`: `relatorio_mensal` usa o primeiro
dia do mês do relatório; `alertas_diarios` usa a data do resumo diário;
`resumo_semanal` usa a segunda-feira da semana. A tabela da etapa 1 já comporta
os três; a coluna nova é só a preferência em `dbo.usuarios`. O mesmo bloqueio
de aplicação SQL exclusivo (mantendo o nome da etapa 1) impede dois executores
reais de processarem o lote ao mesmo tempo, mesmo em computadores diferentes.
O bloqueio é liberado ao terminar ou perder a sessão SQL.

Estados:

| Estado | Significado | Nova tentativa automática |
|---|---|---|
| `preparando` | Reserva persistida, ainda sem SMTP | Após recuperar execução interrompida |
| `falha` | Erro antes do SMTP | Até `max_tentativas` (padrão 3) |
| `enviando` | Estado persistido antes de chamar SMTP | Não; interrupção vira `incerto` |
| `incerto` | Não é possível assegurar se o provedor aceitou | Não |
| `enviado` | SMTP aceitou e a confirmação foi gravada | Não |

A mensagem é preparada antes da reserva. Falhas nessa preparação também são
registradas como `falha` e respeitam o limite de tentativas. A ausência de alertas
não é uma falha. Recuperação de interrupções abrange os três tipos de envio.

O registro guarda destinatário, quantidade de tentativas, Message-ID, timestamps
UTC e último erro resumido. A tabela registra a situação atual de cada envio
lógico; não é uma tabela separada para cada tentativa.

SMTP e SQL Server não participam de uma transação única. Não há promessa de
"exactly once": o processo pode cair após SMTP aceitar, mas antes de confirmar no
banco. Por isso estados incertos ficam bloqueados, priorizando evitar duplicatas.
Até erros SMTP aparentemente recuperáveis são tratados conservadoramente.
"Enviado" significa aceito pelo servidor, não confirmação de entrega na caixa.

Consulta de acompanhamento:

```sql
SELECT id_envio, id_usuario, tipo, periodo, status, tentativas,
       message_id, criado_em, atualizado_em, enviado_em, ultimo_erro
FROM dbo.envios_automaticos
ORDER BY criado_em DESC;
```

Para um registro `incerto`, confira o log do Brevo e o Message-ID antes de agir.
Se aceito, marque manualmente como `enviado`. Se comprovadamente não aceito,
um administrador pode marcar como `falha` para liberar nova tentativa (respeitando
o limite). Use o `id_envio` específico e confira o status antes da atualização.
Não apague o histórico para "tentar de novo". Envios de meses anteriores ao ciclo
atual exigem tratamento manual; não são recuperados pelo executor regular.
Para alertas, o limite e os estados valem para cada dia: um `incerto` de ontem
continua registrado para conferência, mas não bloqueia o resumo novo de hoje.

## Validação

```powershell
python -m pip install -r requirements-testes.txt
python -m pytest tests -q
```

No Windows/PowerShell, configure `PYTHONUTF8=1` antes de executar os testes,
conforme [Desenvolvimento local](DESENVOLVIMENTO.md).

Os testes simulam SQL/SMTP e verificam datas, preferências, PDFs, duplicidade,
interrupções, janelas dos alertas, ausência de conteúdo e estados de erro.
Não enviam e-mails reais. A conexão, a migração e
o bloqueio concorrente no SQL Server real devem ser validados no ambiente de
implantação antes de habilitar a tarefa.
