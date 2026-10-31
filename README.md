# Trixter — Gerenciador Financeiro PF/PJ

Projeto de gestão financeira PF/PJ desenvolvido com **Python, SQL, pandas e Streamlit**. Transforma movimentações inseridas manualmente ou extraídas de PDFs em indicadores, projeções, gráficos e relatórios.

O projeto reúne **processamento e análise de dados, persistência relacional e automação**, com testes de regras financeiras e fluxos da aplicação. É gratuito e foi desenvolvido como portfólio.

**Disponibilidade:** esta é uma cópia independente para portfólio, sem serviço público, credenciais ou automações ativas. Derivada da versão integrada do Trixter; não está conectada à infraestrutura original.

## Demonstração visual

Capturas do ambiente de testes com **dados fictícios**.

### Dashboard Financeiro

Indicadores do período e visualizações de receitas e gastos.

![Indicadores e filtros do Dashboard Financeiro](<docs/Imagens/Readme Dashboard 1.png>)

<details>
<summary>Ver gráficos complementares</summary>

![Comparativo de receitas e gastos](<docs/Imagens/Readme Dashboard 2.png>)

![Movimentações por categoria](<docs/Imagens/Readme Dashboard 3.png>)

</details>

### Cadastro de movimentações

Formulários de receitas e gastos com categorias, classificação e descrição.

![Cadastro de receita com cliente fictício](<docs/Imagens/Readme Cadastrar Receita.png>)

![Cadastro de gasto](<docs/Imagens/Readme Cadastrar Gasto .png>)

### Histórico de movimentações

Consulta por período, tipo, categoria e classificação, com acompanhamento da evolução financeira.

![Filtros e indicadores do histórico de receitas e gastos](<docs/Imagens/Readme Visualizar Gastos e Receitas .png>)

<details>
<summary>Ver gráficos complementares</summary>

![Evolução temporal de receitas e gastos](<docs/Imagens/Readme Visualizar Rec e Gas 2.png>)

</details>

### Planejamento mensal

Receitas, gastos e saldo projetados, com acompanhamento do realizado e do previsto pendente.

![Indicadores do planejamento mensal](<docs/Imagens/Readme Planejamento Mensal final .png>)

### Importação de PDF

Revisão de sete movimentações fictícias extraídas do PDF antes da confirmação da importação.

![Revisão de gastos e receitas extraídos de PDF](<docs/Imagens/Readme Importar PDF .png>)

## Processamento e análise de dados

| Etapa | Implementação |
|---|---|
| Ingestão | Formulários e extração de texto de PDFs com `pypdf`; reconhecimento por regras e expressões regulares |
| Validação | Campos obrigatórios, valores, datas, classificações, limites de importação e revisão do usuário |
| Normalização | Conversão de datas, padronização de clientes e categorias e tratamento de valores ausentes |
| Deduplicação | Verificação de movimentações na importação; histórico por usuário, tipo e período para evitar envios repetidos |
| Transformação | DataFrames, agrupamentos, tabelas dinâmicas, ordenação temporal e acumulados |
| Análise | Indicadores financeiros, comparação entre períodos, orçamento utilizado, margem e projeções |
| Saída | Gráficos Plotly, relatórios PDF e exportação JSON com seleção explícita de campos |

A importação limita arquivos a 2 MiB e 15 páginas, além de limites de texto e movimentações. O PDF é processado na sessão para revisão; o código não persiste o arquivo original no banco. O reconhecimento não é universal e pode exigir correção manual.

As projeções e análises usam regras determinísticas, sem modelos de inteligência artificial ou machine learning. Componentes financeiros utilizam `Decimal`, em conjunto com outros tipos numéricos presentes na aplicação.

## Funcionalidades principais

### Movimentações e organização

- Cadastro de receitas e gastos com datas, categorias e classificação de custos.
- Histórico filtrável, com edição e exclusão por registro e identificação opcional de clientes nas receitas.
- Importação de extratos e comprovantes PDF, com revisão antes da confirmação.
- Orçamentos por categoria, metas financeiras e preferências individuais.

### Planejamento e análise

- Planejamento mensal e anual, compromissos em aberto e acompanhamento de atrasos.
- Recorrências e tratamento de datas de execução.
- Dashboard, resumo financeiro e fluxo de caixa realizado e projetado.
- Análises de custos fixos e variáveis, margem e concentração de receitas por cliente.
- Simulação de cenários, reserva de emergência e provisão tributária.

### Relatórios, conta e manutenção

- Relatórios mensais em PDF, alertas e resumo semanal.
- Cadastro PF/PJ, autenticação, recuperação de acesso e configurações de segurança.
- Exportação JSON e exclusão de conta autenticada.
- Demonstrações temporárias PF/PJ e limpeza de registros elegíveis.
- Executor de e-mails separado da interface e rotina independente de expurgos. Os envios financeiros estão atualmente suspensos.

## Arquitetura técnica

```text
Interface Streamlit
  Gerenciador de Gastos V2.py → módulos trixter/
                 │
                 └── pyodbc / ODBC Driver → SQL Server / Azure SQL

Processos Python independentes
  executar_envios.py   → relatórios e alertas → SMTP/Brevo (suspenso)
  executar_expurgos.py → manutenção SQL, sem envio de e-mails

Docker → GHCR → Azure App Service / runners do GitHub Actions
```

- **Interface:** o arquivo principal coordena navegação e sessão; os módulos separam telas, cálculos e acesso à infraestrutura. Fragmentos Streamlit limitam reruns em formulários específicos.
- **Persistência:** SQL Server, com Azure SQL na infraestrutura hospedada. Consultas parametrizadas, filtros por usuário e transações protegem as operações de dados.
- **Contêineres:** `Dockerfile.web` empacota a interface; `Dockerfile` empacota o executor. Ambos utilizam Python 3.12 e usuário de contêiner não administrativo.
- **Entrega:** os exemplos de GitHub Actions demonstram validação e publicação manual no GHCR. Estão em [docs/workflows](docs/workflows/), fora do diretório de execução do Actions. Publicar e ativar imagens são operações distintas.
- **Manutenção:** a rotina independente e seu workflow de exemplo demonstram expurgos com imagem por digest, sem depender do envio de relatórios. Nenhuma rotina está agendada nesta cópia.

A aplicação é modular, com processos separados para interface, envios e manutenção. A região Azure informada para App Service e SQL é Brazil South.

## Tecnologias

| Tecnologia | Papel no projeto |
|---|---|
| Python | Regras de negócio, processamento e executores |
| Streamlit | Interface, sessão, widgets e fragmentos |
| pandas | Transformações e agregações de dados |
| Plotly | Visualizações interativas |
| SQL Server / Azure SQL + pyodbc | Persistência relacional e consultas parametrizadas |
| pypdf / ReportLab | Extração de PDF e geração de relatórios |
| bcrypt | Hash de senhas |
| Docker / GHCR | Empacotamento e distribuição das imagens |
| GitHub Actions | Validação, publicação manual e manutenção agendada |
| Azure App Service | Hospedagem da interface, atualmente sem acesso público |
| Brevo via SMTP | Integração de e-mails implementada; envios financeiros suspensos |
| pytest / Streamlit AppTest | Testes de regras, integrações simuladas e interface |

As versões estão declaradas em [requirements.txt](requirements.txt), [requirements-envios.txt](requirements-envios.txt) e [requirements-testes.txt](requirements-testes.txt).

## Decisões e desafios técnicos

- **Consistência financeira:** distinguir falta de histórico de valores efetivamente zerados e preservar a ordenação cronológica nas análises.
- **Identidade dos registros:** selecionar e alterar por ID, mesmo quando categorias e descrições são iguais, preservando o filtro por usuário.
- **Calendário:** tratar recorrências, meses de tamanhos diferentes e evolução das próximas execuções.
- **Interface reativa:** preservar edições durante reruns e limpar estado ao salvar, excluir ou trocar de contexto.
- **Concorrência e idempotência:** usar histórico e bloqueios SQL para coordenar executores; um resultado de envio incerto não libera reenvio automático.
- **Minimização:** não persistir o destinatário completo nas novas reservas de envio e separar manutenção de comunicação financeira.
- **Testabilidade:** exercitar cálculos e fluxos com dados fictícios, mocks e AppTest, sem depender de usuários ou credenciais de produção.

Exemplos: [importação](trixter/importacao.py), [fluxo de caixa](trixter/fluxo_caixa.py), [compromissos](trixter/compromissos.py), [histórico de envios](trixter/historico.py) e [manutenção](executar_expurgos.py).

## Testes automatizados

Os testes cobrem cálculos, importação, autenticação, sessão, isolamento por usuário, exportação, navegação, recorrências, demonstrações e expurgos.

Na raiz do repositório, com o ambiente Python selecionado:

```powershell
python -m pip install -r requirements-testes.txt
$env:PYTHONUTF8 = '1'
$env:TRIXTER_TESTAR_IMAGEM_WEB = '0'
python -m pytest -q --basetemp .test-temp-readme-01
```

Use uma pasta temporária nova por execução: o pytest pode apagar e recriar o diretório informado. O UTF-8 evita incompatibilidades do AppTest no Windows.

**Resultados históricos por revisão:**

- Revisão consolidada `567f8fe`: suíte completa com **816 aprovados e 1 ignorado**, antes da inclusão da manutenção independente.
- Preparação de `fde2378`: **59 testes direcionados aprovados**, incluindo manutenção, demonstrações, contadores e histórico de envios.

O teste ignorado corresponde à validação opcional da imagem web, que exige Docker e `TRIXTER_TESTAR_IMAGEM_WEB=1`. As contagens são de execuções distintas e não representam percentual de cobertura.

## Execução local

**Pré-requisitos:** Python com as dependências instaladas, Microsoft ODBC Driver compatível e um SQL Server de desenvolvimento com o esquema e dados fictícios necessários. Os scripts em `sql/` são migrações específicas; não representam um provisionamento automático completo de um banco vazio.

1. Na raiz desta cópia, instale `requirements.txt` ou `requirements-testes.txt`.
2. Prepare exclusivamente um banco de desenvolvimento. Não reutilize credenciais nem dados de produção.
3. Configure privadamente `.streamlit/secrets.toml`, ignorado pelo Git. A interface espera `[database]` com `driver`, `server`, `database`, `username` e `password`; os fluxos de e-mail utilizam `[email]` com `remetente`, `servidor`, `porta`, `usuario` e `senha`.
4. Para exercitar envio ou recuperação, utilize um ambiente com SMTP simulado ou bloqueado. A aplicação normal não instala automaticamente os mocks dos testes.
5. Execute a partir da raiz, necessária para resolver os assets:

```powershell
python -m streamlit run "Gerenciador de Gastos V2.py" --server.address 127.0.0.1
```

Esse comando abre a interface; não prepara o banco nem assegura isolamento por si só. A demonstração PF também depende de uma conta modelo fictícia no banco; a PJ possui exemplos definidos no código.

`iniciar_web.py` é a entrada da imagem web e pode gerar o arquivo de secrets a partir das variáveis previstas no próprio módulo. Não execute `executar_envios.py --enviar` para conhecer o projeto: esse modo realiza operações reais quando configurado.

## Estado atual e limitações

- **Cópia de portfólio:** sem serviço público, configurações privadas, banco de dados ou vínculo Git com o projeto original.
- **Automação:** os sete workflows estão somente em `docs/workflows/`, como exemplos inativos. IDs Azure, nomes de recursos e namespace GHCR foram substituídos por placeholders; não devem ser executados sem configuração própria.
- **Execução:** o código preserva integrações SQL e SMTP. Para testes funcionais, forneça apenas infraestrutura de desenvolvimento e SMTP simulado ou bloqueado.
- **Documentos:** Política e Termos permanecem como minutas, sem declaração de conformidade integral com a LGPD.

No projeto original, o acesso público e os envios financeiros estavam suspensos; a manutenção independente tinha agendamento diário e uma execução manual concluída com sucesso, segundo o responsável. Esse registro de **30/10/2026** e os resultados históricos de testes não representam operação ou validação desta cópia.

## Documentação complementar e autoria

- [Desenvolvimento e testes no Windows](DESENVOLVIMENTO.md)
- [Executor de relatórios e e-mails](ENVIO_AUTOMATICO.md) — documentação técnica da capacidade implementada; o envio está suspenso.
- [Procedimento de restauração do Azure SQL](docs/restauracao-azure-sql.md)
- [Política de Privacidade — minuta](trixter/privacidade.py)
- [Termos de Uso — minuta](trixter/termos.py)

Desenvolvido por **Thales Carvalho Bernardi** como projeto de portfólio em Python, análise e processamento de dados.

Contato: [contato@trixter.app.br](mailto:contato@trixter.app.br).
