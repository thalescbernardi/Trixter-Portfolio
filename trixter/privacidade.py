"""Minutas jurídicas e navegação que preserva os campos da tela de origem."""
import streamlit as st

from . import estilo
from .termos import exibir_termos

VERSAO_POLITICA = "minuta"
_AVISO_REVISAO = "Minuta para revisão jurídica — não aprovada para publicação."

_SECOES = (('Sobre esta Política',
  ('O Trixter é um aplicativo de organização financeira inicialmente gratuito, desenvolvido '
   'como projeto de portfólio, para uso pessoal e profissional. O responsável pelo Trixter e '
   'pelos tratamentos próprios da plataforma é Thales Carvalho Bernardi, pessoa física. O '
   'contato para suporte e privacidade é contato@trixter.app.br.',
   'A gratuidade e a finalidade de portfólio não afastam as responsabilidades aplicáveis ao '
   'tratamento de dados pessoais. Esta Política descreve os recursos existentes e distingue os '
   'tratamentos próprios daqueles realizados sobre informações inseridas por profissionais.')),
 ('Dados de usuários e informações de terceiros',
  ('São tratados dados fornecidos pelo usuário, informações produzidas pelos recursos '
   'financeiros e registros técnicos de operação e segurança. Um cliente mencionado nos '
   'lançamentos pode não possuir conta no Trixter.',
   'Thales Carvalho Bernardi define as finalidades próprias do Trixter para cadastro, '
   'autenticação, relacionamento e segurança. Quando o profissional determina por que e quais '
   'dados de seus clientes serão registrados para sua organização financeira, pode atuar '
   'como controlador. Ao processar esses dados em nome e segundo instruções legítimas do '
   'profissional, o Trixter pode atuar como operador. Os papéis dependem das decisões efetivas '
   'em cada tratamento, sem atribuir um único papel a todas as operações.',
   'O campo Cliente é opcional e não constitui cadastro fiscal ou de tomador. Utilize a '
   'identificação mínima suficiente para distinguir receitas e recebimentos previstos, '
   'acompanhar concentração de receitas e atrasos, somente quando necessária.',
   'Descrições e categorias devem limitar-se à identificação financeira da operação. Esses '
   'campos não se destinam a documentos de identificação, credenciais, informações de saúde '
   'ou outros dados sensíveis ou excessivos. O profissional deve verificar a necessidade e '
   'a legitimidade dos dados, informar seus clientes quando cabível e observar seus direitos.',
   'Informações de terceiros podem aparecer nas consultas, análises por cliente e exportações, '
   'conforme o conteúdo inserido. Categorias e outros conteúdos também podem aparecer em '
   'relatórios e comunicações, nos limites descritos na seção de e-mails. Correções e '
   'exclusões na plataforma não recolhem arquivos baixados nem mensagens já entregues.',
   'Solicitações de titulares podem ser encaminhadas a contato@trixter.app.br para identificar '
   'o tratamento e atender ou encaminhar o pedido ao responsável pertinente. O Trixter deve '
   'cooperar no atendimento dentro de suas atribuições, protegendo informações de outras '
   'pessoas. As responsabilidades do profissional não eliminam as obrigações próprias do '
   'Trixter.')),
 ('Cadastro e acesso',
  ('O cadastro solicita tipo de conta PF/PJ, nome ou nome empresarial, e-mail, senha e renda '
   'ou faturamento mensal, que podem permanecer zerados. São mantidos identificador da conta, '
   'criação, último acesso e controles de credenciais.',
   'O cadastro atual não solicita CPF, CNPJ, endereço ou data de nascimento. Os campos de '
   'CPF/CNPJ permanecem na estrutura e na exportação para compatibilidade com registros '
   'anteriores; isso não comprova a existência de valores históricos.',
   'O serviço é destinado a pessoas com 18 anos ou mais. O cadastro atual exige declaração de '
   'maioridade antes da criação da conta, inclusive antes da gravação. A declaração não é '
   'comprovação documental de idade nem registro persistente de aceite. Não se afirma que '
   'contas anteriores tenham passado por essa declaração.',
   'O código enviado para confirmar acesso ao e-mail vale 10 minutos e possui limites de '
   'tentativas e reenvio. Recuperação de senha e alteração de e-mail também utilizam códigos. '
   'A mudança de endereço pode gerar comunicação ao endereço anterior.',
   'A senha é persistida como hash bcrypt. Senhas digitadas e códigos podem existir '
   'temporariamente na memória da sessão durante os fluxos. Ao abrir estes documentos, campos '
   'podem ser preservados temporariamente para permitir o retorno, inclusive senha e '
   'declaração de maioridade. A cópia segue as regras de limpeza da sessão e não registra '
   'aceite.')),
 ('Finalidades e bases legais propostas',
  ('Os dados permitem criar a conta, autenticar, recuperar acesso, organizar registros, '
   'realizar cálculos, importar movimentos, gerar relatórios e executar comunicações '
   'solicitadas. Contadores e registros técnicos auxiliam a proteção contra abuso e o '
   'funcionamento do serviço.',
   'Adota-se execução de contrato ou procedimentos preliminares relacionados ao serviço '
   '(art. 7º, V, da LGPD) para cadastro, autenticação, recuperação de acesso, comunicações '
   'operacionais e funcionalidades solicitadas, incluindo registros financeiros, cálculos, '
   'importação, demonstração, relatórios e exportação, somente na medida necessária a cada função.',
   'Relatórios mensais, alertas e resumos semanais automáticos são funcionalidades opcionais '
   'executadas quando ativadas pelo usuário, com fundamento na execução do serviço solicitado '
   '(art. 7º, V). Essa base não abrange publicidade nem autoriza automaticamente o rastreamento '
   'de abertura e cliques. As preferências não representam consentimento genérico.',
   'Controles técnicos de segurança, prevenção de abuso e prevenção de envios duplicados '
   'utilizam legítimo interesse (arts. 7º, IX, e 10), observadas a finalidade específica, '
   'necessidade, proporcionalidade, expectativas dos titulares e salvaguardas da avaliação '
   'documentada de cada tratamento. Essa base não autoriza conservação indiscriminada de logs.',
   'O atendimento de obrigações legais, incluindo solicitações de titulares previstas na '
   'LGPD e a verificação proporcional de identidade necessária ao atendimento, fundamenta-se '
   'no art. 7º, II. A conservação excepcional necessária ao exercício regular de direitos '
   'pode fundamentar-se no art. 7º, VI, mediante justificativa específica e pelo tempo '
   'necessário, sem retenção preventiva indiscriminada.',
   'Dados de clientes exigem fundamento do controlador competente, conforme a relação e a '
   'finalidade concretas; o contrato com o usuário não autoriza automaticamente todo '
   'tratamento de terceiros. Ao atuar como operador, o Trixter observa instruções legítimas '
   'e suas próprias obrigações aplicáveis.',
   'Permanece pendente nesta minuta o enquadramento específico do rastreamento da Brevo, '
   'separado das bases das comunicações e da segurança. Os enquadramentos adotados não '
   'representam garantia de conformidade integral. Dados '
   'sensíveis exigem análise específica do art. 11. Textos e PDFs podem revelar saúde, '
   'religião ou outros atributos protegidos mesmo sem campos próprios para isso.')),
 ('Dados financeiros e preferências',
  ('A conta pode armazenar receitas, gastos, valores, datas, categorias, descrições, '
   'classificação e cliente opcional nas receitas; planejamentos de receita também podem '
   'incluir cliente. São tratados orçamentos, recorrências, frequência, situação, metas, '
   'prazos, valores acumulados, alíquota e vencimento de provisão tributária e preferências de '
   'comunicações.',
   'Esses dados alimentam histórico, cálculos, previsões, compromissos e relatórios. Nomes de '
   'clientes, categorias personalizadas, metas e descrições podem identificar terceiros. '
   'Insira somente o necessário e evite conteúdo sensível ou excessivo.',
   'No Histórico, é possível corrigir e excluir movimentos individualmente e corrigir o '
   'cliente de uma receita. Planejamentos também podem ser corrigidos ou excluídos. Essas '
   'operações são vinculadas à conta autenticada. Alterar um planejamento não modifica '
   'automaticamente uma movimentação já realizada, nem arquivos baixados ou mensagens '
   'entregues.')),
 ('Importação de PDF',
  ('A importação aceita PDF de até 2 MB e 15 páginas, sujeito aos demais limites técnicos; '
   'arquivos protegidos por senha são recusados. O processamento ocorre no servidor da '
   'aplicação, sem envio do documento a um serviço de inteligência artificial nesse fluxo.',
   'O documento é recebido e seu texto é processado antes da seleção das movimentações. '
   'Verifique previamente o conteúdo e evite documentos com informações desnecessárias de '
   'terceiros. O arquivo e o texto extraído ficam na sessão do aplicativo para revisão. O PDF original '
   'não é gravado no banco pelo código da importação. Movimentos confirmados tornam-se '
   'lançamentos comuns e seguem suas regras de armazenamento e exclusão; informações presentes '
   'nas descrições desses movimentos podem integrar os registros da conta.',
   'Os fluxos de saída implementados limpam os dados temporários correspondentes. Fechar a aba '
   'do navegador não comprova eliminação imediata de toda memória ou registro técnico. '
   'Verifique sua legitimidade para utilizar o documento antes de enviá-lo.')),
 ('E-mails',
  ('O Trixter envia comunicações operacionais de cadastro, recuperação e alteração de e-mail. '
   'O usuário pode solicitar relatório mensal manualmente e configurar relatórios, alertas e '
   'resumo semanal automáticos. Relatórios podem ser visualizados, baixados em PDF e enviados '
   'como anexo.',
   'No código atualizado, novos cadastros PF e PJ começam com relatório mensal, alertas e '
   'resumo semanal automáticos desativados. Cada modalidade pode ser ativada ou desativada '
   'separadamente em Configurações. Isso não altera preferências de contas existentes nem '
   'controla e-mails operacionais de cadastro, recuperação e alteração de e-mail. O relatório '
   'manual depende de solicitação específica. A configuração dos novos cadastros em '
   'produção depende da implantação dessa versão.',
   'As mensagens podem revelar categorias, valores, datas, orçamentos, compromissos e texto de '
   'metas. O resumo semanal omite nomes de clientes; o alerta de recorrência enviado por '
   'e-mail omite a descrição livre. As mensagens continuam vinculadas ao destinatário e não '
   'são anônimas.',
   'O envio utiliza SMTP pelo serviço Brevo, com remetente contato@trixter.app.br, envolvendo '
   'destinatário, assunto, conteúdo, anexos quando existentes e metadados de entrega. '
   'Desativar uma preferência não recolhe mensagens entregues e pode não interromper operação '
   'já em processamento.',
   'O histórico interno dos envios automáticos registra identificador da conta, tipo, '
   'período, situação, tentativas, identificador da mensagem, datas e diagnóstico resumido. '
   'Ele auxilia o controle e a prevenção de duplicidade. O código atualizado grava NULL '
   'na coluna de destinatário nas novas reservas e tentativas, sem persistir o endereço '
   'completo nesse histórico. Registros legados com destinatários ainda podem existir em '
   'produção até a aplicação e conferência da migração e da limpeza correspondentes; '
   'a validação local não comprova sua eliminação em produção. O endereço continua '
   'necessário ao envio e pode integrar registros do provedor. A exportação inclui somente tipo, período, '
   'situação, tentativas e datas, sem destinatário, identificador da mensagem ou erro.')),
 ('Segurança e limite de acesso',
  ('Há hash bcrypt de senha, verificações de sessão e credenciais, vinculação dos registros à '
   'conta autenticada e limites de tentativas. Essas medidas reduzem riscos, sem garantia de '
   'proteção absoluta.',
   'Os contadores de acesso podem guardar resumo criptográfico do e-mail, IP em texto com '
   'tamanho limitado, fluxo, tentativas, início da janela e eventual bloqueio. O resumo do '
   'e-mail não equivale a anonimização. Os contadores não constituem histórico completo de '
   'telas visitadas. Registros expirados após 24 horas são limpos em lotes, podendo aguardar '
   'execução posterior.',
   'Rotinas e infraestrutura também produzem registros de execução, identificadores internos e '
   'falhas. Proteja dispositivos, e-mail e credenciais. Suspeitas de incidente podem ser '
   'comunicadas a contato@trixter.app.br, sem enviar senhas ou documentos completos no '
   'primeiro contato.')),
 ('Demonstração temporária',
  ('Após autenticar, Explorar Demo abre uma conta temporária no banco configurado, com '
   'exemplos e e-mail interno. A demonstração PJ é definida no código; a PF utiliza uma conta '
   'modelo mantida no sistema. Não insira dados reais ou confidenciais na demonstração. A '
   'origem no modelo PF, por si, não certifica o caráter fictício de todo o conteúdo.',
   'Contas de demonstração são excluídas dos envios automáticos. O envio manual de relatórios '
   'por e-mail está bloqueado na demonstração, tanto no botão quanto na execução. Geração, '
   'visualização e download continuam disponíveis.',
   'Ao voltar à conta original, o aplicativo tenta remover a demonstração. Se a tentativa '
   'falhar, a sessão permanece na demonstração. Contas temporárias de demonstração tornam-se '
   'elegíveis para expurgo após 24 horas de sua criação, conforme os critérios implementados '
   'e a execução da rotina. Fechar o navegador '
   'não a remove imediatamente. A conta modelo PF permanece para abastecer o recurso.')),
 ('Cookies, sessão e estatísticas técnicas',
  ('O Streamlit mantém mecanismos de sessão e proteção contra requisições indevidas, podendo '
   'utilizar cookies técnicos e informações do navegador. Bloqueá-los pode prejudicar '
   'recursos. Esses mecanismos são distintos das preferências de comunicação.',
   'O repositório desabilita explicitamente as estatísticas de uso do Streamlit com '
   'gatherUsageStats = false em .streamlit/config.toml. A versão integrada ainda não foi '
   'publicada no Azure; esta configuração no repositório não comprova sua aplicação na '
   'versão atualmente em produção. Esta minuta também não apresenta como comprovado um '
   'inventário completo de cookies da infraestrutura.',
   'A leitura destes documentos e o simples acesso não representam consentimento genérico para '
   'tratamentos opcionais.')),
 ('Prestadores e tratamento fora do Brasil',
  ('Microsoft Azure hospeda a interface no Azure App Service e a base no Azure SQL Database. A '
   'implantação informada nas verificações administrativas utiliza Brazil South; esta minuta '
   'não reconfirma a configuração em produção. A região não garante que suporte, metadados, '
   'backups e subprocessadores permaneçam exclusivamente no Brasil.',
   'Brevo processa e-mails, anexos e registros relacionados. Sua documentação pública informa '
   'armazenamento de bases na União Europeia, mas não comprova todos os acessos e '
   'transferências posteriores da conta do Trixter. Segundo o fornecedor, o rastreamento de '
   'links dos e-mails transacionais via SMTP não pode ser desativado. Foi habilitada a opção '
   'denominada rastreamento anonimizado, que, segundo as informações recebidas da Brevo, '
   'impede a associação das métricas de abertura e clique à identificação de um contato '
   'específico, preservando métricas de relatórios. Mecanismos de medição de abertura podem '
   'permanecer ativos. Isso não significa ausência de coleta nem comprova anonimização '
   'integral nos termos da LGPD. A identificação dos dados tratados, de sua retenção e '
   'de quem determina essa finalidade ainda exige confirmação para concluir sua base legal.',
   'O acordo de processamento de dados (APD) da Brevo foi analisado pelo responsável. '
   'Permanece aguardada a confirmação específica do fornecedor sobre os mecanismos de '
   'transferência internacional aplicáveis à LGPD brasileira; a análise do APD não é '
   'apresentada como comprovação de todos esses mecanismos.',
   'GitHub armazena código e imagens e executa automações pelo GitHub Actions. A rotina de '
   'envios acessa os dados necessários no banco e transmite mensagens. Seus logs podem incluir '
   'identificador da conta, tipo, período, situação, totais e IP público do runner. O workflow '
   'não garante país específico para cada execução.',
   'O tratamento por esses serviços pode ocorrer fora do Brasil. Documentos públicos de DPA e '
   'subprocessadores não comprovam, sozinhos, as condições efetivamente contratadas pelo '
   'Trixter. Cada fluxo exige destinatários, países e mecanismo internacional aplicável, '
   'considerando a LGPD e a Resolução CD/ANPD nº 19/2024. A adequação reconhecida para a União '
   'Europeia não cobre automaticamente todos os fluxos globais ou transferências posteriores.',
   'Esta minuta não declara mecanismos contratuais ainda não confirmados. Informações sobre '
   'compartilhamentos e instrumentos podem ser solicitadas a contato@trixter.app.br, '
   'observados direitos e limites legais.')),
 ('Retenção e cópias de segurança',
  ('Os dados da conta permanecem para os recursos enquanto a conta existir. Não há expurgo '
   'automático de contas normais por inatividade identificado. O histórico interno de envios '
   'é elegível para expurgo após 30 dias contados da data mais recente entre sua última '
   'atualização e o encerramento da janela de envio mensal, semanal ou diária. Esse expurgo '
   'está implementado na versão atualizada; sua execução em produção depende da atualização '
   'e da execução bem-sucedida do executor de envios. A limpeza '
   'ocorre em lotes nas execuções de envio automático, sob bloqueio exclusivo e após '
   'tratamento de execuções interrompidas; falhas ou ausência de execução podem postergá-la. '
   'Estados ainda em processamento não são apagados diretamente, e resultados incertos '
   'não autorizam reenvio automático. O histórico também é removido com a conta na base '
   'operacional.',
   'Códigos valem 10 minutos; dados temporários seguem a sessão e seus fluxos de limpeza; '
   'contadores e demonstrações seguem a elegibilidade de 24 horas com limpeza em lotes. Falhas '
   'podem postergar a eliminação.',
   'Backups, logs de infraestrutura, registros de e-mail e dados dos prestadores seguem '
   'configurações e condições próprias. Na configuração administrativa do banco trixter-db, '
   'conferida no Azure Portal, a retenção para restauração pontual (PITR) é de 7 dias e a '
   'frequência indicada é de 12 horas. Não há política de retenção de longo prazo (LTR) '
   'semanal, mensal ou anual configurada. Isso não significa eliminação absoluta de todas '
   'as cópias após sete dias.',
   'Os prazos anteriormente informados de 1 mês na Brevo e 90 dias no GitHub Actions '
   'dependem de confirmação administrativa atual e não são garantias gerais desta minuta. '
   'Esses prazos não abrangem todos os dados dos serviços ou imagens GHCR.',
   'Dados removidos da base operacional podem permanecer em backups e registros técnicos até '
   'seu ciclo de eliminação. Conservação excepcional por obrigação legal ou defesa exige '
   'justificativa específica, não autorização para retenção indiscriminada. A restauração de '
   'backups exige procedimento para lidar com dados anteriormente excluídos.')),
 ('Exportação e exclusão',
  ('No encerramento planejado do Trixter, será dado aviso prévio de pelo menos 30 dias, '
   'com orientação para exportar os dados e solicitar atendimento antes da descontinuação. '
   'Situações emergenciais, incidentes ou impossibilidade técnica podem exigir interrupção '
   'sem esse prazo; informações e orientações serão fornecidas assim que viável. Encerrada '
   'a prestação, os dados serão eliminados, ressalvada a conservação necessária nas '
   'hipóteses legais aplicáveis e os ciclos de retenção de backups e registros dos '
   'prestadores. Esse encerramento exige atuação do responsável, sem presumir uma rotina '
   'automática específica já implementada.',
   'Em Segurança, a conta real exporta JSON após confirmação da senha; a demonstração pode '
   'exportar sem essa confirmação. O arquivo reúne perfil, movimentos, categorias, orçamentos, '
   'planejamentos, recorrências e parte do histórico de envios. Campos vazios permanecem '
   'vazios.',
   'O JSON não inclui senha, tokens, identificador de mensagem, resumo de erro, backups, '
   'e-mails entregues ou PDF existente somente na sessão. A exportação disponível não esgota '
   'todos os pedidos de acesso e portabilidade.',
   'A exclusão da conta real exige senha e confirmação. Quando concluída, remove da base '
   'operacional usuário, finanças, categorias, preferências e histórico de envios. Também '
   'remove chaves de limitação associadas ao e-mail atual. Contadores identificados somente '
   'por IP não são apagados por essa operação.',
   'A exclusão não elimina imediatamente backups, logs de prestadores, downloads e mensagens '
   'já enviadas. A demonstração não oferece esse botão e segue seu fluxo próprio. Não há '
   'garantia de recuperação após exclusão concluída.')),
 ('Seus direitos e o contato',
  ('Conforme os requisitos legais, o titular pode solicitar confirmação, acesso, correção, '
   'informações sobre compartilhamentos, anonimização, bloqueio, eliminação, portabilidade e '
   'revisão de decisões automatizadas abrangidas pela legislação. Quando houver consentimento, '
   'pode solicitar informações e revogá-lo. Os recursos da interface não esgotam os direitos.',
   'Envie solicitações a contato@trixter.app.br, inclusive se seus dados foram inseridos por '
   'profissional. A análise pode exigir verificação proporcional de identidade e identificação '
   'do tratamento, protegendo dados de outras pessoas. O atendimento deve observar os '
   'requisitos e prazos legais e explicar impedimentos ou encaminhamentos ao controlador '
   'competente.',
   'É possível recorrer à ANPD e aos demais órgãos competentes. Esta minuta não afirma a '
   'existência de portal, encarregado formalmente designado ou procedimento de incidentes já '
   'validado.')),
 ('Alterações',
  ('Esta é uma minuta para revisão jurídica, sem aprovação ou vigência definitiva. Uma versão '
   'aprovada deverá identificar revisão e vigência e prever informação adequada sobre mudanças '
   'relevantes. Alterações não autorizam retroativamente tratamentos nem substituem '
   'manifestação específica quando necessária.',)))


# Campos com chave de widget. O Streamlit apaga a chave quando o widget
# deixa de ser desenhado; a cópia devolve o valor ao fechar a política.
_CAMPOS = {
    "cadastro": (
        "tipo_pessoa",
        "novo_nome",
        "renda_mensal",
        "novo_nome_empresa",
        "faturamento_mensal",
        "novo_email",
        "nova_senha",
        "confirmar_senha",
        "declaracao_maioridade",
        "codigo_digitado_cadastro",
    ),
    "login": ("email_entrada", "senha"),
    "seguranca": (
        "seguranca_senha_atual",
        "seguranca_nova_senha",
        "seguranca_confirmar_senha",
        "novo_email_seguranca",
        "confirmar_email_seguranca",
        "senha_email_seguranca",
        "codigo_digitado_email",
        "senha_exportacao",
        "senha_exclusao",
    ),
}


def politica_aberta(origem):
    return st.session_state.get("politica_origem") == origem


def abrir_politica(origem):
    guardados = {}
    for chave in _CAMPOS[origem]:
        if chave in st.session_state:
            guardados[chave] = st.session_state[chave]
    st.session_state.politica_campos = guardados
    st.session_state.politica_origem = origem


def fechar_politica():
    guardados = st.session_state.get("politica_campos") or {}
    for chave, valor in guardados.items():
        st.session_state[chave] = valor
    st.session_state.politica_origem = None
    st.session_state.pop("politica_campos", None)


def descartar_politica_fora_de_seguranca(estado):
    """Fecha a política de Segurança quando outra tela passou a valer.

    Cadastro e login não usam esta saída. A cópia dos campos é apagada
    sem ser devolvida.
    """
    origem = estado["politica_origem"] if "politica_origem" in estado else None
    if origem != "seguranca":
        return
    tela = estado["tela_atual"] if "tela_atual" in estado else None
    if tela == "seguranca":
        return
    estado.pop("politica_origem", None)
    estado.pop("politica_campos", None)


def exibir_politica():
    estilo.publicar_fundo_documentos()
    with st.container(key="documentos_legais"):
        politica, termos = st.tabs(["Política de Privacidade", "Termos de Uso"])
        with politica:
            _exibir_texto_politica()
        with termos:
            exibir_termos()


def _exibir_texto_politica():
    st.header("Política de Privacidade")
    st.caption(f"Versão: {VERSAO_POLITICA}")
    st.caption(_AVISO_REVISAO)
    for titulo, paragrafos in _SECOES:
        st.subheader(titulo)
        for paragrafo in paragrafos:
            st.write(paragrafo)
