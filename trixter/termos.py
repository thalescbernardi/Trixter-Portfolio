"""Termos de Uso em minuta, sem aceite ou persistência."""
import streamlit as st

VERSAO_TERMOS = "minuta"
_AVISO_REVISAO = "Minuta para revisão jurídica — não aprovada para publicação."

_SECOES = (('Fornecedor e finalidade',
  ('O Trixter é uma plataforma de organização financeira disponibilizada por Thales Carvalho '
   'Bernardi, pessoa física. O contato para suporte e solicitações é contato@trixter.app.br.',
   'O serviço é inicialmente gratuito, como projeto de portfólio, para uso pessoal e '
   'profissional. Estes Termos descrevem regras propostas de utilização; o tratamento de dados '
   'é explicado na Política de Privacidade. A condição de portfólio não afasta obrigações '
   'legais.')),
 ('Elegibilidade e cadastro',
  ('O serviço é destinado a pessoas com 18 anos ou mais. O cadastro atual exige declaração de '
   'maioridade, sem certificação documental. Não se afirma que contas antigas tenham passado '
   'por essa declaração.',
   'Quem utiliza a plataforma para empresa ou atividade profissional deve ter legitimidade '
   'para representá-la e inserir suas informações. O usuário deve fornecer informações '
   'corretas e manter o e-mail acessível. O código confirma acesso ao endereço, não certifica '
   'identidade, idade ou representação empresarial.',
   'Proteja a senha e comunique suspeitas de comprometimento. A responsabilidade por uso '
   'indevido depende das circunstâncias, sem atribuição automática de toda ocorrência ao '
   'usuário.')),
 ('Recursos e limites',
  ('Há registro e acompanhamento de receitas, gastos, categorias, orçamentos, planejamentos, '
   'recorrências, metas, provisão tributária e relatórios, conforme a interface. Resultados '
   'dependem dos dados, períodos e regras utilizados.',
   'O Trixter auxilia a organização financeira. Não executa pagamentos nem promete '
   'rentabilidade ou resultado econômico. Projeções e provisões exigem conferência e não '
   'substituem análise contábil, tributária, jurídica ou financeira individualizada, '
   'escrituração ou documentos exigidos por lei.')),
 ('Registros, importações e conferência',
  ('Confira valores, datas, categorias, classificação e clientes antes de confirmar. A leitura '
   'de PDF pode apresentar omissões e divergências; revise os movimentos reconhecidos.',
   'Utilize somente documentos sobre os quais tenha legitimidade e evite informações '
   'excessivas de terceiros. A importação aceita até 2 MB e 15 páginas, sujeita aos demais '
   'limites técnicos, e recusa PDFs protegidos por senha.',
   'Correções e exclusões alcançam os registros da operação. Alterar um planejamento não '
   'modifica automaticamente uma movimentação já realizada ou cópias previamente exportadas. A '
   'necessidade de conferência não elimina a responsabilidade do fornecedor por falhas que lhe '
   'sejam atribuíveis.')),
 ('Informações de clientes e uso profissional',
  ('O usuário profissional deve inserir somente informações de terceiros necessárias à '
   'organização financeira de sua atividade, possuir fundamento adequado para utilizá-las, '
   'informar titulares e atender direitos quando lhe couber. O campo Cliente é opcional; '
   'utilize a identificação mínima suficiente quando estritamente necessária.',
   'Não utilize nomes, descrições, categorias ou PDFs para armazenar documentos de '
   'identificação, credenciais, informações sensíveis ou conteúdo excessivo. A possibilidade '
   'técnica de preencher um campo ou importar um documento não autoriza qualquer tratamento.',
   'Ao solicitar armazenamento, consultas, cálculos, análises, exportações ou comunicações '
   'disponíveis, o profissional delimita o processamento necessário a essas funções. Essa '
   'utilização não autoriza o Trixter a explorar dados de clientes para publicidade, '
   'comercialização ou finalidades próprias incompatíveis.',
   'O profissional deve conferir o conteúdo antes de importar, exportar ou compartilhar '
   'informações e evitar exposição desnecessária em arquivos e mensagens. Essas obrigações '
   'não eliminam os deveres próprios do Trixter de segurança, proteção de dados e cooperação '
   'no atendimento aos titulares.',
   'As responsabilidades do Trixter permanecem sujeitas à legislação e à relação concreta de '
   'controlador e operador. O contrato com o usuário não substitui automaticamente o '
   'fundamento para tratamento de dados de seus clientes.')),
 ('Condutas não permitidas',
  ('São incompatíveis com o serviço atividades ilícitas, fraude, violação de direitos de '
   'terceiros, acesso sem autorização, contorno de controles de segurança, inserção de código '
   'malicioso e exploração abusiva que comprometa a disponibilidade.',
   'Vulnerabilidades podem ser relatadas ao suporte sem exposição de dados pessoais ou acesso '
   'além do necessário para descrever o problema. Esses relatos não autorizam invasão, '
   'extração de dados ou interferência no serviço.')),
 ('Relatórios e comunicações',
  ('Relatórios e alertas refletem os dados disponíveis e devem ser conferidos antes de '
   'decisões ou compartilhamentos. É possível baixar PDF, solicitar relatório por e-mail e '
   'configurar comunicações automáticas.',
   'No código atualizado, novos cadastros PF e PJ começam com relatórios mensais, alertas '
   'e resumos semanais automáticos desativados. Cada modalidade pode ser ativada ou '
   'desativada individualmente em Configurações, sem alterar preferências de contas '
   'existentes. Essas escolhas não controlam os e-mails operacionais necessários ao '
   'cadastro, recuperação de senha e alteração de e-mail. A aplicação desse padrão em '
   'produção depende da implantação da versão atualizada.',
   'Mensagens podem conter dados financeiros e ser acessadas por quem acessa a caixa '
   'destinatária. Podem ocorrer filtros, atrasos ou falhas de entrega. Alertas não substituem '
   'controles próprios de vencimentos e obrigações e não oferecem garantia de recebimento '
   'antes de cada compromisso, sem afastar avaliação de falhas atribuíveis ao serviço.')),
 ('Demonstração',
  ('A demonstração utiliza conta temporária no banco configurado, com exemplos, e não se '
   'destina a conservar registros. Não insira dados reais, confidenciais ou necessários à sua '
   'atividade. O modelo PF depende de conteúdo mantido no banco e não é certificado como '
   'fictício apenas por sua origem.',
   'O envio manual de relatórios por e-mail está bloqueado para contas de demonstração; elas '
   'também são excluídas dos envios automáticos. Geração, visualização e download permanecem '
   'disponíveis.',
   'Os dados podem ser removidos ao retornar à conta original ou por expurgo de contas '
   'abandonadas elegíveis após 24 horas. Fechar o navegador não garante exclusão imediata. Não '
   'há garantia de recuperação de alterações feitas na demonstração.')),
 ('Gratuidade e mudanças na oferta',
  ('A oferta inicial é gratuita e não autoriza cobrança automática. Uma modalidade paga '
   'dependerá de condições específicas e informação prévia; a existência de conta gratuita não '
   'obriga a contratar serviço pago.',
   'A gratuidade não afasta obrigações de segurança, proteção de dados ou responsabilidades '
   'legalmente aplicáveis.')),
 ('Disponibilidade e manutenção',
  ('O funcionamento depende da aplicação, conexão do usuário e prestadores de hospedagem, '
   'banco e e-mail. Podem ocorrer manutenção, interrupção, lentidão e falhas. Não há '
   'compromisso contratual específico de disponibilidade contínua ou atendimento em prazo '
   'fixo.',
   'Mudanças relevantes devem observar informação adequada. O encerramento planejado segue '
   'o aviso e as orientações descritos na seção Encerramento e restrições de acesso, '
   'além das obrigações legais. Não '
   'utilize a plataforma como único meio de conservar documentos exigidos ou controlar '
   'obrigações críticas.')),
 ('Segurança e proteção de dados',
  ('Existem medidas técnicas de proteção, sem imunidade a incidentes. Proteja credenciais, '
   'dispositivos, caixa de e-mail e arquivos exportados. Informe suspeitas ao suporte com os '
   'dados mínimos necessários.',
   'A Política de Privacidade descreve tratamentos, prestadores e limites de retenção e '
   'exclusão. Ler estes documentos ou utilizar a plataforma não equivale a consentimento '
   'genérico. Esta minuta não institui aceite obrigatório, registro de aceite ou novo bloqueio '
   'de cadastro.')),
 ('Propriedade intelectual e conteúdo',
  ('O uso do serviço não transfere a titularidade do código, identidade visual ou demais '
   'elementos protegidos do Trixter, respeitadas as licenças de terceiros. O usuário conserva '
   'os direitos que legitimamente possuir sobre seu conteúdo.',
   'A disponibilização do conteúdo permite seu processamento somente na medida necessária às '
   'funções solicitadas, como armazenamento, cálculo, exibição, relatório e comunicação '
   'configurada, observada a legislação. Não autoriza comercialização indiscriminada ou '
   'finalidade incompatível.')),
 ('Responsabilidade',
  ('O usuário responde pela legitimidade e exatidão das informações que fornece e pelas '
   'condutas que lhe sejam atribuíveis. O fornecedor responde por suas obrigações e falhas nos '
   'termos da legislação.',
   'A avaliação de prejuízos considera causa, participação e circunstâncias. A gratuidade não '
   'é exclusão geral de responsabilidade. Estes Termos não restringem direitos obrigatórios de '
   'proteção de dados, direitos do consumidor quando aplicáveis nem acesso a autoridades e ao '
   'Judiciário.')),
 ('Encerramento e restrições de acesso',
  ('No encerramento planejado do Trixter, será dado aviso prévio de pelo menos 30 dias, '
   'com orientação para exportar os dados e solicitar atendimento antes da descontinuação. '
   'Situações emergenciais, incidentes ou impossibilidade técnica podem exigir interrupção '
   'sem esse prazo; informações e orientações serão fornecidas assim que viável. O destino '
   'dos dados após o encerramento segue a Política de Privacidade, incluindo as hipóteses '
   'legais de conservação e os ciclos de retenção de backups e registros dos prestadores.',
   'A conta real pode ser excluída pelo recurso disponível, com senha e confirmação, e seus '
   'dados podem ser previamente exportados. A exclusão tem os limites da Política de '
   'Privacidade, sem recolher downloads ou mensagens entregues e sem promessa de recuperação.',
   'Os controles existentes podem restringir tentativas excessivas temporariamente. Como regra '
   'contratual proposta, eventual suspensão ou encerramento por uso ilícito ou risco concreto '
   'deve ser necessário e proporcional, com esclarecimento pelo suporte, ressalvadas urgências '
   'e impedimentos legais. Esta minuta não afirma a existência de ferramenta administrativa de '
   'suspensão nem de procedimento já aprovado.')),
 ('Atendimento',
  ('O contato é contato@trixter.app.br. Descreva o problema e forneça somente as informações '
   'necessárias, sem enviar sua senha. O suporte por e-mail não representa atendimento '
   'permanente; pedidos sujeitos a prazo legal devem observá-lo.',
   'Buscar suporte não impede reclamações aos órgãos competentes ou acesso ao Judiciário.')),
 ('Alterações e legislação',
  ('Estes Termos são minuta para revisão jurídica, sem aprovação ou vigência definitiva. A '
   'versão aprovada deverá identificar revisão e vigência e definir informação adequada de '
   'mudanças materiais.',
   'Mudanças não autorizam cobranças retroativas nem afastam direitos relativos a fatos '
   'anteriores. Aplica-se a legislação brasileira, preservadas as regras obrigatórias de '
   'competência e proteção dos usuários. A forma de vinculação contratual depende de aprovação '
   'jurídica; esta implementação não registra aceite.')))


def exibir_termos():
    st.header("Termos de Uso")
    st.caption(f"Versão: {VERSAO_TERMOS}")
    st.caption(_AVISO_REVISAO)
    for titulo, paragrafos in _SECOES:
        st.subheader(titulo)
        for paragrafo in paragrafos:
            st.write(paragrafo)
