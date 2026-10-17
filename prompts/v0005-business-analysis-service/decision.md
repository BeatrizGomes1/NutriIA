# Decisão

O próximo incremento será um serviço de análise contextualizada, independente
da camada HTTP e da integração com o Gemini.

## Regras implementadas

- dados essenciais ausentes produzem `insufficient_information`;
- conflitos com alergias ou restrições declaradas produzem
  `not_recommended`;
- conflitos de preferências ou do objetivo alimentar podem produzir
  `attention` quando houver evidência nos dados disponíveis;
- ausência de conflito com dados suficientes produz `recommended`;
- ingredientes e valores nutricionais ausentes não serão inventados;
- o resultado conterá motivos, conflitos, evidências e ressalva informativa.

O reconhecimento de termos será deliberadamente simples e explícito nesta
etapa. Uma taxonomia completa de sinônimos, derivados e fontes externas fica
para uma decisão posterior.

## Escopo técnico

Serão utilizados modelos de domínio em `models/`, configuração em `config/`,
normalização em `utils/` e o serviço em `services/nutrition_service.py`.
O provedor padrão será mockado. Nenhuma alteração será feita na API, no
Gemini, nos testes ou no frontend.

## Status

Implementado. A execução da suíte de testes depende da instalação das
dependências Python do backend no ambiente local.
