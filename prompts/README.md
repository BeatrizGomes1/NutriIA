# Versionamento de prompts

Esta pasta é o registro oficial dos prompts que orientam implementações e
decisões importantes do NutriIA.

## Regra para agentes de IA

Antes de realizar uma implementação relevante ou tomar uma decisão de
arquitetura, produto ou tecnologia:

1. crie uma nova pasta com o próximo identificador sequencial;
2. registre o contexto e o prompt em `prompt.md`;
3. atualize `decision.md` com a decisão ou resultado;
4. atualize `INDEX.md`;
5. só então altere o código ou a estrutura do projeto.

Uma nova versão é necessária para mudanças que afetem, por exemplo:

- arquitetura ou organização de pastas;
- contrato entre frontend e backend;
- escolha de linguagem, framework, banco ou serviço externo;
- regras de negócio;
- comportamento de IA, prompt de análise ou formato de resposta;
- requisitos de segurança, privacidade ou persistência.

Não é necessário criar uma versão para correções tipográficas, ajustes de
formatação ou tarefas sem impacto técnico ou comportamental.

## Formato

Use pastas no formato `vNNNN-descricao-curta/`, contendo:

- `prompt.md`: contexto, objetivo e prompt utilizado;
- `decision.md`: decisão, justificativa, impacto e status.

Versões publicadas são imutáveis. Uma revisão deve criar uma nova versão e
referenciar a anterior. As versões iniciais foram reconstruídas a partir das
decisões já tomadas na conversa e estão identificadas como reconstruídas.
